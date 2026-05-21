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


def build_assets(results: List[Dict[str, Any]], max_images: int = 6, max_links: int = 6) -> Dict[str, List[str]]:
    images = []
    links = []
    sources = []
    for item in results or []:
        images.extend(item.get("images") or [])
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
