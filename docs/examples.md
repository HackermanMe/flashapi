# Full Examples

[Back to main README](../README.md)

---

## Table of Contents

- [Restaurant (FastAPI + SQLAlchemy)](#restaurant-fastapi--sqlalchemy)
- [Library (Flask + Flask-SQLAlchemy)](#library-flask--flask-sqlalchemy)
- [E-Commerce (FastAPI + Pydantic)](#e-commerce-fastapi--pydantic)
- [School Management (Django)](#school-management-django)
- [Blog (Flask + Pydantic)](#blog-flask--pydantic)
- [Multi-tenant SaaS (Django)](#multi-tenant-saas-django)
- [Minimal API (dataclass)](#minimal-api-dataclass)

---

## Restaurant (FastAPI + SQLAlchemy)

**Real-world project with a real database. Most common use case.**

### File structure
```
gestionRestaurant/
├── main.py
├── models.py
├── database.py
└── restaurant.db
```

### `database.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///./restaurant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass
```

### `models.py`
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
    temps_preparation = Column(Integer, nullable=True)
    est_vegetarien = Column(Boolean, default=False)
    categorie = relationship('CategorieMenu', back_populates='plats')

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String(100), nullable=False)
    telephone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)

class TableRestaurant(Base):
    __tablename__ = 'tables'
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(Integer, nullable=False, unique=True)
    capacite = Column(Integer, nullable=False)
    est_libre = Column(Boolean, default=True)

class Commande(Base):
    __tablename__ = 'commandes'
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    table_id = Column(Integer, ForeignKey('tables.id'), nullable=False)
    statut = Column(String(20), default='en_cours')
    montant_total = Column(Numeric(10, 2), default=0)

class LigneCommande(Base):
    __tablename__ = 'lignes_commande'
    id = Column(Integer, primary_key=True, index=True)
    commande_id = Column(Integer, ForeignKey('commandes.id'), nullable=False)
    plat_id = Column(Integer, ForeignKey('plats.id'), nullable=False)
    quantite = Column(Integer, default=1)
    prix_unitaire = Column(Numeric(8, 2), nullable=False)
```

### `main.py`
```python
from flashapi.fastapi import FlashAPI
from flashapi import Model
from database import engine, Base
from models import CategorieMenu, Plat, Client, TableRestaurant, Commande, LigneCommande

# Create tables
Base.metadata.create_all(bind=engine)

# FlashAPI — one line
app = FlashAPI(
    models=[
        CategorieMenu,
        Plat,
        Client,
        Model(TableRestaurant, plural="tables"),
        Model(Commande, exclude=["delete"]),
        LigneCommande,
    ],
    engine=engine,
).app
```

### Run
```bash
pip install flashapi[fastapi] sqlalchemy
uvicorn main:app --reload
```

### What you get
```
GET/POST     /categories_menu          CRUD for categories
GET/PUT/DEL  /categories_menu/{id}
GET/POST     /plats                    CRUD for dishes
GET/PUT/DEL  /plats/{id}
GET/POST     /clients                  CRUD for clients
GET/PUT/DEL  /clients/{id}
GET/POST     /tables                   Custom plural name
GET/PUT/DEL  /tables/{id}
GET/POST     /commandes                No DELETE (exclude=["delete"])
GET/PUT      /commandes/{id}
GET/POST     /lignes_commande
GET/PUT/DEL  /lignes_commande/{id}
GET          /categories_menu/{id}/plats     Nested (auto-detected)
GET          /clients/{id}/commandes         Nested (auto-detected)
GET          /commandes/{id}/lignes_commande Nested (auto-detected)
GET          /docs                           Swagger UI
```

All data goes to `restaurant.db`. No extra database.

---

## Library (Flask + Flask-SQLAlchemy)

**Real-world Flask project with Flask-SQLAlchemy.**

### File structure
```
gestionBibliotheque/
├── app.py
├── models.py
└── instance/
    └── bibliotheque.db
```

### `models.py`
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

class Editeur(db.Model):
    __tablename__ = 'editeurs'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    adresse = db.Column(db.String(300))

class Categorie(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    livres = db.relationship('Livre', back_populates='categorie')

class Livre(db.Model):
    __tablename__ = 'livres'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(13), unique=True)
    auteur_id = db.Column(db.Integer, db.ForeignKey('auteurs.id'), nullable=False)
    categorie_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    editeur_id = db.Column(db.Integer, db.ForeignKey('editeurs.id'))
    annee_publication = db.Column(db.Integer)
    auteur = db.relationship('Auteur', back_populates='livres')
    categorie = db.relationship('Categorie', back_populates='livres')

class Adherent(db.Model):
    __tablename__ = 'adherents'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True)
    telephone = db.Column(db.String(20))
    actif = db.Column(db.Boolean, default=True)

class Emprunt(db.Model):
    __tablename__ = 'emprunts'
    id = db.Column(db.Integer, primary_key=True)
    livre_id = db.Column(db.Integer, db.ForeignKey('livres.id'), nullable=False)
    adherent_id = db.Column(db.Integer, db.ForeignKey('adherents.id'), nullable=False)
    date_emprunt = db.Column(db.String(10), nullable=False)
    date_retour_prevue = db.Column(db.String(10), nullable=False)
    date_retour_effective = db.Column(db.String(10))
    rendu = db.Column(db.Boolean, default=False)

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    livre_id = db.Column(db.Integer, db.ForeignKey('livres.id'), nullable=False)
    adherent_id = db.Column(db.Integer, db.ForeignKey('adherents.id'), nullable=False)
    date_reservation = db.Column(db.String(10), nullable=False)
    statut = db.Column(db.String(20), default='en_attente')

class Amende(db.Model):
    __tablename__ = 'amendes'
    id = db.Column(db.Integer, primary_key=True)
    emprunt_id = db.Column(db.Integer, db.ForeignKey('emprunts.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    payee = db.Column(db.Boolean, default=False)

class Personnel(db.Model):
    __tablename__ = 'personnel'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(200))
```

### `app.py`
```python
from flask import Flask
from flashapi.flask import register_models
from flashapi import Model
from models import db, Auteur, Editeur, Categorie, Livre, Adherent, Emprunt, Reservation, Amende, Personnel


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bibliotheque.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Step 1: Init Flask-SQLAlchemy
    db.init_app(app)

    with app.app_context():
        # Step 2: Create tables
        db.create_all()

        # Step 3: Register FlashAPI (INSIDE app_context, with engine=db.engine)
        register_models(app, models=[
            Auteur,
            Editeur,
            Categorie,
            Livre,
            Adherent,
            Model(Emprunt, exclude=["delete"]),
            Reservation,
            Model(Amende, exclude=["delete"]),
            Model(Personnel, readonly=True),
        ], engine=db.engine)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
```

### Run
```bash
pip install flashapi[flask] flask-sqlalchemy
python app.py
```

### What you get
```
http://localhost:5000/docs        → Swagger UI
http://localhost:5000/auteurs     → GET (list), POST (create)
http://localhost:5000/livres      → Full CRUD
http://localhost:5000/adherents   → Full CRUD
http://localhost:5000/emprunts    → No DELETE
http://localhost:5000/personnel   → Read-only (GET list + GET detail)
http://localhost:5000/auteurs/1/livres  → Nested list
```

All data in `bibliotheque.db`. No extra database.

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
# gestionEcole/auth_backend.py
from flashapi import AuthBackend

class EcoleAuth(AuthBackend):
    def authenticate(self, request):
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"           # Super-admin (multi-school platform)
        if user.groups.filter(name="directeurs").exists():
            return "staff"           # School director
        return "authenticated"       # Teacher

    def get_tenant_id(self, user):
        return getattr(user, 'ecole_id', None)

    def get_owner_id(self, user):
        return user.pk
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
from .auth_backend import EcoleAuth

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(
        models=[
            # Reference data — public read, admin write
            Model(AnneeScolaire,
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin", "delete": "admin"}),
            Model(Niveau, plural="niveaux",
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin", "delete": "admin"}),

            # School-scoped — staff+ can CRUD, isolated per school
            Model(Classe, access="staff", scope="tenant", tenant_field="ecole_id"),
            Model(Enseignant, access="staff", scope="tenant", tenant_field="ecole_id"),
            Model(Eleve, access="staff", scope="tenant", tenant_field="ecole_id",
                  soft_delete=True, audit=True),

            # Notes — isolated by school AND teacher
            Model(Note, access="authenticated", scope="both",
                  tenant_field="ecole_id", owner_field="enseignant_id", audit=True),
        ],
        auth_backend=EcoleAuth(),
    ))),
]
```

**Generated endpoints:**
```
GET          /api/                              (API Root — resource index)
GET/POST     /api/anneescolaires/              (public read, admin write)
GET/PUT/DEL  /api/anneescolaires/{id}/
GET/POST     /api/niveaux/                     (public read, admin write)
GET/PUT/DEL  /api/niveaux/{id}/
GET/POST     /api/classes/                     (staff+, school-scoped)
GET/PUT/DEL  /api/classes/{id}/
GET/POST     /api/enseignants/                 (staff+, school-scoped)
GET/PUT/DEL  /api/enseignants/{id}/
GET/POST     /api/eleves/                      (staff+, school-scoped, soft delete + audit)
GET/PUT/DEL  /api/eleves/{id}/
POST         /api/eleves/{id}/restore          (soft delete enabled)
GET          /api/eleves/{id}/history          (audit enabled)
GET/POST     /api/notes/                       (auth, teacher sees only own notes)
GET/PUT/DEL  /api/notes/{id}/
GET          /api/niveaux/{id}/classes/        (nested)
GET          /api/classes/{id}/eleves/         (nested)
GET          /api/eleves/{id}/notes/           (nested)
GET          /api/docs/                        (Swagger UI)
```

**Usage examples:**
```bash
# Public — anyone can list school years (no auth needed)
curl http://localhost:8000/api/anneescolaires/

# Director (staff, ecole_id=1) lists students — sees only their school
curl -H "Cookie: sessionid=directeur_session" http://localhost:8000/api/eleves/

# Director creates a student — ecole_id=1 auto-injected
curl -X POST -H "Cookie: sessionid=directeur_session" \
  -H "Content-Type: application/json" \
  -d '{"matricule": "E001", "nom": "Dupont", "prenom": "Marie", "date_naissance": "2010-05-15", "sexe": "F"}' \
  http://localhost:8000/api/eleves/

# Teacher (authenticated, ecole_id=1) lists notes — sees only their own notes
curl -H "Cookie: sessionid=teacher_session" http://localhost:8000/api/notes/

# Teacher from school 2 cannot see school 1's students → 404
curl -H "Cookie: sessionid=other_school_teacher" http://localhost:8000/api/eleves/1/

# Super-admin sees ALL data across all schools (admin bypass)
curl -H "Cookie: sessionid=superadmin_session" http://localhost:8000/api/eleves/

# View audit trail for a student
curl -H "Cookie: sessionid=directeur_session" http://localhost:8000/api/eleves/1/history
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

A real multi-tenant SaaS with auth, tenant isolation, and role-based access.

```python
# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    organization_id = models.IntegerField(null=True, blank=True)

class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    plan = models.CharField(max_length=20, default="free")

class Project(models.Model):
    name = models.CharField(max_length=200)
    organization_id = models.IntegerField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Task(models.Model):
    title = models.CharField(max_length=200)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    organization_id = models.IntegerField()
    assigned_to_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="todo")
    priority = models.IntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)

class Invoice(models.Model):
    organization_id = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid = models.BooleanField(default=False)
    issued_at = models.DateTimeField(auto_now_add=True)

class Notification(models.Model):
    user_id = models.IntegerField()
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
```

```python
# auth_backend.py
from flashapi import AuthBackend

class SaaSAuth(AuthBackend):
    def authenticate(self, request):
        if request.user.is_authenticated:
            return request.user
        return None

    def get_role(self, user):
        if user.is_superuser:
            return "admin"          # Platform admin — sees all orgs
        if user.is_staff:
            return "staff"          # Org admin — manages their org
        return "authenticated"      # Regular member

    def get_tenant_id(self, user):
        return user.organization_id

    def get_owner_id(self, user):
        return user.pk
```

```python
# urls.py
from django.contrib import admin
from django.urls import path, include
from flashapi.django import generate_urls
from flashapi import Model
from myapp.models import Organization, Project, Task, Invoice, Notification
from myapp.auth_backend import SaaSAuth

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(generate_urls(
        models=[
            # Platform-level (admin only for write)
            Model(Organization, exclude=["delete"],
                  access={"list": "public", "read": "public", "create": "admin", "update": "admin"}),

            # Org-wide data (all members see their org's data)
            Model(Project, access="authenticated", scope="tenant", tenant_field="organization_id"),
            Model(Task, access="authenticated", scope="tenant", tenant_field="organization_id",
                  soft_delete=True, audit=True),

            # Billing (org admins only)
            Model(Invoice, access="staff", scope="tenant", tenant_field="organization_id",
                  audit=True, exclude=["delete"]),

            # Personal (each user only sees their own)
            Model(Notification, access="authenticated", scope="owner", owner_field="user_id",
                  exclude=["create", "update"]),
        ],
        auth_backend=SaaSAuth(),
    ))),
]
```

**What happens:**
```bash
# Alice (org_id=1, role=authenticated) lists tasks → sees only org 1's tasks
curl -H "Cookie: sessionid=alice_session" http://localhost:8000/api/tasks/

# Alice creates a task → organization_id=1 auto-injected
curl -X POST -H "Cookie: sessionid=alice_session" \
  -H "Content-Type: application/json" \
  -d '{"title": "Fix bug", "status": "todo", "priority": 1}' \
  http://localhost:8000/api/tasks/

# Bob (org_id=2) tries to access Alice's task → 404 (not 403)
curl -H "Cookie: sessionid=bob_session" http://localhost:8000/api/tasks/1/

# Platform admin sees ALL tasks across all orgs
curl -H "Cookie: sessionid=admin_session" http://localhost:8000/api/tasks/

# Staff (org admin) can see invoices, regular members cannot
curl -H "Cookie: sessionid=alice_session" http://localhost:8000/api/invoices/
# → 403 Forbidden (alice is "authenticated", needs "staff")

# Notifications: each user only sees their own
curl -H "Cookie: sessionid=alice_session" http://localhost:8000/api/notifications/
# → Only Alice's notifications
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
