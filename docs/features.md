# Features

[Back to main README](../README.md)

---

## Table of Contents

- [API Root](#api-root)
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
- [Relation Type Inference](#relation-type-inference)
- [Combining Parameters](#combining-parameters)
- [Interactive Documentation](#interactive-documentation)

---

## API Root

FlashAPI generates a JSON index at the base path (`/api/` by default) listing all registered resources with their URLs:

```bash
curl http://localhost:8000/api/
```

Response (200):
```json
{
  "name": "FlashAPI",
  "version": "0.1.0",
  "resources": {
    "products": "/api/products",
    "orders": "/api/orders",
    "categories": "/api/categories"
  },
  "links": {
    "docs": "/api/docs",
    "openapi": "/api/openapi.json",
    "dashboard": "/api/dashboard"
  }
}
```

This gives a discoverable entry point — any client can `GET /api/` and know what's available.

---

## Automatic CRUD

Every model you register gets endpoints automatically under `/api/`:

| Method | URL | Description | HTTP Status | Condition |
|--------|-----|-------------|-------------|-----------|
| `GET` | `/api/` | API Root (resource index) | 200 | Always |
| `GET` | `/api/{entities}` | List all items (paginated) | 200 | Always |
| `POST` | `/api/{entities}` | Create a new item | 201 | Always |
| `GET` | `/api/{entities}/{id}` | Get one item by ID | 200 / 404 | Always |
| `PUT` | `/api/{entities}/{id}` | Update an item | 200 / 404 | Always |
| `DELETE` | `/api/{entities}/{id}` | Delete an item | 204 / 404 | Always |
| `POST` | `/api/{entities}/{id}/restore` | Restore a soft-deleted item | 204 / 404 | `soft_delete=True` |
| `POST` | `/api/{entities}/bulk` | Bulk create | 201 | Always |
| `GET` | `/api/{entities}/export` | Export data | 200 | Always |
| `GET` | `/api/{entities}/{id}/history` | Audit trail | 200 | `audit=True` |

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

Delete behavior depends on the model's `soft_delete` option:
- `soft_delete=True` → marks as deleted, hidden from list queries, can be restored
- `soft_delete=False` (default) → permanent removal from the database

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

Sort by field name. Format: `field,asc` or `field,desc`:

```
GET /api/products?sort=name,asc
GET /api/products?sort=price,desc
GET /api/products?sort=name        ← defaults to ascending
```

---

## Full-Text Search

Search across all text fields:

```
GET /api/products?search=laptop
```

Case-insensitive partial match across all string/text fields.

---

## Soft Delete & Restore

Soft delete is **opt-in** (disabled by default). When enabled, DELETE hides items from list queries instead of removing them. They can be viewed and restored.

```bash
# Soft delete (when enabled)
DELETE /api/products/1   → 204

# View deleted items only
GET /api/products?deleted=true

# Restore
POST /api/products/1/restore   → 204
```

### Configuration

```python
from flashapi import Model

# Per-entity
Model(Product, soft_delete=True)      # Soft delete enabled
Model(LogEntry, soft_delete=False)    # Hard delete (default)
```

### Behavior

| `soft_delete` | DELETE action | Restore available | `?deleted=true` |
|---|---|---|---|
| `True` | Marks as deleted, hidden from list | Yes | Shows deleted items |
| `False` (default) | Permanent removal from database | No | No effect |

### Django / SQLAlchemy: the `deleted_at` field

For Django and SQLAlchemy models, soft delete requires a **`deleted_at` field** on your model:

```python
# Django
class Eleve(models.Model):
    nom = models.CharField(max_length=100)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Required for soft delete
```

```python
# SQLAlchemy
class Eleve(Base):
    __tablename__ = "eleves"
    id = Column(Integer, primary_key=True)
    nom = Column(String(100))
    classe_id = Column(Integer, ForeignKey("classes.id"))
    deleted_at = Column(DateTime, nullable=True)  # Required for soft delete
```

**If `soft_delete=True` but the model has no `deleted_at` field**, FlashAPI raises a `FlashAPIConfigError` at startup with a clear message indicating which field to add. The server will not start until the model is corrected — this prevents silent data loss.

```
flashapi.core.schema.FlashAPIConfigError: Model "Eleve" has soft_delete=True but no 'deleted_at' field. Add:
    deleted_at = models.DateTimeField(null=True, blank=True)
```

For Pydantic/dataclass models (auto storage), FlashAPI manages the `deleted_at` column internally — you don't need to declare it.

### Cascade and soft delete

Soft delete sets `deleted_at = now()` — it does NOT trigger `on_delete=CASCADE`:

| Action | CASCADE triggered? | Explanation |
|--------|-------------------|-------------|
| Soft delete a `Classe` | **No** | The row still exists, just hidden. FK intact. |
| Hard delete a `Classe` | **Yes** | Real SQL DELETE → Django/SQLAlchemy cascades to children |
| Delete via Django Admin | **Yes** | Admin does `.delete()` (hard delete) |

**Consequences:**
- Soft-deleting a `Classe` does NOT soft-delete its `Eleves` — they remain visible
- If you hard-delete a `Classe` (via admin or `soft_delete=False`), all `Eleves` with `on_delete=CASCADE` are permanently removed — even those that were soft-deleted
- FlashAPI does NOT cascade soft deletes. If you need that, implement it in signals/hooks

**Recommendation:** if a parent uses `soft_delete=True`, protect children from accidental cascade:

```python
class Eleve(models.Model):
    classe = models.ForeignKey(Classe, on_delete=models.PROTECT)  # Prevents accidental cascade
    deleted_at = models.DateTimeField(null=True, blank=True)
```

Or use `SET_NULL` if the child can exist without a parent:

```python
class Eleve(models.Model):
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
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

### Sélectionner les champs

Le paramètre `fields` permet de choisir quels champs exporter (séparés par des virgules) :

```
GET /api/enseignants/export?format=xlsx&fields=nom,prenom,email,telephone
```

Si `fields` est omis, tous les champs exportables sont inclus. Si aucun des champs demandés n'est valide, une erreur 400 est retournée avec la liste des champs disponibles.

### Formats

| Format | Content-Type | Dépendance | Notes |
|--------|-------------|------------|-------|
| `csv` | `text/csv` | Aucune | UTF-8 BOM + séparateur `;` (compatible Excel) |
| `xlsx` | `application/vnd.openxmlformats...` | `pip install openpyxl` | Auto-width, header stylé, filtre auto |
| `pdf` | `application/pdf` | `pip install reportlab` | Paysage, tableau paginé, lignes alternées |

Returns binary file with `Content-Disposition: attachment` header.

Si la dépendance n'est pas installée, FlashAPI retourne une **400** avec le message d'installation (pas une 500).

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

### Configuration

Audit is **opt-in** (disabled by default). Enable it per-entity:

**FastAPI:**
```python
from flashapi import Model

FlashAPI(models=[
    Product,                          # no audit (default)
    Model(Invoice, audit=True),       # full audit trail
])
```

**Flask:**
```python
from flashapi import Model
from flashapi.flask import register_models

register_models(app, models=[
    Product,                          # no audit (default)
    Model(Invoice, audit=True),       # full audit trail
], engine=db.engine)
```

**Django:**
```python
from flashapi import Model
from flashapi.django import generate_urls

urlpatterns = [
    path("api/", include(generate_urls(models=[
        Product,                          # no audit (default)
        Model(Invoice, audit=True),       # full audit trail
    ]))),
]
```

---

## Webhooks

Send HTTP POST notifications to external URLs on every CRUD event.

### Configuration

**FastAPI:**
```python
app = FlashAPI(
    models=[Product],
    webhook_urls=["https://hooks.example.com/flashapi"],
).app
```

**Flask:**
```python
register_models(
    app,
    models=[Product],
    engine=db.engine,
    webhook_urls=["https://hooks.example.com/flashapi"],
)
```

**Django:**
```python
urlpatterns = [
    path("api/", include(generate_urls(
        models=[Product],
        webhook_urls=["https://hooks.example.com/flashapi"],
    ))),
]
```

### Payload

```json
{
  "event": "CREATE",
  "entity": "Product",
  "entityId": "1",
  "data": {"id": 1, "name": "Laptop", "price": 999.99},
  "timestamp": "2026-07-21T10:00:00+00:00"
}
```

### Headers

| Header | Example |
|--------|---------|
| `X-FlashAPI-Event` | `CREATE`, `UPDATE`, `DELETE` |
| `X-FlashAPI-Entity` | `Product` |

### Behavior

- Asynchronous delivery (non-blocking)
- Exponential backoff retry (3 attempts: 1s, 2s, 4s)
- Multiple URLs supported (all receive every event)

---

## Rate Limiting

Limit requests per IP with a sliding window.

### Configuration

**FastAPI:**
```python
app = FlashAPI(
    models=[Product],
    rate_limit=100,       # 100 requests max
    rate_window=60,       # per 60 seconds
).app
```

**Flask:**
```python
register_models(
    app,
    models=[Product],
    engine=db.engine,
    rate_limit=100,
    rate_window=60,
)
```

**Django:**

```python
# urls.py
urlpatterns = [
    path("api/", include(generate_urls(
        models=[Product],
        rate_limit=100,
        rate_window=60,
    ))),
]
```

```python
# settings.py — add the middleware
MIDDLEWARE = [
    "flashapi.adapters.django.FlashAPIRateLimitMiddleware",
    # ... other middleware
]
```

### Response headers (every response)

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 45
```

### When exceeded (429)

```json
{"error": "Rate limit exceeded", "status": 429, "retryAfter": 45}
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rate_limit` | `None` (disabled) | Max requests per window |
| `rate_window` | `60` | Window duration in seconds |

---

## Dashboard

A live HTML dashboard + JSON metrics endpoint. Auto-enabled for all frameworks.

### Endpoints

| Framework | HTML Dashboard | JSON Metrics |
|-----------|---------------|--------------|
| FastAPI | `GET /api/dashboard` | `GET /api/dashboard/metrics.json` |
| Flask | `GET /api/dashboard` | `GET /api/dashboard/metrics.json` |
| Django | `GET /api/dashboard/` | `GET /api/dashboard/metrics.json` |

### Features

- Auto-refresh every 5 seconds
- Operations per entity (CREATE, READ, UPDATE, DELETE counts)
- Webhook health (sent/failed/retries)
- Recent events feed
- Per-entity feature flags (soft delete, audit, webhook, rate limit)

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
| `auto="uuid"` | Yes | No (auto-generated) | Yes |
| `auto="datetime"` | Yes | No (auto-generated) | Yes |

---

## Auto-Generated Fields

Fields that are generated server-side on create (UUID tracking IDs, timestamps). They are:
- **Excluded** from the request body (POST/PUT)
- **Excluded** from Swagger/OpenAPI schemas
- **Present** in the response with their auto-generated value

### Pydantic

```python
from pydantic import BaseModel, Field

class Campagne(BaseModel):
    tracking_id: str = Field(default="", json_schema_extra={"flash": {"auto": "uuid"}})
    label: str
    date_debut: str
    date_fin: str
    created_at: str = Field(default="", json_schema_extra={"flash": {"auto": "datetime"}})
```

POST `/api/campagnes` body — only writable fields:
```json
{"label": "Summer Sale", "date_debut": "2026-06-01", "date_fin": "2026-08-31"}
```

Response — includes auto-generated fields:
```json
{
  "data": {
    "id": 1,
    "tracking_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "label": "Summer Sale",
    "date_debut": "2026-06-01",
    "date_fin": "2026-08-31",
    "created_at": "2026-07-23T10:00:00+00:00"
  }
}
```

Bulk create works the same — each item gets its own unique generated values.

### SQLAlchemy

Auto-detection: any column with a `default=callable` is automatically excluded from inputs:

```python
import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    tracking_id = Column(String, default=lambda: str(uuid.uuid4()), unique=True)
    created_at = Column(DateTime, default=func.now())
    label = Column(String, nullable=False)
```

No annotation needed — FlashAPI detects the callable default and handles it.

### Django

Auto-detection: fields with `auto_now_add=True`, `auto_now=True`, or `default=callable` are automatically excluded from inputs:

```python
import uuid
from django.db import models

class Bulletin(models.Model):
    tracking_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    trimestre = models.ForeignKey(Trimestre, on_delete=models.CASCADE)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rang = models.PositiveIntegerField(null=True, blank=True)
    appreciation = models.TextField(blank=True)
    date_generation = models.DateTimeField(auto_now_add=True)
```

POST body attendu (seuls les champs writable) :
```json
{"eleve_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "trimestre_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "moyenne_generale": 14.5, "rang": 3, "appreciation": "Bon travail"}
```

Champs exclus automatiquement de l'input :
- `tracking_id` — a un `default=uuid.uuid4` (callable) ET est `primary_key=True`
- `date_generation` — a `auto_now_add=True`

**Règle Django :** un champ est exclu de l'input si au moins une de ces conditions est vraie :
1. C'est un `AutoField` / `BigAutoField` (l'ID auto-incrémenté classique)
2. Il a `primary_key=True` **et** un `default=callable` (comme un UUID)
3. Il a `auto_now_add=True` (date de création)
4. Il a `auto_now=True` (date de mise à jour)
5. Il a un `default=callable` (ex: `default=uuid.uuid4`, `default=timezone.now`)

**Important :** pour qu'un `UUIDField` soit exclu, il doit avoir `default=uuid.uuid4` (ou un autre callable). Un UUID sans default ne sera pas auto-généré — c'est à vous de le fournir.

```python
# Auto-exclu (a un default callable + primary_key)
tracking_id = models.UUIDField(default=uuid.uuid4, primary_key=True)

# Auto-exclu (a un default callable, même sans être PK)
ref_code = models.UUIDField(default=uuid.uuid4, unique=True)

# PAS exclu (pas de default callable — vous devez le fournir)
external_id = models.UUIDField(unique=True)
```

### Supported auto types (Pydantic)

| Value | Generated value |
|-------|----------------|
| `"uuid"` | `uuid.uuid4()` as string |
| `"datetime"` | Current UTC datetime (ISO 8601) |
| `"date"` | Current UTC date (ISO 8601) |

---

## Relation Type Inference

FlashAPI infers the correct type for ForeignKey fields by inspecting the primary key of the target model. If the target uses a UUID primary key, the FK field is typed as `uuid` (string in OpenAPI), not integer.

### Django

```python
class Eleve(models.Model):
    tracking_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    nom = models.CharField(max_length=100)

class Bulletin(models.Model):
    tracking_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    trimestre = models.ForeignKey(Trimestre, on_delete=models.CASCADE)
```

Le champ `eleve_id` sera typé **uuid** (string, format uuid) dans Swagger, car la PK de `Eleve` est un `UUIDField`.

OpenAPI schema généré :
```json
{
  "eleve_id": {"type": "string", "format": "uuid"},
  "trimestre_id": {"type": "string", "format": "uuid"}
}
```

Si la PK cible est un `AutoField` / `BigAutoField` classique (entier auto-incrémenté), le FK sera typé **integer** comme attendu.

### SQLAlchemy

En SQLAlchemy, le type est directement lu depuis la colonne FK elle-même :

```python
from sqlalchemy.dialects.postgresql import UUID

class Eleve(Base):
    __tablename__ = "eleves"
    tracking_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class Bulletin(Base):
    __tablename__ = "bulletins"
    eleve_id = Column(UUID(as_uuid=True), ForeignKey("eleves.tracking_id"))
```

Le type `UUID` de la colonne `eleve_id` est détecté automatiquement — pas besoin de configuration supplémentaire.

### Résumé

| PK cible | Type FK dans Swagger |
|----------|---------------------|
| `AutoField` / `BigAutoField` | `integer` |
| `UUIDField` | `string` (format: uuid) |
| `CharField` | `string` |

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
