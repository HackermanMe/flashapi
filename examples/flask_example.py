"""
FlashAPI + Flask — Minimal example.

Run:
    pip install flashapi[flask]
    flask --app examples.flask_example run

Then open http://localhost:5000/users
"""

from dataclasses import dataclass

from flask import Flask

from flashapi import Model
from flashapi.flask import register_models


@dataclass
class User:
    name: str
    email: str


@dataclass
class Article:
    title: str
    content: str
    published: bool = False


app = Flask(__name__)
register_models(app, models=[User, Model(Article, readonly=True)])
