"""
Idempotency key support for FlashAPI.

Prevents duplicate operations (double-click, retry, network replay) by storing
request/response pairs keyed by a client-provided UUID.

HTTP Spec v1 compliant:
- Header: Idempotency-Key (UUID)
- Behavior: Same key + same request → replay stored response
- Conflict: Same key + different request → 422 Unprocessable Entity
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class IdempotencyRecord:
    """Stored idempotency record."""

    key: str
    method: str
    path: str
    body_hash: str
    response_status: int
    response_body: str
    response_headers: dict[str, str]
    created_at: float


class IdempotencyStore:
    """Abstract storage interface for idempotency records."""

    def get(self, key: str) -> IdempotencyRecord | None:
        """Retrieve stored record by key."""
        raise NotImplementedError

    def store(
        self,
        key: str,
        method: str,
        path: str,
        body_hash: str,
        response_status: int,
        response_body: str,
        response_headers: dict[str, str],
    ) -> None:
        """Store a new idempotency record."""
        raise NotImplementedError

    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        """Remove records older than max_age_seconds. Returns count deleted."""
        raise NotImplementedError


class InMemoryIdempotencyStore(IdempotencyStore):
    """In-memory idempotency store (for development/testing)."""

    def __init__(self):
        self._store: dict[str, IdempotencyRecord] = {}

    def get(self, key: str) -> IdempotencyRecord | None:
        return self._store.get(key)

    def store(
        self,
        key: str,
        method: str,
        path: str,
        body_hash: str,
        response_status: int,
        response_body: str,
        response_headers: dict[str, str],
    ) -> None:
        self._store[key] = IdempotencyRecord(
            key=key,
            method=method,
            path=path,
            body_hash=body_hash,
            response_status=response_status,
            response_body=response_body,
            response_headers=response_headers,
            created_at=time.time(),
        )

    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        now = time.time()
        expired_keys = [
            k for k, v in self._store.items() if now - v.created_at > max_age_seconds
        ]
        for key in expired_keys:
            del self._store[key]
        return len(expired_keys)


class SQLiteIdempotencyStore(IdempotencyStore):
    """SQLite-based idempotency store (production-ready for single-instance)."""

    def __init__(self, db_path: str = ":memory:"):
        import sqlite3

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_keys (
                key TEXT PRIMARY KEY,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                body_hash TEXT NOT NULL,
                response_status INTEGER NOT NULL,
                response_body TEXT NOT NULL,
                response_headers TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created_at ON idempotency_keys(created_at)"
        )
        self._conn.commit()

    def get(self, key: str) -> IdempotencyRecord | None:
        row = self._conn.execute(
            "SELECT * FROM idempotency_keys WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return IdempotencyRecord(
            key=row["key"],
            method=row["method"],
            path=row["path"],
            body_hash=row["body_hash"],
            response_status=row["response_status"],
            response_body=row["response_body"],
            response_headers=json.loads(row["response_headers"]),
            created_at=row["created_at"],
        )

    def store(
        self,
        key: str,
        method: str,
        path: str,
        body_hash: str,
        response_status: int,
        response_body: str,
        response_headers: dict[str, str],
    ) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO idempotency_keys
            (key, method, path, body_hash, response_status, response_body, response_headers, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                method,
                path,
                body_hash,
                response_status,
                response_body,
                json.dumps(response_headers),
                time.time(),
            ),
        )
        self._conn.commit()

    def cleanup_expired(self, max_age_seconds: int = 86400) -> int:
        cutoff = time.time() - max_age_seconds
        cursor = self._conn.execute(
            "DELETE FROM idempotency_keys WHERE created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cursor.rowcount


def compute_body_hash(body: bytes | str) -> str:
    """Compute SHA-256 hash of request body for comparison."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def check_idempotency_conflict(
    stored: IdempotencyRecord, method: str, path: str, body_hash: str
) -> bool:
    """Check if request conflicts with stored record (same key, different request)."""
    return (
        stored.method != method or stored.path != path or stored.body_hash != body_hash
    )


