# Relations

[Back to main README](../README.md)

---

## Table of Contents

- [How relations are detected](#how-relations-are-detected)
- [Nested Routes](#nested-routes)
- [Expand (Inline Related Data)](#expand-inline-related-data)
- [Multiple Relations](#multiple-relations)
- [Edge Cases](#edge-cases)

---

## How relations are detected

FlashAPI detects relationships by looking at fields ending in `_id`:

```python
class Book(BaseModel):
    title: str
    author_id: int    # ← FlashAPI sees this as a relation to "Author"
    category_id: int  # ← FlashAPI sees this as a relation to "Category"
```

The matching is based on the field name: `author_id` → looks for a registered model named `Author`. If `Author` is in your models list, two things happen:

1. A **nested route** is created: `GET /authors/{id}/books/`
2. An **expand** option becomes available: `GET /books/?expand=author`

If the target model is NOT in your models list, the field is treated as a regular integer field (no nested route, no expand).

**For Django models**, FlashAPI uses `ForeignKey` metadata directly — it knows the exact related model.

---

## Nested Routes

Nested routes let you fetch all children of a parent.

### Generated endpoints

If `Book` has `author_id` and `category_id`, FlashAPI generates:

```
GET /authors/{id}/books/       → all books by this author
GET /categories/{id}/books/    → all books in this category
```

### Usage

```bash
curl http://localhost:8000/authors/1/books/
```

Response:
```json
{
  "data": [
    {"id": 1, "title": "Les Miserables", "pages": 1200, "author_id": 1},
    {"id": 2, "title": "Notre-Dame de Paris", "pages": 800, "author_id": 1}
  ],
  "total": 2,
  "page": 1,
  "pages": 1,
  "page_size": 20
}
```

### Features on nested routes

Nested routes support the same features as regular list endpoints:

```
GET /authors/1/books/?page=1&page_size=5
GET /authors/1/books/?sort=-pages
GET /authors/1/books/?search=miserables
```

### Parent not found

If the parent ID doesn't exist, you get a 404:

```bash
curl http://localhost:8000/authors/999/books/
# → 404 {"detail": "Parent not found"}
```

---

## Expand (Inline Related Data)

Expand lets you include the full related object in the response instead of just the foreign key ID.

### On a single item

```bash
# Without expand — only the ID
GET /books/1/
{
  "data": {"id": 1, "title": "Les Miserables", "author_id": 1, "category_id": 3}
}

# With expand — full author object included
GET /books/1/?expand=author
{
  "data": {
    "id": 1,
    "title": "Les Miserables",
    "author_id": 1,
    "category_id": 3,
    "author": {"id": 1, "name": "Victor Hugo", "email": "hugo@example.com"}
  }
}
```

### On a list

```bash
GET /books/?expand=author
{
  "data": [
    {
      "id": 1,
      "title": "Les Miserables",
      "author_id": 1,
      "author": {"id": 1, "name": "Victor Hugo", "email": "hugo@example.com"}
    },
    {
      "id": 2,
      "title": "Le Malade imaginaire",
      "author_id": 2,
      "author": {"id": 2, "name": "Moliere", "email": "moliere@example.com"}
    }
  ],
  "total": 2,
  "page": 1,
  "pages": 1,
  "page_size": 20
}
```

### Multiple expands

Expand multiple relations by separating with commas:

```bash
GET /books/1/?expand=author,category
{
  "data": {
    "id": 1,
    "title": "Les Miserables",
    "author_id": 1,
    "category_id": 3,
    "author": {"id": 1, "name": "Victor Hugo"},
    "category": {"id": 3, "name": "Fiction"}
  }
}
```

---

## Multiple Relations

A model can have multiple foreign keys:

```python
class Article(BaseModel):
    title: str
    author_id: int
    category_id: int
    editor_id: int
```

This generates:
```
GET /authors/{id}/articles/
GET /categories/{id}/articles/
GET /editors/{id}/articles/
GET /articles/?expand=author
GET /articles/?expand=category
GET /articles/?expand=editor
GET /articles/?expand=author,category,editor
```

---

## Edge Cases

| Situation | Behavior |
|-----------|----------|
| `expand=author` but `author_id` is `null` | The `author` field is not added to the response |
| `expand=author` but author ID=999 doesn't exist | The `author` field is not added to the response |
| `expand=nonexistent` (field doesn't exist) | Silently ignored, no error |
| Nested route with empty results | Returns `{"data": [], "total": 0, ...}` |
| Model with `_id` field but target not registered | No nested route, no expand — just a normal integer field |
| Model has a field named `expand` | The query parameter `?expand=` takes priority for relation expansion. To filter by the field, use `?expand__eq=value` or rename the field |

---

## Related Docs

- [Integration Guide](integration.md)
- [Features (CRUD, pagination, filtering, sorting, search)](features.md)
- [Customization](customization.md)
