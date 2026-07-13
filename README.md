<p align="center">
  <img src="https://raw.githubusercontent.com/HackermanMe/flashapi/main/docs/logo.svg" alt="FlashAPI" width="400">
</p>

<p align="center">
  <strong>Define your models. FlashAPI does the rest.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/python-flashapi/"><img src="https://img.shields.io/pypi/v/python-flashapi?color=blue" alt="PyPI version"></a>
  <a href="https://github.com/HackermanMe/flashapi/actions/workflows/ci.yml"><img src="https://github.com/HackermanMe/flashapi/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/python-flashapi/"><img src="https://img.shields.io/pypi/pyversions/python-flashapi" alt="Python versions"></a>
  <a href="https://github.com/HackermanMe/flashapi/blob/master/LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue" alt="License"></a>
</p>

<p align="center">
  <a href="#installation">Installation</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="docs/integration.md">Docs</a> &bull;
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

FlashAPI generates a full REST API with CRUD, pagination, filtering, sorting, full-text search, relations, and interactive documentation from your existing models — in one line.

---

## Documentation

| Doc | Description |
|-----|-------------|
| **[Integration Guide](docs/integration.md)** | Where to put FlashAPI in your project, new vs existing project, all 3 frameworks |
| **[Features](docs/features.md)** | CRUD, pagination, filtering, sorting, search — detailed usage |
| **[Relations](docs/relations.md)** | Nested routes, expand, how relations are detected |
| **[Customization](docs/customization.md)** | Model wrapper, readonly, exclude, only, plural, response format, database |
| **[Authentication](docs/authentication.md)** | How to protect endpoints (Django middleware, FastAPI deps, Flask before_request) |
| **[Custom Logic](docs/custom-logic.md)** | How FlashAPI coexists with your business logic, when to use what |
| **[Framework Notes](docs/framework-notes.md)** | Django, FastAPI, Flask specifics (serialization, URLs, field behavior) |
| **[Full Examples](docs/examples.md)** | E-commerce, school, restaurant, blog, SaaS, minimal todo |

---

## Installation

```bash
pip install python-flashapi[fastapi]   # or python-flashapi[django] or python-flashapi[flask] or python-flashapi[all]
```

---

## Quick Start

### FastAPI (new project)

```python
# main.py
from pydantic import BaseModel
from flashapi.fastapi import FlashAPI

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool = True

app = FlashAPI(models=[Product]).app
```

```bash
uvicorn main:app --reload
# Open http://localhost:8000/docs
```

### FastAPI (existing project)

```python
# main.py — you already have app = FastAPI(...)
from fastapi import FastAPI
from flashapi.fastapi import FlashAPI
from models import Product, Order

app = FastAPI(title="My App")

# Your existing routes stay untouched
@app.get("/health")
async def health():
    return {"ok": True}

# Mount FlashAPI under /api
flash = FlashAPI(models=[Product, Order])
app.mount("/api", flash.app)
```

See [Integration Guide](docs/integration.md) for all patterns (Option A/B/C).

### Django

```python
# urls.py
from django.urls import path, include
from flashapi.django import generate_urls
from myapp.models import Product, Order, Customer

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(models=[Product, Order, Customer]))),
]
```

Open `http://localhost:8000/api/docs/` for Swagger UI.

### Flask

```python
# app.py
from flask import Flask
from flashapi.flask import register_models
from models import Product, Order

app = Flask(__name__)
register_models(app, models=[Product, Order])
```

Open `http://localhost:5000/docs` for Swagger UI.

---

## What you get

For every model, FlashAPI generates:

```
GET    /{plural}/           → List (paginated, filterable, sortable, searchable)
POST   /{plural}/           → Create
GET    /{plural}/{id}/      → Read
PUT    /{plural}/{id}/      → Update
DELETE /{plural}/{id}/      → Delete
GET    /{parent}/{id}/{children}/  → Nested list (auto-detected relations)
```

Plus: `?expand=relation` to inline related objects, and Swagger UI docs.

---

## Model support

| Type | Detection | Storage |
|------|-----------|---------|
| Django Model | `_meta` attribute | Django ORM (your DB) |
| SQLAlchemy | `__table__` attribute | Your SQLAlchemy engine |
| Pydantic | `model_fields` attribute | Auto SQLite |
| dataclass | `@dataclass` | Auto SQLite |

---

## Customization

```python
from flashapi import Model

FlashAPI(models=[
    Product,                               # Full CRUD
    Model(Order, exclude=["delete"]),      # No delete
    Model(Config, readonly=True),          # GET only
    Model(Log, only=["list"]),             # List only
    Model(Animal, plural="animaux"),       # Custom plural
])
```

See [Customization docs](docs/customization.md) for all options.

---

## Authentication

FlashAPI does NOT handle auth. You protect routes using your framework's standard mechanisms:

- **Django**: middleware ([example](docs/authentication.md#django-middleware))
- **FastAPI**: dependencies / middleware ([example](docs/authentication.md#fastapi-dependency-injection))
- **Flask**: `before_request` ([example](docs/authentication.md#flask-before_request))

See [Authentication docs](docs/authentication.md) for full examples including RBAC, JWT, API keys.

---

## Custom business logic

FlashAPI does not interfere with your project. Add custom endpoints alongside:

```python
# FlashAPI handles CRUD
flash = FlashAPI(models=[Product, Order])
app = flash.app

# You handle business logic
@app.post("/checkout")
async def checkout(request):
    # Payment, emails, inventory...
    return {"order_id": 42}
```

See [Custom Logic docs](docs/custom-logic.md) for patterns and decision guide.

---

## Philosophy

- **FlashAPI handles CRUD, you handle business logic.** No black magic, no monkey-patching.
- **Zero intrusion.** Does not modify your models, migrations, or existing code.
- **Composable.** Use it for 2 models or 20. Mix with custom endpoints freely.
- **No opinion on auth.** Your project, your rules.
- **Framework-native.** Generates standard routes. No lock-in, no proprietary runtime.

---

## License

[Apache License 2.0](LICENSE)
