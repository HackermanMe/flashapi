# Features

[Back to main README](../README.md)

---

## Table of Contents

- [Automatic CRUD](#automatic-crud)
- [Pagination](#pagination)
- [Filtering](#filtering)
- [Sorting](#sorting)
- [Full-Text Search](#full-text-search)
- [Soft Delete & Restore](#soft-delete--restore)
- [Bulk Operations](#bulk-operations)
- [Export](#export)
- [Audit Trail](#audit-trail)
- [Webhooks](#webhooks)
- [Rate Limiting](#rate-limiting)
- [Dashboard](#dashboard)
- [Field Visibility](#field-visibility)
- [Combining Parameters](#combining-parameters)
- [Interactive Documentation](#interactive-documentation)

---

## Automatic CRUD

Every model you register gets endpoints automatically under `/api/`:

| Method | URL | Description | HTTP Status |
|--------|-----|-------------|-------------|
| `GET` | `/api/{entities}` | List all items (paginated) | 200 |
| `POST` | `/api/{entities}` | Create a new item | 201 |
| `GET` | `/api/{entities}/{id}` | Get one item by ID | 200 / 404 |
| `PUT` | `/api/{entities}/{id}` | Update an item | 200 / 404 |
| `DELETE` | `/api/{entities}/{id}` | Soft delete an item | 204 / 404 |
| `POST` | `/api/{entities}/{id}/restore` | Restore a soft-deleted item | 204 / 404 |
| `POST` | `/api/{entities}/bulk` | Bulk create | 201 |
| `GET` | `/api/{entities}/export` | Export data | 200 |
| `GET` | `/api/{entities}/{id}/history` | Audit trail | 200 |

The base path (`/api`) is configurable:

```python
FlashAPI(models=[Product], base_path="/v2")
```

### Create (POST)

```bash
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "price": 999.99}'
```

Response (201):
```json
{
  "data": {
    "id": 1,
    "name": "Laptop",
    "price": 999.99
  }
}
```

### List (GET collection)

```bash
curl http://localhost:8000/api/products
```

Response (200):
```json
{
  "data": [
    {"id": 1, "name": "Laptop", "price": 999.99},
    {"id": 2, "name": "Mouse", "price": 29.99}
  ],
  "meta": {
    "page": 0,
    "size": 20,
    "totalElements": 2,
    "totalPages": 1
  }
}
```

### Read (GET by ID)

```bash
curl http://localhost:8000/api/products/1
```

Response (200):
```json
{
  "data": {"id": 1, "name": "Laptop", "price": 999.99}
}
```

### Error Response

All errors follow the same format:
```json
{"error": "Not found", "status": 404}
```

### Delete (DELETE)

Delete performs a **soft delete** by default. The item is hidden from list queries but can be restored.

```bash
curl -X DELETE http://localhost:8000/api/products/1
```

Response: 204 (empty body).

---

## Pagination

All list endpoints return paginated results. **Pages are 0-indexed.**

```
GET /api/products?page=1&size=10
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | `0` | Page number (0-indexed) |
| `size` | `20` | Items per page (max 100) |

Response metadata:
```json
{
  "data": [...],
  "meta": {
    "page": 1,
    "size": 10,
    "totalElements": 42,
    "totalPages": 5
  }
}
```

---

## Filtering

Filter by exact field value:

```
GET /api/products?category_id=3
GET /api/orders?status=pending&customer_id=5
```

Multiple filters = AND logic.

---

## Sorting

Sort by field name. Use `field,asc` or `field,desc`:

```
GET /api/products?sort=name,asc
GET /api/products?sort=price,desc
```

Or simply `?sort=name` for ascending, `?sort=-name` for descending.

---

## Full-Text Search

Search across all text fields:

```
GET /api/products?search=laptop
```

Case-insensitive partial match across all string/text fields.

---

## Soft Delete & Restore

DELETE performs a soft delete. Items are hidden by default but can be viewed and restored.

```bash
# Soft delete
DELETE /api/products/1   → 204

# View deleted items only
GET /api/products?deleted=true

# Restore
POST /api/products/1/restore   → 204
```

---

## Bulk Operations

Create multiple items in one request:

```bash
POST /api/products/bulk
Content-Type: application/json

[{"name": "A", "price": 10}, {"name": "B", "price": 20}]
```

Response (201):
```json
{
  "data": [{"id": 1, "name": "A", "price": 10}, {"id": 2, "name": "B", "price": 20}],
  "meta": {"total": 2, "succeeded": 2, "failed": 0}
}
```

---

## Export

Export all items in CSV, XLSX, or PDF format:

```
GET /api/products/export?format=csv
GET /api/products/export?format=xlsx
GET /api/products/export?format=pdf
```

Returns binary file with `Content-Disposition: attachment` header.

XLSX requires `openpyxl`. PDF requires `reportlab`.

---

## Audit Trail

Every create, update, and delete is logged. View the history of any entity:

```
GET /api/products/1/history
```

Response:
```json
{
  "data": [
    {
      "action": "CREATE",
      "entityType": "Product",
      "entityId": "1",
      "timestamp": "2026-07-21T10:00:00+00:00",
      "performedBy": "",
      "changes": null
    },
    {
      "action": "UPDATE",
      "entityType": "Product",
      "entityId": "1",
      "timestamp": "2026-07-21T11:00:00+00:00",
      "performedBy": "",
      "changes": {"price": {"from": 999.99, "to": 899.99}}
    }
  ]
}
```

Enable/disable:
```python
FlashAPI(models=[Product], audit=True)   # default
FlashAPI(models=[Product], audit=False)  # disable
```

---

## Webhooks

Send HTTP POST notifications to external URLs on every CRUD event:

```python
FlashAPI(models=[Product], webhook_urls=["http://localhost:9090/webhooks"])
```

Webhook payload:
```json
{
  "event": "CREATE",
  "entity": "Product",
  "entityId": "1",
  "data": {"id": 1, "name": "Laptop", "price": 999.99},
  "timestamp": "2026-07-21T10:00:00+00:00"
}
```

Headers:
- `X-FlashAPI-Event`: CREATE, UPDATE, or DELETE
- `X-FlashAPI-Entity`: Entity name

Features:
- Asynchronous delivery (does not block the API response)
- Exponential backoff retry (3 attempts)

---

## Rate Limiting

Limit requests per IP with a sliding window:

```python
FlashAPI(models=[Product], rate_limit=100, rate_window=60)  # 100 req/min
```

Every response includes headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 45
```

When exceeded (429):
```json
{"error": "Rate limit exceeded", "status": 429, "retryAfter": 45}
```

---

## Dashboard

A live HTML dashboard + JSON metrics endpoint:

```
GET /api/dashboard           → HTML (auto-refresh 5s)
GET /api/dashboard/metrics.json  → JSON metrics
```

Auto-discovers all registered entities and shows:
- Operations per entity (CREATE, READ, UPDATE, DELETE counts)
- Total operations
- Webhook health (sent/failed/retries)
- Recent events feed

---

## Field Visibility

Control which fields appear in responses, inputs, and exports:

### Pydantic

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    name: str
    email: str
    password: str = Field(json_schema_extra={"flash": {"writeonly": True}})
    created_at: str = Field(default="", json_schema_extra={"flash": {"readonly": True}})
    internal: str = Field(default="", json_schema_extra={"flash": {"hidden": True}})
    ssn: str = Field(default="", json_schema_extra={"flash": {"export_exclude": True}})
```

### SQLAlchemy

```python
password = Column(String, info={"writeonly": True})
created_at = Column(DateTime, info={"readonly": True})
```

### dataclass

```python
from dataclasses import dataclass, field

@dataclass
class User:
    name: str
    password: str = field(metadata={"writeonly": True})
```

### Rules

| Option | In Response | In Create/Update | In Export |
|--------|-------------|------------------|-----------|
| (none) | Yes | Yes | Yes |
| `readonly=True` | Yes | No | Yes |
| `writeonly=True` | No | Yes | No |
| `hidden=True` | No | No | No |
| `export_exclude=True` | Yes | Yes | No |

---

## Combining Parameters

All features work together:

```
GET /api/products?search=laptop&category_id=3&sort=price,desc&page=0&size=5
```

---

## Interactive Documentation

| Framework | Swagger UI | OpenAPI JSON |
|-----------|------------|--------------|
| FastAPI | `/docs` | `/openapi.json` (built-in) |
| Flask | `/api/docs` | `/api/openapi.json` |

---

## Related Docs

- [Integration Guide](integration.md)
- [Relations (nested routes, expand)](relations.md)
- [Customization](customization.md)
- [Authentication & Permissions](authentication.md)
