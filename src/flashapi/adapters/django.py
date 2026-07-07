from __future__ import annotations

from typing import Callable

from flashapi.core.schema import Model, ModelSchema
from flashapi.core.response import create_list_response, create_item_response
from flashapi.features import paginate, apply_filters, apply_sorting, apply_search
from flashapi.inspectors import inspect_model
from flashapi.storage.orm import DjangoORMStorage


def generate_urls(
    models: list[type | Model],
    *,
    formatter: Callable | None = None,
):
    """Generate Django URL patterns for the given models."""
    from django.urls import path

    urlpatterns = []

    for model_entry in models:
        if isinstance(model_entry, Model):
            wrapper = model_entry
        else:
            wrapper = Model(model_entry)

        schema = inspect_model(wrapper.model_class, plural=wrapper.plural)
        schema.permissions = wrapper.permissions
        storage = DjangoORMStorage(wrapper.model_class)
        patterns = _create_django_views(schema, storage, formatter)
        urlpatterns.extend(patterns)

    return urlpatterns


def _create_django_views(
    schema: ModelSchema,
    storage: DjangoORMStorage,
    formatter: Callable | None,
):
    from django.urls import path
    from django.http import JsonResponse
    import json

    table = schema.plural
    field_names = {f.name for f in schema.fields if not f.primary_key}
    patterns = []

    if "list" in schema.permissions or "create" in schema.permissions:

        def collection_view(request, _table=table, _fields=field_names, _schema=schema):
            if request.method == "GET" and "list" in _schema.permissions:
                items = storage.list_all(_table)
                params = dict(request.GET)
                params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
                page = int(params.get("page", 1))
                page_size = int(params.get("page_size", 20))
                sort = params.get("sort")
                search = params.get("search")

                items = apply_filters(items, params, _fields)
                items = apply_search(items, search, _fields)
                items = apply_sorting(items, sort, _fields)
                page_items, total = paginate(items, page, page_size)
                return JsonResponse(
                    create_list_response(page_items, total, page, page_size, formatter)
                )

            elif request.method == "POST" and "create" in _schema.permissions:
                body = json.loads(request.body)
                data = {k: v for k, v in body.items() if k in _fields}
                item = storage.create(_table, data)
                return JsonResponse(create_item_response(item, formatter), status=201)

            return JsonResponse({"error": "Method not allowed"}, status=405)

        methods = []
        if "list" in schema.permissions:
            methods.append("GET")
        if "create" in schema.permissions:
            methods.append("POST")

        patterns.append(path(f"{table}/", collection_view, name=f"{table}_collection"))

    if any(op in schema.permissions for op in ["read", "update", "delete"]):

        def detail_view(request, item_id, _table=table, _fields=field_names, _schema=schema):
            if request.method == "GET" and "read" in _schema.permissions:
                item = storage.get(_table, item_id)
                if item is None:
                    return JsonResponse({"error": "Not found"}, status=404)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "PUT" and "update" in _schema.permissions:
                body = json.loads(request.body)
                data = {k: v for k, v in body.items() if k in _fields}
                item = storage.update(_table, item_id, data)
                if item is None:
                    return JsonResponse({"error": "Not found"}, status=404)
                return JsonResponse(create_item_response(item, formatter))

            elif request.method == "DELETE" and "delete" in _schema.permissions:
                deleted = storage.delete(_table, item_id)
                if not deleted:
                    return JsonResponse({"error": "Not found"}, status=404)
                return JsonResponse({}, status=204)

            return JsonResponse({"error": "Method not allowed"}, status=405)

        patterns.append(path(f"{table}/<int:item_id>/", detail_view, name=f"{table}_detail"))

    return patterns
