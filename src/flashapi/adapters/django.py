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
):
    """Generate Django URL patterns for the given models (spec v1 compliant)."""

    urlpatterns = []
    all_schemas: list[ModelSchema] = []

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
        storage = DjangoORMStorage(wrapper.model_class)
        all_schemas.append(schema)
        patterns = _create_django_views(schema, storage, formatter)
        urlpatterns.extend(patterns)

    if docs:
        urlpatterns.extend(_create_docs_views(
            all_schemas, custom_routes or [], extra_views or [],
        ))

    return urlpatterns


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
):
    from django.urls import path
    from django.http import JsonResponse, HttpResponse
    from django.views.decorators.csrf import csrf_exempt
    import json

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}
    input_fields = writable_fields(schema)
    lookup_field = schema.lookup_field
    patterns = []

    # --- List + Create ---
    if "list" in schema.permissions or "create" in schema.permissions:

        def collection_view(request, _table=table, _fields=field_names, _schema=schema,
                            _input=input_fields, _lookup=lookup_field):
            if request.method == "GET" and "list" in _schema.permissions:
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

                include_deleted = deleted_param and _schema.soft_delete
                items = storage.list_all(_table, include_deleted=include_deleted)
                items = apply_filters(items, params, _fields)
                items = apply_search(items, search, _fields)
                items = apply_sorting(items, sort, _fields)
                page_items, total = paginate(items, page, size)
                page_items = [filter_response(item, _schema) for item in page_items]
                return JsonResponse(
                    create_list_response(page_items, total, page, size, formatter)
                )

            elif request.method == "POST" and "create" in _schema.permissions:
                try:
                    body = json.loads(request.body)
                except (json.JSONDecodeError, ValueError):
                    return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)
                data = {k: v for k, v in body.items() if k in _input}
                item = storage.create(_table, data)
                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter), status=201)

            return JsonResponse(create_error_response("Method not allowed", 405), status=405)

        patterns.append(path(f"{table}/", csrf_exempt(collection_view), name=f"{table}_collection"))

    # --- Bulk create ---
    if "create" in schema.permissions:

        def bulk_create_view(request, _table=table, _input=input_fields, _schema=schema):
            if request.method != "POST":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)
            try:
                body = json.loads(request.body)
            except (json.JSONDecodeError, ValueError):
                return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)
            if not isinstance(body, list):
                return JsonResponse(create_error_response("Request body must be a JSON array", 400), status=400)
            succeeded = 0
            failed = 0
            results = []
            for item_data in body:
                try:
                    data = {k: v for k, v in item_data.items() if k in _input}
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
            fmt = request.GET.get("format", "csv").lower()
            if fmt not in EXPORTERS:
                return JsonResponse(
                    create_error_response(f"Unsupported format: {fmt}. Use csv, xlsx, or pdf", 400), status=400
                )
            items = storage.list_all(_table)
            fields = sorted(export_fields(_schema))
            content = EXPORTERS[fmt](items, fields)
            response = HttpResponse(content, content_type=CONTENT_TYPES[fmt])
            response["Content-Disposition"] = f'attachment; filename="{_table}.{fmt}"'
            return response

        patterns.append(path(f"{table}/export/", export_view, name=f"{table}_export"))

    # --- Detail (read, update, delete) ---
    if any(op in schema.permissions for op in ["read", "update", "delete"]):

        def detail_view(request, item_id, _table=table, _fields=field_names, _schema=schema,
                        _input=input_fields, _lookup=lookup_field):
            if request.method == "GET" and "read" in _schema.permissions:
                item = storage.get(_table, item_id, lookup_field=_lookup)
                if item is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)
                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "PUT" and "update" in _schema.permissions:
                try:
                    body = json.loads(request.body)
                except (json.JSONDecodeError, ValueError):
                    return JsonResponse(create_error_response("Invalid JSON body", 400), status=400)
                data = {k: v for k, v in body.items() if k in _input}
                item = storage.update(_table, item_id, data, lookup_field=_lookup)
                if item is None:
                    return JsonResponse(create_error_response("Not found", 404), status=404)
                item = filter_response(item, _schema)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "DELETE" and "delete" in _schema.permissions:
                deleted = storage.delete(_table, item_id, soft=_schema.soft_delete, lookup_field=_lookup)
                if not deleted:
                    return JsonResponse(create_error_response("Not found", 404), status=404)
                return HttpResponse(status=204)

            return JsonResponse(create_error_response("Method not allowed", 405), status=405)

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/", csrf_exempt(detail_view), name=f"{table}_detail"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/", csrf_exempt(detail_view), name=f"{table}_detail"))

    # --- Restore (only if soft_delete) ---
    if "delete" in schema.permissions and schema.soft_delete:

        def restore_view(request, item_id, _table=table, _lookup=lookup_field):
            if request.method != "POST":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)
            restored = storage.restore(_table, item_id, lookup_field=_lookup)
            if not restored:
                return JsonResponse(create_error_response("Not found", 404), status=404)
            return HttpResponse(status=204)

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/restore/", csrf_exempt(restore_view), name=f"{table}_restore"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/restore/", csrf_exempt(restore_view), name=f"{table}_restore"))

    # --- History (only if audit) ---
    if "read" in schema.permissions and schema.audit:

        def history_view(request, item_id, _table=table, _entity=schema.name):
            if request.method != "GET":
                return JsonResponse(create_error_response("Method not allowed", 405), status=405)
            return JsonResponse({"data": []})

        if lookup_field == "id":
            patterns.append(path(f"{table}/<int:item_id>/history/", history_view, name=f"{table}_history"))
        else:
            patterns.append(path(f"{table}/<str:item_id>/history/", history_view, name=f"{table}_history"))

    return patterns
