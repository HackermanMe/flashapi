from typing import Any, Callable, Optional
from datetime import date, datetime, time
import uuid

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, create_model

from flashapi.core.schema import Model, ModelSchema, FieldType
from flashapi.core.response import create_list_response, create_item_response, create_error_response
from flashapi.core.relations import resolve_relations, find_expandable_fields
from flashapi.core.visibility import filter_response, writable_fields, export_fields
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.features.export import EXPORTERS, CONTENT_TYPES
from flashapi.features.dashboard import MetricsCollector, DASHBOARD_HTML
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage
from flashapi.storage.sqlalchemy import SQLAlchemyStorage


DEFAULT_BASE_PATH = "/api"


def _parse_lookup_id(value: str, lookup_field: str):
    """Parse the URL path parameter to the appropriate type."""
    if lookup_field == "id":
        try:
            return int(value)
        except ValueError:
            return value
    return value

FIELD_TYPE_TO_PYTHON = {
    FieldType.STRING: str,
    FieldType.TEXT: str,
    FieldType.INTEGER: int,
    FieldType.FLOAT: float,
    FieldType.BOOLEAN: bool,
    FieldType.DATE: date,
    FieldType.DATETIME: datetime,
    FieldType.TIME: time,
    FieldType.UUID: uuid.UUID,
    FieldType.JSON: dict,
    FieldType.BINARY: bytes,
}


def _build_pydantic_model(schema: ModelSchema, *, all_optional: bool = False) -> type[BaseModel]:
    fields = {}
    for f in schema.fields:
        if f.primary_key and f.auto_generated:
            continue
        if f.auto_generated or f.auto:
            continue
        if f.hidden or f.readonly:
            continue
        python_type = FIELD_TYPE_TO_PYTHON.get(f.type, str)
        if f.required and not all_optional:
            fields[f.name] = (python_type, ...)
        else:
            fields[f.name] = (Optional[python_type], None)
    suffix = "Update" if all_optional else "Create"
    return create_model(f"{schema.name}{suffix}", **fields)


