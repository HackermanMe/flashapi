# FlashAPI ⚡

**Define your models. FlashAPI does the rest.**

FlashAPI generates a full REST API (CRUD + pagination + filtering + sorting + search + docs) from your existing models — in one line.

## Install

```bash
pip install flashapi[fastapi]   # or flashapi[django] or flashapi[flask]
```

## Quick Start (FastAPI)

```python
from pydantic import BaseModel
from flashapi.fastapi import FlashAPI

class User(BaseModel):
    name: str
    email: str

app = FlashAPI(models=[User]).app
```

Run it:
```bash
uvicorn app:app --reload
```

Open `http://localhost:8000/docs` — your API is live with full CRUD.

## Quick Start (Django)

```python
# urls.py
from flashapi.django import generate_urls
from myapp.models import User, Product

urlpatterns = [
    path("api/", include(generate_urls(models=[User, Product]))),
]
```

## Quick Start (Flask)

```python
from flask import Flask
from flashapi.flask import register_models
from models import User

app = Flask(__name__)
register_models(app, models=[User])
```

## Features

- **Automatic CRUD** — GET, POST, PUT, DELETE generated for each model
- **Pagination** — `?page=1&page_size=20`
- **Filtering** — `?name=John` (exact match on any field)
- **Sorting** — `?sort=name` or `?sort=-name` (descending)
- **Search** — `?search=john` (searches all text fields)
- **Interactive docs** — Swagger UI at `/docs` (FastAPI) or auto-generated
- **Zero config** — SQLite storage auto-created for Pydantic/dataclass models
- **Framework agnostic** — works with FastAPI, Django, Flask

## Model Support

FlashAPI auto-detects your model type:

| Model Type | Storage |
|-----------|---------|
| Django Model | Uses Django ORM |
| SQLAlchemy | Uses SQLAlchemy engine |
| Pydantic | Auto SQLite |
| dataclass | Auto SQLite |

## Customize

```python
from flashapi import Model

FlashAPI(models=[
    User,                                  # full CRUD
    Model(Product, readonly=True),         # GET only
    Model(Order, exclude=["delete"]),      # no DELETE
    Model(Category, only=["list", "read"]),# list + detail only
    Model(Tag, plural="tags"),             # custom plural
])
```

## Custom Response Format

```python
def my_formatter(data, meta):
    return {"results": data, "info": meta}

FlashAPI(models=[User], formatter=my_formatter)
```

## License

MIT
