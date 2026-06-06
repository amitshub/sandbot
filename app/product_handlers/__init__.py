from .base import BaseProductHandler
from .desipos import DesiPosProductHandler
from .desithread import DesiThreadProductHandler


HANDLER_MAP = {
    "desipos": DesiPosProductHandler,
    "desithread": DesiThreadProductHandler,
}


def get_product_handler(handler_key: str = ""):
    """Return product handler based on tenant_agents.handler_key.

    handler_key should match the handler mapping key, for example:
    - desipos -> desipos.py
    - desithread -> desithread.py

    Unknown or empty handler_key safely uses BaseProductHandler.
    """
    normalized_key = str(handler_key or "").strip().lower()
    handler_class = HANDLER_MAP.get(normalized_key, BaseProductHandler)
    return handler_class()
