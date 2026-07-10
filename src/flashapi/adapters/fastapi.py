from typing import Any, Callable, Optional
from datetime import date, datetime, time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, create_model

from flashapi.core.schema import Model, ModelSchema, FieldType
from flashapi.core.response import create_list_response, create_item_response
from flashapi.core.relations import resolve_relations, find_expandable_fields
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage
from flashapi.storage.sqlalchemy import SQLAlchemyStorage


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
    """Create a Pydantic model from a ModelSchema for request body validation."""
    fields = {}
    for f in schema.fields:
        if f.primary_key and f.auto_generated:
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
        database: str = "flashapi.db",
        docs: bool = True,
        formatter: Optional[Callable] = None,
    ):
        self._app = FastAPI(
            title="FlashAPI",
            description="Define your models. FlashAPI does the rest.",
            docs_url="/docs" if docs else None,
            redoc_url="/redoc" if docs else None,
        )
        self._engine = engine
        self._session_factory = None
        if engine is not None:
            from sqlalchemy.orm import sessionmaker
            self._session_factory = sessionmaker(bind=engine)
        self._auto_storage = AutoStorage(database) if engine is None else None
        self._formatter = formatter
        self._schemas: list[ModelSchema] = []
        self._storages: dict[str, Any] = {}

        for model_entry in models:
            self._prepare_model(model_entry)

        resolve_relations(self._schemas)

        for schema in self._schemas:
            self._create_routes(schema)

        self._register_relations()

    def _prepare_model(self, model_entry) -> None:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions

        is_sa = hasattr(wrapper.model_class, "__table__") and hasattr(wrapper.model_class, "__tablename__")

        if is_sa and self._session_factory is not None:
            storage = SQLAlchemyStorage(self._session_factory, wrapper.model_class)
        else:
            self._auto_storage.ensure_table(schema)
            storage = self._auto_storage

        self._storages[schema.plural] = storage
        self._schemas.append(schema)

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

    def _create_routes(self, schema: ModelSchema) -> None:
        table = schema.plural
        field_names = {f.name for f in schema.fields if not f.primary_key}
        formatter = self._formatter
        storage = self._storages[table]
        expandable = find_expandable_fields(schema)
        create_model_cls = _build_pydantic_model(schema)
        update_model_cls = _build_pydantic_model(schema, all_optional=True)

        if "list" in schema.permissions:
            self._add_list_route(table, field_names, formatter, storage, schema.name, expandable)

        if "read" in schema.permissions:
            self._add_read_route(table, formatter, storage, schema.name, expandable)

        if "create" in schema.permissions:
            self._add_create_route(table, field_names, formatter, storage, schema.name, create_model_cls)

        if "update" in schema.permissions:
            self._add_update_route(table, field_names, formatter, storage, schema.name, update_model_cls)

        if "delete" in schema.permissions:
            self._add_delete_route(table, storage, schema.name)

    def _add_list_route(self, table, field_names, formatter, storage, tag, expandable):
        @self._app.get(f"/{table}", tags=[tag], name=f"{table}_list")
        async def route(
            request: Request,
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
            sort: Optional[str] = None,
            search: Optional[str] = None,
            expand: Optional[str] = None,
        ):
            items = storage.list_all(table)
            params = dict(request.query_params)
            items = apply_filters(items, params, field_names)
            items = apply_search(items, search, field_names)
            items = apply_sorting(items, sort, field_names)
            page_items, total = paginate(items, page, page_size)

            if expand:
                page_items = self._expand_items(page_items, expand, expandable)

            return create_list_response(page_items, total, page, page_size, formatter)

    def _add_read_route(self, table, formatter, storage, tag, expandable):
        @self._app.get(f"/{table}/{{item_id}}", tags=[tag], name=f"{table}_read")
        async def route(item_id: int, expand: Optional[str] = None):
            item = storage.get(table, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="Not found")

            if expand:
                item = self._expand_items([item], expand, expandable)[0]

            return create_item_response(item, formatter)

    def _add_create_route(self, table, field_names, formatter, storage, tag, body_model):
        @self._app.post(f"/{table}", status_code=201, tags=[tag], name=f"{table}_create")
        async def route(body: body_model):
            data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in field_names}
            item = storage.create(table, data)
            return create_item_response(item, formatter)

    def _add_update_route(self, table, field_names, formatter, storage, tag, body_model):
        @self._app.put(f"/{table}/{{item_id}}", tags=[tag], name=f"{table}_update")
        async def route(item_id: int, body: body_model):
            data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in field_names}
            item = storage.update(table, item_id, data)
            if item is None:
                raise HTTPException(status_code=404, detail="Not found")
            return create_item_response(item, formatter)

    def _add_delete_route(self, table, storage, tag):
        @self._app.delete(f"/{table}/{{item_id}}", status_code=204, tags=[tag], name=f"{table}_delete")
        async def route(item_id: int):
            deleted = storage.delete(table, item_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Not found")

    def _add_nested_list_route(self, parent_plural, child_plural, foreign_key, parent_storage, child_storage, formatter):
        @self._app.get(
            f"/{parent_plural}/{{parent_id}}/{child_plural}",
            tags=[parent_plural.title()],
            name=f"{parent_plural}_{child_plural}_nested",
        )
        async def route(
            parent_id: int,
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
            sort: Optional[str] = None,
            search: Optional[str] = None,
        ):
            parent = parent_storage.get(parent_plural, parent_id)
            if parent is None:
                raise HTTPException(status_code=404, detail="Parent not found")

            all_items = child_storage.list_all(child_plural)
            items = [i for i in all_items if i.get(foreign_key) == parent_id]

            child_fields = {k for item in items for k in item.keys() if k != "id"}
            if search:
                items = apply_search(items, search, child_fields)
            if sort:
                items = apply_sorting(items, sort, child_fields)

            page_items, total = paginate(items, page, page_size)
            return create_list_response(page_items, total, page, page_size, formatter)

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
        """Register a custom GET route — appears in Swagger docs."""
        def decorator(func):
            self._app.get(path, tags=[tag], summary=summary or f"GET {path}", **kwargs)(func)
            return func
        return decorator

    def post(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        """Register a custom POST route — appears in Swagger docs."""
        def decorator(func):
            self._app.post(path, tags=[tag], summary=summary or f"POST {path}", **kwargs)(func)
            return func
        return decorator

    def put(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        """Register a custom PUT route — appears in Swagger docs."""
        def decorator(func):
            self._app.put(path, tags=[tag], summary=summary or f"PUT {path}", **kwargs)(func)
            return func
        return decorator

    def delete(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        """Register a custom DELETE route — appears in Swagger docs."""
        def decorator(func):
            self._app.delete(path, tags=[tag], summary=summary or f"DELETE {path}", **kwargs)(func)
            return func
        return decorator

    def patch(self, path: str, *, tag: str = "Custom", summary: str = "", **kwargs):
        """Register a custom PATCH route — appears in Swagger docs."""
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
