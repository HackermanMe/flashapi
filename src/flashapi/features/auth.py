"""Authentication & authorization guard for FlashAPI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuthBackend(ABC):
    """Interface that the developer implements with their auth stack.

    FlashAPI never handles login, tokens, passwords, or OAuth flows.
    It only asks: who is this user, and what can they do?
    """

    @abstractmethod
    def authenticate(self, request) -> Any | None:
        """Return the user object if authenticated, None otherwise.

        The request object is framework-specific (Django HttpRequest, Flask request, etc.).
        """
        ...

    def get_role(self, user) -> str:
        """Return the user's role as a string.

        Built-in roles (ordered by privilege):
          - "public"        — no authentication required
          - "authenticated" — any logged-in user
          - "staff"         — elevated privileges
          - "admin"         — full access, bypasses scopes

        Custom roles are supported — they're matched literally against `access` config.
        """
        return "authenticated"

    def get_tenant_id(self, user) -> Any | None:
        """Return the tenant identifier for this user (e.g., organization_id, school_id).

        Return None if the user has no tenant (e.g., superadmin).
        """
        return None

    def get_owner_id(self, user) -> Any | None:
        """Return the owner identifier for this user (typically user.pk or user.id).

        Used for scope="owner" models where each user only sees their own data.
        """
        return getattr(user, "pk", None) or getattr(user, "id", None)

    def get_user_identifier(self, user) -> str:
        """Return a display identifier for audit trail (e.g., username, email).

        Override to customize. Default tries common attributes.
        """
        for attr in ("username", "email", "name"):
            val = getattr(user, attr, None)
            if val:
                return str(val)
        return str(user)


# Access levels ordered by privilege
ROLE_HIERARCHY = ["public", "authenticated", "staff", "admin"]


def check_access(user_role: str, required_access: str | dict | bool | None, operation: str) -> bool:
    """Check if a user role satisfies the required access for an operation.

    Args:
        user_role: The role of the current user ("public" if unauthenticated).
        required_access: The access requirement, can be:
            - None or "public" or True: no restriction
            - "authenticated", "staff", "admin": minimum role required
            - dict mapping operation -> role: per-operation control
            - False: block all access
        operation: The CRUD operation being performed ("list", "read", "create", "update", "delete").

    Returns:
        True if access is granted, False otherwise.
    """
    if required_access is None or required_access is True or required_access == "public":
        return True

    if required_access is False:
        return user_role == "admin"

    if isinstance(required_access, dict):
        op_access = required_access.get(operation, "authenticated")
        return check_access(user_role, op_access, operation)

    if isinstance(required_access, str):
        if required_access not in ROLE_HIERARCHY:
            return user_role == required_access or user_role == "admin"
        required_level = ROLE_HIERARCHY.index(required_access)
        if user_role not in ROLE_HIERARCHY:
            return False
        user_level = ROLE_HIERARCHY.index(user_role)
        return user_level >= required_level

    return False


def get_scope_filter(
    user,
    auth_backend: AuthBackend,
    scope: str | None,
    tenant_field: str | None,
    owner_field: str | None,
    user_role: str,
) -> dict[str, Any] | None:
    """Compute the filter dict to apply for multi-tenancy/ownership.

    Returns None if no filtering is needed (admin or no scope).
    Returns a dict like {"ecole_id": 5} or {"enseignant_id": 12}.
    Scope "both" combines tenant AND owner filters (both must match).
    """
    if scope is None or user_role == "admin":
        return None

    filters = {}

    if scope in ("tenant", "both"):
        tenant_id = auth_backend.get_tenant_id(user)
        if tenant_id is not None and tenant_field:
            filters[tenant_field] = tenant_id

    if scope in ("owner", "both"):
        owner_id = auth_backend.get_owner_id(user)
        if owner_id is not None and owner_field:
            filters[owner_field] = owner_id

    return filters if filters else None
