# Authentication & Permissions

[Back to main README](../README.md)

---

## Table of Contents

- [Philosophy](#philosophy)
- [Django: Middleware](#django-middleware)
- [FastAPI: Dependency Injection](#fastapi-dependency-injection)
- [Flask: before_request](#flask-before_request)
- [Protect Specific Operations](#protect-specific-operations)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Token Validation Examples](#token-validation-examples)
- [Combining FlashAPI restrictions + Auth](#combining-flashapi-restrictions--auth)

---

## Philosophy

FlashAPI **does not handle authentication or authorization.** This is a deliberate design choice:

- Every project has different auth needs (JWT, session, OAuth2, API keys, SAML...)
- Auth logic is tightly coupled to your user model and business rules
- Existing frameworks already have excellent auth mechanisms
- FlashAPI generates standard routes — protect them the same way you protect any route

**FlashAPI generates routes. You protect routes.**

---

## Django: Middleware

### Protect all API routes

```python
# middleware.py
class APIAuthMiddleware:
    """Require authentication for all /api/ routes except docs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip docs
        if request.path.startswith("/api/docs") or request.path.endswith("openapi.json"):
            return self.get_response(request)

        # Protect all other /api/ routes
        if request.path.startswith("/api/"):
            token = request.headers.get("Authorization", "")
            if not token.startswith("Bearer "):
                from django.http import JsonResponse
                return JsonResponse({"error": "Authentication required"}, status=401)

            if not self._validate_token(token[7:]):  # Remove "Bearer " prefix
                from django.http import JsonResponse
                return JsonResponse({"error": "Invalid token"}, status=401)

        return self.get_response(request)

    def _validate_token(self, token):
        # Replace with your actual validation (JWT decode, DB lookup, etc.)
        import jwt
        try:
            payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
            return True
        except jwt.InvalidTokenError:
            return False
```

```python
# settings.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Add BEFORE CsrfViewMiddleware if you want it to run first
    "myapp.middleware.APIAuthMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # ...
]
```

### Protect specific paths only

```python
# middleware.py
PROTECTED_PREFIXES = ["/api/orders", "/api/users", "/api/payments"]
PUBLIC_PREFIXES = ["/api/products", "/api/categories"]  # Public read access

class SelectiveAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in PROTECTED_PREFIXES):
            token = request.headers.get("Authorization", "")
            if not self._is_valid(token):
                from django.http import JsonResponse
                return JsonResponse({"error": "Unauthorized"}, status=401)
        return self.get_response(request)
```

---

## FastAPI: Dependency Injection

### Global auth (all routes)

```python
from fastapi import Depends, FastAPI, HTTPException, Header
from flashapi.fastapi import FlashAPI

async def require_auth(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization[7:]
    # Validate token (JWT, DB lookup, etc.)
    return token

# Option 1: Mount FlashAPI under an authenticated app
app = FastAPI(dependencies=[Depends(require_auth)])
flash = FlashAPI(models=[User, Product, Order])
app.mount("/api", flash.app)

# Option 2: Use middleware on FlashAPI's app
flash = FlashAPI(models=[User, Product, Order])
app = flash.app

@app.middleware("http")
async def auth_middleware(request, call_next):
    if request.url.path not in ["/docs", "/redoc", "/openapi.json"]:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)
```

### Public read, authenticated write

```python
@app.middleware("http")
async def write_auth(request, call_next):
    # Only protect write operations
    if request.method in ("POST", "PUT", "DELETE"):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Login required"}, status_code=401)
    return await call_next(request)
```

---

## Flask: before_request

### Protect all routes

```python
from flask import Flask, request, jsonify
from flashapi.flask import register_models

app = Flask(__name__)

@app.before_request
def require_auth():
    # Skip docs
    if request.path in ("/docs", "/openapi.json"):
        return None

    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return jsonify({"error": "Authentication required"}), 401

    if not validate_token(token[7:]):
        return jsonify({"error": "Invalid token"}), 401

register_models(app, models=[User, Product, Order])
```

### Public read, protected write

```python
@app.before_request
def protect_writes():
    if request.method in ("POST", "PUT", "DELETE"):
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            return jsonify({"error": "Login required"}), 401
```

---

## Protect Specific Operations

### By HTTP method

| Goal | Check |
|------|-------|
| Anyone can read, login to create | Require auth on `POST` |
| Anyone can read, admin to modify | Require auth on `POST`, `PUT`, `DELETE` + check role |
| Admin-only delete | Require auth + admin role on `DELETE` |
| Write-only endpoint (feedback form) | Only generate `POST` with `Model(Feedback, only=["create"])` |

### Django example: admin-only delete

```python
class AdminDeleteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "DELETE" and request.path.startswith("/api/"):
            if not request.user.is_authenticated:
                from django.http import JsonResponse
                return JsonResponse({"error": "Login required"}, status=401)
            if not request.user.is_staff:
                from django.http import JsonResponse
                return JsonResponse({"error": "Admin only"}, status=403)
        return self.get_response(request)
```

---

## Role-Based Access Control (RBAC)

### Django with user roles

```python
# middleware.py
ROLE_PERMISSIONS = {
    "admin": ["GET", "POST", "PUT", "DELETE"],
    "editor": ["GET", "POST", "PUT"],
    "viewer": ["GET"],
}

class RBACMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/") or request.path.startswith("/api/docs"):
            return self.get_response(request)

        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({"error": "Login required"}, status=401)

        role = getattr(request.user, "role", "viewer")
        allowed_methods = ROLE_PERMISSIONS.get(role, [])

        if request.method not in allowed_methods:
            from django.http import JsonResponse
            return JsonResponse({"error": "Insufficient permissions"}, status=403)

        return self.get_response(request)
```

### FastAPI with JWT roles

```python
import jwt
from fastapi import Request
from fastapi.responses import JSONResponse

@app.middleware("http")
async def rbac_middleware(request: Request, call_next):
    if request.url.path.startswith("/docs") or request.url.path == "/openapi.json":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        payload = jwt.decode(auth[7:], "secret", algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return JSONResponse({"error": "Invalid token"}, status_code=401)

    role = payload.get("role", "viewer")
    role_permissions = {
        "admin": {"GET", "POST", "PUT", "DELETE"},
        "editor": {"GET", "POST", "PUT"},
        "viewer": {"GET"},
    }

    if request.method not in role_permissions.get(role, set()):
        return JSONResponse({"error": "Forbidden"}, status_code=403)

    return await call_next(request)
```

---

## Token Validation Examples

### JWT (PyJWT)

```python
import jwt

def validate_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
        return payload  # {"user_id": 1, "role": "admin", "exp": ...}
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

### API Key (simple)

```python
VALID_API_KEYS = {"key-abc123", "key-def456"}

def validate_api_key(key: str) -> bool:
    return key in VALID_API_KEYS
```

### Session-based (Django)

```python
# No special token needed — use Django's built-in session auth
class SessionAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/") and not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({"error": "Login required"}, status=401)
        return self.get_response(request)
```

---

## Combining FlashAPI restrictions + Auth

You can combine `Model()` restrictions (which remove endpoints entirely) with auth middleware (which protects existing endpoints):

```python
from flashapi import Model

models = [
    # Public catalog — anyone can list and read, no one can modify via API
    Model(Product, readonly=True),

    # Orders — full CRUD but protected by auth middleware
    Order,

    # Payments — can create and read, but never delete (even admins)
    Model(Payment, exclude=["delete"]),

    # Audit logs — read-only, only admins can access (via middleware)
    Model(AuditLog, readonly=True),
]
```

Then your middleware handles WHO can access the remaining endpoints:
- `Model(readonly=True)` = "this endpoint does not exist, period"
- Middleware auth = "this endpoint exists but you need permission"

---

## Related Docs

- [Integration Guide](integration.md)
- [Customization](customization.md)
- [Custom Logic & Coexistence](custom-logic.md)