class FlashAPI:
    """FastAPI adapter — generates a full CRUD API from models."""

    def __init__(
        self,
        models: list,
        *,
        engine=None,
        base_path: str = DEFAULT_BASE_PATH,
        database: str = "flashapi.db",
        docs: bool = True,
        formatter: Optional[Callable] = None,
        audit: bool = True,
        webhook_urls: Optional[list[str]] = None,
        rate_limit: Optional[int] = None,
        rate_window: int = 60,
        auth_backend=None,
    ):
        self._app = FastAPI(
            title="FlashAPI",
            description="Define your models. FlashAPI does the rest.",
            docs_url="/docs" if docs else None,
            redoc_url="/redoc" if docs else None,
        )
        self._base_path = base_path.rstrip("/")
        self._engine = engine
        self._session_factory = None
        if engine is not None:
            from sqlalchemy.orm import sessionmaker
            self._session_factory = sessionmaker(bind=engine)
        self._auto_storage = AutoStorage(database) if engine is None else None
        self._formatter = formatter
        self._schemas: list[ModelSchema] = []
        self._storages: dict[str, Any] = {}

        # Audit
        self._audit = None
        if audit and self._auto_storage:
            from flashapi.features.audit import AuditLog
            self._audit = AuditLog(self._auto_storage._conn)

        # Webhooks
        self._webhook = None
        if webhook_urls:
            from flashapi.features.webhooks import WebhookDispatcher
            self._webhook = WebhookDispatcher(webhook_urls)

        # Rate limiting
        self._rate_limiter = None
        if rate_limit:
            from flashapi.features.rate_limit import RateLimiter
            self._rate_limiter = RateLimiter(limit=rate_limit, window=rate_window)
            self._add_rate_limit_middleware()

        # Metrics
        self._metrics = MetricsCollector()

        # Auth
        self._auth_backend = auth_backend

        for model_entry in models:
            self._prepare_model(model_entry)

        resolve_relations(self._schemas)

        for schema in self._schemas:
            self._metrics.register_entity(
                schema.name,
                soft_delete=schema.soft_delete,
                audit=schema.audit,
                webhook=bool(webhook_urls),
                rate_limited=bool(rate_limit),
            )
            self._create_routes(schema)

        self._register_relations()
        self._add_dashboard_routes()
        self._add_api_root()

    def _prepare_model(self, model_entry) -> None:
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

        is_sa = hasattr(wrapper.model_class, "__table__") and hasattr(wrapper.model_class, "__tablename__")

        if is_sa and self._session_factory is not None:
            storage = SQLAlchemyStorage(self._session_factory, wrapper.model_class)
        else:
            self._auto_storage.ensure_table(schema, soft_delete=schema.soft_delete)
            storage = self._auto_storage

        self._storages[schema.plural] = storage
        self._schemas.append(schema)

    def _add_dashboard_routes(self) -> None:
        bp = self._base_path
        metrics = self._metrics
        webhook = self._webhook

        @self._app.get(f"{bp}/dashboard", tags=["Dashboard"], name="dashboard_html", include_in_schema=False)
        async def dashboard_html():
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=DASHBOARD_HTML)

        @self._app.get(f"{bp}/dashboard/metrics.json", tags=["Dashboard"], name="dashboard_metrics")
        async def dashboard_metrics():
            return metrics.get_metrics(webhook)

    def _add_api_root(self) -> None:
        bp = self._base_path
        schemas = self._schemas

        @self._app.get(f"{bp}", tags=["Root"], name="api_root", include_in_schema=False)
        @self._app.get(f"{bp}/", tags=["Root"], name="api_root_slash", include_in_schema=False)
        async def api_root(request: Request):
            base = str(request.base_url).rstrip("/") + bp
            if not base.endswith("/"):
                base += "/"
            resources = {s.plural: base + s.plural + "/" for s in schemas}
            links = {
                "docs": base + "docs/",
                "openapi": base + "openapi.json",
                "dashboard": base + "dashboard/",
            }
            return {"resources": resources, "links": links}

    def _add_rate_limit_middleware(self) -> None:
        from starlette.middleware.base import BaseHTTPMiddleware

        limiter = self._rate_limiter

        class RateLimitMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                client_ip = request.client.host if request.client else "unknown"
                allowed, remaining, reset = limiter.check(client_ip)
                if not allowed:
                    return JSONResponse(
                        status_code=429,
                        content={"error": "Rate limit exceeded", "status": 429, "retryAfter": reset},
                        headers={
                            "X-RateLimit-Limit": str(limiter.limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(reset),
                        },
                    )
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(limiter.limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(reset)
                return response

        self._app.add_middleware(RateLimitMiddleware)

    def _register_relations(self) -> None:
        parent_to_children = resolve_relations(self._schemas)
        formatter = self._formatter

        for parent_plural, relations in parent_to_children.items():
            for relation in relations:
                self._add_nested_list_route(
                    parent_plural=parent_plural,
                    child_plural=relation.target_plural,
                    foreign_key=relation.foreign_key,
                    parent_storage=self._storages.get(parent_plural),
                    child_storage=self._storages.get(relation.target_plural),
                    formatter=formatter,
                )

    def _check_auth(self, request: Request, operation: str, schema: ModelSchema):
        """Returns (user, role, error_response). error_response is None if access granted."""
        from flashapi.features.auth import check_access, get_scope_filter

        if self._auth_backend is None:
            return None, "admin", None

        model_access = schema.access
        if model_access is None or model_access == "public" or model_access is True:
            if isinstance(model_access, dict):
                op_access = model_access.get(operation, "public")
                if op_access == "public":
                    return None, "public", None
            else:
                return None, "public", None

        user = self._auth_backend.authenticate(request)
        if user is None:
            if isinstance(model_access, dict):
                op_access = model_access.get(operation, "authenticated")
                if op_access == "public":
                    return None, "public", None
            return None, "public", JSONResponse(
                status_code=401,
                content=create_error_response("Authentication required", 401),
            )

        role = self._auth_backend.get_role(user)
        if not check_access(role, model_access, operation):
            return user, role, JSONResponse(
                status_code=403,
                content=create_error_response("Forbidden", 403),
            )
        return user, role, None

    def _get_scope_filter(self, user, role: str, schema: ModelSchema):
        """Returns the scope filter dict or None."""
        from flashapi.features.auth import get_scope_filter
        if self._auth_backend is None or user is None:
            return None
        return get_scope_filter(user, self._auth_backend, schema.scope, schema.tenant_field, schema.owner_field, role)

    def _create_routes(self, schema: ModelSchema) -> None:
        table = schema.plural
        field_names = {f.name for f in schema.fields if not f.primary_key}
        input_fields = writable_fields(schema)
        formatter = self._formatter
        storage = self._storages[table]
        expandable = find_expandable_fields(schema)
        create_model_cls = _build_pydantic_model(schema)
        update_model_cls = _build_pydantic_model(schema, all_optional=True)
        model_schema = schema
        lookup_field = schema.lookup_field

        if "list" in schema.permissions:
            self._add_list_route(table, field_names, formatter, storage, schema.name, expandable, model_schema)
            self._add_export_route(table, storage, schema.name, model_schema)

        if "create" in schema.permissions:
            self._add_create_route(table, input_fields, formatter, storage, schema.name, create_model_cls, model_schema)
            self._add_bulk_create_route(table, input_fields, formatter, storage, schema.name, model_schema)

        if "delete" in schema.permissions and schema.soft_delete:
            self._add_restore_route(table, storage, schema.name, lookup_field, model_schema=schema)

        if "read" in schema.permissions:
            self._add_read_route(table, formatter, storage, schema.name, expandable, model_schema, lookup_field)
            if schema.audit:
                self._add_history_route(table, schema.name, lookup_field, model_schema=schema)

        if "update" in schema.permissions:
            self._add_update_route(table, input_fields, formatter, storage, schema.name, update_model_cls, model_schema, lookup_field)

        if "delete" in schema.permissions:
            self._add_delete_route(table, storage, schema.name, lookup_field)

    def _add_list_route(self, table, field_names, formatter, storage, tag, expandable, model_schema):
        bp = self._base_path
        metrics = self._metrics
        supports_soft_delete = model_schema.soft_delete

        @self._app.get(f"{bp}/{table}", tags=[tag], name=f"{table}_list")
        async def route(
            request: Request,
            page: int = Query(0, ge=0),
            size: int = Query(20, ge=1, le=100),
            sort: Optional[str] = None,
            search: Optional[str] = None,
            expand: Optional[str] = None,
            deleted: bool = False,
        ):
            user, role, err = self._check_auth(request, "list", model_schema)
            if err:
                return err

            include_deleted = deleted and supports_soft_delete
            items = storage.list_all(table, include_deleted=include_deleted)

            scope_filter = self._get_scope_filter(user, role, model_schema)
            if scope_filter:
                items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

            params = dict(request.query_params)
            items = apply_filters(items, params, field_names)
            if search:
                metrics.record("SEARCH", tag)
            items = apply_search(items, search, field_names)
            items = apply_sorting(items, sort, field_names)
            page_items, total = paginate(items, page, size)

            if expand:
                page_items = self._expand_items(page_items, expand, expandable)

            metrics.record("READ", tag)
            page_items = [filter_response(item, model_schema) for item in page_items]
            return create_list_response(page_items, total, page, size, formatter)

    def _add_read_route(self, table, formatter, storage, tag, expandable, model_schema, lookup_field="id"):
        bp = self._base_path
        lf = lookup_field

        @self._app.get(f"{bp}/{table}/{{item_id}}", tags=[tag], name=f"{table}_read")
        async def route(request: Request, item_id: str, expand: Optional[str] = None):
            user, role, err = self._check_auth(request, "read", model_schema)
            if err:
                return err

            lookup_id = _parse_lookup_id(item_id, lf)
            item = storage.get(table, lookup_id, lookup_field=lf)
            if item is None:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

            scope_filter = self._get_scope_filter(user, role, model_schema)
            if scope_filter and not all(item.get(k) == v for k, v in scope_filter.items()):
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

            if expand:
                item = self._expand_items([item], expand, expandable)[0]

            item = filter_response(item, model_schema)
            return create_item_response(item, formatter)

    def _add_history_route(self, table, entity_name, lookup_field="id", model_schema=None):
        bp = self._base_path
        audit = self._audit
        _schema = model_schema

        @self._app.get(f"{bp}/{table}/{{item_id}}/history", tags=[entity_name], name=f"{table}_history")
        async def route(request: Request, item_id: str):
            if _schema:
                user, role, err = self._check_auth(request, "read", _schema)
                if err:
                    return err

            if audit is None:
                return JSONResponse(status_code=404, content=create_error_response("Audit not enabled", 404))
            history = audit.get_history(entity_name, item_id)
            return {"data": history}

    def _add_create_route(self, table, input_fields, formatter, storage, tag, body_model, model_schema):
        bp = self._base_path
        audit = self._audit
        webhook = self._webhook
        metrics = self._metrics
        entity_audit = model_schema.audit

        @self._app.post(f"{bp}/{table}", status_code=201, tags=[tag], name=f"{table}_create")
        async def route(request: Request, body: body_model):
            user, role, err = self._check_auth(request, "create", model_schema)
            if err:
                return err

            data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in input_fields}

            scope_filter = self._get_scope_filter(user, role, model_schema)
            if scope_filter:
                data.update(scope_filter)

            item = storage.create(table, data)
            metrics.record("CREATE", tag, str(item.get("id", "")))
            if audit and entity_audit:
                audit.record("CREATE", tag, item.get("id", ""))
            if webhook:
                webhook.dispatch("CREATE", tag, item.get("id", ""), item)
            item = filter_response(item, model_schema)
            return create_item_response(item, formatter)

    def _add_update_route(self, table, input_fields, formatter, storage, tag, body_model, model_schema, lookup_field="id"):
        bp = self._base_path
        audit = self._audit
        webhook = self._webhook
        metrics = self._metrics
        lf = lookup_field
        entity_audit = model_schema.audit

        @self._app.put(f"{bp}/{table}/{{item_id}}", tags=[tag], name=f"{table}_update")
        async def route(request: Request, item_id: str, body: body_model):
            user, role, err = self._check_auth(request, "update", model_schema)
            if err:
                return err

            lookup_id = _parse_lookup_id(item_id, lf)
            old_item = storage.get(table, lookup_id, lookup_field=lf)
            if old_item is None:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

            scope_filter = self._get_scope_filter(user, role, model_schema)
            if scope_filter and not all(old_item.get(k) == v for k, v in scope_filter.items()):
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

            data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in input_fields}
            item = storage.update(table, lookup_id, data, lookup_field=lf)
            if item is None:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )
            metrics.record("UPDATE", tag, str(item_id))
            if audit and entity_audit:
                audit.record("UPDATE", tag, item_id, old_data=old_item, new_data=item)
            if webhook:
                webhook.dispatch("UPDATE", tag, item_id, item)
            item = filter_response(item, model_schema)
            return create_item_response(item, formatter)

    def _add_delete_route(self, table, storage, tag, lookup_field="id"):
        bp = self._base_path
        audit = self._audit
        webhook = self._webhook
        metrics = self._metrics
        lf = lookup_field
        schema_audit = next((s.audit for s in self._schemas if s.name == tag), False)
        schema_soft_delete = next((s.soft_delete for s in self._schemas if s.name == tag), False)
        _model_schema = next((s for s in self._schemas if s.name == tag), None)

        @self._app.delete(f"{bp}/{table}/{{item_id}}", status_code=204, tags=[tag], name=f"{table}_delete")
        async def route(request: Request, item_id: str):
            if _model_schema:
                user, role, err = self._check_auth(request, "delete", _model_schema)
                if err:
                    return err
            else:
                user, role = None, "admin"

            lookup_id = _parse_lookup_id(item_id, lf)
            existing = storage.get(table, lookup_id, lookup_field=lf)
            if existing is None:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

            if _model_schema:
                scope_filter = self._get_scope_filter(user, role, _model_schema)
                if scope_filter and not all(existing.get(k) == v for k, v in scope_filter.items()):
                    return JSONResponse(
                        status_code=404,
                        content=create_error_response("Not found", 404),
                    )

            deleted = storage.delete(table, lookup_id, soft=schema_soft_delete, lookup_field=lf)
            if not deleted:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )
            metrics.record("DELETE", tag, str(item_id))
            if audit and schema_audit:
                audit.record("DELETE", tag, item_id)
            if webhook:
                webhook.dispatch("DELETE", tag, item_id, {})

    def _add_export_route(self, table, storage, tag, model_schema):
        bp = self._base_path

        @self._app.get(f"{bp}/{table}/export", tags=[tag], name=f"{table}_export")
        async def route(request: Request, format: str = Query("csv"), fields: str = Query("")):
            user, role, err = self._check_auth(request, "list", model_schema)
            if err:
                return err

            fmt = format.lower()
            if fmt not in EXPORTERS:
                return JSONResponse(
                    status_code=400,
                    content=create_error_response(f"Unsupported format: {fmt}. Use csv, xlsx, or pdf", 400),
                )
            items = storage.list_all(table)

            scope_filter = self._get_scope_filter(user, role, model_schema)
            if scope_filter:
                items = [i for i in items if all(i.get(k) == v for k, v in scope_filter.items())]

            all_fields = sorted(export_fields(model_schema))
            if fields:
                export_cols = [f for f in fields.split(",") if f in all_fields]
                if not export_cols:
                    return JSONResponse(
                        status_code=400,
                        content=create_error_response(f"No valid fields. Available: {', '.join(all_fields)}", 400),
                    )
            else:
                export_cols = all_fields
            try:
                content = EXPORTERS[fmt](items, export_cols)
            except ImportError as e:
                return JSONResponse(
                    content=create_error_response(str(e), 400), status_code=400
                )
            return Response(
                content=content,
                media_type=CONTENT_TYPES[fmt],
                headers={"Content-Disposition": f'attachment; filename="{table}.{fmt}"'},
            )

    def _add_bulk_create_route(self, table, input_fields, formatter, storage, tag, model_schema):
        bp = self._base_path

        @self._app.post(f"{bp}/{table}/bulk", status_code=201, tags=[tag], name=f"{table}_bulk_create")
        async def route(request: Request):
            user, role, err = self._check_auth(request, "create", model_schema)
            if err:
                return err

            body = await request.json()
            if not isinstance(body, list):
                return JSONResponse(
                    status_code=400,
                    content=create_error_response("Request body must be a JSON array", 400),
                )

            scope_filter = self._get_scope_filter(user, role, model_schema)
            succeeded = 0
            failed = 0
            results = []
            for item_data in body:
                try:
                    data = {k: v for k, v in item_data.items() if k in input_fields}
                    if scope_filter:
                        data.update(scope_filter)
                    item = storage.create(table, data)
                    item = filter_response(item, model_schema)
                    results.append(item)
                    succeeded += 1
                except Exception:
                    failed += 1
            return {
                "data": results,
                "meta": {"total": len(body), "succeeded": succeeded, "failed": failed},
            }

    def _add_restore_route(self, table, storage, tag, lookup_field="id", model_schema=None):
        bp = self._base_path
        lf = lookup_field
        _schema = model_schema

        @self._app.post(f"{bp}/{table}/{{item_id}}/restore", status_code=204, tags=[tag], name=f"{table}_restore")
        async def route(request: Request, item_id: str):
            if _schema:
                user, role, err = self._check_auth(request, "delete", _schema)
                if err:
                    return err

            lookup_id = _parse_lookup_id(item_id, lf)
            restored = storage.restore(table, lookup_id, lookup_field=lf)
            if not restored:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Not found", 404),
                )

    def _add_nested_list_route(self, parent_plural, child_plural, foreign_key, parent_storage, child_storage, formatter):
        bp = self._base_path

        @self._app.get(
            f"{bp}/{parent_plural}/{{parent_id}}/{child_plural}",
            tags=[parent_plural.title()],
            name=f"{parent_plural}_{child_plural}_nested",
        )
        async def route(
            parent_id: int,
            page: int = Query(0, ge=0),
            size: int = Query(20, ge=1, le=100),
            sort: Optional[str] = None,
            search: Optional[str] = None,
        ):
            parent = parent_storage.get(parent_plural, parent_id)
            if parent is None:
                return JSONResponse(
                    status_code=404,
                    content=create_error_response("Parent not found", 404),
                )

            all_items = child_storage.list_all(child_plural)
            items = [i for i in all_items if i.get(foreign_key) == parent_id]

            child_fields = {k for item in items for k in item.keys() if k != "id"}
            if search:
                items = apply_search(items, search, child_fields)
            if sort:
                items = apply_sorting(items, sort, child_fields)

            page_items, total = paginate(items, page, size)
            return create_list_response(page_items, total, page, size, formatter)

    def _expand_items(self, items, expand_param, expandable):
        expand_fields = [f.strip() for f in expand_param.split(",")]
        expanded_items = []

        for item in items:
            item_copy = dict(item)
            for field_name in expand_fields:
                if field_name in expandable:
                    target_plural = expandable[field_name]
                    target_storage = self._storages.get(target_plural)
                    if target_storage is None:
                        continue
                    fk_field = f"{field_name}_id"
                    fk_value = item_copy.get(fk_field)
                    if fk_value is not None:
                        related = target_storage.get(target_plural, fk_value)
                        if related:
                            item_copy[field_name] = related
            expanded_items.append(item_copy)

        return expanded_items

    def get(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        def decorator(func):
            self._app.get(path, tags=[tag], summary=summary or f"GET {path}", **kwargs)(func)
            return func
        return decorator

    def post(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        def decorator(func):
            self._app.post(path, tags=[tag], summary=summary or f"POST {path}", **kwargs)(func)
            return func
        return decorator

    def put(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        def decorator(func):
            self._app.put(path, tags=[tag], summary=summary or f"PUT {path}", **kwargs)(func)
            return func
        return decorator

    def delete(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        def decorator(func):
            self._app.delete(path, tags=[tag], summary=summary or f"DELETE {path}", **kwargs)(func)
            return func
        return decorator

    def patch(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        def decorator(func):
            self._app.patch(path, tags=[tag], summary=summary or f"PATCH {path}", **kwargs)(func)
            return func
        return decorator

    @property
    def app(self):
        return self._app

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        import uvicorn
        uvicorn.run(self._app, host=host, port=port, **kwargs)
