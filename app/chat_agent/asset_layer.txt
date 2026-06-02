from typing import Any, Dict, List


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


# def build_assets(results: List[Dict[str, Any]], max_images: int = 6, max_links: int = 6) -> Dict[str, List[str]]:
#     images = []
#     links = []
#     sources = []
#     for item in results or []:
#         images.extend(item.get("images") or [])
#         links.extend(item.get("links") or [])
#         source = item.get("url") or item.get("file_name") or item.get("title")
#         if source:
#             sources.append(source)

#     clean_images = [normalize_url(x) for x in _unique_keep_order(images)]
#     clean_links = [normalize_url(x) for x in _unique_keep_order(links)]
#     clean_sources = _unique_keep_order(sources)

#     return {
#         "images": [x for x in clean_images if x.startswith(("http://", "https://"))][:max_images],
#         "links": [x for x in clean_links if x.startswith(("http://", "https://"))][:max_links],
#         "sources": clean_sources[:max_links],
#     }

def build_assets(
    results: List[Dict[str, Any]],
    max_images: int = 6,
    max_links: int = 6,
    intent: str = "",
    focus: str = "",
) -> Dict[str, List[str]]:
    images = []
    links = []
    sources = []

    blocked_image_words = [
        "founder", "director", "chairman", "team", "management",
        "leadership", "employee", "profile", "about"
    ]

    product_intents = {
        "product_overview",
        "product_options",
        "buying_guidance",
        "product_followup_detail",
    }

    focus = (focus or "").lower().strip()

    for item in results or []:
        item_text = " ".join([
            str(item.get("url") or ""),
            str(item.get("title") or ""),
            str(item.get("file_name") or ""),
            str(item.get("page_type") or ""),
            str(item.get("text") or ""),
            str(item.get("chunk_text") or ""),
            str(item.get("content") or ""),
        ]).lower()

        for img in item.get("images") or []:
            img_text = f"{img} {item_text}".lower()

            if intent in product_intents:
                if any(word in img_text for word in blocked_image_words):
                    continue

            if focus and focus not in img_text:
                continue

            images.append(img)

        links.extend(item.get("links") or [])

        source = item.get("url") or item.get("file_name") or item.get("title")
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