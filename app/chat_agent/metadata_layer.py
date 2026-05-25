from typing import Any, Dict, List
import re

PRODUCT_URL_HINTS = (
    "/product", "/products", "/catalog", "/catalogue", "/shop", "/item", "/category", "product", "products"
)
CONTACT_URL_HINTS = (
    "contact", "contact-us", "contact_us", "enquiry", "inquiry", "support", "customer-care"
)
COMPANY_URL_HINTS = (
    "about", "about-us", "company", "profile", "who-we-are", "who_we_are"
)
SERVICE_URL_HINTS = (
    "service", "services", "installation", "technical", "support"
)
CERTIFICATION_URL_HINTS = (
    "certificate", "certification", "certified", "iso", "bis", "isi", "approved", "quality", "standard", "compliance"
)
NOISE_URL_HINTS = (
    "privacy", "terms", "cookie", "login", "cart", "checkout", "blog", "article", "news", "refund", "disclaimer"
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(query: str) -> List[str]:
    return [
        t for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9&./-]{2,}", (query or "").lower())
        if len(t) >= 3
    ]


def detect_query_intent(query: str = "") -> str:
    q = (query or "").lower()
    if any(x in q for x in [
        "contact", "phone", "mobile", "call", "email", "mail", "address", "location",
        "reach", "whatsapp", "connect", "enquiry", "inquiry", "customer care", "support number",
    ]):
        return "contact"
    if any(x in q for x in [
        "certificate", "certification", "certified", "iso", "bis", "isi",
        "approved", "standard", "quality", "compliance",
    ]):
        return "certification"
    if any(x in q for x in [
        "product", "products", "catalog", "catalogue", "item", "items", "model", "models",
        "range", "category", "categories", "sell", "provide", "buy", "price", "pricing",
        "rate", "cost", "quote", "quotation", "image", "images", "photo", "picture",
        "link", "page", "specification", "size",
    ]):
        return "product"
    if any(x in q for x in ["about", "company", "business", "profile", "who are you", "manufacturer", "brand"]):
        return "company"
    if any(x in q for x in ["service", "installation", "repair", "warranty", "technical", "help"]):
        return "support"
    return "general"


def classify_page_type(url: str = "", title: str = "", text: str = "") -> str:
    """
    Classify page type safely.
    Important: contact/about/product decisions are based primarily on URL/title.
    Body text can contain common CTA lines like 'Contact Now', so it must not turn
    an about page into a contact page.
    """
    url_title = f"{url or ''} {title or ''}".lower()
    body = (text or "")[:700].lower()

    if any(x in url_title for x in NOISE_URL_HINTS):
        if any(x in url_title for x in ["blog", "article", "news"]):
            return "blog_page"
        return "policy_page"

    if any(x in url_title for x in CERTIFICATION_URL_HINTS):
        return "certification_page"

    if any(x in url_title for x in CONTACT_URL_HINTS):
        return "contact_page"

    if any(x in url_title for x in COMPANY_URL_HINTS):
        return "company_page"

    if any(x in url_title for x in PRODUCT_URL_HINTS):
        return "product_page"

    if any(x in url_title for x in SERVICE_URL_HINTS):
        return "service_page"

    # Body fallback is allowed only for strong product/service evidence, not contact.
    if any(x in body for x in ["certificate", "certification", "certified", "iso", "bis", "isi", "approved", "quality standard", "compliance"]):
        return "certification_page"
    if any(x in body for x in ["catalogue", "catalog", "product range", "specification", "stainless steel", "fittings", "pipes"]):
        return "product_page"
    if any(x in body for x in ["installation", "service", "technical support", "warranty"]):
        return "service_page"

    return "website_page"


def enrich_result_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    item = dict(item)
    url = _safe_text(item.get("url") or item.get("source_url") or item.get("source") or "")
    title = _safe_text(item.get("title") or item.get("file_name") or "")
    text = _safe_text(item.get("text") or item.get("answer_text") or item.get("chunk_text") or item.get("content") or "")

    page_type = _safe_text(item.get("page_type"))
    if not page_type or page_type in {"general", "website"}:
        page_type = classify_page_type(url=url, title=title, text=text)

    item["page_type"] = page_type
    item.setdefault("source_url", url)
    item.setdefault("url", url)
    item.setdefault("title", title or url or "trained data")
    return item


def rank_results_for_product_pages(results: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    """Backward-compatible function name; ranking is now sales/support intent-aware."""
    q = (query or "").lower()
    intent = detect_query_intent(q)
    query_tokens = _tokens(q)

    def score(item: Dict[str, Any]) -> float:
        item = enrich_result_metadata(item)
        url = _safe_text(item.get("url") or item.get("source_url") or item.get("source")).lower()
        title = _safe_text(item.get("title") or item.get("file_name")).lower()
        text = _safe_text(item.get("text") or item.get("answer_text") or item.get("chunk_text") or item.get("content")).lower()
        page_type = _safe_text(item.get("page_type")).lower()
        tags = " ".join([str(x).lower() for x in item.get("tags") or []])
        links = " ".join([str(x).lower() for x in (item.get("important_links") or item.get("links") or [])])
        base = float(item.get("rank_score") or item.get("score") or 0.0)
        haystack = f"{url} {title} {page_type} {tags} {links} {text[:900]}"

        bonus = 0.0
        try:
            bonus += min(0.18, max(0.0, float(item.get("priority") or 0)) / 100.0)
        except Exception:
            pass

        if intent == "contact":
            if page_type in {"contact_page", "support_page"}:
                bonus += 0.45
            if any(x in url or x in title for x in CONTACT_URL_HINTS):
                bonus += 0.35
            if item.get("answer_text"):
                bonus += 0.25
            if page_type in {"about_page", "company_page"}:
                bonus -= 0.22
            if any(x in url for x in ["about", "blog", "article", "privacy", "terms", "cookie"]):
                bonus -= 0.30

        elif intent == "certification":
            if page_type == "certification_page":
                bonus += 0.60
            if any(x in url or x in title or x in tags or x in links for x in CERTIFICATION_URL_HINTS):
                bonus += 0.35
            if item.get("images"):
                bonus += 0.10

        elif intent == "product":
            if page_type in {"product_page", "catalog_page", "catalog", "catalogue", "service_page"}:
                bonus += 0.35
            if any(x in url or x in title for x in PRODUCT_URL_HINTS):
                bonus += 0.25
            if item.get("images"):
                bonus += 0.10
            if item.get("links") or item.get("important_links"):
                bonus += 0.08

        elif intent == "company":
            if page_type in {"about_page", "company_page"}:
                bonus += 0.30
            if any(x in url or x in title for x in COMPANY_URL_HINTS):
                bonus += 0.20

        elif intent == "support":
            if page_type in {"support_page", "service_page", "contact_page"}:
                bonus += 0.30
            if any(x in haystack for x in ["support", "service", "installation", "technical", "warranty"]):
                bonus += 0.15

        else:
            if page_type in {"product_page", "service_page", "contact_page", "company_page", "certification_page"}:
                bonus += 0.08

        if any(x in url for x in NOISE_URL_HINTS) or page_type in {"policy_page", "blog_page", "low_priority"}:
            bonus -= 0.28

        for token in query_tokens:
            if token in title or token in url or token in tags or token in links:
                bonus += 0.05
            elif token in text:
                bonus += 0.02

        return base + bonus

    enriched = [enrich_result_metadata(x) for x in results or []]
    return sorted(enriched, key=score, reverse=True)
