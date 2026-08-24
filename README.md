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
| **[Authentication](docs/authentication.md)** | AuthBackend interface, access control, multi-tenancy, scope, full examples |
| **[Custom Logic](docs/custom-logic.md)** | How FlashAPI coexists with your business logic |
| **[Framework Notes](docs/framework-notes.md)** | Django, FastAPI, Flask specifics |
| **[Full Examples](docs/examples.md)** | E-commerce, school, restaurant, blog, SaaS, minimal todo |

---

## Installation

```bash
# x-release-please-start-version
pip install python-flashapi==0.3.0
# x-release-please-end

# With framework extras:
pip install python-flashapi[fastapi]   # or [flask] or [django] or [all]
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
GET    /api/                   → API Root (resource index)
GET    /api/products           → List (paginated, filterable, sortable, searchable)
POST   /api/products           → Create
GET    /api/products/{id}      → Read
PUT    /api/products/{id}      → Update
DELETE /api/products/{id}      → Delete (hard delete by default)
POST   /api/products/bulk      → Bulk create
GET    /api/products/export    → Export (CSV/XLSX/PDF)
GET    /api/dashboard          → Live dashboard
```

Add `soft_delete=True` for restore + soft delete, `audit=True` for history endpoint.

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

| Endpoint | Description | Condition |
|----------|-------------|-----------|
| `GET /api/` | API Root (resource index) | Always |
| `GET /api/{entities}` | Paginated list with filtering, sorting, search | Always |
| `POST /api/{entities}` | Create | Always |
| `GET /api/{entities}/{id}` | Read one | Always |
| `PUT /api/{entities}/{id}` | Update | Always |
| `DELETE /api/{entities}/{id}` | Delete | Always |
| `POST /api/{entities}/{id}/restore` | Restore deleted | `soft_delete=True` |
| `POST /api/{entities}/bulk` | Bulk create | Always |
| `GET /api/{entities}/export?format=csv` | Export (csv, xlsx, pdf) | Always |
| `GET /api/{entities}/{id}/history` | Audit trail | `audit=True` |
| `GET /api/dashboard` | Live metrics dashboard | Always |

Plus: `?expand=relation` to inline related objects, `?deleted=true` to view deleted items (when soft_delete enabled), auth+scope enforcement, and Swagger UI docs.

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
from flashapi import Model, AuthBackend

FlashAPI(
    models=[
        Product,                                           # Full CRUD, public
        Model(Order, exclude=["delete"]),                  # No delete
        Model(Config, readonly=True, access="admin"),      # GET only, admin
        Model(Log, only=["list"]),                         # List only
        Model(Animal, plural="animaux"),                   # Custom plural
        Model(Invoice, soft_delete=True, audit=True),      # Opt-in features
        Model(Eleve, access="staff", scope="tenant", tenant_field="ecole_id"),
    ],
    base_path="/api",       # Configurable prefix (default: /api)
    auth_backend=MyAuth(),  # Your AuthBackend implementation
    webhook_urls=["http://localhost:9090/hooks"],
    rate_limit=100,         # 100 requests per window
    rate_window=60,         # 60 seconds window
)
```

See [Customization docs](docs/customization.md) for all options.

---

## Authentication & Multi-Tenancy

FlashAPI does NOT handle login/tokens/OAuth. It consumes auth decisions from your existing stack via a simple `AuthBackend` interface:

```python
from flashapi import Model, AuthBackend

class MyAuth(AuthBackend):
    def authenticate(self, request):
        return request.user if request.user.is_authenticated else None
    def get_role(self, user):
        if user.is_superuser: return "admin"
        return "staff" if user.is_staff else "authenticated"
    def get_tenant_id(self, user):
        return user.organization_id

FlashAPI(
    models=[
        Model(Product, access="public"),
        Model(Order, access="authenticated", scope="owner", owner_field="user_id"),
        Model(Eleve, access="staff", scope="tenant", tenant_field="ecole_id"),
    ],
    auth_backend=MyAuth(),
)
```

**Features:**
- Per-model / per-operation access control (role hierarchy: public < authenticated < staff < admin)
- Multi-tenancy: automatic tenant/owner data isolation
- Automatic tenant_id injection on create
- Cross-tenant attempts return 404 (no information leakage)
- Admin bypasses all scopes
- Works identically on Django, Flask, FastAPI

See [Authentication docs](docs/authentication.md) for full examples (JWT, OAuth2 Google, API keys, SaaS, school management).

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
- **Auth-agnostic.** Plug in any auth stack (OAuth2, JWT, session, OTP, magic links). FlashAPI never handles login/crypto — it only consumes auth decisions.
- **Multi-tenant ready.** Built-in tenant/owner data isolation with zero custom code.
- **Framework-native.** Generates standard routes. No lock-in, no proprietary runtime.

---

## License

[Apache License 2.0](LICENSE)
