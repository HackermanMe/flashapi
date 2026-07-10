"""OpenAPI schema generation and Swagger UI for Flask and Django."""

from typing import Any

from flashapi.core.schema import ModelSchema, FieldType

FIELD_TYPE_TO_OPENAPI = {
    FieldType.STRING: {"type": "string"},
    FieldType.INTEGER: {"type": "integer"},
    FieldType.FLOAT: {"type": "number"},
    FieldType.BOOLEAN: {"type": "boolean"},
    FieldType.DATE: {"type": "string", "format": "date"},
    FieldType.DATETIME: {"type": "string", "format": "date-time"},
    FieldType.TIME: {"type": "string", "format": "time"},
    FieldType.UUID: {"type": "string", "format": "uuid"},
    FieldType.JSON: {"type": "object"},
    FieldType.TEXT: {"type": "string"},
    FieldType.BINARY: {"type": "string", "format": "binary"},
}

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>{title} - Docs</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
    SwaggerUIBundle({{
        url: "{openapi_url}",
        dom_id: '#swagger-ui',
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
    }})
    </script>
</body>
</html>"""


def generate_openapi_schema(
    schemas: list[ModelSchema],
    title: str = "FlashAPI",
    version: str = "0.1.0",
    description: str = "Define your models. FlashAPI does the rest.",
    trailing_slash: bool = False,
) -> dict[str, Any]:
    """Generate a full OpenAPI 3.1.0 schema from model schemas."""
    paths = {}
    components_schemas = {}

    for schema in schemas:
        components_schemas[schema.name] = _build_model_schema(schema)
        components_schemas[f"{schema.name}Create"] = _build_model_schema(schema, exclude_auto_pk=True)
        model_paths = _build_paths(schema, trailing_slash=trailing_slash)
        paths.update(model_paths)

    return {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": version,
            "description": description,
        },
        "paths": paths,
        "components": {
            "schemas": components_schemas,
        },
    }


def _build_model_schema(schema: ModelSchema, *, exclude_auto_pk: bool = False) -> dict:
    properties = {}
    required = []

    for field in schema.fields:
        if exclude_auto_pk and field.primary_key and field.auto_generated:
            continue
        prop = dict(FIELD_TYPE_TO_OPENAPI.get(field.type, {"type": "string"}))
        if field.constraints.get("max_length"):
            prop["maxLength"] = field.constraints["max_length"]
        if field.constraints.get("min_length"):
            prop["minLength"] = field.constraints["min_length"]
        if field.constraints.get("min_value") is not None:
            prop["minimum"] = field.constraints["min_value"]
        if field.constraints.get("max_value") is not None:
            prop["maximum"] = field.constraints["max_value"]
        properties[field.name] = prop
        if field.required and not field.primary_key:
            required.append(field.name)

    result = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _build_paths(schema: ModelSchema, trailing_slash: bool = False) -> dict:
    paths = {}
    table = schema.plural
    tag = schema.name
    suffix = "/" if trailing_slash else ""

    collection_ops = {}
    detail_ops = {}

    if "list" in schema.permissions:
        collection_ops["get"] = {
            "tags": [tag],
            "summary": f"List all {table}",
            "parameters": [
                {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                {"name": "page_size", "in": "query", "schema": {"type": "integer", "default": 20}},
                {"name": "sort", "in": "query", "schema": {"type": "string"}},
                {"name": "search", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "Paginated list",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "data": {"type": "array", "items": {"$ref": f"#/components/schemas/{schema.name}"}},
                            "total": {"type": "integer"},
                            "page": {"type": "integer"},
                            "pages": {"type": "integer"},
                            "page_size": {"type": "integer"},
                        }
                    }}}
                }
            }
        }

    if "create" in schema.permissions:
        collection_ops["post"] = {
            "tags": [tag],
            "summary": f"Create a {schema.name.lower()}",
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema.name}Create"}}}
            },
            "responses": {
                "201": {
                    "description": "Created",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"data": {"$ref": f"#/components/schemas/{schema.name}"}}
                    }}}
                }
            }
        }

    if "read" in schema.permissions:
        detail_ops["get"] = {
            "tags": [tag],
            "summary": f"Get a {schema.name.lower()} by ID",
            "parameters": [
                {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Item detail",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"data": {"$ref": f"#/components/schemas/{schema.name}"}}
                    }}}
                },
                "404": {"description": "Not found"}
            }
        }

    if "update" in schema.permissions:
        detail_ops["put"] = {
            "tags": [tag],
            "summary": f"Update a {schema.name.lower()}",
            "parameters": [
                {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{schema.name}Create"}}}
            },
            "responses": {
                "200": {
                    "description": "Updated",
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"data": {"$ref": f"#/components/schemas/{schema.name}"}}
                    }}}
                },
                "404": {"description": "Not found"}
            }
        }

    if "delete" in schema.permissions:
        detail_ops["delete"] = {
            "tags": [tag],
            "summary": f"Delete a {schema.name.lower()}",
            "parameters": [
                {"name": "item_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "204": {"description": "Deleted"},
                "404": {"description": "Not found"}
            }
        }

    if collection_ops:
        paths[f"/{table}{suffix}"] = collection_ops
    if detail_ops:
        paths[f"/{table}/{{item_id}}{suffix}"] = detail_ops

    return paths


def get_swagger_html(title: str = "FlashAPI", openapi_url: str = "/openapi.json") -> str:
    return SWAGGER_UI_HTML.format(title=title, openapi_url=openapi_url)
