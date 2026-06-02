from typing import Any, Dict, List

from .knowledge_admin import apply_kb_rules
from .metadata_layer import detect_query_intent, rank_results_for_product_pages

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
        item.get("answer_text")
        or item.get("text")
        or item.get("chunk_text")
        or item.get("content")
        or item.get("page_content")
        or item.get("body")
        or item.get("description")
        or ""
    ).strip()


def get_full_text_from_result(item: Dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    return (
        item.get("exact_knowledge_text")
        or item.get("text")
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
        # Pull a few extra semantic candidates, then apply tenant rules + intent-aware reranking.
        # This helps contact/support queries recover when a contact page is not the top cosine match.
        candidate_k = max(top_k * 3, 12)
        results = search_faiss(query, tenant_id=tenant_id, top_k=candidate_k)
        results = apply_kb_rules(results, tenant_id)
        results = rank_results_for_product_pages(results, query)
        return filter_by_score(results, min_score=min_score)[:top_k]
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
        "company overview business overview about company "
        "services offerings capabilities solutions "
        "organization profile business profile"
    )
    results = retrieve_context(tenant_id, query, top_k=top_k, min_score=0.12)
    if results:
        return results
    return retrieve_product_pages_from_metadata(tenant_id, message=message, limit=top_k)


def _clean_context_text(text: str, max_len: int = 900) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Safety cleanup for old chunks that may still contain metadata labels.
    bad_prefixes = ["Knowledge label:", "Tags:", "Priority:", "Chunk:"]
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(stripped.lower().startswith(x.lower()) for x in bad_prefixes):
            continue
        lines.append(line)
    text = "\n".join(lines).strip()
    if len(text) > max_len:
        return text[:max_len].rsplit(" ", 1)[0].strip() + "..."
    return text


def _links_for_context(item: Dict[str, Any], limit: int = 4) -> List[str]:
    links = item.get("important_links") or item.get("links") or []
    if isinstance(links, str):
        links = [links]
    output = []
    for link in links:
        value = str(link or "").strip()
        if value and value not in output:
            output.append(value)
        if len(output) >= limit:
            break
    return output


def build_context(results: List[Dict[str, Any]], max_chars: int = 2500) -> str:
    """
    Build LLM context from retrieved chunks.

    Priority:
    1. answer_text - short answer-ready text created during training, best for contact/support.
    2. text - normal searchable chunk.
    3. exact_knowledge_text - only as fallback and truncated.

    Metadata is included as labels for the LLM to reason with, but not as customer-facing text.
    """
    parts = []
    total = 0
    for idx, item in enumerate(results or [], start=1):
        if not isinstance(item, dict):
            continue

        answer_text = str(item.get("answer_text") or "").strip()
        text = answer_text or str(item.get("text") or "").strip() or get_full_text_from_result(item)
        text = _clean_context_text(text, max_len=850 if answer_text else 700)
        if not text:
            continue

        source_url = item.get("source_url") or item.get("url") or ""
        source = source_url or item.get("file_name") or item.get("title") or "trained data"
        page_type = item.get("page_type") or "website_page"
        title = item.get("title") or item.get("file_name") or "Knowledge"
        links = _links_for_context(item)
        images = item.get("images") or []
        if isinstance(images, str):
            images = [images]

        meta_lines = [
            f"[Source {idx}]",
            f"Title: {title}",
            f"Page type: {page_type}",
            f"Source URL: {source}",
        ]
        if links:
            meta_lines.append("Useful links: " + ", ".join(links[:4]))
        if images:
            meta_lines.append("Images available: yes")
        if answer_text:
            meta_lines.append("Answer-ready text:")
        else:
            meta_lines.append("Knowledge text:")

        block = "\n".join(meta_lines) + "\n" + text
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 180:
                parts.append(block[:remaining].rsplit(" ", 1)[0].strip())
            break
        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


def classify_match_quality(results: List[Dict[str, Any]], message: str = "") -> str:
    """
    Lightweight match quality for the prompt grounding ladder.
    This does not decide truth; it only tells the LLM whether retrieved KB looks exact,
    nearby, or missing, so the answer can be safer and more human.
    """
    if not results:
        return "zero_match"

    query_terms = [
        t for t in str(message or "").lower().replace("316 l", "316l").split()
        if len(t) >= 3 and t not in {"what", "which", "need", "have", "your", "for", "the", "and", "with"}
    ]
    top = results[0] if isinstance(results[0], dict) else {}
    top_score = _score_float(top, default=0.0)
    haystack = " ".join([
        str(top.get("title") or ""),
        str(top.get("page_type") or ""),
        " ".join([str(x) for x in top.get("tags") or []]),
        get_text_from_result(top)[:1500],
    ]).lower()

    matched_terms = sum(1 for t in query_terms if t in haystack)
    if top_score >= 0.48 or (query_terms and matched_terms >= max(1, min(3, len(query_terms)))):
        return "exact_match"
    if top_score >= 0.18 or len(results) >= 1:
        return "nearby_match"
    return "zero_match"
