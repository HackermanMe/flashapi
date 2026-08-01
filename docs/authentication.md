# Authentication, Authorization & Multi-Tenancy

[Back to main README](../README.md)

---

## Table of Contents

- [Philosophy](#philosophy)
- [Quick Start](#quick-start)
- [AuthBackend Interface](#authbackend-interface)
- [Access Control](#access-control)
  - [Per-model access](#per-model-access)
  - [Per-operation access](#per-operation-access)
  - [Role hierarchy](#role-hierarchy)
- [Multi-Tenancy (Scope)](#multi-tenancy-scope)
  - [Tenant isolation](#tenant-isolation)
  - [Owner isolation](#owner-isolation)
  - [Combined scope](#combined-scope)
- [Full Examples](#full-examples)
  - [Django + allauth + JWT](#django--allauth--jwt)
  - [Django + session auth](#django--session-auth)
  - [FastAPI + OAuth2 Google](#fastapi--oauth2-google)
  - [Flask + API Keys](#flask--api-keys)
  - [School management (gestionEcole)](#school-management-gestionecole)
  - [SaaS multi-tenant](#saas-multi-tenant)
- [Security Model](#security-model)
- [What FlashAPI does NOT do](#what-flashapi-does-not-do)
- [Migration from middleware approach](#migration-from-middleware-approach)
- [CORS](#cors)

---

## Philosophy

FlashAPI handles **authorization** (who can do what) but NOT **authentication** (login, tokens, OAuth).

You plug in your auth stack (django-allauth, python-jose, authlib, OTP, magic links, passkeys — whatever you use) via a simple interface. FlashAPI only asks two questions:

1. **Who is this user?** (or is there no user at all)
2. **What role do they have?**

From there, FlashAPI enforces access rules and data isolation automatically.

```
┌─────────────────────────────────────────────────────────────┐
│                     Your auth stack                          │
│  (django-allauth, JWT, OAuth2, OTP, session, API keys...)   │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  AuthBackend (you write)                     │
│  authenticate(request) → user or None                       │
│  get_role(user) → "authenticated" | "staff" | "admin"       │
│  get_tenant_id(user) → school_id, org_id, etc.              │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  FlashAPI (automatic)                        │
│  • Check access (401/403)                                   │
│  • Filter data by tenant/owner                              │
│  • Inject tenant_id on create                               │
│  • Block cross-tenant read/update/delete                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```python
from flashapi import Model, AuthBackend
from flashapi.django import generate_urls

class MyAuth(AuthBackend):
    def authenticate(self, request):
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"
        if user.is_staff:
            return "staff"
        return "authenticated"

urlpatterns = [
    path("api/", include(generate_urls(
        models=[
            Model(Product, access="authenticated"),
            Model(Order, access={"list": "public", "create": "authenticated", "delete": "admin"}),
        ],
        auth_backend=MyAuth(),
    ))),
]
```

That's it. No middleware to write, no decorators, no URL path matching.

---

## AuthBackend Interface

You implement this class. It's the bridge between your auth system and FlashAPI.

```python
from flashapi import AuthBackend

class MyAuth(AuthBackend):
    def authenticate(self, request) -> User | None:
        """Return the user object if authenticated, None otherwise.

        The request object is framework-specific:
        - Django: HttpRequest (request.user, request.META, etc.)
        - Flask: flask.request (request.headers, etc.)
        - FastAPI: starlette Request (request.headers, etc.)

        You decide how to validate: JWT decode, session lookup, API key check, etc.
        """
        ...

    def get_role(self, user) -> str:
        """Return the user's role as a string.

        Built-in roles (ordered by privilege):
        - "public"        — unauthenticated (FlashAPI uses this internally)
        - "authenticated" — any logged-in user
        - "staff"         — elevated privileges
        - "admin"         — full access, bypasses all scopes

        You can also return custom role strings — they're matched literally.
        """
        ...

    def get_tenant_id(self, user) -> Any | None:
        """Return the tenant/organization ID for this user.

        Used with scope="tenant". Return None for users without a tenant (e.g., superadmin).
        """
        ...

    def get_owner_id(self, user) -> Any | None:
        """Return the user's own ID (for scope="owner").

        Default implementation returns user.pk or user.id.
        Override only if your user identifier is something else.
        """
        ...
```

### Minimal implementation (most projects)

```python
class MyAuth(AuthBackend):
    def authenticate(self, request):
        # Django session-based
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"
        if user.is_staff:
            return "staff"
        return "authenticated"
```

### JWT implementation

```python
import jwt

class JWTAuth(AuthBackend):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            payload = jwt.decode(auth[7:], "your-secret", algorithms=["HS256"])
            return payload  # dict with user_id, role, etc.
        except jwt.InvalidTokenError:
            return None

    def get_role(self, user):
        return user.get("role", "authenticated")

    def get_tenant_id(self, user):
        return user.get("org_id")

    def get_owner_id(self, user):
        return user.get("user_id")
```

---

## Access Control

### Per-model access

Set a single access level for all operations on a model:

```python
Model(Product, access="public")          # Anyone (no auth needed)
Model(Order, access="authenticated")     # Any logged-in user
Model(Report, access="staff")            # Staff or higher
Model(Config, access="admin")            # Admin only
Model(Secret, access=False)              # Only admin can access (blocks everyone else)
```

Without `access` (or `access=None`), the model is **public** — no authentication required. This preserves backward compatibility.

### Per-operation access

Fine-grained control with a dict mapping operation to minimum role:

```python
Model(Article, access={
    "list": "public",           # Anyone can browse
    "read": "public",           # Anyone can read
    "create": "authenticated",  # Must be logged in to write
    "update": "staff",          # Only staff can edit
    "delete": "admin",          # Only admin can remove
})
```

Operations are: `"list"`, `"read"`, `"create"`, `"update"`, `"delete"`.

Any operation not in the dict defaults to `"authenticated"`.

### Role hierarchy

Roles are ordered by privilege level:

```
public < authenticated < staff < admin
```

A role grants access to its level AND all levels below:
- `admin` can access everything
- `staff` can access `staff`, `authenticated`, and `public`
- `authenticated` can access `authenticated` and `public`
- `public` can only access `public`

### Custom roles

You can return any string from `get_role()`. Custom roles are matched literally:

```python
def get_role(self, user):
    return user.department  # "finance", "hr", "engineering", etc.

# Then in Model:
Model(Budget, access="finance")  # Only users with role "finance" or "admin"
```

Custom roles are not part of the hierarchy — only `"admin"` gets automatic bypass.

### HTTP responses

| Situation | Status | Body |
|-----------|--------|------|
| No auth header + protected resource | 401 | `{"error": "Authentication required", "status": 401}` |
| Valid auth but insufficient role | 403 | `{"error": "Forbidden", "status": 403}` |
| Valid auth but item belongs to another tenant | 404 | `{"error": "Not found", "status": 404}` |

Cross-tenant violations return **404** (not 403) to avoid leaking information about existence.

---

## Multi-Tenancy (Scope)

Scope controls **data isolation** — which records a user can see and touch.

### Tenant isolation

Each user belongs to an organization/school/company. They only see data from their tenant.

```python
Model(
    Eleve,
    access="authenticated",
    scope="tenant",
    tenant_field="ecole_id",  # column in your Eleve model
)
```

**What happens automatically:**

| Operation | Behavior |
|-----------|----------|
| `GET /api/eleves` | WHERE ecole_id = user's tenant |
| `GET /api/eleves/5` | Returns 404 if eleve.ecole_id != user's tenant |
| `POST /api/eleves` | Injects ecole_id = user's tenant into the data |
| `PUT /api/eleves/5` | Returns 404 if trying to update another tenant's record |
| `DELETE /api/eleves/5` | Returns 404 if trying to delete another tenant's record |
| `GET /api/eleves/export` | Only exports current tenant's data |
| `POST /api/eleves/bulk` | Injects ecole_id into every item |

### Owner isolation

Each user only sees their own records.

```python
Model(
    EmploiDuTemps,
    access="authenticated",
    scope="owner",
    owner_field="enseignant_id",  # column in EmploiDuTemps
)
```

Same behavior as tenant isolation, but filtered by the individual user's ID.

### Combined scope

When a record must belong to both the right tenant AND the right owner:

```python
Model(
    Note,
    access="authenticated",
    scope="both",
    tenant_field="ecole_id",
    owner_field="enseignant_id",
)
```

Both filters are applied. A teacher in school A can only see notes they created in school A.

### Admin bypass

Users with role `"admin"` (from `get_role()`) **bypass all scopes**. They see all data across all tenants. This is intentional — admins need full visibility.

If you don't want global admin access, don't return `"admin"` from `get_role()`. Use `"staff"` as your highest role instead — it doesn't bypass scopes.

### No scope (shared data)

Some models are reference data shared across all tenants:

```python
Model(AnneeScolaire, access="authenticated")  # No scope — all authenticated users see everything
Model(Matiere, access={"list": "public", "read": "public", "create": "admin"})
```

Without `scope`, no filtering is applied (but `access` still enforces authentication/role).

---

## Full Examples

### Django + allauth + JWT

Using django-allauth for login (Google, email, etc.) and JWT for API access:

```python
# auth_backend.py
import jwt
from django.conf import settings
from flashapi import AuthBackend

class DjangoAllauthJWT(AuthBackend):
    """Supports both session auth (browser) and JWT (API clients)."""

    def authenticate(self, request):
        # Try session first (browser requests via allauth)
        if hasattr(request, 'user') and request.user.is_authenticated:
            return request.user

        # Try JWT (API clients)
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if auth.startswith("Bearer "):
            try:
                payload = jwt.decode(auth[7:], settings.SECRET_KEY, algorithms=["HS256"])
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.get(pk=payload["user_id"])
            except (jwt.InvalidTokenError, User.DoesNotExist):
                return None
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"
        if user.is_staff:
            return "staff"
        return "authenticated"

    def get_tenant_id(self, user):
        return getattr(user, 'organization_id', None)
```

```python
# urls.py
from flashapi import Model
from flashapi.django import generate_urls
from .auth_backend import DjangoAllauthJWT

urlpatterns = [
    path("accounts/", include("allauth.urls")),  # allauth handles login
    path("api/", include(generate_urls(
        models=[
            Model(Product, access={"list": "public", "read": "public", "create": "staff"}),
            Model(Order, access="authenticated", scope="owner", owner_field="user_id"),
        ],
        auth_backend=DjangoAllauthJWT(),
    ))),
]
```

### Django + session auth

Simplest case — standard Django login:

```python
# auth_backend.py
from flashapi import AuthBackend

class SessionAuth(AuthBackend):
    def authenticate(self, request):
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"
        if user.is_staff:
            return "staff"
        return "authenticated"
```

```python
# urls.py
urlpatterns = [
    path("api/", include(generate_urls(
        models=[Model(Task, access="authenticated")],
        auth_backend=SessionAuth(),
    ))),
]
```

### FastAPI + OAuth2 Google

Using authlib for Google OAuth2:

```python
# auth_backend.py
from flashapi import AuthBackend

class GoogleOAuth(AuthBackend):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None

        # Verify Google token (using your auth service)
        from your_auth_service import verify_google_token
        user_info = verify_google_token(auth[7:])
        return user_info  # {"email": "...", "sub": "...", "org_id": "..."}

    def get_role(self, user):
        # You define roles based on your DB or the token
        if user.get("email") in ADMIN_EMAILS:
            return "admin"
        return "authenticated"

    def get_tenant_id(self, user):
        return user.get("org_id")

    def get_owner_id(self, user):
        return user.get("sub")  # Google's user ID
```

```python
# main.py
from flashapi.fastapi import FlashAPI
from flashapi import Model

flash = FlashAPI(
    models=[
        Model(Document, access="authenticated", scope="tenant", tenant_field="org_id"),
    ],
    auth_backend=GoogleOAuth(),
)
app = flash.app
```

### Flask + API Keys

Simple API key authentication for a service-to-service API:

```python
# auth_backend.py
from flashapi import AuthBackend

API_KEYS = {
    "key-abc123": {"name": "Mobile App", "role": "authenticated", "tenant": 1},
    "key-def456": {"name": "Admin Panel", "role": "admin", "tenant": None},
    "key-ghi789": {"name": "Partner API", "role": "staff", "tenant": 2},
}

class APIKeyAuth(AuthBackend):
    def authenticate(self, request):
        key = request.headers.get("X-API-Key", "")
        return API_KEYS.get(key)

    def get_role(self, user):
        return user["role"]

    def get_tenant_id(self, user):
        return user["tenant"]
```

```python
# app.py
from flask import Flask
from flashapi.flask import register_models
from flashapi import Model

app = Flask(__name__)
register_models(app, models=[
    Model(Metric, access="authenticated", scope="tenant", tenant_field="app_id"),
], auth_backend=APIKeyAuth())
```

### School management (gestionEcole)

Real-world example with multiple roles and mixed access:

```python
# auth_backend.py
from flashapi import AuthBackend

class EcoleAuth(AuthBackend):
    def authenticate(self, request):
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"            # Super-admin: all schools
        if user.groups.filter(name="directeurs").exists():
            return "staff"            # Director: their school only
        return "authenticated"        # Teacher: their own data

    def get_tenant_id(self, user):
        return user.ecole_id          # Each user belongs to a school

    def get_owner_id(self, user):
        return user.pk
```

```python
# urls.py
from flashapi import Model
from flashapi.django import generate_urls
from .auth_backend import EcoleAuth

urlpatterns = [
    path("api/", include(generate_urls(
        models=[
            # Reference data — public read, admin write
            Model(AnneeScolaire, lookup_field='tracking_id',
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin", "delete": "admin"}),
            Model(Matiere, lookup_field='tracking_id',
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin", "delete": "admin"}),
            Model(Niveau, lookup_field='tracking_id',
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin", "delete": "admin"}),

            # School-scoped data — staff+ can CRUD, isolated by school
            Model(Eleve, lookup_field='tracking_id', audit=True, soft_delete=True,
                  access="staff", scope="tenant", tenant_field="ecole_id"),
            Model(Classe, lookup_field='tracking_id',
                  access="staff", scope="tenant", tenant_field="ecole_id"),
            Model(Enseignant, lookup_field='tracking_id',
                  access="staff", scope="tenant", tenant_field="ecole_id"),

            # Teacher's own data — each teacher sees only their schedule
            Model(EmploiDuTemps, lookup_field='tracking_id', soft_delete=True,
                  access="authenticated", scope="owner", owner_field="enseignant_id"),

            # Notes — isolated by school AND teacher
            Model(Note, lookup_field='tracking_id', audit=True,
                  access="authenticated", scope="both",
                  tenant_field="ecole_id", owner_field="enseignant_id"),

            # Payments — school-scoped, staff only, with audit
            Model(Paiement, lookup_field='tracking_id', audit=True,
                  access="staff", scope="tenant", tenant_field="ecole_id"),
        ],
        auth_backend=EcoleAuth(),
    ))),
]
```

### SaaS multi-tenant

A typical SaaS with organizations, users, and plans:

```python
class SaaSAuth(AuthBackend):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        # Decode your JWT / session token
        return decode_token(auth[7:])

    def get_role(self, user):
        if user.get("is_platform_admin"):
            return "admin"
        if user.get("is_org_admin"):
            return "staff"
        return "authenticated"

    def get_tenant_id(self, user):
        return user.get("organization_id")

    def get_owner_id(self, user):
        return user.get("user_id")
```

```python
FlashAPI(
    models=[
        # Org-wide data (all members see)
        Model(Project, access="authenticated", scope="tenant", tenant_field="organization_id"),
        Model(Invoice, access="staff", scope="tenant", tenant_field="organization_id"),

        # Personal data (only the user sees)
        Model(Notification, access="authenticated", scope="owner", owner_field="user_id"),
        Model(Draft, access="authenticated", scope="owner", owner_field="user_id"),

        # Platform-wide (admin only)
        Model(Plan, access={"list": "public", "read": "public", "create": "admin", "update": "admin"}),
    ],
    auth_backend=SaaSAuth(),
)
```

---

## Security Model

### What is enforced

| Layer | Mechanism | When |
|-------|-----------|------|
| Authentication | `authenticate()` returns user or None | Before every operation on protected models |
| Authorization | Role compared against `access` | After authentication |
| Data isolation | Scope filter applied to queries | After authorization |
| Write isolation | Scope filter injected into CREATE data | On create/bulk-create |
| Cross-tenant block | Scope check before update/delete | On mutation of existing records |

### Security guarantees

1. **No information leakage**: Cross-tenant/cross-owner attempts return 404 (not 403), so attackers can't enumerate IDs
2. **Automatic injection**: The tenant_id/owner_id is ALWAYS injected on create — users can't forge it in the request body
3. **No bypass via direct ID access**: Reading `/api/eleves/123` checks scope even if you know the ID
4. **Export respects scope**: CSV/XLSX/PDF exports only contain records the user can see
5. **Bulk create respects scope**: Every item in a bulk request gets the correct tenant_id/owner_id

### What is NOT enforced (by design)

- **Admin bypass**: role `"admin"` sees all data. Don't return "admin" if you don't want this.
- **No row-level encryption**: Data is filtered, not encrypted. A DB admin sees everything.
- **No audit of who accessed what**: The audit trail logs mutations, not reads. Add request logging for that.

---

## What FlashAPI does NOT do

| Responsibility | Who handles it |
|----------------|----------------|
| Login page / register form | Your framework (django-allauth, etc.) |
| OAuth2 flows (redirects, callbacks) | authlib, python-social-auth, etc. |
| JWT creation / signing | python-jose, PyJWT, etc. |
| Password hashing | Django's auth, passlib, bcrypt, etc. |
| OTP / 2FA | django-otp, pyotp, etc. |
| Magic links / email verification | Your code or a service |
| Session management | Your framework |
| Token refresh / rotation | Your code |
| CORS | Your framework middleware |

FlashAPI is NOT an auth provider. It consumes auth decisions from your existing stack.

---

## Migration from middleware approach

If you previously used middleware to protect FlashAPI routes (as shown in older documentation), you can migrate incrementally:

### Before (middleware approach)

```python
# middleware.py
class APIAuthMiddleware:
    def __call__(self, request):
        if request.path.startswith("/api/") and request.method != "GET":
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
        return self.get_response(request)

# urls.py
generate_urls(models=[Product, Order])
```

### After (AuthBackend approach)

```python
# auth_backend.py
class MyAuth(AuthBackend):
    def authenticate(self, request):
        return request.user if request.user.is_authenticated else None
    def get_role(self, user):
        return "admin" if user.is_superuser else "authenticated"

# urls.py
generate_urls(
    models=[
        Model(Product, access={"list": "public", "read": "public", "create": "authenticated"}),
        Model(Order, access="authenticated"),
    ],
    auth_backend=MyAuth(),
)
```

**Advantages of the new approach:**
- Per-model, per-operation granularity (no URL path matching)
- Automatic data isolation (multi-tenancy)
- Automatic tenant_id injection on create
- No middleware ordering issues
- Works identically across Django/Flask/FastAPI

You can still use middleware for cross-cutting concerns (CORS, logging, rate limiting) — just move auth logic into the AuthBackend.

---

## CORS

FlashAPI does not configure CORS. If your frontend runs on a different origin, configure CORS with your framework:

### Django

```bash
pip install django-cors-headers
```

```python
# settings.py
INSTALLED_APPS = [..., "corsheaders", ...]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", ...]
CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
```

### FastAPI

```python
from fastapi.middleware.cors import CORSMiddleware

app = flash.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Flask

```bash
pip install flask-cors
```

```python
from flask_cors import CORS
CORS(app, origins=["http://localhost:3000"])
```

---

## Related Docs

- [Integration Guide](integration.md)
- [Customization](customization.md)
- [Features (CRUD, pagination, export, audit, etc.)](features.md)
- [Custom Logic](custom-logic.md)
