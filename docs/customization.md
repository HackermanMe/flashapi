# Customization

[Back to main README](../README.md)

---

## Table of Contents

- [Model Wrapper](#model-wrapper)
  - [readonly](#readonly)
  - [exclude](#exclude)
  - [only](#only)
  - [plural](#plural)
  - [Combining options](#combining-options)
- [Custom Plural Names](#custom-plural-names)
- [Custom Response Format](#custom-response-format)
- [Custom Database Path](#custom-database-path)
- [Disable Documentation](#disable-documentation)
- [Model Support Details](#model-support-details)

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
GET /products/       ✓
GET /products/{id}/  ✓
POST /products/      ✗ (not generated)
PUT /products/{id}/  ✗ (not generated)
DELETE /products/{id}/ ✗ (not generated)
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
Model(Person, plural="people")             # /people/ instead of /persons/
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
// List
{"data": [...], "total": 42, "page": 1, "pages": 3, "page_size": 20}

// Single item
{"data": {"id": 1, "name": "..."}}
```

### Custom formatter function

```python
def my_formatter(data, meta):
    """
    data: the actual data (list or dict)
    meta: {"total": int, "page": int, "pages": int, "page_size": int} (only for lists)
    """
    if meta:  # List response
        return {
            "results": data,
            "count": meta["total"],
            "next_page": meta["page"] + 1 if meta["page"] < meta["pages"] else None,
            "previous_page": meta["page"] - 1 if meta["page"] > 1 else None,
        }
    else:  # Single item response
        return {"result": data}
```

### Using the formatter

```python
# FastAPI
FlashAPI(models=[User, Product], formatter=my_formatter)

# Django
generate_urls(models=[User, Product], formatter=my_formatter)

# Flask
register_models(app, models=[User, Product], formatter=my_formatter)
```

### DRF-style response format example

```python
def drf_style(data, meta):
    if meta:
        return {
            "count": meta["total"],
            "next": f"?page={meta['page']+1}" if meta["page"] < meta["pages"] else None,
            "previous": f"?page={meta['page']-1}" if meta["page"] > 1 else None,
            "results": data,
        }
    return data  # Single item returned as-is (no wrapper)
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

## Disable Documentation

```python
# FastAPI — disables /docs and /redoc
FlashAPI(models=[User, Product], docs=False)

# Django — does not generate /docs/ or /openapi.json routes
generate_urls(models=[User, Product], docs=False)
```

Useful for production if you don't want the API schema publicly accessible.

---

## Model Support Details

### Pydantic models

```python
from pydantic import BaseModel

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool = True    # Optional with default
    description: str = ""    # Optional with default
```

- `id` field is auto-added (auto-increment integer) — do NOT define it
- Default values make fields optional in POST requests
- Validation is handled by Pydantic at the model level

### dataclass models

```python
from dataclasses import dataclass

@dataclass
class Product:
    name: str
    price: float
    in_stock: bool = True
```

- Same behavior as Pydantic: auto `id`, SQLite storage

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
```

- Uses your SQLAlchemy engine

---

## Related Docs

- [Integration Guide](integration.md)
- [Features (CRUD, pagination, filtering, sorting, search)](features.md)
- [Relations (nested routes, expand)](relations.md)
- [Authentication & Permissions](authentication.md)
