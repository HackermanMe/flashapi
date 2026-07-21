"""Audit trail — records CREATE, UPDATE, DELETE with field diffs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class AuditLog:
    """SQLite-backed audit trail."""

    def __init__(self, conn: sqlite3.Connection, table_name: str = "flash_audit_log"):
        self._conn = conn
        self._table = table_name
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{self._table}" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                performed_by TEXT DEFAULT '',
                changes TEXT
            )
        """)
        self._conn.commit()

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: str | int,
        *,
        performed_by: str = "",
        old_data: dict | None = None,
        new_data: dict | None = None,
    ) -> None:
        changes = None
        if action == "UPDATE" and old_data and new_data:
            changes = self._compute_diff(old_data, new_data)

        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            f'INSERT INTO "{self._table}" (action, entity_type, entity_id, timestamp, performed_by, changes) VALUES (?, ?, ?, ?, ?, ?)',
            (action, entity_type, str(entity_id), now, performed_by, json.dumps(changes) if changes else None),
        )
        self._conn.commit()

    def get_history(self, entity_type: str, entity_id: str | int) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            f'SELECT * FROM "{self._table}" WHERE entity_type = ? AND entity_id = ? ORDER BY timestamp ASC',
            (entity_type, str(entity_id)),
        )
        results = []
        for row in cursor.fetchall():
            entry = {
                "action": row["action"],
                "entityType": row["entity_type"],
                "entityId": row["entity_id"],
                "timestamp": row["timestamp"],
                "performedBy": row["performed_by"],
                "changes": json.loads(row["changes"]) if row["changes"] else None,
            }
            results.append(entry)
        return results

    def _compute_diff(self, old: dict, new: dict) -> dict:
        diff = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            if key == "id":
                continue
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                diff[key] = {"from": old_val, "to": new_val}
        return diff if diff else None
