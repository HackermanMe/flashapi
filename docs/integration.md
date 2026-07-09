# Integration Guide

[Back to main README](../README.md)

---

## Table of Contents

- [Where to put the FlashAPI line](#where-to-put-the-flashapi-line)
- [FastAPI Integration](#fastapi-integration)
  - [New project (no existing routes)](#fastapi--new-project)
  - [Existing project (you already have routes)](#fastapi--existing-project)
  - [Configuration options](#fastapi-configuration-options)
- [Django Integration](#django-integration)
  - [Setup](#django-setup)
  - [Configuration options](#django-configuration-options)
- [Flask Integration](#flask-integration)
  - [Setup](#flask-setup)
  - [Configuration options](#flask-configuration-options)

---

## Where to put the FlashAPI line

| Framework | File | What FlashAPI does |
|-----------|------|-------------------|
| **FastAPI** | `main.py` (your entry point) | Creates or mounts onto a FastAPI `app` instance |
| **Django** | `urls.py` | Returns URL patterns to `include()` |
| **Flask** | `app.py` (where you create Flask app) | Registers routes on your Flask app |

**Never in your `models.py` file.** Models define data structure, not routing.

---

## FastAPI Integration

### FastAPI — New project

FlashAPI creates the FastAPI app for you. Your `main.py` looks like this:

```python
# main.py
from pydantic import BaseModel
from flashapi.fastapi import FlashAPI

class User(BaseModel):
    name: str
    email: str

class Product(BaseModel):
    name: str
    price: float

app = FlashAPI(models=[User, Product]).app
```

Run:
```bash
uvicorn main:app --reload
```

That's it. Full CRUD + docs at `http://localhost:8000/docs`.

### FastAPI — Existing project

You already have `app = FastAPI(...)` and custom routes. Three options:

#### Option A — Mount FlashAPI under a prefix (recommended)

Your existing app stays untouched. FlashAPI CRUD lives under `/api/`:

```python
# main.py
from fastapi import FastAPI, Request
from flashapi.fastapi import FlashAPI
from models import User, Product, Order

# Your existing app — unchanged
app = FastAPI(title="My App", version="1.0.0")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/checkout")
async def checkout(request: Request):
    body = await request.json()
    # Your business logic
    return {"order_id": 42}

# Mount FlashAPI under /api
flash = FlashAPI(models=[User, Product, Order])
app.mount("/api", flash.app)
```

Result:
```
Your routes:     /health, /checkout (unchanged)
FlashAPI CRUD:   /api/users, /api/products, /api/orders
FlashAPI docs:   /api/docs
```

#### Option B — Add custom routes to FlashAPI's app

Use FlashAPI's app as your main app and add custom routes on top:

```python
# main.py
from fastapi import FastAPI, Request
from flashapi.fastapi import FlashAPI
from models import User, Product, Order

# FlashAPI creates the app
flash = FlashAPI(models=[User, Product, Order])
app = flash.app

# Add your custom routes on the same app
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/checkout")
async def checkout(request: Request):
    body = await request.json()
    return {"order_id": 42}
```

Result:
```
Everything at root: /users, /products, /orders, /health, /checkout, /docs
```

#### Option C — Replace FastAPI entirely

If your project is purely CRUD with no custom logic:

```python
# Before
app = FastAPI(title="My App", version="1.0.0")
# ... 200 lines of CRUD routes ...

# After — delete all those CRUD routes
app = FlashAPI(models=[User, Product, Order]).app
```

### FastAPI configuration options

```python
flash = FlashAPI(
    models=[...],             # Required: list of model classes or Model() wrappers
    database="myapp.db",      # SQLite path for Pydantic/dataclass (default: "flashapi.db")
    docs=True,                # Enable /docs and /redoc (default: True)
    formatter=my_formatter,   # Custom response format function (optional)
)
app = flash.app
```

---

## Django Integration

### Django setup

Always in `urls.py`:

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

FlashAPI just returns a list of URL patterns. You `include()` them wherever you want.

You can add custom views alongside:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(models=[Product, Order, Customer]))),

    # Your custom views
    path("api/cart/add/", add_to_cart_view),
    path("api/reports/daily/", daily_report_view),
]
```

### Django configuration options

```python
generate_urls(
    models=[...],             # Required: list of model classes or Model() wrappers
    docs=True,                # Enable /docs/ and /openapi.json (default: True)
    formatter=my_formatter,   # Custom response format function (optional)
)
```

**URLs generated:**
```
{prefix}/{plural}/                → list + create
{prefix}/{plural}/{id}/           → read + update + delete
{prefix}/{parent}/{id}/{child}/   → nested list (auto-detected relations)
{prefix}/docs/                    → Swagger UI
{prefix}/openapi.json             → OpenAPI spec
```

---

## Flask Integration

### Flask setup

In the file where you create your Flask app:

```python
# app.py
from flask import Flask
from flashapi.flask import register_models
from models import Product, Order, Customer

app = Flask(__name__)
register_models(app, models=[Product, Order, Customer])

# Your custom routes
@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    # Your logic
    ...
```

### Flask configuration options

```python
register_models(
    app,                      # Your Flask app instance
    models=[...],             # Required: list of model classes or Model() wrappers
    docs=True,                # Enable /docs and /openapi.json (default: True)
    formatter=my_formatter,   # Custom response format function (optional)
)
```

---

## Related Docs

- [Features (CRUD, pagination, filtering, sorting, search)](features.md)
- [Relations (nested routes, expand)](relations.md)
- [Customization (Model wrapper, response format)](customization.md)
- [Authentication & Permissions](authentication.md)
- [Custom Logic & Coexistence](custom-logic.md)
- [Framework-Specific Notes](framework-notes.md)
- [Full Examples](examples.md)
