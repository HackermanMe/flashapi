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

FlashAPI generates a full REST API with CRUD, pagination, filtering, sorting, full-text search, relations, soft delete, bulk operations, export, audit trail, webhooks, rate limiting, and a live dashboard — from your existing models, in one line.

Part of the **FlashAPI Ecosystem** — ensuring SDK client compatibility across all backends (Python, Java Spring, Node.js).

---

## Documentation

| Doc | Description |
|-----|-------------|
| **[Integration Guide](docs/integration.md)** | Where to put FlashAPI in your project, new vs existing project |
| **[Features](docs/features.md)** | CRUD, pagination, soft delete, bulk, export, audit, webhooks, rate limiting, dashboard |
| **[Relations](docs/relations.md)** | Nested routes, expand, how relations are detected |
| **[Customization](docs/customization.md)** | Base path, Model wrapper, response format, feature toggles |
| **[Authentication](docs/authentication.md)** | How to protect endpoints (Django middleware, FastAPI deps, Flask before_request) |
| **[Custom Logic](docs/custom-logic.md)** | How FlashAPI coexists with your business logic |
| **[Framework Notes](docs/framework-notes.md)** | Django, FastAPI, Flask specifics |
| **[Full Examples](docs/examples.md)** | E-commerce, school, restaurant, blog, SaaS, minimal todo |

---

## Installation

```bash
pip install python-flashapi[fastapi]   # or python-flashapi[flask] or python-flashapi[all]
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

That's it. You now have:

```
GET    /api/products           → List (paginated, filterable, sortable, searchable)
POST   /api/products           → Create
GET    /api/products/{id}      → Read
PUT    /api/products/{id}      → Update
DELETE /api/products/{id}      → Soft delete
POST   /api/products/{id}/restore  → Restore
POST   /api/products/bulk      → Bulk create
GET    /api/products/export    → Export (CSV/XLSX/PDF)
GET    /api/products/{id}/history  → Audit trail
GET    /api/dashboard          → Live dashboard
```

### FastAPI (existing project)

```python
from fastapi import FastAPI
from flashapi.fastapi import FlashAPI
from models import Product, Order

app = FastAPI(title="My App")

@app.get("/health")
async def health():
    return {"ok": True}

# Mount FlashAPI — all routes under /api by default
flash = FlashAPI(models=[Product, Order])
app.mount("/api", flash.app)
```

See [Integration Guide](docs/integration.md) for all patterns.

### Flask

```python
from flask import Flask
from flashapi.flask import register_models
from models import Product, Order

app = Flask(__name__)
register_models(app, models=[Product, Order])
```

---

## Response Format

All responses follow a consistent format:

```json
// List
{"data": [...], "meta": {"page": 0, "size": 20, "totalElements": 42, "totalPages": 3}}

// Single item
{"data": {"id": 1, "name": "Laptop", "price": 999.99}}

// Error
{"error": "Not found", "status": 404}
```

---

## What you get

For every model, FlashAPI generates:

| Endpoint | Description |
|----------|-------------|
| `GET /api/{entities}` | Paginated list with filtering, sorting, search |
| `POST /api/{entities}` | Create |
| `GET /api/{entities}/{id}` | Read one |
| `PUT /api/{entities}/{id}` | Update |
| `DELETE /api/{entities}/{id}` | Soft delete |
| `POST /api/{entities}/{id}/restore` | Restore deleted |
| `POST /api/{entities}/bulk` | Bulk create |
| `GET /api/{entities}/export?format=csv` | Export (csv, xlsx, pdf) |
| `GET /api/{entities}/{id}/history` | Audit trail |
| `GET /api/dashboard` | Live metrics dashboard |

Plus: `?expand=relation` to inline related objects, `?deleted=true` to view deleted items, and Swagger UI docs.

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

FlashAPI(
    models=[
        Product,                               # Full CRUD
        Model(Order, exclude=["delete"]),      # No delete
        Model(Config, readonly=True),          # GET only
        Model(Log, only=["list"]),             # List only
        Model(Animal, plural="animaux"),       # Custom plural
    ],
    base_path="/api",       # Configurable prefix (default: /api)
    audit=True,             # Audit trail
    webhook_urls=["http://localhost:9090/hooks"],
    rate_limit=100,         # 100 requests per window
    rate_window=60,         # 60 seconds window
)
```

See [Customization docs](docs/customization.md) for all options.

---

## Authentication

FlashAPI does NOT handle auth. You protect routes using your framework's standard mechanisms:

- **FastAPI**: dependencies / middleware ([example](docs/authentication.md#fastapi-dependency-injection))
- **Flask**: `before_request` ([example](docs/authentication.md#flask-before_request))
- **Django**: middleware ([example](docs/authentication.md#django-middleware))

See [Authentication docs](docs/authentication.md) for full examples including RBAC, JWT, API keys.

---

## Custom business logic

FlashAPI does not interfere with your project. Add custom endpoints alongside:

```python
flash = FlashAPI(models=[Product, Order])
app = flash.app

@app.post("/checkout")
async def checkout(request):
    # Payment, emails, inventory...
    return {"order_id": 42}
```

See [Custom Logic docs](docs/custom-logic.md) for patterns and decision guide.

---

## Philosophy

- **FlashAPI handles CRUD, you handle business logic.** No black magic, no monkey-patching.
- **Standardized.** One SDK client works seamlessly across backends.
- **Zero intrusion.** Does not modify your models, migrations, or existing code.
- **Composable.** Use it for 2 models or 20. Mix with custom endpoints freely.
- **No opinion on auth.** Your project, your rules.
- **Framework-native.** Generates standard routes. No lock-in, no proprietary runtime.

---

## License

[Apache License 2.0](LICENSE)
