"""FlashAPI — Define your models. FlashAPI does the rest."""

from flashapi.core.schema import Model
from flashapi.core.custom_routes import CustomRoute, RouteParam, RouteBody, api_doc

__version__ = "0.1.0"
__all__ = ["Model", "CustomRoute", "RouteParam", "RouteBody", "api_doc"]
