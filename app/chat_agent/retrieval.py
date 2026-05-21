from typing import Any, Dict, List

try:
    from app.index_builder import search_faiss, load_metadata
except Exception:  # keeps imports safe during local linting/tests
    search_faiss = None
    load_metadata = None


def _score_float(item: Dict[str, Any], default: float = 0.0) -> float:
    try:
        score = item.get("score")
        return float(score) if score is not None else default
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
        score = item.get("score")
        try:
            if score is None or float(score) >= min_score:
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
        return filter_by_score(results, min_score=min_score)
    except Exception as exc:
        print("[CHAT_AGENT RETRIEVAL ERROR]", repr(exc))
        return []


def retrieve_overview_context(tenant_id: int, message: str, business_type: str = "", top_k: int = 15) -> List[Dict[str, Any]]:
    query = (
        f"{message} {business_type or ''} "
        "product products product list product range product category product categories "
        "catalogue catalog items offerings what we sell what we provide "
        "company overview business overview about company"
    )
    return retrieve_context(tenant_id, query, top_k=top_k, min_score=0.15)


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


def load_tenant_metadata(tenant_id: int) -> List[Dict[str, Any]]:
    if load_metadata is None:
        return []
    try:
        return load_metadata(tenant_id) or []
    except Exception as exc:
        print("[CHAT_AGENT METADATA ERROR]", repr(exc))
        return []
