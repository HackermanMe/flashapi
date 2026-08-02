"""FlashAPI — Define your models. FlashAPI does the rest."""

from flashapi.core.custom_routes import CustomRoute, RouteBody, RouteParam, api_doc
from flashapi.core.schema import Model
from flashapi.features.auth import AuthBackend

__version__ = "0.1.0"
__all__ = ["AuthBackend", "CustomRoute", "Model", "RouteBody", "RouteParam", "api_doc"]
