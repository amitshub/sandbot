import os

from .base import BaseProductHandler


class DesiPosProductHandler(BaseProductHandler):
    """Handler for handler_key='desipos'."""

    def get_base_image_url(self) -> str:
        return os.getenv("DESIPOS_IMAGE_BASE_URL", "")
