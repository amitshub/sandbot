from typing import Any, Dict, List
import re


def _unique_keep_order(values):
    seen = set()
    output = []
    for value in values or []:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if "." in url and " " not in url:
        return "https://" + url.lstrip("/")
    return url


def _item_text(item: Dict[str, Any]) -> str:
    return " ".join([
        str(item.get("url") or item.get("source_url") or item.get("source") or ""),
        str(item.get("title") or ""),
        str(item.get("file_name") or ""),
        str(item.get("page_type") or ""),
        " ".join(str(x) for x in (item.get("tags") or [])),
        str(item.get("text") or ""),
        str(item.get("answer_text") or ""),
        str(item.get("chunk_text") or ""),
        str(item.get("content") or ""),
    ]).lower()


def _is_product_asset_item(item: Dict[str, Any]) -> bool:
    """Allow product images only from product/catalogue related KB chunks/pages."""
    text = _item_text(item)
    page_type = str(item.get("page_type") or "").lower().strip()

    product_page_types = {
        "product_page",
        "products_page",
        "catalog_page",
        "catalogue_page",
        "catalog",
        "catalogue",
    }

    if page_type in product_page_types:
        return True

    non_product_words = [
        "career", "careers", "job", "jobs", "hiring", "vacancy", "resume", "cv",
        "founder", "director", "chairman", "team", "management", "leadership",
        "testimonial", "review", "csr", "charity", "blog", "article", "about",
        "board", "contact", "office", "address",
    ]
    if any(word in text for word in non_product_words):
        return False

    product_words = [
        "/product", "product.html", "products", "catalog", "catalogue", "pipe", "pipes",
        "fitting", "fittings", "elbow", "tee", "adapter", "adaptor", "coupling",
        "coupler", "socket", "bend", "reducer", "press", "end cap", "socket",
        "male elbow", "female elbow", "pipe bridge", "branch tee",
    ]
    return any(word in text for word in product_words)


def _image_looks_non_product(image_url: str, item: Dict[str, Any]) -> bool:
    text = f"{image_url} {_item_text(item)}".lower()
    blocked_image_words = [
        "career", "careers", "job", "jobs", "hiring", "vacancy", "resume", "cv",
        "founder", "director", "chairman", "team", "management", "leadership",
        "employee", "profile", "about", "board", "testimonial", "csr", "charity",
        "blog", "article", "contact", "office", "banner", "logo",
    ]
    return any(word in text for word in blocked_image_words)


def _is_product_page(item: Dict[str, Any]) -> bool:
    page_type = str(item.get("page_type") or "").lower().strip()
    text = _item_text(item)
    return page_type in {"product_page", "products_page"} or "product.html" in text or "/product" in text


def build_assets(
    results: List[Dict[str, Any]],
    max_images: int = 12,
    max_links: int = 6,
    intent: str = "",
    focus: str = "",
) -> Dict[str, List[str]]:
    images = []
    links = []
    sources = []

    intent = (intent or "").strip()
    focus = (focus or "").lower().strip()
    is_image_request = intent == "image_request"
    is_product_intent = intent in {
        "image_request", "product_overview", "product_options", "buying_guidance", "product_followup_detail",
    }

    ordered_results = list(results or [])
    if is_product_intent:
        # Product page first, then other product-related chunks, then everything else.
        ordered_results.sort(key=lambda item: (0 if _is_product_page(item) else 1 if _is_product_asset_item(item) else 2))

    for item in ordered_results:
        is_product_item = _is_product_asset_item(item)

        for img in item.get("images") or []:
            img = str(img or "").strip()
            if not img:
                continue

            if is_product_intent:
                if not is_product_item:
                    continue
                if _image_looks_non_product(img, item):
                    continue

            img_text = f"{img} {_item_text(item)}".lower()

            # For direct image requests, filter by product name/focus using the image filename.
            # Example: focus "equal tee" should match "equal-tee.png" and skip elbow images.
            if focus:
                focus_words = [
                    word.strip()
                    for word in re.split(r"[\s_-]+", focus.lower())
                    if len(word.strip()) >= 3
                ]

                if is_image_request:
                    file_name = img.lower().split("/")[-1]
                    if focus_words and not any(word in file_name for word in focus_words):
                        continue
                else:
                    if focus not in img_text:
                        continue

            images.append(img)

        # Links are returned only by engine/chatbot when customer asks for links.
        links.extend(item.get("links") or item.get("important_links") or [])

        source = item.get("url") or item.get("source_url") or item.get("file_name") or item.get("title")
        if source:
            sources.append(source)

    clean_images = [normalize_url(x) for x in _unique_keep_order(images)]
    clean_links = [normalize_url(x) for x in _unique_keep_order(links)]
    clean_sources = _unique_keep_order(sources)

    return {
        "images": [x for x in clean_images if x.startswith(("http://", "https://"))][:max_images],
        "links": [x for x in clean_links if x.startswith(("http://", "https://"))][:max_links],
        "sources": clean_sources[:max_links],
    }
