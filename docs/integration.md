# Integration Guide

[Back to main README](../README.md)

---

## Table of Contents

- [FastAPI + SQLAlchemy (real project)](#fastapi--sqlalchemy)
- [FastAPI + Pydantic (quick prototype)](#fastapi--pydantic)
- [Flask + Flask-SQLAlchemy (real project)](#flask--flask-sqlalchemy)
- [Flask + Pydantic (quick prototype)](#flask--pydantic)
- [Django](#django)
- [Adding custom routes alongside FlashAPI](#adding-custom-routes)
- [All configuration options](#all-configuration-options)

---

## FastAPI + SQLAlchemy

**This is the most common real-world usage.** You have SQLAlchemy models and an existing database.

### Project structure

```
my_project/
├── main.py          ← FlashAPI goes here
├── models.py        ← Your SQLAlchemy models
├── database.py      ← Engine + session setup
├── requirements.txt
└── restaurant.db    ← Your database (ONE database, shared)
```

### Step-by-step

**`database.py`** — your engine (you probably already have this):
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./restaurant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
```

**`models.py`** — your models (no changes needed):
```python
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from database import Base

class CategorieMenu(Base):
    __tablename__ = 'categories_menu'
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    plats = relationship('Plat', back_populates='categorie')

class Plat(Base):
    __tablename__ = 'plats'
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    prix = Column(Numeric(8, 2), nullable=False)
    categorie_id = Column(Integer, ForeignKey('categories_menu.id'), nullable=False)
    disponible = Column(Boolean, default=True)

    categorie = relationship('CategorieMenu', back_populates='plats')

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    telephone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
```

**`main.py`** — FlashAPI setup (**the key file**):
```python
from flashapi.fastapi import FlashAPI
from database import engine, Base
from models import CategorieMenu, Plat, Client

# 1. Create tables (if they don't exist yet)
Base.metadata.create_all(bind=engine)

# 2. Pass engine= so FlashAPI uses YOUR database
app = FlashAPI(
    models=[CategorieMenu, Plat, Client],
    engine=engine,      # ← THIS IS THE KEY PARAMETER
).app
```

**Run:**
```bash
pip install flashapi[fastapi]
uvicorn main:app --reload
```

**Result:**
- Swagger UI at `http://localhost:8000/docs`
- All data goes to `restaurant.db` (your database)
- No `flashapi.db` is created

### Common mistakes

| Mistake | Fix |
|---------|-----|
| Forgot `engine=engine` | FlashAPI creates a separate `flashapi.db` and your data isn't there |
| `Base.metadata.create_all()` after FlashAPI | Tables don't exist yet → crash. Put it BEFORE. |
| Passing a URL string as `database=` | `database=` is for Pydantic models only. Use `engine=` for SQLAlchemy. |

---

## FastAPI + Pydantic

**For quick prototypes.** No database setup needed — FlashAPI handles everything.

### Single file (minimal)

```python
# main.py
from pydantic import BaseModel
from flashapi.fastapi import FlashAPI

class User(BaseModel):
    name: str
    email: str

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool = True

app = FlashAPI(models=[User, Product]).app
```

```bash
pip install flashapi[fastapi]
uvicorn main:app --reload
```

That's it. FlashAPI auto-creates `flashapi.db` with the right schema.

### Custom database path

```python
app = FlashAPI(models=[User, Product], database="my_data.db").app
```

---

## Flask + Flask-SQLAlchemy

**The most common Flask setup.** You use `flask-sqlalchemy` with `db = SQLAlchemy()`.

### Project structure

```
my_project/
├── app.py           ← FlashAPI goes here
├── models.py        ← Your Flask-SQLAlchemy models
├── requirements.txt
└── instance/
    └── bibliotheque.db
```

### Step-by-step

**`models.py`** — your models (no changes needed):
```python
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Auteur(db.Model):
    __tablename__ = 'auteurs'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    nationalite = db.Column(db.String(50))

    livres = db.relationship('Livre', back_populates='auteur')

class Categorie(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)

class Livre(db.Model):
    __tablename__ = 'livres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(13), unique=True)
    auteur_id = db.Column(db.Integer, db.ForeignKey('auteurs.id'), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    annee_publication = db.Column(db.Integer)

    auteur = db.relationship('Auteur', back_populates='livres')

class Adherent(db.Model):
    __tablename__ = 'adherents'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True)
    telephone = db.Column(db.String(20))

class Emprunt(db.Model):
    __tablename__ = 'emprunts'
    id = db.Column(db.Integer, primary_key=True)
    livre_id = db.Column(db.Integer, db.ForeignKey('livres.id'), nullable=False)
    adherent_id = db.Column(db.Integer, db.ForeignKey('adherents.id'), nullable=False)
    date_emprunt = db.Column(db.String(10), nullable=False)
    date_retour = db.Column(db.String(10))
    rendu = db.Column(db.Boolean, default=False)
```

**`app.py`** — FlashAPI setup (**the key file**):
```python
from flask import Flask
from flashapi.flask import register_models
from models import db, Auteur, Categorie, Livre, Adherent, Emprunt


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bibliotheque.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # 1. Initialize Flask-SQLAlchemy
    db.init_app(app)

    with app.app_context():
        # 2. Create tables
        db.create_all()

        # 3. Register FlashAPI with engine=db.engine
        register_models(app, models=[
            Auteur, Categorie, Livre, Adherent, Emprunt
        ], engine=db.engine)    # ← THIS IS THE KEY PARAMETER

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
```

**Run:**
```bash
pip install flashapi[flask] flask-sqlalchemy
python app.py
```

**Result:**
- Swagger UI at `http://localhost:5000/docs`
- All data goes to `bibliotheque.db` (your database)
- No `flashapi.db` is created

### The 3 rules for Flask-SQLAlchemy

1. **`db.init_app(app)` FIRST** — before anything else
2. **`db.create_all()` SECOND** — tables must exist
3. **`register_models(..., engine=db.engine)` THIRD** — inside `with app.app_context():`

### Common mistakes

| Mistake | Fix |
|---------|-----|
| `register_models()` outside `app.app_context()` | Flask-SQLAlchemy needs the app context. Wrap in `with app.app_context():` |
| Forgot `engine=db.engine` | FlashAPI tries to create `flashapi.db` and crashes (can't parse SQLAlchemy URL) |
| `database="sqlite:///..."` | That's a SQLAlchemy URL, not a file path. Use `engine=db.engine` instead. |
| `register_models()` before `db.init_app(app)` | `db.engine` doesn't exist yet → crash |

---

## Flask + Pydantic

**For quick prototypes without a real database.**

```python
# app.py
from flask import Flask
from pydantic import BaseModel
from flashapi.flask import register_models

class Book(BaseModel):
    title: str
    author: str
    year: int = 2024

class Member(BaseModel):
    name: str
    email: str

app = Flask(__name__)
register_models(app, models=[Book, Member])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

No `engine=` needed — FlashAPI auto-creates `flashapi.db`.

---

## Django

**Django models always use your Django database.** No `engine=` parameter needed.

### Project structure

```
my_project/
├── manage.py
├── my_project/
│   ├── settings.py
│   └── urls.py      ← FlashAPI goes here
└── backend/
    └── models.py    ← Your Django models (no changes needed)
```

### `urls.py`

```python
from django.contrib import admin
from django.urls import path, include
from flashapi.django import generate_urls
from backend.models import Eleve, Enseignant, Classe, Note, Matiere

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(
        models=[Eleve, Enseignant, Classe, Note, Matiere]
    ))),
]
```

**Run:**
```bash
python manage.py migrate
python manage.py runserver
```

Swagger UI at `http://localhost:8000/api/docs/`.

---

## Adding custom routes

### FastAPI — use `@flash.get()` / `@flash.post()`

```python
from fastapi import Request
from flashapi.fastapi import FlashAPI
from database import engine, Base
from models import Plat, Commande, Client

Base.metadata.create_all(bind=engine)

flash = FlashAPI(models=[Plat, Commande, Client], engine=engine)
app = flash.app

# Custom route — appears in /docs alongside CRUD
@flash.post("/checkout", tag="Business Logic", summary="Passer une commande")
async def checkout(request: Request):
    body = await request.json()
    # your logic...
    return {"commande_id": 1}
```

### Django — use `@api_doc()` decorator

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from flashapi import api_doc
import json

@api_doc(tag="Commandes", summary="Passer une commande", methods=["post"],
         body={"client_id": "int", "plats": "array"})
@csrf_exempt
def checkout(request):
    body = json.loads(request.body)
    return JsonResponse({"commande_id": 1}, status=201)
```

```python
# urls.py
from django.urls import path, include
from flashapi.django import generate_urls
from backend.models import Plat, Commande, Client
from backend import views

custom_views = [
    path("checkout/", views.checkout),
]

urlpatterns = [
    path("api/", include(
        generate_urls(models=[Plat, Commande, Client], extra_views=custom_views)
        + custom_views
    )),
]
```

### Flask — use `@api_doc()` decorator

```python
from flask import Flask, request, jsonify
from flashapi.flask import register_models
from flashapi import api_doc
from models import db, Plat, Commande, Client

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
    db.init_app(app)

    with app.app_context():
        db.create_all()
        register_models(app, models=[Plat, Commande, Client], engine=db.engine)

    # Custom route — auto-discovered in /docs
    @app.route("/checkout", methods=["POST"])
    @api_doc(tag="Commandes", summary="Passer une commande",
             body={"client_id": "int", "plats": "array"})
    def checkout():
        body = request.get_json()
        return jsonify({"commande_id": 1}), 201

    return app
```

---

## All configuration options

### FastAPI — `FlashAPI()`

```python
FlashAPI(
    models=[...],             # Required. List of model classes or Model() wrappers.
    engine=engine,            # For SQLAlchemy models: uses YOUR database.
    database="flashapi.db",   # For Pydantic/dataclass models only: SQLite file path.
    docs=True,                # Enable /docs and /redoc. Default: True.
    formatter=my_func,        # Custom response format function.
)
```

### Flask — `register_models()`

```python
register_models(
    app,                      # Your Flask app instance.
    models=[...],             # Required. List of model classes or Model() wrappers.
    engine=db.engine,         # For SQLAlchemy/Flask-SQLAlchemy: uses YOUR database.
    database="flashapi.db",   # For Pydantic/dataclass models only: SQLite file path.
    docs=True,                # Enable /docs and /openapi.json. Default: True.
    formatter=my_func,        # Custom response format function.
)
```

### Django — `generate_urls()`

```python
generate_urls(
    models=[...],             # Required. List of model classes or Model() wrappers.
    extra_views=[...],        # URL patterns with @api_doc views (auto-discovered).
    docs=True,                # Enable /docs/ and /openapi.json. Default: True.
    formatter=my_func,        # Custom response format function.
)
```

No `engine=` for Django — it always uses the Django ORM.

### When to use `engine=` vs `database=`

| Your models are... | Use | Example |
|-------------------|-----|---------|
| SQLAlchemy (raw) | `engine=engine` | `engine = create_engine("sqlite:///app.db")` |
| Flask-SQLAlchemy | `engine=db.engine` | After `db.init_app(app)` |
| Pydantic | `database="app.db"` (or omit) | File path, not a URL |
| dataclass | `database="app.db"` (or omit) | File path, not a URL |
| Django | Neither | Django ORM handles it |

---

## Related Docs

- [Features (CRUD, pagination, filtering, sorting, search)](features.md)
- [Relations (nested routes, expand)](relations.md)
- [Customization (Model wrapper, response format)](customization.md)
- [Authentication & Permissions](authentication.md)
- [Custom Logic & Coexistence](custom-logic.md)
- [Framework-Specific Notes](framework-notes.md)
- [Full Examples](examples.md)
