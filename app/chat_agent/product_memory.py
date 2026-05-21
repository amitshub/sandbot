import re
from typing import Any, Dict, List

from .retrieval import get_text_from_result


def extract_product_like_terms_from_context(context: str, max_terms: int = 8) -> List[str]:
    text = re.sub(r"[^a-zA-Z0-9\s&/-]", " ", context or "").lower()
    stopwords = {
        "the", "and", "for", "with", "from", "this", "that", "your", "our",
        "you", "are", "can", "will", "have", "has", "about", "company",
        "business", "products", "product", "services", "service", "details",
        "information", "page", "website", "contact", "home", "read", "more",
        "quality", "best", "provide", "offer", "offers", "available", "solution",
        "solutions", "customer", "support", "range", "category", "categories",
    }
    words = [w for w in text.split() if len(w) >= 4 and w not in stopwords and not w.isdigit()]
    freq = {}
    for word in words:
        freq[word] = freq.get(word, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in ranked[:max_terms] if count >= 2]


def build_product_memory(results: List[Dict[str, Any]], context: str = "") -> Dict[str, Any]:
    images, links, titles = [], [], []
    texts = []
    for item in results or []:
        texts.append(get_text_from_result(item))
        images.extend(item.get("images") or [])
        links.extend(item.get("links") or [])
        title = item.get("title") or item.get("file_name") or item.get("url")
        if title:
            titles.append(str(title))

    merged_context = context or "\n".join(texts)
    return {
        "terms": extract_product_like_terms_from_context(merged_context),
        "titles": list(dict.fromkeys(titles))[:8],
        "images": list(dict.fromkeys(images))[:8],
        "links": list(dict.fromkeys(links))[:8],
        "context_length": len(merged_context),
    }
