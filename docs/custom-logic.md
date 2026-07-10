# Custom Logic & Coexistence

[Back to main README](../README.md)

---

## Table of Contents

- [Core Principle](#core-principle)
- [Custom routes in Swagger docs](#custom-routes-in-swagger-docs)
  - [FastAPI](#custom-routes-fastapi)
  - [Django](#custom-routes-django)
  - [Flask](#custom-routes-flask)
- [What FlashAPI does NOT do](#what-flashapi-does-not-do)
- [Adding custom endpoints (Django)](#adding-custom-endpoints-django)
- [Adding custom endpoints (FastAPI)](#adding-custom-endpoints-fastapi)
- [Adding custom endpoints (Flask)](#adding-custom-endpoints-flask)
- [When to use FlashAPI vs custom logic](#when-to-use-flashapi-vs-custom-logic)
- [Real-world patterns](#real-world-patterns)

---

## Core Principle

**FlashAPI generates additional routes. It does not modify, override, or interfere with anything else in your project.**

Think of FlashAPI like a colleague who writes all the boring CRUD code for you. Your existing code stays untouched. You can always add more routes alongside FlashAPI's generated routes.

---

## Custom routes in Swagger docs

Your custom endpoints appear **in the same Swagger documentation** as FlashAPI's auto-generated CRUD. Just add `@api_doc()` on your view — FlashAPI discovers them automatically. Like `drf-spectacular`, but simpler.

### Custom routes (FastAPI)

Use `@flash.get()`, `@flash.post()`, etc. — same as `@app.get()` but appears in Swagger:

```python
from fastapi import Request
from flashapi.fastapi import FlashAPI
from models import Base, Plat, Commande, Client

flash = FlashAPI(models=[Plat, Commande, Client], engine=engine)
app = flash.app

@flash.get("/stats/revenue", tag="Statistics", summary="Get total revenue")
async def revenue():
    return {"revenue": 42000, "currency": "EUR"}

@flash.post("/checkout", tag="Business Logic", summary="Process checkout")
async def checkout(request: Request):
    body = await request.json()
    return {"order_id": 1, "status": "confirmed"}

@flash.get("/reports/bestsellers", tag="Reports", summary="Top selling dishes")
async def bestsellers(limit: int = 10):
    return {"top": [...]}
```

### Custom routes (Django)

Just add `@api_doc()` on your views. FlashAPI auto-discovers them:

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from flashapi import api_doc
import json

@api_doc(tag="Commandes", summary="Passer une commande", methods=["post"],
         body={"client_id": "int", "table_id": "int", "plats": "array"},
         body_required=["client_id", "table_id", "plats"])
@csrf_exempt
def checkout(request):
    body = json.loads(request.body)
    # your business logic...
    return JsonResponse({"commande_id": 1, "statut": "en_preparation"}, status=201)

@api_doc(tag="Statistiques", summary="Chiffre d'affaires", params={"date": "string"})
def chiffre_affaires(request):
    jour = request.GET.get("date")
    # your logic...
    return JsonResponse({"date": jour, "chiffre_affaires": 15000})

@api_doc(tag="Rapports", summary="Plats les plus vendus", params={"limit": "int"})
def bestsellers(request):
    return JsonResponse({"top": [...]})
```

```python
# urls.py
from django.urls import path, include
from flashapi.django import generate_urls
from myapp.models import Plat, Commande, Client
from myapp import views

# Your custom URL patterns
custom_views = [
    path("checkout/", views.checkout),
    path("stats/chiffre-affaires/", views.chiffre_affaires),
    path("reports/bestsellers/", views.bestsellers),
]

urlpatterns = [
    path("api/", include(
        generate_urls(models=[Plat, Commande, Client], extra_views=custom_views)
        + custom_views
    )),
]
```

That's it. `@api_doc` on the view + pass `extra_views` to `generate_urls()`. FlashAPI reads the decorator metadata and adds your endpoints to Swagger — no duplicate declarations.

### Custom routes (Flask)

Same `@api_doc()` decorator — FlashAPI auto-discovers them from your Flask app:

```python
from flask import Flask, request, jsonify
from flashapi.flask import register_models
from flashapi import api_doc
from models import Plat, Commande, Client

app = Flask(__name__)
register_models(app, models=[Plat, Commande, Client])

@app.route("/checkout", methods=["POST"])
@api_doc(tag="Commandes", summary="Passer une commande",
         body={"client_id": "int", "table_id": "int", "plats": "array"},
         body_required=["client_id", "table_id"])
def checkout():
    body = request.get_json()
    return jsonify({"commande_id": 1}), 201

@app.route("/stats/revenue")
@api_doc(tag="Statistiques", summary="Chiffre d'affaires", params={"date": "string"})
def revenue():
    return jsonify({"revenue": 42000})
```

No extra configuration needed. FlashAPI scans the Flask app and finds all `@api_doc` views.

### @api_doc reference

```python
from flashapi import api_doc

@api_doc(
    tag="Business Logic",           # Group in Swagger UI
    summary="Process checkout",     # One-line description
    methods=["post"],               # HTTP methods (auto-detected if omitted)
    body={                          # Request body fields (for POST/PUT/PATCH)
        "client_id": "int",
        "table_id": "int",
        "notes": "string",
    },
    body_required=["client_id"],    # Required fields in body
    params={                        # Query parameters
        "limit": "int",
        "date": "string",
    },
    response={                      # Response schema (optional, raw OpenAPI)
        "type": "object",
        "properties": {"id": {"type": "integer"}}
    },
)
def my_view(request):
    ...
```

Available types for `body` and `params`: `str`, `int`, `float`, `bool`, `array`, `object`

---

## What FlashAPI does NOT do

| Action | Does FlashAPI do it? |
|--------|---------------------|
| Modify your model classes | No |
| Create or alter database migrations | No |
| Override existing routes | No |
| Monkey-patch your framework | No |
| Add middleware automatically | No |
| Create hidden database tables | No (except auto SQLite for Pydantic/dataclass) |
| Interfere with your ORM queries | No |
| Touch your existing views/controllers | No |

---

## Adding custom endpoints (Django)

```python
# urls.py
from django.urls import path, include
from flashapi.django import generate_urls
from myapp.models import Product, Cart, CartItem, Order, Customer
from myapp import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # === FlashAPI: automatic CRUD for all these models ===
    path("api/", include(generate_urls(
        models=[Product, Cart, CartItem, Order, Customer]
    ))),

    # === Your custom business logic endpoints ===
    path("api/cart/add/", views.add_to_cart),
    path("api/cart/remove/", views.remove_from_cart),
    path("api/cart/clear/", views.clear_cart),
    path("api/checkout/", views.checkout),
    path("api/checkout/confirm/", views.confirm_payment),
    path("api/reports/sales/", views.sales_report),
    path("api/reports/inventory/", views.inventory_report),
    path("api/webhooks/stripe/", views.stripe_webhook),
    path("api/notifications/send/", views.send_notification),
]
```

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def add_to_cart(request):
    """Custom logic: validate stock, apply discounts, update totals."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    body = json.loads(request.body)
    product_id = body["product_id"]
    quantity = body.get("quantity", 1)

    # Your business logic
    product = Product.objects.get(id=product_id)

    if product.stock < quantity:
        return JsonResponse({"error": "Insufficient stock"}, status=400)

    cart, _ = Cart.objects.get_or_create(user_id=request.user.id)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    item.quantity = item.quantity + quantity if not created else quantity
    item.save()

    # Update cart total
    cart.total = sum(i.product.price * i.quantity for i in cart.items.all())
    cart.save()

    return JsonResponse({
        "data": {
            "message": "Added to cart",
            "cart_total": float(cart.total),
            "items_count": cart.items.count(),
        }
    })


@csrf_exempt
def checkout(request):
    """Custom logic: create order, process payment, send email."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    cart = Cart.objects.get(user_id=request.user.id)

    if cart.items.count() == 0:
        return JsonResponse({"error": "Cart is empty"}, status=400)

    # Create order
    order = Order.objects.create(
        customer_id=request.user.id,
        total=cart.total,
        status="pending",
    )

    # Move cart items to order lines
    for item in cart.items.all():
        OrderLine.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            unit_price=item.product.price,
        )

    # Clear cart
    cart.items.all().delete()
    cart.total = 0
    cart.save()

    # Process payment, send confirmation email, etc.
    # ...

    return JsonResponse({
        "data": {"order_id": order.id, "status": "confirmed", "total": float(order.total)}
    }, status=201)
```

---

## Adding custom endpoints (FastAPI)

```python
# main.py
from fastapi import FastAPI, Request, HTTPException
from flashapi.fastapi import FlashAPI
from flashapi import Model
from models import Product, Cart, CartItem, Order, Customer

# FlashAPI handles all standard CRUD
flash = FlashAPI(
    models=[Product, Cart, CartItem, Order, Customer],
    database="shop.db",
)
app = flash.app

# === Your custom business logic on the same app ===

@app.post("/cart/add", tags=["Business Logic"])
async def add_to_cart(request: Request):
    body = await request.json()
    product_id = body["product_id"]
    quantity = body.get("quantity", 1)

    # Verify product exists and has stock
    product = flash._storage.get("products", product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    if not product.get("in_stock"):
        raise HTTPException(400, "Product out of stock")

    # Add to cart (your logic)
    cart_item = flash._storage.create("cartitems", {
        "cart_id": body["cart_id"],
        "product_id": product_id,
        "quantity": quantity,
    })

    return {"message": "Added to cart", "item": cart_item}


@app.post("/checkout", tags=["Business Logic"])
async def checkout(request: Request):
    body = await request.json()
    cart_id = body["cart_id"]

    # Get all items in cart
    all_items = flash._storage.list_all("cartitems")
    cart_items = [i for i in all_items if i["cart_id"] == cart_id]

    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    # Calculate total
    total = 0
    for item in cart_items:
        product = flash._storage.get("products", item["product_id"])
        total += product["price"] * item["quantity"]

    # Create order
    order = flash._storage.create("orders", {
        "customer_id": body["customer_id"],
        "total": total,
        "status": "confirmed",
    })

    # Clear cart
    for item in cart_items:
        flash._storage.delete("cartitems", item["id"])

    return {"order_id": order["id"], "total": total, "status": "confirmed"}


@app.get("/reports/bestsellers", tags=["Reports"])
async def bestsellers():
    # Custom aggregation logic
    orders = flash._storage.list_all("orders")
    # ... your analytics logic ...
    return {"top_products": [...]}
```

---

## Adding custom endpoints (Flask)

```python
# app.py
from flask import Flask, request, jsonify
from flashapi.flask import register_models
from models import Product, Cart, CartItem, Order

app = Flask(__name__)
register_models(app, models=[Product, Cart, CartItem, Order])

@app.route("/cart/add", methods=["POST"])
def add_to_cart():
    body = request.get_json()
    # Your business logic...
    return jsonify({"message": "Added to cart"})

@app.route("/checkout", methods=["POST"])
def checkout():
    body = request.get_json()
    # Order creation, payment, email...
    return jsonify({"order_id": 42, "status": "confirmed"}), 201

@app.route("/reports/revenue")
def revenue_report():
    # Custom aggregation
    return jsonify({"revenue": 150000, "period": "2024-Q1"})
```

---

## When to use FlashAPI vs custom logic

| Need | Use | Why |
|------|-----|-----|
| List products | FlashAPI | Standard CRUD |
| Get product by ID | FlashAPI | Standard CRUD |
| Create/update a product | FlashAPI | Standard CRUD |
| Delete a product | FlashAPI | Standard CRUD |
| Add product to cart | Custom endpoint | Multi-step logic: check stock, calculate price, update cart |
| Checkout / payment | Custom endpoint | Multi-model transaction, payment gateway, emails |
| User registration | Custom endpoint | Password hashing, email verification, token generation |
| Password reset | Custom endpoint | Token generation, email sending |
| File upload with processing | Custom endpoint | Resize images, generate thumbnails, virus scan |
| Dashboard statistics | Custom endpoint | Aggregations, JOINs, complex queries |
| Webhook receiver | Custom endpoint | External service integration |
| Export to CSV/PDF | Custom endpoint | File generation |
| Search with ranking/scoring | Custom endpoint | Complex search beyond simple text match |
| Send notifications | Custom endpoint | Side effects (push, email, SMS) |
| Bulk operations | Custom endpoint | Create/update many items at once |
| Admin approve/reject | Custom endpoint | State machine with validation rules |
| CRUD for a simple settings table | FlashAPI | Standard CRUD |
| CRUD for reference data (categories, tags) | FlashAPI | Standard CRUD |
| Read-only public catalog | FlashAPI + `readonly=True` | Standard read |

**Rule of thumb:** If you're just reading/writing a single row in one table, FlashAPI handles it. If there are multiple steps, side effects, or multiple tables involved, write your own endpoint.

---

## Real-world patterns

### Pattern: FlashAPI for admin panel, custom for user-facing

```python
# FlashAPI for internal/admin CRUD (protected by admin middleware)
path("admin-api/", include(generate_urls(models=[Product, Order, Customer, Inventory])))

# Custom endpoints for the user-facing app
path("api/shop/", shop_views.product_list),      # Custom filtering, scoring
path("api/cart/", cart_views.cart_operations),    # Business logic
path("api/account/", account_views.profile),     # User-specific logic
```

### Pattern: FlashAPI for read, custom for write

```python
# FlashAPI: read-only access to all models
path("api/", include(generate_urls(models=[
    Model(Product, readonly=True),
    Model(Order, readonly=True),
    Model(Customer, readonly=True),
])))

# Custom: all writes go through validated business logic
path("api/products/create/", views.create_product),    # With image processing
path("api/orders/place/", views.place_order),          # With payment
```

### Pattern: Full FlashAPI + a few custom endpoints

```python
# FlashAPI handles 90% of the work
path("api/", include(generate_urls(models=[
    Category, Product, Customer, Order, OrderLine, Review,
    Model(Payment, exclude=["delete"]),
])))

# You only write the 10% that needs custom logic
path("api/checkout/", views.checkout),
path("api/reviews/moderate/", views.moderate_review),
```

---

## Related Docs

- [Integration Guide](integration.md)
- [Authentication & Permissions](authentication.md)
- [Customization](customization.md)
- [Full Examples](examples.md)
