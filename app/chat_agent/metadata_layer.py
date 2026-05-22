from typing import Any, Dict, List

PRODUCT_URL_HINTS = (
    "/product", "/products", "/catalog", "/catalogue", "/shop", "/item", "/category"
)
NOISE_URL_HINTS = (
    "privacy", "terms", "cookie", "login", "cart", "checkout", "blog", "article", "news"
)


def classify_page_type(url: str = "", title: str = "", text: str = "") -> str:
    haystack = f"{url} {title} {text[:500]}".lower()
    if any(x in haystack for x in PRODUCT_URL_HINTS):
        return "product_page"
    if "about" in haystack:
        return "about_page"
    if "contact" in haystack:
        return "contact_page"
    if any(x in haystack for x in NOISE_URL_HINTS):
        return "low_priority"
    return "general"


def enrich_result_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    item = dict(item)
    url = str(item.get("url") or item.get("source") or "")
    title = str(item.get("title") or item.get("file_name") or "")
    text = str(item.get("text") or item.get("chunk_text") or item.get("content") or "")
    item.setdefault("page_type", classify_page_type(url=url, title=title, text=text))
    return item


def rank_results_for_product_pages(results: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    q = (query or "").lower()

    def score(item: Dict[str, Any]) -> float:
        item = enrich_result_metadata(item)
        url = str(item.get("url") or item.get("source") or "").lower()
        title = str(item.get("title") or item.get("file_name") or "").lower()
        text = str(item.get("text") or item.get("chunk_text") or item.get("content") or "").lower()
        tags = " ".join([str(x).lower() for x in item.get("tags") or []])
        links = " ".join([str(x).lower() for x in item.get("links") or []])
        base = float(item.get("rank_score") or item.get("score") or 0.0)
        bonus = 0.0
        if item.get("page_type") == "product_page":
            bonus += 0.30
        if any(x in url for x in PRODUCT_URL_HINTS):
            bonus += 0.25
        if "product" in title or "catalog" in title or "catalogue" in title:
            bonus += 0.20
        if item.get("images"):
            bonus += 0.08
        if item.get("links"):
            bonus += 0.06
        try:
            bonus += min(0.20, max(0.0, float(item.get("priority") or 0)) / 100.0)
        except Exception:
            pass
        if any(x in url for x in NOISE_URL_HINTS):
            bonus -= 0.30
        for token in q.split():
            if len(token) >= 4 and (token in title or token in url or token in tags or token in links):
                bonus += 0.05
            elif len(token) >= 4 and token in text:
                bonus += 0.02
        return base + bonus

    return sorted([enrich_result_metadata(x) for x in results or []], key=score, reverse=True)
