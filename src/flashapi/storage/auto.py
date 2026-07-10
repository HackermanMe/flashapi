from __future__ import annotations

import sqlite3
from typing import Any

from flashapi.core.schema import FieldType, ModelSchema
from flashapi.storage.base import Storage

FIELD_TYPE_TO_SQL = {
    FieldType.STRING: "TEXT",
    FieldType.INTEGER: "INTEGER",
    FieldType.FLOAT: "REAL",
    FieldType.BOOLEAN: "INTEGER",
    FieldType.DATE: "TEXT",
    FieldType.DATETIME: "TEXT",
    FieldType.TIME: "TEXT",
    FieldType.UUID: "TEXT",
    FieldType.JSON: "TEXT",
    FieldType.TEXT: "TEXT",
    FieldType.BINARY: "BLOB",
}


def _validate_identifier(name: str) -> str:
    """Validate and quote a SQL identifier to prevent injection."""
    import re
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


class AutoStorage(Storage):
    """SQLite-backed automatic storage for Pydantic/dataclass models."""

    def __init__(self, database: str = "flashapi.db"):
        self._db_path = database
        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    def ensure_table(self, schema: ModelSchema) -> None:
        table = _validate_identifier(schema.plural)
        columns = []
        for field in schema.fields:
            col_name = _validate_identifier(field.name)
            if field.primary_key:
                columns.append(f"{col_name} INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                sql_type = FIELD_TYPE_TO_SQL.get(field.type, "TEXT")
                not_null = " NOT NULL" if field.required else ""
                columns.append(f"{col_name} {sql_type}{not_null}")

        sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)})"
        self._conn.execute(sql)
        self._conn.commit()

    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        safe_table = _validate_identifier(table)
        columns = [_validate_identifier(k) for k in data.keys()]
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = list(data.values())

        cursor = self._conn.execute(
            f"INSERT INTO {safe_table} ({col_names}) VALUES ({placeholders})", values
        )
        self._conn.commit()

        item_id = cursor.lastrowid
        return self.get(table, item_id)

    def get(self, table: str, item_id: int | str) -> dict[str, Any] | None:
        safe_table = _validate_identifier(table)
        cursor = self._conn.execute(f"SELECT * FROM {safe_table} WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_all(self, table: str) -> list[dict[str, Any]]:
        safe_table = _validate_identifier(table)
        cursor = self._conn.execute(f"SELECT * FROM {safe_table}")
        return [dict(row) for row in cursor.fetchall()]

    def update(self, table: str, item_id: int | str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self.get(table, item_id):
            return None

        safe_table = _validate_identifier(table)
        set_clause = ", ".join([f"{_validate_identifier(k)} = ?" for k in data.keys()])
        values = list(data.values()) + [item_id]

        self._conn.execute(f"UPDATE {safe_table} SET {set_clause} WHERE id = ?", values)
        self._conn.commit()
        return self.get(table, item_id)

    def delete(self, table: str, item_id: int | str) -> bool:
        if not self.get(table, item_id):
            return False
        safe_table = _validate_identifier(table)
        self._conn.execute(f"DELETE FROM {safe_table} WHERE id = ?", (item_id,))
        self._conn.commit()
        return True

    def close(self) -> None:
        self._conn.close()
