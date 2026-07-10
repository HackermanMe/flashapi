"""Decorator and registry for custom routes appearing in FlashAPI's Swagger docs.

Usage — place @api_doc on your view:

    @api_doc(tag="Orders", summary="Checkout", body={"cart_id": "int"})
    def checkout(request):
        ...

FlashAPI auto-discovers these views and adds them to the OpenAPI spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TYPE_MAP = {
    "string": {"type": "string"},
    "str": {"type": "string"},
    "integer": {"type": "integer"},
    "int": {"type": "integer"},
    "number": {"type": "number"},
    "float": {"type": "number"},
    "boolean": {"type": "boolean"},
    "bool": {"type": "boolean"},
    "array": {"type": "array", "items": {"type": "string"}},
    "list": {"type": "array", "items": {"type": "string"}},
    "object": {"type": "object"},
    "dict": {"type": "object"},
}


def api_doc(
    *,
    tag: str = "Custom",
    summary: str = "",
    methods: list[str] | None = None,
    body: dict[str, str] | None = None,
    body_required: list[str] | None = None,
    params: dict[str, str] | None = None,
    response: dict[str, Any] | None = None,
):
    """Decorator that marks a view for inclusion in FlashAPI's Swagger docs.

    Args:
        tag: Group name in Swagger UI.
        summary: One-line description of the endpoint.
        methods: HTTP methods (auto-detected if not specified).
        body: Request body fields as {name: type}. Types: str, int, float, bool, array, object.
        body_required: List of required field names in body.
        params: Query parameters as {name: type}.
        response: Response schema (raw OpenAPI schema dict).
    """
    def decorator(func):
        func._flashapi_doc = {
            "tag": tag,
            "summary": summary,
            "methods": [m.lower() for m in methods] if methods else None,
            "body": body,
            "body_required": body_required or [],
            "params": params,
            "response": response,
        }
        return func
    return decorator


def _extract_doc_from_view(view_func) -> dict | None:
    """Extract _flashapi_doc metadata from a view function (unwrapping decorators)."""
    func = view_func
    # Unwrap csrf_exempt and other decorators
    while func is not None:
        if hasattr(func, "_flashapi_doc"):
            return func._flashapi_doc
        func = getattr(func, "__wrapped__", None)
    return None


def _build_openapi_operation(doc: dict, method: str) -> dict[str, Any]:
    """Build an OpenAPI operation from @api_doc metadata."""
    operation: dict[str, Any] = {
        "tags": [doc["tag"]],
        "summary": doc["summary"] or f"{method.upper()} endpoint",
        "responses": {
            "200": {"description": "Success"}
        },
    }

    if doc.get("response"):
        operation["responses"]["200"]["content"] = {
            "application/json": {"schema": doc["response"]}
        }

    if doc.get("params"):
        operation["parameters"] = []
        for name, ptype in doc["params"].items():
            operation["parameters"].append({
                "name": name,
                "in": "query",
                "required": False,
                "schema": TYPE_MAP.get(ptype, {"type": "string"}),
            })

    if doc.get("body") and method in ("post", "put", "patch"):
        properties = {}
        for fname, ftype in doc["body"].items():
            properties[fname] = TYPE_MAP.get(ftype, {"type": "string"})
        body_schema: dict[str, Any] = {"type": "object", "properties": properties}
        if doc.get("body_required"):
            body_schema["required"] = doc["body_required"]
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": body_schema}},
        }

    return operation


def discover_django_views(url_patterns, trailing_slash: bool = True) -> dict[str, dict]:
    """Scan Django URL patterns for @api_doc-decorated views and build OpenAPI paths."""
    paths: dict[str, dict] = {}

    for pattern in url_patterns:
        callback = getattr(pattern, "callback", None)
        if callback is None:
            continue

        doc = _extract_doc_from_view(callback)
        if doc is None:
            continue

        # Build path from Django pattern
        path_str = "/" + str(pattern.pattern)
        if trailing_slash and not path_str.endswith("/"):
            path_str += "/"

        # Determine methods
        methods = doc["methods"]
        if not methods:
            methods = ["get"]

        if path_str not in paths:
            paths[path_str] = {}

        for method in methods:
            paths[path_str][method] = _build_openapi_operation(doc, method)

    return paths


def discover_flask_views(app) -> dict[str, dict]:
    """Scan a Flask app for @api_doc-decorated views and build OpenAPI paths."""
    paths: dict[str, dict] = {}

    for rule in app.url_map.iter_rules():
        view_func = app.view_functions.get(rule.endpoint)
        if view_func is None:
            continue

        doc = _extract_doc_from_view(view_func)
        if doc is None:
            continue

        # Convert Flask rule to OpenAPI path: /items/<int:item_id> → /items/{item_id}
        path_str = rule.rule
        import re
        path_str = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", path_str)

        # Determine methods
        methods = doc["methods"]
        if not methods:
            rule_methods = [m.lower() for m in rule.methods if m not in ("HEAD", "OPTIONS")]
            methods = rule_methods or ["get"]

        if path_str not in paths:
            paths[path_str] = {}

        for method in methods:
            paths[path_str][method] = _build_openapi_operation(doc, method)

    return paths


# Keep backward compat with CustomRoute for users who prefer explicit declaration
@dataclass
class RouteParam:
    name: str
    location: str = "query"
    type: str = "string"
    required: bool = False
    description: str = ""


@dataclass
class RouteBody:
    fields: dict[str, str] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)


@dataclass
class CustomRoute:
    path: str
    method: str = "get"
    summary: str = ""
    tag: str = "Custom"
    parameters: list[RouteParam] = field(default_factory=list)
    body: RouteBody | None = None
    response_description: str = "Success"
    response_schema: dict[str, Any] | None = None


def custom_routes_to_openapi_paths(routes: list[CustomRoute], trailing_slash: bool = False) -> dict:
    """Convert a list of CustomRoute to OpenAPI path entries."""
    paths: dict[str, dict] = {}
    suffix = "/" if trailing_slash else ""

    for route in routes:
        path_key = route.path.rstrip("/") + suffix if trailing_slash else route.path
        if path_key not in paths:
            paths[path_key] = {}

        operation: dict[str, Any] = {
            "tags": [route.tag],
            "summary": route.summary or f"{route.method.upper()} {route.path}",
            "responses": {
                "200": {"description": route.response_description}
            },
        }

        if route.response_schema:
            operation["responses"]["200"]["content"] = {
                "application/json": {"schema": route.response_schema}
            }

        if route.parameters:
            operation["parameters"] = []
            for param in route.parameters:
                operation["parameters"].append({
                    "name": param.name,
                    "in": param.location,
                    "required": param.required,
                    "description": param.description,
                    "schema": TYPE_MAP.get(param.type, {"type": "string"}),
                })

        if route.body:
            properties = {}
            for fname, ftype in route.body.fields.items():
                properties[fname] = TYPE_MAP.get(ftype, {"type": "string"})
            body_schema: dict[str, Any] = {"type": "object", "properties": properties}
            if route.body.required_fields:
                body_schema["required"] = route.body.required_fields
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": body_schema}},
            }

        paths[path_key][route.method.lower()] = operation

    return paths
