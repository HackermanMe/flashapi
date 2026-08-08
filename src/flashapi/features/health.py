"""
Health check endpoints for production monitoring.

Provides /health (liveness) and /ready (readiness) endpoints for Kubernetes,
load balancers, and monitoring systems.
"""

from __future__ import annotations

import time
from typing import Any


class HealthCheck:
    """Health check manager with liveness and readiness probes."""

    def __init__(self) -> None:
        self._start_time = time.time()
        self._ready = False
        self._checks: dict[str, callable] = {}

    def mark_ready(self) -> None:
        """Mark the application as ready to receive traffic."""
        self._ready = True

    def register_check(self, name: str, check_fn: callable) -> None:
        """Register a custom readiness check (e.g., database connection)."""
        self._checks[name] = check_fn

    def liveness(self) -> dict[str, Any]:
        """
        Liveness probe — is the application running?
        Returns 200 if alive, should return 5xx if deadlocked/crashed.
        """
        uptime = int(time.time() - self._start_time)
        return {"status": "ok", "uptime": uptime}

    def readiness(self) -> tuple[dict[str, Any], int]:
        """
        Readiness probe — is the application ready to serve traffic?
        Returns 200 if ready, 503 if not yet ready or dependencies failing.
        """
        if not self._ready:
            return {"status": "not_ready", "reason": "Application still initializing"}, 503

        failed_checks = []
        for name, check_fn in self._checks.items():
            try:
                if not check_fn():
                    failed_checks.append(name)
            except Exception as e:
                failed_checks.append(f"{name}: {e}")

        if failed_checks:
            return {
                "status": "not_ready",
                "failed_checks": failed_checks,
            }, 503

        uptime = int(time.time() - self._start_time)
        return {"status": "ready", "uptime": uptime, "checks_passed": len(self._checks)}, 200


_health = HealthCheck()


def get_health_check() -> HealthCheck:
    """Get the global health check instance."""
    return _health
