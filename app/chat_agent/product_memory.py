import re
from typing import Any, Dict, List

from .retrieval import get_text_from_result


STOP_TERMS = {
    "insta", "pressfit", "source", "sources", "resistance", "resistant", "quality",
    "performance", "solution", "solutions", "systems", "system", "products", "product",
    "service", "services", "company", "business", "plumbing", "water", "hygienic",
    "durable", "durability", "excellent", "premium", "advanced", "designed", "provide",
    "provides", "available", "range", "types", "grade", "grades", "stainless", "steel",
}

PRODUCT_PATTERNS = [
    r"\b\d{2,3}\s*°\s*[a-z0-9\s-]*(?:elbow|bend)\b",
    r"\b(?:male|female)\s+[a-z0-9\s-]*(?:elbow|adaptor|adapter|thread|socket|tee)\b",
    r"\b(?:equal|branch)\s+tee\b",
    r"\b(?:end\s+cap|pipe\s+bridge|socket|coupler|coupling|reducer|elbow|tee|adaptor|adapter|bend|pipe|fitting|manifold)\b",
    r"\b(?:ss|stainless\s+steel)\s+[a-z0-9\s-]*(?:pipe|pipes|fitting|fittings|elbow|tee|adaptor|adapter|socket|coupler|reducer)\b",
    r"\b(?:304|316l?)\s+[a-z0-9\s-]*(?:pipe|pipes|fitting|fittings|grade pipes|grade fittings)\b",
]


def _clean_term(term: str) -> str:
    term = re.sub(r"\s+", " ", term or "").strip(" -_/.,:;|\n\t")
    if not term:
        return ""
    words = [w for w in term.split() if w.lower() not in STOP_TERMS or w.lower() in {"pipe", "pipes", "fitting", "fittings"}]
    cleaned = " ".join(words).strip()
    if len(cleaned) < 3:
        return ""
    if cleaned.lower() in STOP_TERMS:
        return ""
    return cleaned


def extract_product_like_terms_from_context(context: str, max_terms: int = 12) -> List[str]:
    text = re.sub(r"[^a-zA-Z0-9°\s&/()-]", " ", context or "")
    found: List[str] = []

    for pattern in PRODUCT_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            term = _clean_term(str(match))
            if term:
                found.append(term)

    # Keep order and remove junk/single SEO words.
    output = []
    seen = set()
    for term in found:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(term)
        if len(output) >= max_terms:
            break
    return output


def _terms_from_result_metadata(item: Dict[str, Any]) -> List[str]:
    raw_values = []
    title = item.get("title") or item.get("file_name") or ""
    if title:
        raw_values.append(str(title))
    for tag in item.get("tags") or []:
        raw_values.append(str(tag))

    terms = []
    for value in raw_values:
        terms.extend(extract_product_like_terms_from_context(value, max_terms=6))
        cleaned = _clean_term(value)
        if cleaned and any(x in cleaned.lower() for x in [
            "pipe", "fitting", "elbow", "tee", "adaptor", "adapter", "socket", "coupler", "reducer", "cap", "bridge",
        ]):
            terms.append(cleaned)
    return terms


def build_product_memory(results: List[Dict[str, Any]], context: str = "") -> Dict[str, Any]:
    images, links, titles = [], [], []
    texts = []
    metadata_terms = []

    for item in results or []:
        text = get_text_from_result(item)
        texts.append(text)
        metadata_terms.extend(_terms_from_result_metadata(item))
        images.extend(item.get("images") or [])
        links.extend(item.get("links") or item.get("important_links") or [])
        title = item.get("title") or item.get("file_name") or item.get("url")
        if title:
            titles.append(str(title))

    merged_context = context or "\n".join(texts)
    terms = []
    for term in metadata_terms + extract_product_like_terms_from_context(merged_context):
        cleaned = _clean_term(term)
        if cleaned:
            terms.append(cleaned)

    unique_terms = []
    seen = set()
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_terms.append(term)

    return {
        "terms": unique_terms[:12],
        "titles": list(dict.fromkeys(titles))[:8],
        "images": list(dict.fromkeys(images))[:8],
        "links": list(dict.fromkeys(links))[:8],
        "context_length": len(merged_context),
    }
