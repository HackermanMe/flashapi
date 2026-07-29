from __future__ import annotations

from typing import Callable

from flashapi.core.schema import Model, ModelSchema
from flashapi.core.response import create_list_response, create_item_response, create_error_response
from flashapi.core.custom_routes import (
    CustomRoute, custom_routes_to_openapi_paths, discover_django_views,
)
from flashapi.core.visibility import filter_response, writable_fields, export_fields
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.orm import DjangoORMStorage
from flashapi.docs.openapi import generate_openapi_schema, get_swagger_html


DEFAULT_BASE_PATH = "/api"


def generate_urls(
    models: list[type | Model],
    *,
    custom_routes: list[CustomRoute] | None = None,
    extra_views: list | None = None,
    base_path: str = DEFAULT_BASE_PATH,
    docs: bool = True,
    formatter: Callable | None = None,
    webhook_urls: list[str] | None = None,
    rate_limit: int | None = None,
    rate_window: int = 60,
    auth_backend=None,
):
    """Generate Django URL patterns for the given models (spec v1 compliant)."""

    urlpatterns = []
    all_schemas: list[ModelSchema] = []

    # Webhooks
    webhook = None
    if webhook_urls:
        from flashapi.features.webhooks import WebhookDispatcher
        webhook = WebhookDispatcher(webhook_urls)

    # Rate limiting
    rate_limiter = None
    if rate_limit:
        from flashapi.features.rate_limit import RateLimiter
        rate_limiter = RateLimiter(limit=rate_limit, window=rate_window)

    # Metrics
    from flashapi.features.dashboard import MetricsCollector
    metrics = MetricsCollector()

    # Audit (in-memory SQLite for Django adapter)
    audit_log = None
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        from flashapi.features.audit import AuditLog
        audit_log = AuditLog(conn)
    except Exception:
        pass

    for model_entry in models:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions
        schema.soft_delete = wrapper.soft_delete
        schema.audit = wrapper.audit
        schema.lookup_field = wrapper.lookup_field
        schema.access = wrapper.access
        schema.scope = wrapper.scope
        schema.tenant_field = wrapper.tenant_field
        schema.owner_field = wrapper.owner_field

        from flashapi.core.schema import validate_soft_delete
        validate_soft_delete(wrapper.model_class, wrapper.soft_delete)

        storage = DjangoORMStorage(wrapper.model_class)
        all_schemas.append(schema)

        metrics.register_entity(
            schema.name,
            soft_delete=schema.soft_delete,
            audit=schema.audit,
            webhook=bool(webhook_urls),
            rate_limited=bool(rate_limit),
        )

        patterns = _create_django_views(
            schema, storage, formatter,
            audit_log=audit_log, webhook=webhook, metrics=metrics,
            auth_backend=auth_backend,
        )
        urlpatterns.extend(patterns)

    # Dashboard
    urlpatterns.extend(_create_dashboard_views(metrics, webhook))

    # Rate limiting middleware class (user must add to MIDDLEWARE)
    if rate_limiter:
        _register_rate_limit_middleware(rate_limiter)

    if docs:
        urlpatterns.extend(_create_docs_views(
            all_schemas, custom_routes or [], extra_views or [],
        ))

    urlpatterns.extend(_create_api_root_view(all_schemas, docs))

    return urlpatterns


def _create_api_root_view(schemas: list[ModelSchema], docs: bool):
    from django.urls import path
    from django.http import JsonResponse

    def api_root(request):
        resources = {}
        base = request.build_absolute_uri(request.path)
        if not base.endswith("/"):
            base += "/"
        for schema in schemas:
            resources[schema.plural] = base + schema.plural + "/"
        links = {}
        if docs:
            links["docs"] = base + "docs/"
            links["openapi"] = base + "openapi.json"
        links["dashboard"] = base + "dashboard/"
        return JsonResponse({"resources": resources, "links": links})

    return [path("", api_root, name="flashapi_root")]


def _register_rate_limit_middleware(rate_limiter):
    """Store rate_limiter globally for FlashAPIRateLimitMiddleware to pick up."""
    global _RATE_LIMITER
    _RATE_LIMITER = rate_limiter


_RATE_LIMITER = None


