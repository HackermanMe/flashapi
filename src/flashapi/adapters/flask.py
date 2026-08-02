from __future__ import annotations

from typing import TYPE_CHECKING

from flashapi.core.custom_routes import (
    CustomRoute,
    custom_routes_to_openapi_paths,
    discover_flask_views,
)
from flashapi.core.relations import find_expandable_fields, resolve_relations
from flashapi.core.response import create_error_response, create_item_response, create_list_response
from flashapi.core.schema import Model, ModelSchema
from flashapi.core.visibility import export_fields, filter_response, writable_fields
from flashapi.docs.openapi import generate_openapi_schema, get_swagger_html
from flashapi.features import apply_filters, apply_search, apply_sorting, paginate
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage
from flashapi.storage.sqlalchemy import SQLAlchemyStorage

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_BASE_PATH = "/api"


def register_models(
    app,
    models: list[type | Model],
    *,
    engine=None,
    base_path: str = DEFAULT_BASE_PATH,
    custom_routes: list[CustomRoute] | None = None,
    database: str = "flashapi.db",
    docs: bool = True,
    formatter: Callable | None = None,
    webhook_urls: list[str] | None = None,
    rate_limit: int | None = None,
    rate_window: int = 60,
    auth_backend=None,
) -> None:
    """Register models on an existing Flask app."""
    from flask import Blueprint

    session_factory = None
    if engine is not None:
        from sqlalchemy.orm import sessionmaker
        session_factory = sessionmaker(bind=engine)

    auto_storage = AutoStorage(database) if engine is None else None
    blueprint = Blueprint("flashapi", __name__, url_prefix=base_path)
    all_schemas: list[ModelSchema] = []
    storages: dict[str, any] = {}

    # Audit
    audit_log = None
    if auto_storage:
        from flashapi.features.audit import AuditLog
        audit_log = AuditLog(auto_storage._conn)

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

    for model_entry in models:
        wrapper = model_entry if isinstance(model_entry, Model) else Model(model_entry)

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

        is_sa = hasattr(wrapper.model_class, "__table__") and hasattr(wrapper.model_class, "__tablename__")

        if is_sa and session_factory is not None:
            storage = SQLAlchemyStorage(session_factory, wrapper.model_class)
        else:
            auto_storage.ensure_table(schema, soft_delete=schema.soft_delete)
            storage = auto_storage

        storages[schema.plural] = storage
        all_schemas.append(schema)
        expandable = find_expandable_fields(schema)

        metrics.register_entity(
            schema.name,
            soft_delete=schema.soft_delete,
            audit=schema.audit,
            webhook=bool(webhook_urls),
            rate_limited=bool(rate_limit),
            multi_tenant=schema.scope in ("tenant", "both"),
        )

        _create_flask_routes(
            blueprint, schema, storage, formatter, expandable, schema,
            audit_log=audit_log, webhook=webhook, metrics=metrics,
            auth_backend=auth_backend,
        )

    parent_to_children = resolve_relations(all_schemas)
    for parent_plural, relations in parent_to_children.items():
        for relation in relations:
            _create_nested_route(
                blueprint, parent_plural, relation.target_plural,
                relation.foreign_key, storages.get(relation.target_plural, storage), formatter,
            )

    # Dashboard
    _add_dashboard_routes(blueprint, metrics, webhook)

    # WebSocket
    _add_websocket_route(app, base_path)

    # Rate limit middleware
    if rate_limiter:
        _add_rate_limit_middleware(app, rate_limiter)

    if docs:
        _add_docs_routes(blueprint, all_schemas, custom_routes or [], flask_app=app)

    _add_api_root_route(blueprint, all_schemas, base_path, docs)

    app.register_blueprint(blueprint)


def _add_websocket_route(app, base_path: str) -> None:
    """Add WebSocket endpoint via flask-sock (optional dependency)."""
    try:
        from flask_sock import Sock
    except ImportError:
        return

    import json

    from flashapi.features.websocket import get_hub

    sock = Sock(app)

    class _FlaskConnection:
        def __init__(self, ws) -> None:
            self._ws = ws

        def send_message(self, message: str) -> None:
            self._ws.send(message)

        def __hash__(self):
            return id(self._ws)

        def __eq__(self, other):
            return isinstance(other, _FlaskConnection) and self._ws is other._ws

    @sock.route(f"{base_path}/ws")
    def websocket_endpoint(ws) -> None:
        hub = get_hub()
        conn = _FlaskConnection(ws)
        try:
            while True:
                text = ws.receive()
                if text is None:
                    break
                try:
                    msg = json.loads(text)
                except (json.JSONDecodeError, ValueError):
                    continue

                action = msg.get("action")
                topic = msg.get("topic", "")

                if action == "subscribe" and topic:
                    hub.subscribe(topic, conn)
                elif action == "unsubscribe" and topic:
                    hub.unsubscribe(topic, conn)
        except Exception:
            pass
        finally:
            hub.remove_connection(conn)


