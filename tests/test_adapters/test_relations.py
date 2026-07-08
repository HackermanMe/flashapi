import pytest
from pydantic import BaseModel

from flashapi import Model
from flashapi.fastapi import FlashAPI


class Author(BaseModel):
    name: str


class Book(BaseModel):
    title: str
    author_id: int


class Category(BaseModel):
    name: str


class Article(BaseModel):
    title: str
    category_id: int
    author_id: int


@pytest.fixture
def client(tmp_path):
    from fastapi.testclient import TestClient

    db_path = str(tmp_path / "test.db")
    flash = FlashAPI(models=[Author, Book, Category, Article], database=db_path)
    return TestClient(flash.app)


@pytest.fixture
def seeded_client(client):
    client.post("/authors", json={"name": "Victor Hugo"})
    client.post("/authors", json={"name": "Moliere"})
    client.post("/categories", json={"name": "Fiction"})
    client.post("/categories", json={"name": "Theater"})
    client.post("/books", json={"title": "Les Miserables", "author_id": 1})
    client.post("/books", json={"title": "Notre-Dame de Paris", "author_id": 1})
    client.post("/books", json={"title": "Le Malade imaginaire", "author_id": 2})
    client.post("/articles", json={"title": "Review Hugo", "category_id": 1, "author_id": 1})
    client.post("/articles", json={"title": "Theater History", "category_id": 2, "author_id": 2})
    return client


class TestNestedRoutes:
    def test_nested_list(self, seeded_client):
        resp = seeded_client.get("/authors/1/books")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert all(b["author_id"] == 1 for b in data)

    def test_nested_other_parent(self, seeded_client):
        resp = seeded_client.get("/authors/2/books")
        assert len(resp.json()["data"]) == 1

    def test_nested_empty(self, seeded_client):
        seeded_client.post("/authors", json={"name": "New Author"})
        resp = seeded_client.get("/authors/3/books")
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_nested_404_parent(self, seeded_client):
        resp = seeded_client.get("/authors/999/books")
        assert resp.status_code == 404

    def test_nested_pagination(self, seeded_client):
        resp = seeded_client.get("/authors/1/books?page=1&page_size=1")
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["total"] == 2

    def test_nested_multiple_relations(self, seeded_client):
        resp = seeded_client.get("/authors/1/articles")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

        resp = seeded_client.get("/categories/1/articles")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1


class TestExpand:
    def test_expand_single(self, seeded_client):
        resp = seeded_client.get("/books/1?expand=author")
        data = resp.json()["data"]
        assert "author" in data
        assert data["author"]["name"] == "Victor Hugo"
        assert data["author"]["id"] == 1

    def test_expand_list(self, seeded_client):
        resp = seeded_client.get("/books?expand=author")
        books = resp.json()["data"]
        assert all("author" in b for b in books)
        assert books[0]["author"]["name"] == "Victor Hugo"

    def test_expand_multiple_fields(self, seeded_client):
        resp = seeded_client.get("/articles/1?expand=author,category")
        data = resp.json()["data"]
        assert "author" in data
        assert "category" in data
        assert data["author"]["name"] == "Victor Hugo"
        assert data["category"]["name"] == "Fiction"

    def test_expand_unknown_field_ignored(self, seeded_client):
        resp = seeded_client.get("/books/1?expand=nonexistent")
        data = resp.json()["data"]
        assert "nonexistent" not in data
        assert resp.status_code == 200

    def test_expand_no_param(self, seeded_client):
        resp = seeded_client.get("/books/1")
        data = resp.json()["data"]
        assert "author" not in data
        assert "author_id" in data

    def test_expand_with_null_fk(self, seeded_client):
        seeded_client.post("/books", json={"title": "Orphan Book", "author_id": 999})
        resp = seeded_client.get("/books/4?expand=author")
        data = resp.json()["data"]
        assert "author" not in data