class IdempotencyMiddleware:
    """
    Idempotency middleware for FlashAPI.

    Usage (Django):
        from flashapi.features.idempotency import IdempotencyMiddleware, SQLiteIdempotencyStore

        # In settings.py MIDDLEWARE
        MIDDLEWARE = [
            'flashapi.features.idempotency.DjangoIdempotencyMiddleware',
            ...
        ]

        # Register store globally
        from flashapi.features.idempotency import register_idempotency_store
        register_idempotency_store(SQLiteIdempotencyStore('idempotency.db'))
    """

    def __init__(self, store: IdempotencyStore | None = None):
        self.store = store or InMemoryIdempotencyStore()

    def process_request(
        self, method: str, path: str, headers: dict[str, str], body: bytes | str
    ) -> tuple[bool, Any]:
        """
        Process request for idempotency.

        Returns:
            (is_replay, response_or_none):
                - If is_replay=True, response_or_none contains the stored response to replay
                - If is_replay=False, response_or_none is None (continue normal processing)
                - If is_replay=False but response_or_none is dict, it's a 422 conflict error
        """
        # Only apply to POST/PUT/DELETE
        if method not in ("POST", "PUT", "DELETE"):
            return False, None

        idempotency_key = headers.get("idempotency-key") or headers.get(
            "Idempotency-Key"
        )
        if not idempotency_key:
            return False, None

        # Validate UUID format (basic check)
        if len(idempotency_key) < 32:
            return False, {
                "error": "Invalid Idempotency-Key format (must be UUID)",
                "status": 400,
            }

        # Check if key exists
        stored = self.store.get(idempotency_key)
        if stored is None:
            return False, None

        # Check for conflict (same key, different request)
        body_hash = compute_body_hash(body)
        if check_idempotency_conflict(stored, method, path, body_hash):
            return False, {
                "error": {
                    "code": "IDEMPOTENCY_CONFLICT",
                    "message": "Idempotency key reused with different request",
                    "status": 422,
                },
                "status": 422,
            }

        # Replay stored response
        return True, {
            "status": stored.response_status,
            "body": stored.response_body,
            "headers": stored.response_headers,
            "replay": True,
        }

    def store_response(
        self,
        idempotency_key: str,
        method: str,
        path: str,
        body: bytes | str,
        response_status: int,
        response_body: str,
        response_headers: dict[str, str] | None = None,
    ) -> None:
        """Store response for future replay."""
        if method not in ("POST", "PUT", "DELETE"):
            return

        body_hash = compute_body_hash(body)
        self.store.store(
            key=idempotency_key,
            method=method,
            path=path,
            body_hash=body_hash,
            response_status=response_status,
            response_body=response_body,
            response_headers=response_headers or {},
        )


# Global store registry (for Django middleware)
_IDEMPOTENCY_STORE: IdempotencyStore | None = None


def register_idempotency_store(store: IdempotencyStore) -> None:
    """Register global idempotency store."""
    global _IDEMPOTENCY_STORE
    _IDEMPOTENCY_STORE = store


def get_idempotency_store() -> IdempotencyStore | None:
    """Get global idempotency store."""
    return _IDEMPOTENCY_STORE


# Django middleware class
class DjangoIdempotencyMiddleware:
    """Django middleware for idempotency support."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.middleware = IdempotencyMiddleware(get_idempotency_store())

    def __call__(self, request):
        from django.http import JsonResponse

        # Extract request data
        method = request.method
        path = request.path
        headers = {k.lower(): v for k, v in request.META.items() if k.startswith("HTTP_")}
        headers = {k.replace("http_", ""): v for k, v in headers.items()}
        body = request.body

        # Check idempotency
        is_replay, result = self.middleware.process_request(method, path, headers, body)

        if result and "status" in result and result["status"] in (400, 422):
            # Error response (invalid key or conflict)
            return JsonResponse(result.get("error", result), status=result["status"])

        if is_replay and result:
            # Replay stored response
            response = JsonResponse(
                json.loads(result["body"]), status=result["status"], safe=False
            )
            for key, value in result.get("headers", {}).items():
                response[key] = value
            response["Idempotency-Replay"] = "true"
            return response

        # Process request normally
        response = self.get_response(request)

        # Store response if idempotency key present and success
        idempotency_key = headers.get("idempotency-key")
        if (
            idempotency_key
            and method in ("POST", "PUT", "DELETE")
            and 200 <= response.status_code < 300
        ):
            response_body = response.content.decode("utf-8")
            response_headers = {
                k: v for k, v in response.items() if k.lower() in ("content-type",)
            }
            self.middleware.store_response(
                idempotency_key=idempotency_key,
                method=method,
                path=path,
                body=body,
                response_status=response.status_code,
                response_body=response_body,
                response_headers=response_headers,
            )

        return response