class FlashAPIRateLimitMiddleware:
    """Django middleware for rate limiting. Add 'flashapi.adapters.django.FlashAPIRateLimitMiddleware' to MIDDLEWARE."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import JsonResponse

        if _RATE_LIMITER is None:
            return self.get_response(request)

        client_ip = self._get_client_ip(request)
        allowed, remaining, reset = _RATE_LIMITER.check(client_ip)

        if not allowed:
            response = JsonResponse(
                {"error": "Rate limit exceeded", "status": 429, "retryAfter": reset},
                status=429,
            )
            response["X-RateLimit-Limit"] = str(_RATE_LIMITER.limit)
            response["X-RateLimit-Remaining"] = "0"
            response["X-RateLimit-Reset"] = str(reset)
            return response

        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(_RATE_LIMITER.limit)
        response["X-RateLimit-Remaining"] = str(remaining)
        response["X-RateLimit-Reset"] = str(reset)
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


def _create_dashboard_views(metrics, webhook):
    from django.urls import path
    from django.http import JsonResponse, HttpResponse
    from flashapi.features.dashboard import DASHBOARD_HTML

    def dashboard_html(request):
        return HttpResponse(DASHBOARD_HTML, content_type="text/html")

    def dashboard_metrics(request):
        return JsonResponse(metrics.get_metrics(webhook))

    return [
        path("dashboard/", dashboard_html, name="flashapi_dashboard"),
        path("dashboard/metrics.json", dashboard_metrics, name="flashapi_dashboard_metrics"),
    ]


def _create_docs_views(schemas: list[ModelSchema], custom_routes: list[CustomRoute], extra_views: list):
    from django.urls import path
    from django.http import JsonResponse, HttpResponse

    openapi_spec = generate_openapi_schema(schemas, trailing_slash=True)

    if custom_routes:
        custom_paths = custom_routes_to_openapi_paths(custom_routes, trailing_slash=True)
        openapi_spec["paths"].update(custom_paths)

    if extra_views:
        discovered = discover_django_views(extra_views, trailing_slash=True)
        openapi_spec["paths"].update(discovered)

    def openapi_json(request):
        spec = dict(openapi_spec)
        base_path = request.path.rsplit("openapi.json", 1)[0]
        spec["servers"] = [{"url": base_path}]
        return JsonResponse(spec, safe=False)

    def docs_ui(request):
        base_path = request.path.rsplit("docs/", 1)[0]
        openapi_url = f"{base_path}openapi.json"
        html = get_swagger_html(title="FlashAPI", openapi_url=openapi_url)
        return HttpResponse(html, content_type="text/html")

    return [
        path("openapi.json", openapi_json, name="flashapi_openapi"),
        path("docs/", docs_ui, name="flashapi_docs"),
    ]


def _create_django_views(
    schema: ModelSchema,
    storage: DjangoORMStorage,
    formatter: Callable | None,
    *,
    audit_log=None,
    webhook=None,
    metrics=None,
    auth_backend=None,
):
    from django.urls import path
    from django.http import JsonResponse, HttpResponse
    from django.views.decorators.csrf import csrf_exempt
    import json
    from flashapi.features.auth import check_access, get_scope_filter

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}
    input_fields = writable_fields(schema)
    lookup_field = schema.lookup_field
    entity_name = schema.name
    entity_audit = schema.audit
    supports_soft_delete = schema.soft_delete
    model_access = schema.access
    model_scope = schema.scope
    model_tenant_field = schema.tenant_field
    model_owner_field = schema.owner_field
    patterns = []

    def _check_auth(request, operation):
        """Returns (user, role, error_response). error_response is None if access granted."""
        if auth_backend is None:
            return None, "admin", None

        if model_access is None or model_access == "public" or model_access is True:
            if isinstance(model_access, dict):
                op_access = model_access.get(operation, "public")
                if op_access == "public":
                    return None, "public", None
            else:
                return None, "public", None

        user = auth_backend.authenticate(request)
        if user is None:
            if isinstance(model_access, dict):
                op_access = model_access.get(operation, "authenticated")
                if op_access == "public":
                    return None, "public", None
            return None, "public", JsonResponse(
                create_error_response("Authentication required", 401), status=401
            )

        role = auth_backend.get_role(user)
        if not check_access(role, model_access, operation):
            return user, role, JsonResponse(
                create_error_response("Forbidden", 403), status=403
            )
        return user, role, None

    def _get_scope(user, role):
        """Returns the scope filter dict or None."""
        if auth_backend is None or user is None:
            return None
        return get_scope_filter(user, auth_backend, model_scope, model_tenant_field, model_owner_field, role)

    # --- List + Create ---
    if "list" in schema.permissions or "create" in schema.permissions:

        def collection_view(request, _table=table, _fields=field_names, _schema=schema,
                            _input=input_fields, _lookup=lookup_field):
            if request.method == "GET" and "list" in _schema.permissions:
                user, role, err = _check_auth(request, "list")
                if err:
                    return err

                params = dict(request.GET)
                params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                try:
                    page = max(0, int(params.get("page", 0)))
                    size = max(1, min(100, int(params.get("size", 20))))
                except (ValueError, TypeError):
                    return JsonResponse(create_error_response("Invalid page or size parameter", 400), status=400)
                sort = params.get("sort")
                search = params.get("search")
                deleted_param = params.get("deleted", "false").lower() == "true"

                include_deleted = deleted_param and supports_soft_delete
                items = storage.list_all(_table, include_deleted=include_deleted)

                scope_filter = _get_scope(user, role)
                if scope_filter:
                    items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

                items = apply_filters(items, params, _fields)
                if search and metrics:
                    metrics.record("SEARCH", entity_name)
                items = apply_search(items, search, _fields)
                items = apply_sorting(items, sort, _fields)
                page_items, total = paginate(items, page, size)
                page_items = [filter_response(item, _schema) for item in page_items]
                if metrics:
                    metrics.record("READ", entity_name)
                return JsonResponse(
                    create_list_response(page_items, total, page, size, formatter)
                )

            elif request.method == "POST" and "create" in _schema.permissions:
                user, role, err = _check_auth(request, "create")
                if err:
                    return err

                try:
                    body = json.loads(request.body)
                except (json.JSONDecodeError, ValueError):
                    return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)
                data = {k: v for k, v in body.items() if k in _input}

                scope_filter = _get_scope(user, role)
                if scope_filter:
                    data.update(scope_filter)

                item = storage.create(_table, data)
                if metrics:
                    metrics.record("CREATE", entity_name, str(item.get("id", "")))
                if audit_log and entity_audit:
                    audit_log.record("CREATE", entity_name, item.get("id", ""))
                if webhook:
                    webhook.dispatch("CREATE", entity_name, item.get("id", ""), item)
                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter), status=201)

            return JsonResponse(create_error_response("Method not allowed", 405), status=405)

        patterns.append(path(f"{table}/", csrf_exempt(collection_view), name=f"{table}_collection"))

    # --- Bulk create ---
    if "create" in schema.permissions:

        def bulk_create_view(request, _table=table, _input=input_fields, _schema=schema):
            if request.method != "POST":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)

            user, role, err = _check_auth(request, "create")
            if err:
                return err

            try:
                body = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)
            if not isinstance(body, list):
                return JsonResponse(create_error_response("Request body must be a JSON array", 400), status=400)

            scope_filter = _get_scope(user, role)
            succeeded = 0
            failed = 0
            results = []
            for item_data in body:
                try:
                    data = {k: v for k, v in item_data.items() if k in _input}
                    if scope_filter:
                        data.update(scope_filter)
                    item = storage.create(_table, data)
                    item = filter_response(item, _schema)
                    results.append(item)
                    succeeded += 1
                except Exception:
                    failed += 1
            return JsonResponse({
                "data": results,
                "meta": {"total": len(body), "succeeded": succeeded, "failed": failed},
            }, status=201)

        patterns.append(path(f"{table}/bulk/", csrf_exempt(bulk_create_view), name=f"{table}_bulk_create"))

    # --- Export ---
    if "list" in schema.permissions:
        from flashapi.features.export import EXPORTERS, CONTENT_TYPES

        def export_view(request, _table=table, _schema=schema):
            if request.method != "GET":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)

            user, role, err = _check_auth(request, "list")
            if err:
                return err

            fmt = request.GET.get("format", "csv").lower()
            if fmt not in EXPORTERS:
                return JsonResponse(
                    create_error_response(f"Unsupported format: {fmt}. Use csv, xlsx, or pdf", 400), status=400
                )
            items = storage.list_all(_table)

            scope_filter = _get_scope(user, role)
            if scope_filter:
                items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

            fields = sorted(export_fields(_schema))
            try:
                content = EXPORTERS[fmt](items, fields)
            except ImportError as e:
                return JsonResponse(
                    create_error_response(str(e), 400), status=400
                )
            response = HttpResponse(content, content_type=CONTENT_TYPES[fmt])
            response["Content-Disposition"] = f'attachment; filename="{_table}.{fmt}"'
            return response

        patterns.append(path(f"{table}/export/", export_view, name=f"{table}_export"))

    # --- Detail (read, update, delete) ---
    if any(op in schema.permissions for op in ["read", "update", "delete"]):

        def detail_view(request, item_id, _table=table, _fields=field_names, _schema=schema,
                        _input=input_fields, _lookup=lookup_field):
            if request.method == "GET" and "read" in _schema.permissions:
                user, role, err = _check_auth(request, "read")
                if err:
                    return err

                item = storage.get(_table, item_id, lookup_field=_lookup)
                if item is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                scope_filter = _get_scope(user, role)
                if scope_filter and not all(item.get(k) == v for k, v in scope_filter.items()):
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "PUT" and "update" in _schema.permissions:
                user, role, err = _check_auth(request, "update")
                if err:
                    return err

                try:
                    body = json.loads(request.body)
                except (json.JSONDecodeError, ValueError):
                    return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)

                old_item = storage.get(_table, item_id, lookup_field=_lookup)
                if old_item is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                scope_filter = _get_scope(user, role)
                if scope_filter and not all(old_item.get(k) == v for k, v in scope_filter.items()):
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                data = {k: v for k, v in body.items() if k in _input}
                item = storage.update(_table, item_id, data, lookup_field=_lookup)
                if item is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)
                if metrics:
                    metrics.record("UPDATE", entity_name, str(item_id))
                if audit_log and entity_audit:
                    audit_log.record("UPDATE", entity_name, item_id, old_data=old_item, new_data=item)
                if webhook:
                    webhook.dispatch("UPDATE", entity_name, item_id, item)
                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "DELETE" and "delete" in _schema.permissions:
                user, role, err = _check_auth(request, "delete")
                if err:
                    return err

                existing = storage.get(_table, item_id, lookup_field=_lookup)
                if existing is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                scope_filter = _get_scope(user, role)
                if scope_filter and not all(existing.get(k) == v for k, v in scope_filter.items()):
                    return JsonResponse(create_error_response("Not found", 404), status=404)

                deleted = storage.delete(_table, item_id, soft=supports_soft_delete, lookup_field=_lookup)
                if not deleted:
                    return JsonResponse(create_error_response("Not found", 404), status=404)
                if metrics:
                    metrics.record("DELETE", entity_name, str(item_id))
                if audit_log and entity_audit:
                    audit_log.record("DELETE", entity_name, item_id)
                if webhook:
                    webhook.dispatch("DELETE", entity_name, item_id, {})
                return HttpResponse(status=204)

            return JsonResponse(create_error_response("Method not allowed", 405), status=405)

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/", csrf_exempt(detail_view), name=f"{table}_detail"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/", csrf_exempt(detail_view), name=f"{table}_detail"))

    # --- Restore (only if soft_delete) ---
    if "delete" in schema.permissions and supports_soft_delete:

        def restore_view(request, item_id, _table=table, _lookup=lookup_field):
            if request.method != "POST":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)

            user, role, err = _check_auth(request, "delete")
            if err:
                return err

            restored = storage.restore(_table, item_id, lookup_field=_lookup)
            if not restored:
                return JsonResponse(create_error_response("Not found", 404), status=404)
            return HttpResponse(status=204)

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/restore/", csrf_exempt(restore_view), name=f"{table}_restore"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/restore/", csrf_exempt(restore_view), name=f"{table}_restore"))

    # --- History (only if audit) ---
    if "read" in schema.permissions and entity_audit:

        def history_view(request, item_id, _table=table, _entity=entity_name, _audit=audit_log):
            if request.method != "GET":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)

            user, role, err = _check_auth(request, "read")
            if err:
                return err

            if _audit is None:
                return JsonResponse(create_error_response("Audit not enabled", 404), status=404)
            history = _audit.get_history(_entity, str(item_id))
            return JsonResponse({"data": history}, safe=False)

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/history/", history_view, name=f"{table}_history"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/history/", history_view, name=f"{table}_history"))

    return patterns
