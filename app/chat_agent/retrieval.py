from typing import Any, Dict, List

from .knowledge_admin import apply_kb_rules
from .metadata_layer import rank_results_for_product_pages

try:
    from app.index_builder import search_faiss, load_metadata
except Exception:  # keeps imports safe during local linting/tests
    search_faiss = None
    load_metadata = None


def _score_float(item: Dict[str, Any], default: float = 0.0) -> float:
    try:
        candidates = [item.get("rank_score"), item.get("score"), item.get("base_score")]
        return max(float(x) for x in candidates if x is not None)
    except Exception:
        return default


def get_text_from_result(item: Dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    return (
        item.get("text")
        or item.get("chunk_text")
        or item.get("content")
        or item.get("page_content")
        or item.get("body")
        or item.get("description")
        or ""
    ).strip()


def filter_by_score(results: List[Dict[str, Any]], min_score: float = 0.20) -> List[Dict[str, Any]]:
    output = []
    for item in results or []:
        try:
            if _score_float(item) >= min_score:
                output.append(item)
        except Exception:
            output.append(item)
    return output


def retrieve_context(tenant_id: int, query: str, top_k: int = 8, min_score: float = 0.20) -> List[Dict[str, Any]]:
    """Tenant-scoped FAISS retrieval. No cross-tenant data is mixed."""
    if search_faiss is None:
        return []
    try:
        results = search_faiss(query, tenant_id=tenant_id, top_k=top_k)
        results = apply_kb_rules(results, tenant_id)
        results = rank_results_for_product_pages(results, query)
        return filter_by_score(results, min_score=min_score)
    except Exception as exc:
        print("[CHAT_AGENT RETRIEVAL ERROR]", repr(exc))
        return []


def load_tenant_metadata(tenant_id: int) -> List[Dict[str, Any]]:
    if load_metadata is None:
        return []
    try:
        return load_metadata(tenant_id) or []
    except Exception as exc:
        print("[CHAT_AGENT METADATA ERROR]", repr(exc))
        return []


def retrieve_product_pages_from_metadata(tenant_id: int, message: str = "", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Deterministic tenant-only fallback for broad product questions.
    This reads only /data/faiss/{tenant_id}/chunks.json and chooses confirmed
    product/catalog/service pages when semantic score filtering is too strict.
    """
    metadata = load_tenant_metadata(tenant_id)
    query = (message or "").lower()
    product_words = [
        "product", "products", "catalog", "catalogue", "category", "categories",
        "item", "items", "sell", "provide", "manufacture", "range", "pipe", "fitting",
    ]

    def score(item: Dict[str, Any]) -> float:
        text = get_text_from_result(item).lower()
        title = str(item.get("title") or "").lower()
        url = str(item.get("url") or "").lower()
        page_type = str(item.get("page_type") or "").lower()
        tags = " ".join([str(x).lower() for x in item.get("tags") or []])
        links = " ".join([str(x).lower() for x in item.get("links") or []])
        haystack = f"{title} {url} {page_type} {tags} {links} {text[:1200]}"

        value = 0.0
        if page_type in {"product_page", "catalog", "catalogue", "service_page"}:
            value += 10.0
        if any(w in haystack for w in product_words):
            value += 4.0
        if item.get("images"):
            value += 2.0
        if item.get("links"):
            value += 1.0
        for token in query.split():
            if len(token) >= 3 and token in haystack:
                value += 1.0
        if any(noise in haystack for noise in ["privacy", "terms", "cookie", "login", "cart", "checkout"]):
            value -= 8.0
        if not text:
            value -= 20.0
        return value

    candidates = [dict(item) for item in metadata if get_text_from_result(item)]
    candidates = sorted(candidates, key=score, reverse=True)
    return [item for item in candidates if score(item) > 0][:limit]


def retrieve_overview_context(tenant_id: int, message: str, business_type: str = "", top_k: int = 15) -> List[Dict[str, Any]]:
    query = (
        f"{message} {business_type or ''} "
        "product products product list product range product category product categories "
        "catalogue catalog items offerings what we sell what we provide "
        "company overview business overview about company"
    )
    results = retrieve_context(tenant_id, query, top_k=top_k, min_score=0.12)
    if results:
        return results
    return retrieve_product_pages_from_metadata(tenant_id, message=message, limit=top_k)


def build_context(results: List[Dict[str, Any]], max_chars: int = 2500) -> str:
    parts = []
    total = 0
    for idx, item in enumerate(results or [], start=1):
        text = get_text_from_result(item)
        if not text:
            continue
        source = item.get("url") or item.get("file_name") or item.get("title") or "trained data"
        block = f"[Source {idx}: {source}]\n{text}"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 150:
                parts.append(block[:remaining])
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)
