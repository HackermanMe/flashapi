"""
FlashAPI + FastAPI — Minimal example.

Run:
    pip install flashapi[fastapi]
    uvicorn examples.fastapi_example:app --reload

Then open http://localhost:8000/docs
"""

from pydantic import BaseModel

from flashapi import Model
from flashapi.fastapi import FlashAPI


class User(BaseModel):
    name: str
    email: str


class Product(BaseModel):
    title: str
    price: float
    in_stock: bool = True


# One line — full CRUD API with docs
flash = FlashAPI(
    models=[
        User,
        Model(Product, exclude=["delete"]),
    ]
)

app = flash.app
