import os

from .base import BaseProductHandler


class DesiThreadProductHandler(BaseProductHandler):
    """Handler for handler_key='desithread'."""

    def get_base_image_url(self) -> str:
        return os.getenv("DESITHREAD_IMAGE_BASE_URL", "")
