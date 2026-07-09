# Full Examples

[Back to main README](../README.md)

---

## Table of Contents

- [E-Commerce (FastAPI + Pydantic)](#e-commerce-fastapi--pydantic)
- [School Management (Django)](#school-management-django)
- [Restaurant (FastAPI + Pydantic)](#restaurant-fastapi--pydantic)
- [Blog (Flask + Pydantic)](#blog-flask--pydantic)
- [Multi-tenant SaaS (Django)](#multi-tenant-saas-django)
- [Minimal API (dataclass)](#minimal-api-dataclass)

---

## E-Commerce (FastAPI + Pydantic)

```python
# main.py
from pydantic import BaseModel
from flashapi import Model
from flashapi.fastapi import FlashAPI
from fastapi import Request, HTTPException

# === Models ===

class Category(BaseModel):
    name: str
    description: str = ""

class Product(BaseModel):
    name: str
    price: float
    category_id: int
    in_stock: bool = True
    description: str = ""
    image_url: str = ""

class Customer(BaseModel):
    name: str
    email: str
    phone: str = ""

class Order(BaseModel):
    customer_id: int
    total: float = 0
    status: str = "pending"

class OrderLine(BaseModel):
    order_id: int
    product_id: int
    quantity: int = 1
    unit_price: float = 0

# === FlashAPI setup ===

flash = FlashAPI(
    models=[
        Category,
        Product,
        Customer,
        Model(Order, exclude=["delete"]),       # Orders can't be deleted
        Model(OrderLine, exclude=["delete"]),   # Order lines can't be deleted
    ],
    database="shop.db",
)
app = flash.app

# === Custom business logic ===

@app.post("/checkout", tags=["Business Logic"])
async def checkout(request: Request):
    """Create an order from a list of items."""
    body = await request.json()
    customer_id = body["customer_id"]
    items = body["items"]  # [{"product_id": 1, "quantity": 2}, ...]

    # Validate customer
    customer = flash._storage.get("customers", customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Calculate total and validate products
    total = 0
    line_items = []
    for item in items:
        product = flash._storage.get("products", item["product_id"])
        if not product:
            raise HTTPException(400, f"Product {item['product_id']} not found")
        if not product["in_stock"]:
            raise HTTPException(400, f"Product '{product['name']}' is out of stock")

        line_total = product["price"] * item["quantity"]
        total += line_total
        line_items.append({
            "product_id": product["id"],
            "quantity": item["quantity"],
            "unit_price": product["price"],
        })

    # Create order
    order = flash._storage.create("orders", {
        "customer_id": customer_id,
        "total": total,
        "status": "confirmed",
    })

    # Create order lines
    for line in line_items:
        flash._storage.create("orderlines", {**line, "order_id": order["id"]})

    return {
        "data": {
            "order_id": order["id"],
            "total": total,
            "items_count": len(line_items),
            "status": "confirmed",
        }
    }
```

**Run:**
```bash
uvicorn main:app --reload
# Open http://localhost:8000/docs
```

**Generated endpoints:**
```
GET/POST     /categories
GET/PUT/DEL  /categories/{id}
GET/POST     /products
GET/PUT/DEL  /products/{id}
GET/POST     /customers
GET/PUT/DEL  /customers/{id}
GET/POST     /orders              (no DELETE)
GET/PUT      /orders/{id}         (no DELETE)
GET/POST     /orderlines          (no DELETE)
GET/PUT      /orderlines/{id}     (no DELETE)
GET          /categories/{id}/products    (nested)
GET          /customers/{id}/orders       (nested)
GET          /orders/{id}/orderlines      (nested)
GET          /products?expand=category    (expand)
GET          /orders?expand=customer      (expand)
POST         /checkout                    (custom)
```

---

## School Management (Django)

```python
# backend/models.py
from django.db import models

class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=50)
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_active = models.BooleanField(default=True)

class Niveau(models.Model):
    nom = models.CharField(max_length=50)
    description = models.TextField(blank=True)

class Classe(models.Model):
    nom = models.CharField(max_length=50)
    niveau = models.ForeignKey(Niveau, on_delete=models.CASCADE)
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    capacite_max = models.IntegerField(default=30)

class Enseignant(models.Model):
    matricule = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    date_embauche = models.DateField()

class Eleve(models.Model):
    matricule = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField()
    sexe = models.CharField(max_length=1)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to="eleves/", blank=True, null=True)

class Note(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    matiere = models.CharField(max_length=100)
    valeur = models.DecimalField(max_digits=5, decimal_places=2)
    date = models.DateField()
    commentaire = models.TextField(blank=True)
```

```python
# gestionEcole/urls.py
from django.contrib import admin
from django.urls import path, include
from flashapi.django import generate_urls
from flashapi import Model
from backend.models import (
    AnneeScolaire, Niveau, Classe, Enseignant, Eleve, Note
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(
        models=[
            AnneeScolaire,
            Model(Niveau, plural="niveaux"),
            Classe,
            Enseignant,
            Eleve,
            Note,
        ]
    ))),
]
```

**Generated endpoints:**
```
GET/POST     /api/anneescolaires/
GET/PUT/DEL  /api/anneescolaires/{id}/
GET/POST     /api/niveaux/
GET/PUT/DEL  /api/niveaux/{id}/
GET/POST     /api/classes/
GET/PUT/DEL  /api/classes/{id}/
GET/POST     /api/enseignants/
GET/PUT/DEL  /api/enseignants/{id}/
GET/POST     /api/eleves/
GET/PUT/DEL  /api/eleves/{id}/
GET/POST     /api/notes/
GET/PUT/DEL  /api/notes/{id}/
GET          /api/niveaux/{id}/classes/        (nested)
GET          /api/classes/{id}/eleves/         (nested)
GET          /api/eleves/{id}/notes/           (nested)
GET          /api/classes/?expand=niveau       (expand)
GET          /api/eleves/?expand=classe        (expand)
GET          /api/docs/                        (Swagger UI)
```

**Usage examples:**
```bash
# Create a school year
curl -X POST http://localhost:8000/api/anneescolaires/ \
  -H "Content-Type: application/json" \
  -d '{"libelle": "2024-2025", "date_debut": "2024-09-01", "date_fin": "2025-06-30", "est_active": true}'

# List students in class 1
curl http://localhost:8000/api/classes/1/eleves/

# Get a student with class details
curl http://localhost:8000/api/eleves/1/?expand=classe

# Search students by name
curl http://localhost:8000/api/eleves/?search=dupont

# Filter notes by student
curl http://localhost:8000/api/notes/?eleve_id=1&sort=-valeur
```

---

## Restaurant (FastAPI + Pydantic)

```python
# main.py
from pydantic import BaseModel
from flashapi import Model
from flashapi.fastapi import FlashAPI

class CategorieMenu(BaseModel):
    nom: str
    description: str = ""

class Plat(BaseModel):
    nom: str
    prix: float
    categorie_id: int
    disponible: bool = True
    description: str = ""

class Ingredient(BaseModel):
    nom: str
    unite: str = "kg"
    stock: float = 0

class PlatIngredient(BaseModel):
    plat_id: int
    ingredient_id: int
    quantite: float

class TableRestaurant(BaseModel):
    numero: int
    capacite: int
    est_libre: bool = True

class Client(BaseModel):
    nom: str
    telephone: str
    email: str = ""

class Reservation(BaseModel):
    client_id: int
    table_id: int
    date: str
    heure: str
    nombre_personnes: int
    statut: str = "confirmee"

class Commande(BaseModel):
    table_id: int
    statut: str = "en_cours"
    montant_total: float = 0

class LigneCommande(BaseModel):
    commande_id: int
    plat_id: int
    quantite: int = 1
    prix_unitaire: float = 0

class Paiement(BaseModel):
    commande_id: int
    montant: float
    mode: str = "carte"
    statut: str = "effectue"

class Employe(BaseModel):
    nom: str
    prenom: str
    poste: str
    telephone: str = ""

app = FlashAPI(
    models=[
        CategorieMenu,
        Plat,
        Ingredient,
        PlatIngredient,
        TableRestaurant,
        Client,
        Reservation,
        Commande,
        LigneCommande,
        Model(Paiement, exclude=["delete"]),
        Employe,
    ],
    database="restaurant.db",
).app
```

```bash
uvicorn main:app --reload
# All CRUD ready at http://localhost:8000/docs
```

---

## Blog (Flask + Pydantic)

```python
# app.py
from flask import Flask
from pydantic import BaseModel
from flashapi import Model
from flashapi.flask import register_models

class Author(BaseModel):
    name: str
    email: str
    bio: str = ""

class Category(BaseModel):
    name: str
    slug: str

class Post(BaseModel):
    title: str
    slug: str
    content: str
    author_id: int
    category_id: int
    published: bool = False

class Comment(BaseModel):
    post_id: int
    author_name: str
    content: str
    approved: bool = False

app = Flask(__name__)

register_models(app, models=[
    Author,
    Category,
    Post,
    Model(Comment, exclude=["update"]),  # Comments can't be edited
])

if __name__ == "__main__":
    app.run(debug=True)
```

```bash
python app.py
# Open http://localhost:5000/docs
```

---

## Multi-tenant SaaS (Django)

```python
# models.py
from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    plan = models.CharField(max_length=20, default="free")

class Project(models.Model):
    name = models.CharField(max_length=200)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    title = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    assigned_to = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, default="todo")
    priority = models.IntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)


# urls.py
from django.urls import path, include
from flashapi.django import generate_urls
from flashapi import Model
from myapp.models import Organization, Project, Task

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(
        models=[
            Model(Organization, exclude=["delete"]),  # Can't delete orgs via API
            Project,
            Task,
        ]
    ))),
]
```

**Usage:**
```bash
# List all tasks in project 1
curl http://localhost:8000/api/projects/1/tasks/

# Filter tasks by status
curl http://localhost:8000/api/tasks/?status=todo&sort=priority

# Get task with project details
curl http://localhost:8000/api/tasks/1/?expand=project

# Search across all tasks
curl http://localhost:8000/api/tasks/?search=refactor
```

---

## Minimal API (dataclass)

The simplest possible FlashAPI usage — no framework knowledge needed:

```python
# main.py
from dataclasses import dataclass
from flashapi.fastapi import FlashAPI

@dataclass
class Todo:
    title: str
    done: bool = False

@dataclass
class Note:
    content: str
    tag: str = ""

app = FlashAPI(models=[Todo, Note], database="todos.db").app
```

```bash
pip install flashapi[fastapi]
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` — full CRUD for Todo and Note is ready.

---

## Related Docs

- [Integration Guide](integration.md)
- [Features](features.md)
- [Relations](relations.md)
- [Customization](customization.md)
- [Authentication & Permissions](authentication.md)
- [Custom Logic & Coexistence](custom-logic.md)
