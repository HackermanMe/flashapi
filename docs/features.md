# Features

[Back to main README](../README.md)

---

## Table of Contents

- [Automatic CRUD](#automatic-crud)
- [Pagination](#pagination)
- [Filtering](#filtering)
- [Sorting](#sorting)
- [Full-Text Search](#full-text-search)
- [Combining Parameters](#combining-parameters)
- [Interactive Documentation](#interactive-documentation)

---

## Automatic CRUD

Every model you register gets 5 endpoints automatically:

| Method | URL | Description | HTTP Status |
|--------|-----|-------------|-------------|
| `GET` | `/{plural}/` | List all items (paginated) | 200 |
| `POST` | `/{plural}/` | Create a new item | 201 |
| `GET` | `/{plural}/{id}/` | Get one item by ID | 200 / 404 |
| `PUT` | `/{plural}/{id}/` | Update an item | 200 / 404 |
| `DELETE` | `/{plural}/{id}/` | Delete an item | 204 / 404 |

### Create (POST)

Send a JSON body with the fields. Auto-incremented primary keys (like `id = Column(Integer, primary_key=True)`) are excluded from the request body — FlashAPI generates them automatically.

**If your primary key is NOT auto-incremented** (e.g. `matricule = Column(String(20), primary_key=True)`), FlashAPI will include it in the request body because you need to provide it yourself.

```bash
curl -X POST http://localhost:8000/products/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "price": 999.99, "category_id": 1}'
```

Response (201):
```json
{
  "data": {
    "id": 1,
    "name": "Laptop",
    "price": 999.99,
    "category_id": 1
  }
}
```

### List (GET collection)

```bash
curl http://localhost:8000/products/
```

Response (200):
```json
{
  "data": [
    {"id": 1, "name": "Laptop", "price": 999.99, "category_id": 1},
    {"id": 2, "name": "Mouse", "price": 29.99, "category_id": 2}
  ],
  "total": 2,
  "page": 1,
  "pages": 1,
  "page_size": 20
}
```

### Read (GET by ID)

```bash
curl http://localhost:8000/products/1/
```

Response (200):
```json
{
  "data": {"id": 1, "name": "Laptop", "price": 999.99, "category_id": 1}
}
```

If not found (404):
```json
{"error": "Not found"}
```

### Update (PUT)

Send only the fields you want to update. Fields not included keep their current value.

```bash
curl -X PUT http://localhost:8000/products/1/ \
  -H "Content-Type: application/json" \
  -d '{"price": 899.99}'
```

Response (200):
```json
{
  "data": {"id": 1, "name": "Laptop", "price": 899.99, "category_id": 1}
}
```

### Delete (DELETE)

```bash
curl -X DELETE http://localhost:8000/products/1/
```

Response: 204 (empty body).

If not found: 404 `{"error": "Not found"}`.

---

## Pagination

All list endpoints return paginated results by default.

```
GET /products/?page=2&page_size=10
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | `1` | Page number (1-indexed) |
| `page_size` | `20` | Items per page |

Response includes metadata:
```json
{
  "data": [...],
  "total": 42,
  "page": 2,
  "pages": 5,
  "page_size": 10
}
```

- `total` — total number of items matching current filters
- `pages` — total number of pages
- If `page` exceeds `pages`, `data` is an empty array

---

## Filtering

Filter by exact field value using query parameters:

```
GET /products/?category_id=3
GET /products/?price=29.99
GET /products/?in_stock=true
GET /orders/?status=pending&customer_id=5
```

**Rules:**
- Field name must match a field in the model
- Values are exact match (not partial)
- Multiple filters = AND logic (all must match)
- Parameters that are not field names are ignored (like `page`, `sort`, `search`)

---

## Sorting

Sort results by any field. Use `-` prefix for descending:

```
GET /products/?sort=name          # Alphabetical A → Z
GET /products/?sort=-name         # Reverse Z → A
GET /products/?sort=-price        # Most expensive first
GET /products/?sort=created_at    # Oldest first
GET /products/?sort=-created_at   # Newest first
```

Only one sort field is supported at a time.

---

## Full-Text Search

Search across all text fields (STRING and TEXT types) simultaneously:

```
GET /products/?search=laptop
GET /customers/?search=dupont
GET /orders/?search=2024
```

**How it works:**
- Case-insensitive
- Partial match (contains)
- Searches ALL text fields in the model
- Non-text fields (integer, boolean, date) are skipped

---

## Combining Parameters

All features work together in a single request:

```
GET /products/?search=laptop&category_id=3&sort=-price&page=1&page_size=5
```

Execution order:
1. Filter by `category_id=3`
2. Search for "laptop" in text fields
3. Sort by price descending
4. Paginate: page 1, 5 items per page

---

## Interactive Documentation

FlashAPI serves Swagger UI automatically where you can test all endpoints in the browser:

| Framework | Swagger UI | OpenAPI JSON |
|-----------|------------|--------------|
| FastAPI | `/docs` | `/openapi.json` (built-in) |
| Django | `{prefix}/docs/` | `{prefix}/openapi.json` |
| Flask | `/docs` | `/openapi.json` |

Features of the Swagger UI:
- Try out any endpoint directly
- See request/response schemas
- See available parameters
- Grouped by model name

---

## Related Docs

- [Integration Guide](integration.md)
- [Relations (nested routes, expand)](relations.md)
- [Customization](customization.md)
- [Authentication & Permissions](authentication.md)
