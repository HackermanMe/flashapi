# Customization

[Back to main README](../README.md)

---

## Table of Contents

- [Base Path](#base-path)
- [Model Wrapper](#model-wrapper)
  - [readonly](#readonly)
  - [exclude](#exclude)
  - [only](#only)
  - [plural](#plural)
  - [Combining options](#combining-options)
- [Custom Plural Names](#custom-plural-names)
- [Custom Response Format](#custom-response-format)
- [Custom Database Path](#custom-database-path)
- [Feature Toggles](#feature-toggles)
- [Disable Documentation](#disable-documentation)
- [Model Support Details](#model-support-details)

---

## Base Path

All generated routes use a configurable base path. Default is `/api`.

```python
# Default: /api/products, /api/orders, ...
FlashAPI(models=[Product])

# Custom: /v2/products, /v2/orders, ...
FlashAPI(models=[Product], base_path="/v2")

# Another example
FlashAPI(models=[Product], base_path="/custom-prefix")
```

This mirrors Spring Boot's `flashapi.base-path` configuration. All routes (CRUD, bulk, export, dashboard) use this prefix.

---

## Model Wrapper

By default, every model gets full CRUD (list, read, create, update, delete). Use `Model()` to restrict or customize:

```python
from flashapi import Model
```

### readonly

Only allows GET operations (list + read). No create, update, or delete.

```python
Model(Product, readonly=True)
```

Generated endpoints:
```
GET /api/products       ✓
GET /api/products/{id}  ✓
POST /api/products      ✗ (not generated)
PUT /api/products/{id}  ✗ (not generated)
DELETE /api/products/{id} ✗ (not generated)
```

### exclude

Removes specific operations from the default full CRUD:

```python
Model(Order, exclude=["delete"])           # Everything except delete
Model(User, exclude=["delete", "update"])  # Read + create only
```

Available values: `"list"`, `"read"`, `"create"`, `"update"`, `"delete"`

### only

Keeps ONLY the listed operations:

```python
Model(Category, only=["list", "read"])     # Same as readonly
Model(Feedback, only=["create"])           # POST only (write-only)
Model(Log, only=["list"])                  # List only, no detail view
```

### plural

Override the auto-generated plural name used in the URL:

```python
Model(Person, plural="people")             # /api/people instead of /api/persons
Model(EmploiDuTemps, plural="emplois-du-temps")  # Custom French plural
Model(MatrixData, plural="matrix-data")    # Invariable
```

### Combining options

```python
Model(AuditLog, readonly=True, plural="audit-logs")
Model(Report, only=["list", "read"], plural="reports")
```

**Note:** `readonly=True` and `only=[...]` are mutually exclusive — use one or the other.

---

## Custom Plural Names

FlashAPI auto-pluralizes model names with rules for both English and French:

### Automatic rules

| Pattern | Rule | Example |
|---------|------|---------|
| Default | +s | book → books, user → users |
| -ss, -sh, -ch | +es | class → classes, dish → dishes |
| consonant + y | -ies | category → categories, city → cities |
| -eau, -au, -eu | +x | niveau → niveaux, jeu → jeux |
| -al | -aux | animal → animaux, journal → journaux |
| -s, -x, -z | invariable | temps → temps, voix → voix, nez → nez |

### Built-in irregulars

```
person → people       child → children      mouse → mice
man → men             woman → women         tooth → teeth
foot → feet           leaf → leaves         wolf → wolves
knife → knives        index → indices       datum → data
bus → buses           box → boxes           travail → travaux
journal → journaux    oeil → yeux
```

### Manual override

When automatic pluralization doesn't work for your case:

```python
Model(Sheep, plural="sheep")
Model(Analysis, plural="analyses")
Model(Curriculum, plural="curricula")
```

---

## Custom Response Format

### Default format

```json
// List response
{
  "data": [...],
  "meta": {
    "page": 0,
    "size": 20,
    "totalElements": 42,
    "totalPages": 3
  }
}

// Single item response
{"data": {"id": 1, "name": "..."}}

// Error response
{"error": "Not found", "status": 404}
```

### Custom formatter function

The formatter receives the full pre-built response object and can transform it:

```python
def my_formatter(response):
    """
    response: the full response dict (always contains "data", and "meta" for lists)
    """
    if "meta" in response:  # List response
        meta = response["meta"]
        return {
            "results": response["data"],
            "count": meta["totalElements"],
            "next_page": meta["page"] + 1 if meta["page"] < meta["totalPages"] - 1 else None,
        }
    else:  # Single item response
        return {"result": response["data"]}
```

### Using the formatter

```python
# FastAPI
FlashAPI(models=[User, Product], formatter=my_formatter)

# Flask
register_models(app, models=[User, Product], formatter=my_formatter)
```

### DRF-style response format example

```python
def drf_style(response):
    if "meta" in response:
        meta = response["meta"]
        return {
            "count": meta["totalElements"],
            "next": f"?page={meta['page']+1}" if meta["page"] < meta["totalPages"] - 1 else None,
            "previous": f"?page={meta['page']-1}" if meta["page"] > 0 else None,
            "results": response["data"],
        }
    return response["data"]  # Single item returned as-is (no wrapper)
```

---

## Custom Database Path

For **Pydantic** and **dataclass** models only. FlashAPI creates a SQLite database to store data.

```python
# Default: creates "flashapi.db" in current directory
FlashAPI(models=[User, Product])

# Custom path
FlashAPI(models=[User, Product], database="data/my_app.db")
FlashAPI(models=[User, Product], database="/tmp/test.db")
```

**This does NOT apply to:**
- Django models (they use your Django database configured in `settings.py`)
- SQLAlchemy models (they use your SQLAlchemy engine)

---

## Feature Toggles

All features are configurable via constructor parameters:

```python
FlashAPI(
    models=[Product, Order],
    base_path="/api",           # URL prefix (default: "/api")
    database="app.db",         # SQLite path (Pydantic/dataclass only)
    formatter=None,            # Custom response formatter
    audit=True,                # Audit trail (default: True)
    webhook_urls=[],           # Webhook target URLs (default: [])
    rate_limit=None,           # Requests per window (default: None = disabled)
    rate_window=60,            # Window in seconds (default: 60)
    docs=True,                 # Enable interactive docs (default: True)
)
```

| Feature | Enabled by | Disabled by |
|---------|-----------|-------------|
| Soft delete | Always on | — |
| Bulk create | Always on | — |
| Export | Always on | — |
| Dashboard | Always on | — |
| Audit trail | `audit=True` (default) | `audit=False` |
| Webhooks | `webhook_urls=["..."]` | Default (empty list) |
| Rate limiting | `rate_limit=100` | Default (None) |
| Interactive docs | `docs=True` (default) | `docs=False` |

---

## Disable Documentation

```python
# FastAPI — disables /docs and /redoc
FlashAPI(models=[User, Product], docs=False)
```

Useful for production if you don't want the API schema publicly accessible.

---

## Model Support Details

### Pydantic models

```python
from pydantic import BaseModel, Field

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool = True
    description: str = ""
    internal_code: str = Field(default="", json_schema_extra={"flash": {"hidden": True}})
```

- `id` field is auto-added (auto-increment integer) — do NOT define it in your Pydantic model
- Default values make fields optional in POST requests
- Validation is handled by Pydantic at the model level
- Field visibility controlled via `json_schema_extra={"flash": {...}}`

### dataclass models

```python
from dataclasses import dataclass, field

@dataclass
class Product:
    name: str
    price: float
    in_stock: bool = True
    secret: str = field(default="", metadata={"hidden": True})
```

- Same behavior as Pydantic: auto `id`, SQLite storage
- Field visibility controlled via `metadata={...}`

### Django models

```python
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to="products/", blank=True, null=True)
```

- Uses your existing Django database and migrations
- ForeignKey fields are exposed as `category_id` (the DB column name)
- ImageField/FileField serialized as string path or `null`
- Decimal serialized as float
- DateTime/Date/Time serialized as ISO 8601 strings

### SQLAlchemy models

```python
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    price = Column(Float)
    secret = Column(String, info={"hidden": True})
```

- Uses your SQLAlchemy engine
- Field visibility controlled via `Column(info={...})`

---

## Related Docs

- [Integration Guide](integration.md)
- [Features (all endpoints, pagination, soft delete, export, audit, etc.)](features.md)
- [Relations (nested routes, expand)](relations.md)
- [Authentication & Permissions](authentication.md)
