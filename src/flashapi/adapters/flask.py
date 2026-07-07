from __future__ import annotations

from typing import Callable

from flashapi.core.schema import Model, ModelSchema
from flashapi.core.response import create_list_response, create_item_response
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage


def register_models(
    app,
    models: list[type | Model],
    *,
    database: str = "flashapi.db",
    docs: bool = True,
    formatter: Callable | None = None,
):
    """Register models on an existing Flask app."""
    from flask import Blueprint, request, jsonify, abort

    storage = AutoStorage(database)
    blueprint = Blueprint("flashapi", __name__)

    for model_entry in models:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions
        storage.ensure_table(schema)
        _create_flask_routes(blueprint, schema, storage, formatter)

    app.register_blueprint(blueprint)


def _create_flask_routes(
    blueprint,
    schema: ModelSchema,
    storage: AutoStorage,
    formatter: Callable | None,
) -> None:
    from flask import request, jsonify

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}

    if "list" in schema.permissions:
        @blueprint.route(f"/{table}", methods=["GET"], endpoint=f"{table}_list")
        def list_items(_table=table, _fields=field_names):
            items = storage.list_all(_table)
            params = dict(request.args)
            page = int(params.get("page", 1))
            page_size = int(params.get("page_size", 20))
            sort = params.get("sort")
            search = params.get("search")

            items = apply_filters(items, params, _fields)
            items = apply_search(items, search, _fields)
            items = apply_sorting(items, sort, _fields)
            page_items, total = paginate(items, page, page_size)
            return jsonify(create_list_response(page_items, total, page, page_size, formatter))

    if "read" in schema.permissions:
        @blueprint.route(f"/{table}/<int:item_id>", methods=["GET"], endpoint=f"{table}_get")
        def get_item(item_id, _table=table):
            item = storage.get(_table, item_id)
            if item is None:
                return jsonify({"error": "Not found"}), 404
            return jsonify(create_item_response(item, formatter))

    if "create" in schema.permissions:
        @blueprint.route(f"/{table}", methods=["POST"], endpoint=f"{table}_create")
        def create_item(_table=table, _fields=field_names):
            body = request.get_json()
            data = {k: v for k, v in body.items() if k in _fields}
            item = storage.create(_table, data)
            return jsonify(create_item_response(item, formatter)), 201

    if "update" in schema.permissions:
        @blueprint.route(f"/{table}/<int:item_id>", methods=["PUT"], endpoint=f"{table}_update")
        def update_item(item_id, _table=table, _fields=field_names):
            body = request.get_json()
            data = {k: v for k, v in body.items() if k in _fields}
            item = storage.update(_table, item_id, data)
            if item is None:
                return jsonify({"error": "Not found"}), 404
            return jsonify(create_item_response(item, formatter))

    if "delete" in schema.permissions:
        @blueprint.route(f"/{table}/<int:item_id>", methods=["DELETE"], endpoint=f"{table}_delete")
        def delete_item(item_id, _table=table):
            deleted = storage.delete(_table, item_id)
            if not deleted:
                return jsonify({"error": "Not found"}), 404
            return "", 204
