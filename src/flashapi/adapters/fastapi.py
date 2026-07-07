from typing import Any, Callable, Optional

from fastapi import FastAPI, HTTPException, Query, Request

from flashapi.core.schema import Model, ModelSchema
from flashapi.core.response import create_list_response, create_item_response
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage


class FlashAPI:
    """FastAPI adapter — generates a full CRUD API from models."""

    def __init__(
        self,
        models: list,
        *,
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
        self._storage = AutoStorage(database)
        self._formatter = formatter

        for model_entry in models:
            self._register_model(model_entry)

    def _register_model(self, model_entry: type | Model) -> None:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions
        self._storage.ensure_table(schema)
        self._create_routes(schema)

    def _create_routes(self, schema: ModelSchema) -> None:
        table = schema.plural
        field_names = {f.name for f in schema.fields if not f.primary_key}
        formatter = self._formatter
        storage = self._storage

        if "list" in schema.permissions:
            self._add_list_route(table, field_names, formatter, storage, schema.name)

        if "read" in schema.permissions:
            self._add_read_route(table, formatter, storage, schema.name)

        if "create" in schema.permissions:
            self._add_create_route(table, field_names, formatter, storage, schema.name)

        if "update" in schema.permissions:
            self._add_update_route(table, field_names, formatter, storage, schema.name)

        if "delete" in schema.permissions:
            self._add_delete_route(table, storage, schema.name)

    def _add_list_route(self, table, field_names, formatter, storage, tag):
        @self._app.get(f"/{table}", tags=[tag], name=f"{table}_list")
        async def route(
            request: Request,
            page: int = Query(1, ge=1),
            page_size: int = Query(20, ge=1, le=100),
            sort: Optional[str] = None,
            search: Optional[str] = None,
        ):
            items = storage.list_all(table)
            params = dict(request.query_params)
            items = apply_filters(items, params, field_names)
            items = apply_search(items, search, field_names)
            items = apply_sorting(items, sort, field_names)
            page_items, total = paginate(items, page, page_size)
            return create_list_response(page_items, total, page, page_size, formatter)

    def _add_read_route(self, table, formatter, storage, tag):
        @self._app.get(f"/{table}/{{item_id}}", tags=[tag], name=f"{table}_read")
        async def route(item_id: int):
            item = storage.get(table, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="Not found")
            return create_item_response(item, formatter)

    def _add_create_route(self, table, field_names, formatter, storage, tag):
        @self._app.post(f"/{table}", status_code=201, tags=[tag], name=f"{table}_create")
        async def route(request: Request):
            body = await request.json()
            data = {k: v for k, v in body.items() if k in field_names}
            item = storage.create(table, data)
            return create_item_response(item, formatter)

    def _add_update_route(self, table, field_names, formatter, storage, tag):
        @self._app.put(f"/{table}/{{item_id}}", tags=[tag], name=f"{table}_update")
        async def route(item_id: int, request: Request):
            body = await request.json()
            data = {k: v for k, v in body.items() if k in field_names}
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

    @property
    def app(self):
        return self._app

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs):
        import uvicorn
        uvicorn.run(self._app, host=host, port=port, **kwargs)
