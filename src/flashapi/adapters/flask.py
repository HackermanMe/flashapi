from __future__ import annotations

from typing import Callable

from flashapi.core.schema import Model, ModelSchema
from flashapi.core.response import create_list_response, create_item_response
from flashapi.core.relations import resolve_relations, find_expandable_fields
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage
from flashapi.docs.openapi import generate_openapi_schema, get_swagger_html


def register_models(
    app,
    models: list[type | Model],
    *,
    database: str = "flashapi.db",
    docs: bool = True,
    formatter: Callable | None = None,
):
    """Register models on an existing Flask app."""
    from flask import Blueprint

    storage = AutoStorage(database)
    blueprint = Blueprint("flashapi", __name__)
    all_schemas: list[ModelSchema] = []

    for model_entry in models:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions
        storage.ensure_table(schema)
        all_schemas.append(schema)
        expandable = find_expandable_fields(schema)
        _create_flask_routes(blueprint, schema, storage, formatter, expandable)

    parent_to_children = resolve_relations(all_schemas)
    for parent_plural, relations in parent_to_children.items():
        for relation in relations:
            _create_nested_route(
                blueprint, parent_plural, relation.target_plural,
                relation.foreign_key, storage, formatter,
            )

    if docs:
        _add_docs_routes(blueprint, all_schemas)

    app.register_blueprint(blueprint)


def _add_docs_routes(blueprint, schemas: list[ModelSchema]) -> None:
    from flask import jsonify, Response

    openapi_spec = generate_openapi_schema(schemas)

    @blueprint.route("/openapi.json", methods=["GET"], endpoint="flashapi_openapi")
    def openapi_json():
        return jsonify(openapi_spec)

    @blueprint.route("/docs", methods=["GET"], endpoint="flashapi_docs")
    def docs_ui():
        html = get_swagger_html(title="FlashAPI", openapi_url="/openapi.json")
        return Response(html, content_type="text/html")


def _create_nested_route(blueprint, parent_plural, child_plural, foreign_key, storage, formatter):
    from flask import request, jsonify

    @blueprint.route(
        f"/{parent_plural}/<int:parent_id>/{child_plural}",
        methods=["GET"],
        endpoint=f"{parent_plural}_{child_plural}_nested",
    )
    def nested_list(parent_id, _pp=parent_plural, _cp=child_plural, _fk=foreign_key):
        parent = storage.get(_pp, parent_id)
        if parent is None:
            return jsonify({"error": "Parent not found"}), 404

        all_items = storage.list_all(_cp)
        items = [i for i in all_items if i.get(_fk) == parent_id]

        params = dict(request.args)
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
        sort = params.get("sort")
        search = params.get("search")

        child_fields = {k for item in items for k in item.keys() if k != "id"}
        if search:
            items = apply_search(items, search, child_fields)
        if sort:
            items = apply_sorting(items, sort, child_fields)

        page_items, total = paginate(items, page, page_size)
        return jsonify(create_list_response(page_items, total, page, page_size, formatter))


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
    storage: AutoStorage,
    formatter: Callable | None,
    expandable: dict,
) -> None:
    from flask import request, jsonify

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}

    if "list" in schema.permissions:
        @blueprint.route(f"/{table}", methods=["GET"], endpoint=f"{table}_list")
        def list_items(_table=table, _fields=field_names, _exp=expandable):
            items = storage.list_all(_table)
            params = dict(request.args)
            page = int(params.get("page", 1))
            page_size = int(params.get("page_size", 20))
            sort = params.get("sort")
            search = params.get("search")
            expand = params.get("expand")

            items = apply_filters(items, params, _fields)
            items = apply_search(items, search, _fields)
            items = apply_sorting(items, sort, _fields)
            page_items, total = paginate(items, page, page_size)

            if expand:
                page_items = _expand_items(page_items, expand, _exp, storage)

            return jsonify(create_list_response(page_items, total, page, page_size, formatter))

    if "read" in schema.permissions:
        @blueprint.route(f"/{table}/<int:item_id>", methods=["GET"], endpoint=f"{table}_get")
        def get_item(item_id, _table=table, _exp=expandable):
            item = storage.get(_table, item_id)
            if item is None:
                return jsonify({"error": "Not found"}), 404

            expand = request.args.get("expand")
            if expand:
                item = _expand_items([item], expand, _exp, storage)[0]

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
