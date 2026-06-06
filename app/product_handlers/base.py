from typing import Any, Dict, List, Optional


class BaseProductHandler:
    """Default product handler.

    This class keeps product_query_bot.py generic. If handler_key does not
    match any custom handler, product lookup still works and image rendering
    safely falls back to the raw URL only when item_simage is already a full URL.
    """

    def get_base_image_url(self) -> str:
        return ""

    def build_image_url(self, image_name: Optional[str]) -> str:
        image_value = str(image_name or "").strip()
        if not image_value:
            return ""

        # If DB already stores complete image URL, use it directly.
        if image_value.startswith(("http://", "https://")):
            return image_value

        base_url = self.get_base_image_url().strip().rstrip("/")
        if not base_url:
            return ""

        return f"{base_url}/{image_value.lstrip('/')}"

    def get_feature_product_image(self, rows: Optional[List[Dict[str, Any]]]) -> str:
        for row in rows or []:
            is_feature = str(row.get("is_feature_item") or "").strip()
            image_name = str(row.get("item_simage") or "").strip()

            if is_feature == "1" and image_name:
                return self.build_image_url(image_name)

        return ""