def _add_api_root_route(blueprint, schemas: list[ModelSchema], base_path: str, docs: bool) -> None:
    from flask import jsonify, request

    @blueprint.route("/", endpoint="flashapi_root")
    def api_root():
        base = request.url_root.rstrip("/") + base_path
        if not base.endswith("/"):
            base += "/"
        resources = {s.plural: base + s.plural + "/" for s in schemas}
        links = {}
        if docs:
            links["docs"] = base + "docs/"
            links["openapi"] = base + "openapi.json"
        links["dashboard"] = base + "dashboard/"
        return jsonify({"resources": resources, "links": links})


def _add_rate_limit_middleware(app, rate_limiter) -> None:
    from flask import jsonify, request

    @app.before_request
    def _check_rate_limit():
        client_ip = request.remote_addr or "unknown"
        allowed, _remaining, reset = rate_limiter.check(client_ip)
        if not allowed:
            response = jsonify({"error": "Rate limit exceeded", "status": 429, "retryAfter": reset})
            response.status_code = 429
            response.headers["X-RateLimit-Limit"] = str(rate_limiter.limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(reset)
            return response
        return None

    @app.after_request
    def _add_rate_limit_headers(response):
        client_ip = request.remote_addr or "unknown"
        _allowed, remaining, reset = rate_limiter.check(client_ip)
        response.headers["X-RateLimit-Limit"] = str(rate_limiter.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response


def _add_dashboard_routes(blueprint, metrics, webhook) -> None:
    from flask import Response, jsonify

    from flashapi.features.dashboard import DASHBOARD_HTML

    @blueprint.route("/dashboard", methods=["GET"], endpoint="flashapi_dashboard")
    def dashboard_html():
        return Response(DASHBOARD_HTML, content_type="text/html")

    @blueprint.route("/dashboard/metrics.json", methods=["GET"], endpoint="flashapi_dashboard_metrics")
    def dashboard_metrics():
        return jsonify(metrics.get_metrics(webhook))


def _add_docs_routes(blueprint, schemas: list[ModelSchema], custom_routes: list[CustomRoute], flask_app=None) -> None:
    from flask import Response, jsonify

    openapi_spec = generate_openapi_schema(schemas)

    if custom_routes:
        custom_paths = custom_routes_to_openapi_paths(custom_routes)
        openapi_spec["paths"].update(custom_paths)

    _discovered = {"done": False}

    @blueprint.route("/openapi.json", methods=["GET"], endpoint="flashapi_openapi")
    def openapi_json():
        if not _discovered["done"] and flask_app is not None:
            discovered = discover_flask_views(flask_app)
            openapi_spec["paths"].update(discovered)
            _discovered["done"] = True
        return jsonify(openapi_spec)

    @blueprint.route("/docs", methods=["GET"], endpoint="flashapi_docs")
    def docs_ui():
        html = get_swagger_html(title="FlashAPI", openapi_url="/api/openapi.json")
        return Response(html, content_type="text/html")


def _create_nested_route(blueprint, parent_plural, child_plural, foreign_key, storage, formatter) -> None:
    from flask import jsonify, request

    @blueprint.route(
        f"/{parent_plural}/<int:parent_id>/{child_plural}",
        methods=["GET"],
        endpoint=f"{parent_plural}_{child_plural}_nested",
    )
    def nested_list(parent_id, _pp=parent_plural, _cp=child_plural, _fk=foreign_key):
        parent = storage.get(_pp, parent_id)
        if parent is None:
            return jsonify(create_error_response("Parent not found", 404)), 404

        all_items = storage.list_all(_cp)
        items = [i for i in all_items if i.get(_fk) == parent_id]

        params = dict(request.args)
        page = int(params.get("page", 0))
        size = int(params.get("size", 20))
        sort = params.get("sort")
        search = params.get("search")

        child_fields = {k for item in items for k in item if k != "id"}
        if search:
            items = apply_search(items, search, child_fields)
        if sort:
            items = apply_sorting(items, sort, child_fields)

        page_items, total = paginate(items, page, size)
        return jsonify(create_list_response(page_items, total, page, size, formatter))


def _expand_items(items, expand_param, expandable, storage):
    expand_fields = [f.strip() for f in expand_param.split(",")]
    expanded_items = []

    for item in items:
        item_copy = dict(item)
        for field_name in expand_fields:
            if field_name in expandable:
                fk_field = f"{field_name}_id"
                fk_value = item_copy.get(fk_field)
                if fk_value is not None:
                    related = storage.get(expandable[field_name], fk_value)
                    if related:
                        item_copy[field_name] = related
        expanded_items.append(item_copy)

    return expanded_items


def _create_flask_routes(
    blueprint,
    schema: ModelSchema,
    storage,
    formatter: Callable | None,
    expandable: dict,
    model_schema: ModelSchema,
    *,
    audit_log=None,
    webhook=None,
    metrics=None,
    auth_backend=None,
) -> None:
    from flask import jsonify, request

    from flashapi.features.auth import check_access, get_scope_filter

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}
    input_fields = writable_fields(model_schema)
    lookup_field = schema.lookup_field
    supports_soft_delete = schema.soft_delete
    entity_audit = schema.audit
    entity_name = schema.name
    model_access = schema.access
    model_scope = schema.scope
    model_tenant_field = schema.tenant_field
    model_owner_field = schema.owner_field

    id_converter = "int" if lookup_field == "id" else "string"

    def _check_auth(operation):
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
            return None, "public", (jsonify(create_error_response("Authentication required", 401)), 401)

        role = auth_backend.get_role(user)
        if not check_access(role, model_access, operation):
            return user, role, (jsonify(create_error_response("Forbidden", 403)), 403)
        return user, role, None

    def _get_scope(user, role):
        if auth_backend is None or user is None:
            return None
        return get_scope_filter(user, auth_backend, model_scope, model_tenant_field, model_owner_field, role)

    def _get_performer(user):
        if auth_backend is None or user is None:
            return ""
        return auth_backend.get_user_identifier(user)

    def _broadcast(entity: str, action: str, data: dict | None = None) -> None:
        from flashapi.features.websocket import EVENT_MAP, broadcast_event
        event_type = EVENT_MAP.get(action)
        if event_type:
            broadcast_event(entity, event_type, data)

    if "list" in schema.permissions:
        @blueprint.route(f"/{table}", methods=["GET"], endpoint=f"{table}_list")
        def list_items(_table=table, _fields=field_names, _exp=expandable, _schema=model_schema,
                       _metrics=metrics):
            user, role, err = _check_auth("list")
            if err:
                return err

            deleted_param = request.args.get("deleted", "false").lower() == "true"
            only_deleted = deleted_param and supports_soft_delete
            items = storage.list_all(_table, only_deleted=only_deleted)

            scope_filter = _get_scope(user, role)
            if scope_filter:
                items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

            params = dict(request.args)
            try:
                page = max(0, int(params.get("page", 0)))
                size = max(1, min(100, int(params.get("size", 20))))
            except (ValueError, TypeError):
                return jsonify(create_error_response("Invalid page or size parameter", 400)), 400
            sort = params.get("sort")
            search = params.get("search")
            expand = params.get("expand")

            items = apply_filters(items, params, _fields)
            if search and _metrics:
                _metrics.record("SEARCH", entity_name)
            items = apply_search(items, search, _fields)
            items = apply_sorting(items, sort, _fields)
            page_items, total = paginate(items, page, size)

            if expand:
                page_items = _expand_items(page_items, expand, _exp, storage)

            if _metrics:
                _metrics.record("READ", entity_name)
            page_items = [filter_response(item, _schema) for item in page_items]
            return jsonify(create_list_response(page_items, total, page, size, formatter))

    if "read" in schema.permissions:
        @blueprint.route(f"/{table}/<{id_converter}:item_id>", methods=["GET"], endpoint=f"{table}_get")
        def get_item(item_id, _table=table, _exp=expandable, _schema=model_schema, _lf=lookup_field):
            user, role, err = _check_auth("read")
            if err:
                return err

            item = storage.get(_table, item_id, lookup_field=_lf)
            if item is None:
                return jsonify(create_error_response("Not found", 404)), 404

            scope_filter = _get_scope(user, role)
            if scope_filter and not all(item.get(k) == v for k, v in scope_filter.items()):
                return jsonify(create_error_response("Not found", 404)), 404

            expand = request.args.get("expand")
            if expand:
                item = _expand_items([item], expand, _exp, storage)[0]

            item = filter_response(item, _schema)
            return jsonify(create_item_response(item, formatter))

    if "read" in schema.permissions and entity_audit:
        @blueprint.route(f"/{table}/<{id_converter}:item_id>/history", methods=["GET"], endpoint=f"{table}_history")
        def history_item(item_id, _table=table, _entity=entity_name, _audit=audit_log):
            _user, _role, err = _check_auth("read")
            if err:
                return err

            if _audit is None:
                return jsonify(create_error_response("Audit not enabled", 404)), 404
            history = _audit.get_history(_entity, str(item_id))
            return jsonify({"data": history})

    if "create" in schema.permissions:
        @blueprint.route(f"/{table}", methods=["POST"], endpoint=f"{table}_create")
        def create_item(_table=table, _input=input_fields, _schema=model_schema,
                        _audit=audit_log, _webhook=webhook, _metrics=metrics):
            user, role, err = _check_auth("create")
            if err:
                return err

            body = request.get_json(silent=True)
            if not body:
                return jsonify(create_error_response("Request body is required", 400)), 400
            data = {k: v for k, v in body.items() if k in _input}

            scope_filter = _get_scope(user, role)
            if scope_filter:
                data.update(scope_filter)

            item = storage.create(_table, data)
            if _metrics:
                _metrics.record("CREATE", entity_name, str(item.get("id", "")))
            if _audit and entity_audit:
                _audit.record("CREATE", entity_name, item.get("id", ""), performed_by=_get_performer(user))
            if _webhook:
                _webhook.dispatch("CREATE", entity_name, item.get("id", ""), item)
            _broadcast(entity_name, "CREATE", item)
            item = filter_response(item, _schema)
            return jsonify(create_item_response(item, formatter)), 201

    if "update" in schema.permissions:
        @blueprint.route(f"/{table}/<{id_converter}:item_id>", methods=["PUT"], endpoint=f"{table}_update")
        def update_item(item_id, _table=table, _input=input_fields, _schema=model_schema,
                        _lf=lookup_field, _audit=audit_log, _webhook=webhook, _metrics=metrics):
            user, role, err = _check_auth("update")
            if err:
                return err

            body = request.get_json(silent=True)
            if not body:
                return jsonify(create_error_response("Request body is required", 400)), 400

            old_item = storage.get(_table, item_id, lookup_field=_lf)
            if old_item is None:
                return jsonify(create_error_response("Not found", 404)), 404

            scope_filter = _get_scope(user, role)
            if scope_filter and not all(old_item.get(k) == v for k, v in scope_filter.items()):
                return jsonify(create_error_response("Not found", 404)), 404

            data = {k: v for k, v in body.items() if k in _input}
            item = storage.update(_table, item_id, data, lookup_field=_lf)
            if item is None:
                return jsonify(create_error_response("Not found", 404)), 404
            if _metrics:
                _metrics.record("UPDATE", entity_name, str(item_id))
            if _audit and entity_audit:
                _audit.record("UPDATE", entity_name, item_id, performed_by=_get_performer(user), old_data=old_item, new_data=item)
            if _webhook:
                _webhook.dispatch("UPDATE", entity_name, item_id, item)
            _broadcast(entity_name, "UPDATE", item)
            item = filter_response(item, _schema)
            return jsonify(create_item_response(item, formatter))

    if "delete" in schema.permissions:
        @blueprint.route(f"/{table}/<{id_converter}:item_id>", methods=["DELETE"], endpoint=f"{table}_delete")
        def delete_item(item_id, _table=table, _lf=lookup_field, _audit=audit_log,
                        _webhook=webhook, _metrics=metrics):
            user, role, err = _check_auth("delete")
            if err:
                return err

            existing = storage.get(_table, item_id, lookup_field=_lf)
            if existing is None:
                return jsonify(create_error_response("Not found", 404)), 404

            scope_filter = _get_scope(user, role)
            if scope_filter and not all(existing.get(k) == v for k, v in scope_filter.items()):
                return jsonify(create_error_response("Not found", 404)), 404

            deleted = storage.delete(_table, item_id, soft=supports_soft_delete, lookup_field=_lf)
            if not deleted:
                return jsonify(create_error_response("Not found", 404)), 404
            if _metrics:
                _metrics.record("DELETE", entity_name, str(item_id))
            if _audit and entity_audit:
                _audit.record("DELETE", entity_name, item_id, performed_by=_get_performer(user))
            if _webhook:
                _webhook.dispatch("DELETE", entity_name, item_id, {})
            _broadcast(entity_name, "DELETE", {"id": str(item_id)})
            return "", 204

        if supports_soft_delete:
            @blueprint.route(f"/{table}/<{id_converter}:item_id>/restore", methods=["POST"], endpoint=f"{table}_restore")
            def restore_item(item_id, _table=table, _lf=lookup_field):
                _user, _role, err = _check_auth("delete")
                if err:
                    return err

                restored = storage.restore(_table, item_id, lookup_field=_lf)
                if not restored:
                    return jsonify(create_error_response("Not found", 404)), 404
                _broadcast(entity_name, "RESTORE", {"id": str(item_id)})
                return "", 204

    if "create" in schema.permissions:
        @blueprint.route(f"/{table}/bulk", methods=["POST"], endpoint=f"{table}_bulk_create")
        def bulk_create(_table=table, _input=input_fields, _schema=model_schema):
            user, role, err = _check_auth("create")
            if err:
                return err

            body = request.get_json(silent=True)
            if not isinstance(body, list):
                return jsonify(create_error_response("Request body must be a JSON array", 400)), 400

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
            return jsonify({
                "data": results,
                "meta": {"total": len(body), "succeeded": succeeded, "failed": failed},
            }), 201

    if "update" in schema.permissions:
        @blueprint.route(f"/{table}/bulk", methods=["PUT"], endpoint=f"{table}_bulk_update")
        def bulk_update(_table=table, _input=input_fields, _schema=model_schema, _lf=lookup_field):
            user, role, err = _check_auth("update")
            if err:
                return err

            body = request.get_json(silent=True)
            if not isinstance(body, list):
                return jsonify(create_error_response("Request body must be a JSON array", 400)), 400

            scope_filter = _get_scope(user, role)
            succeeded = 0
            failed = 0
            results = []
            for item_data in body:
                try:
                    item_id = item_data.get(_lf)
                    if item_id is None:
                        failed += 1
                        continue
                    existing = storage.get(_table, item_id, lookup_field=_lf)
                    if existing is None:
                        failed += 1
                        continue
                    if scope_filter and not all(existing.get(k) == v for k, v in scope_filter.items()):
                        failed += 1
                        continue
                    data = {k: v for k, v in item_data.items() if k in _input and k != _lf}
                    item = storage.update(_table, item_id, data, lookup_field=_lf)
                    if item:
                        item = filter_response(item, _schema)
                        results.append(item)
                        succeeded += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return jsonify({
                "data": results,
                "meta": {"total": len(body), "succeeded": succeeded, "failed": failed},
            }), 200

    if "delete" in schema.permissions:
        @blueprint.route(f"/{table}/bulk", methods=["DELETE"], endpoint=f"{table}_bulk_delete")
        def bulk_delete(_table=table, _lf=lookup_field, _schema=model_schema):
            user, role, err = _check_auth("delete")
            if err:
                return err

            body = request.get_json(silent=True)
            if not isinstance(body, list):
                return jsonify(create_error_response("Request body must be a JSON array", 400)), 400

            scope_filter = _get_scope(user, role)
            succeeded = 0
            failed = 0
            for item_id in body:
                try:
                    existing = storage.get(_table, item_id, lookup_field=_lf)
                    if existing is None:
                        failed += 1
                        continue
                    if scope_filter and not all(existing.get(k) == v for k, v in scope_filter.items()):
                        failed += 1
                        continue
                    deleted = storage.delete(_table, item_id, soft=supports_soft_delete, lookup_field=_lf)
                    if deleted:
                        succeeded += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
            return jsonify({
                "data": [],
                "meta": {"total": len(body), "succeeded": succeeded, "failed": failed},
            }), 200

    if "list" in schema.permissions:
        from flashapi.features.export import CONTENT_TYPES, EXPORTERS

        @blueprint.route(f"/{table}/export", methods=["GET"], endpoint=f"{table}_export")
        def export_items(_table=table, _schema=model_schema):
            from flask import Response as FlaskResponse

            user, role, err = _check_auth("list")
            if err:
                return err

            fmt = request.args.get("format", "csv").lower()
            if fmt not in EXPORTERS:
                return jsonify(create_error_response(
                    f"Unsupported format: {fmt}. Use csv, xlsx, or pdf", 400,
                )), 400
            items = storage.list_all(_table)

            scope_filter = _get_scope(user, role)
            if scope_filter:
                items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

            all_fields = sorted(export_fields(_schema))
            requested = request.args.get("fields", "")
            if requested:
                fields = [f for f in requested.split(",") if f in all_fields]
                if not fields:
                    return jsonify(create_error_response(f"No valid fields. Available: {', '.join(all_fields)}", 400)), 400
            else:
                fields = all_fields
            try:
                content = EXPORTERS[fmt](items, fields)
            except ImportError as e:
                return jsonify(create_error_response(str(e), 400)), 400
            return FlaskResponse(
                content,
                mimetype=CONTENT_TYPES[fmt],
                headers={"Content-Disposition": f'attachment; filename="{_table}.{fmt}"'},
            )
