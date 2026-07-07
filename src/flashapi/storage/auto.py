from __future__ import annotations

import sqlite3
from typing import Any

from flashapi.core.schema import FieldSchema, FieldType, ModelSchema
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


class AutoStorage(Storage):
    """SQLite-backed automatic storage for Pydantic/dataclass models."""

    def __init__(self, database: str = "flashapi.db"):
        self._db_path = database
        self._conn = sqlite3.connect(database, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    def ensure_table(self, schema: ModelSchema) -> None:
        columns = []
        for field in schema.fields:
            if field.primary_key:
                columns.append(f"{field.name} INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                sql_type = FIELD_TYPE_TO_SQL.get(field.type, "TEXT")
                nullable = "" if field.required else ""
                columns.append(f"{field.name} {sql_type}{nullable}")

        sql = f"CREATE TABLE IF NOT EXISTS {schema.plural} ({', '.join(columns)})"
        self._conn.execute(sql)
        self._conn.commit()

    def create(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        values = list(data.values())

        cursor = self._conn.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values
        )
        self._conn.commit()

        item_id = cursor.lastrowid
        return self.get(table, item_id)

    def get(self, table: str, item_id: int | str) -> dict[str, Any] | None:
        cursor = self._conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def list_all(self, table: str) -> list[dict[str, Any]]:
        cursor = self._conn.execute(f"SELECT * FROM {table}")
        return [dict(row) for row in cursor.fetchall()]

    def update(self, table: str, item_id: int | str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self.get(table, item_id):
            return None

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [item_id]

        self._conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
        self._conn.commit()
        return self.get(table, item_id)

    def delete(self, table: str, item_id: int | str) -> bool:
        if not self.get(table, item_id):
            return False
        self._conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        self._conn.commit()
        return True

    def close(self) -> None:
        self._conn.close()
