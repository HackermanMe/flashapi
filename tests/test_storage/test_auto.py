import pytest
import os
from dataclasses import dataclass

from flashapi.inspectors import inspect_model
from flashapi.storage.auto import AutoStorage


@dataclass
class Task:
    title: str
    done: bool = False


@pytest.fixture
def storage(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = AutoStorage(db_path)
    schema = inspect_model(Task)
    s.ensure_table(schema)
    yield s
    s.close()


class TestAutoStorage:
    def test_create(self, storage):
        item = storage.create("tasks", {"title": "Buy milk", "done": False})
        assert item["id"] == 1
        assert item["title"] == "Buy milk"
        assert item["done"] == 0  # SQLite stores bool as int

    def test_get(self, storage):
        storage.create("tasks", {"title": "Test"})
        item = storage.get("tasks", 1)
        assert item is not None
        assert item["title"] == "Test"

    def test_get_nonexistent(self, storage):
        item = storage.get("tasks", 999)
        assert item is None

    def test_list_all(self, storage):
        storage.create("tasks", {"title": "A"})
        storage.create("tasks", {"title": "B"})
        storage.create("tasks", {"title": "C"})
        items = storage.list_all("tasks")
        assert len(items) == 3

    def test_list_empty(self, storage):
        items = storage.list_all("tasks")
        assert items == []

    def test_update(self, storage):
        storage.create("tasks", {"title": "Old", "done": False})
        updated = storage.update("tasks", 1, {"title": "New", "done": True})
        assert updated["title"] == "New"
        assert updated["done"] == 1

    def test_update_partial(self, storage):
        storage.create("tasks", {"title": "Original", "done": False})
        updated = storage.update("tasks", 1, {"title": "Changed"})
        assert updated["title"] == "Changed"
        assert updated["done"] == 0

    def test_update_nonexistent(self, storage):
        result = storage.update("tasks", 999, {"title": "X"})
        assert result is None

    def test_delete(self, storage):
        storage.create("tasks", {"title": "To delete"})
        assert storage.delete("tasks", 1) is True
        assert storage.get("tasks", 1) is None

    def test_delete_nonexistent(self, storage):
        assert storage.delete("tasks", 999) is False

    def test_auto_increment_id(self, storage):
        item1 = storage.create("tasks", {"title": "First"})
        item2 = storage.create("tasks", {"title": "Second"})
        assert item1["id"] == 1
        assert item2["id"] == 2
