import hashlib
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.tokenizer import clean_text, create_chunks
from app.utils import FAISS_DIR, load_json, save_json

PROCESSED_FILES_PATH = FAISS_DIR / "processed_files.json"


# -----------------------------------------------------------------------------
# Training registry helpers
# -----------------------------------------------------------------------------

def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def get_registry() -> Dict:
    data = load_json(PROCESSED_FILES_PATH, default={})
    return data if isinstance(data, dict) else {}


def save_registry(registry: Dict):
    save_json(PROCESSED_FILES_PATH, registry)


def is_done(source_key: str, source_hash: str) -> bool:
    item = get_registry().get(source_key)
    return bool(item and item.get("hash") == source_hash and item.get("status") == "done")


def mark_processing(source_key: str, source_hash: str, extra: Dict = None):
    registry = get_registry()
    registry[source_key] = {
        "hash": source_hash,
        "status": "processing",
        **(extra or {}),
    }
    save_registry(registry)


def mark_done(source_key: str, source_hash: str, chunks_count: int, extra: Dict = None):
    registry = get_registry()
    registry[source_key] = {
        "hash": source_hash,
        "status": "done",
        "chunks": chunks_count,
        **(extra or {}),
    }
    save_registry(registry)


def mark_failed(source_key: str, source_hash: str, error: str, extra: Dict = None):
    registry = get_registry()
    registry[source_key] = {
        "hash": source_hash,
        "status": "failed",
        "error": error,
        **(extra or {}),
    }
    save_registry(registry)


# -----------------------------------------------------------------------------
# Sales/support chunk metadata helpers
# -----------------------------------------------------------------------------

PAGE_TYPE_PRIORITY = {
    "product_page": 90,
    "catalog_page": 88,
    "service_page": 80,
    "support_page": 78,
    "contact_page": 75,
    "about_page": 55,
    "company_page": 50,
    "blog_page": 30,
    "policy_page": 8,
    "website_page": 40,
    "file_document": 45,
}

SALES_SUPPORT_KEYWORDS = [
    "product", "products", "catalog", "catalogue", "model", "item", "items",
    "price", "pricing", "rate", "cost", "quote", "quotation", "buy", "purchase",
    "specification", "specifications", "size", "material", "finish", "warranty",
    "installation", "service", "support", "contact", "phone", "email", "address",
    "whatsapp", "dealer", "distributor", "manufacturer", "supplier",
]

STOP_TAGS = {
    "home", "page", "website", "click", "here", "read", "more", "about", "contact",
    "privacy", "terms", "cookie", "policy", "width", "device", "initial", "scale",
    "http", "https", "www", "html", "com", "php", "asp", "default",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _unique_keep_order(values: List[Any], limit: Optional[int] = None) -> List[Any]:
    seen = set()
    output = []
    for value in values or []:
        if value is None:
            continue
        key = json.dumps(value, sort_keys=True, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
        if limit and len(output) >= limit:
            break
    return output


def _extract_url(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, dict):
        return (
            _as_text(value.get("url"))
            or _as_text(value.get("href"))
            or _as_text(value.get("src"))
            or _as_text(value.get("link"))
        )
    return _as_text(value)


def _normalize_url_list(values: Any, limit: int = 20) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = [values]

    urls = []
    for item in values:
        url = _extract_url(item)
        if url and (url.startswith("http://") or url.startswith("https://") or url.startswith("/")):
            urls.append(url)
    return _unique_keep_order(urls, limit=limit)


def _url_path_words(url: str) -> List[str]:
    if not url:
        return []
    try:
        parsed = urlparse(url)
        value = f"{parsed.netloc} {parsed.path}"
    except Exception:
        value = url
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9-]{2,}", value.lower())


def infer_page_type_from_url(url: str = "", title: str = "", text: str = "") -> str:
    value = f"{url or ''} {title or ''} {text[:600] if text else ''}".lower()

    # Low-value pages must be detected before generic company/product matches.
    if any(x in value for x in ["privacy", "terms", "cookie", "refund", "return-policy", "disclaimer"]):
        return "policy_page"
    if any(x in value for x in ["/blog", "blog/", "article", "news", "post"]):
        return "blog_page"

    if any(x in value for x in ["/product", "products", "catalog", "catalogue", "shop", "item", "model", "category"]):
        return "product_page"
    if any(x in value for x in ["/service", "services", "support", "repair", "installation"]):
        return "service_page"
    if any(x in value for x in ["contact", "phone", "email", "address", "whatsapp", "enquiry", "inquiry"]):
        return "contact_page"
    if any(x in value for x in ["about", "company", "profile", "who-we-are"]):
        return "company_page"

    return "website_page"


def _priority_for_page(page_type: str, explicit_priority: Any = None) -> int:
    try:
        priority = int(explicit_priority or 0)
    except Exception:
        priority = 0

    base = PAGE_TYPE_PRIORITY.get(page_type or "website_page", 40)

    # Keep manually supplied high priority, but never allow empty/zero priority to weaken important pages.
    if priority > 0:
        return max(priority, base)
    return base


def _infer_tags(title: str, url: str, text: str, explicit_tags: Any = None, limit: int = 14) -> List[str]:
    tags = []

    if isinstance(explicit_tags, str):
        explicit_tags = re.split(r"[,|;/]", explicit_tags)
    if isinstance(explicit_tags, list):
        tags.extend([_as_text(x).lower() for x in explicit_tags if _as_text(x)])

    haystack = f"{title or ''} {url or ''} {text[:2000] if text else ''}".lower()

    for word in SALES_SUPPORT_KEYWORDS:
        if word in haystack:
            tags.append(word)

    for token in _url_path_words(url):
        tags.append(token.replace("-", " "))

    for part in re.split(r"[-|:/,]", title or ""):
        part = part.strip().lower()
        if 3 <= len(part) <= 45:
            tags.append(part)

    # Add frequent meaningful words from exact text.
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9&./-]{3,}", (text or "").lower())
    freq = {}
    for word in words:
        clean_word = word.strip("./-")
        if clean_word in STOP_TAGS or clean_word.isdigit():
            continue
        freq[clean_word] = freq.get(clean_word, 0) + 1

    for word, count in sorted(freq.items(), key=lambda item: item[1], reverse=True):
        if count >= 2:
            tags.append(word)
        if len(tags) >= limit * 2:
            break

    clean_tags = []
    for tag in tags:
        tag = re.sub(r"\s+", " ", _as_text(tag).lower()).strip()
        if not tag or tag in STOP_TAGS or len(tag) < 3:
            continue
        clean_tags.append(tag)

    return _unique_keep_order(clean_tags, limit=limit)


def _important_links(doc: Dict, source_url: str, page_type: str, limit: int = 12) -> List[str]:
    links = []
    links.extend(_normalize_url_list(doc.get("important_links"), limit=limit))
    links.extend(_normalize_url_list(doc.get("links"), limit=limit))
    links.extend(_normalize_url_list(doc.get("link_urls"), limit=limit))

    if source_url and page_type in {"product_page", "catalog_page", "service_page", "contact_page"}:
        links.insert(0, source_url)

    useful = []
    for link in links:
        low = link.lower()
        if any(x in low for x in [".css", ".js", "javascript:", "#", "mailto:", "tel:"]):
            continue
        useful.append(link)

    return _unique_keep_order(useful, limit=limit)


def _normalize_document(doc: Dict, source_key: str, source_hash: str) -> Optional[Dict]:
    text = clean_text(doc.get("text") or doc.get("content") or doc.get("body") or "")
    if not text:
        return None

    title = (
        _as_text(doc.get("title"))
        or _as_text(doc.get("name"))
        or _as_text(doc.get("file_name"))
        or _as_text(doc.get("url"))
        or "Knowledge Entry"
    )
    source_url = _as_text(doc.get("source_url")) or _as_text(doc.get("url"))
    existing_page_type = _as_text(doc.get("page_type"))
    page_type = existing_page_type or infer_page_type_from_url(source_url, title, text)
    priority = _priority_for_page(page_type, doc.get("priority"))
    tags = _infer_tags(title, source_url, text, doc.get("tags") or doc.get("labels"))
    images = _normalize_url_list(doc.get("images") or doc.get("image_urls"), limit=20)
    important_links = _important_links(doc, source_url, page_type)

    normalized = dict(doc)
    normalized.update({
        "text": text,
        "exact_knowledge_text": text,
        "title": title,
        "page_type": page_type,
        "priority": priority,
        "source_url": source_url,
        "url": source_url,
        "tags": tags,
        "images": images,
        "important_links": important_links,
        "links": important_links,
        "source_key": source_key,
        "source_hash": source_hash,
        "is_disabled": bool(doc.get("is_disabled") or False),
    })
    return normalized


def _clean_chunk_text(chunk: Dict) -> str:
    """
    tokenizer.create_chunks() currently may add embedding labels into chunk['text'].
    For clean sales/support answers, keep chunk['text'] as exact customer-safe knowledge only.
    Metadata remains available separately for reranking and prompt formatting.
    """
    raw = chunk.get("raw_text") or chunk.get("exact_knowledge_text") or chunk.get("text") or ""
    raw = re.sub(r"^Knowledge label:.*?Chunk:\s*\d+/\d+\.\s*", "", str(raw), flags=re.IGNORECASE | re.DOTALL)
    return clean_text(raw)


def docs_to_chunks(
    documents: List[Dict],
    source_key: str,
    source_hash: str,
    chunk_size: int = 250,
    overlap: int = 50,
) -> List[Dict]:
    """
    Convert scraped/uploaded documents into clean sales/support knowledge chunks.

    Important behavior:
    - Keeps customer-safe text separate from metadata.
    - Every chunk carries title, page_type, priority, source_url, tags, images,
      important_links, and exact_knowledge_text.
    - Does not print metadata inside chunk['text']; this prevents answers like
      "Knowledge label / Tags / Priority / Chunk" from leaking to users.
    """
    cleaned_documents = []
    for doc in documents or []:
        if not isinstance(doc, dict):
            doc = {"text": str(doc), "title": "Knowledge Entry"}
        normalized = _normalize_document(doc, source_key=source_key, source_hash=source_hash)
        if normalized:
            cleaned_documents.append(normalized)

    chunks = create_chunks(cleaned_documents, chunk_size=chunk_size, overlap=overlap)
    final_chunks = []

    for chunk in chunks:
        exact_text = _clean_chunk_text(chunk)
        if not exact_text:
            continue

        source_url = _as_text(chunk.get("source_url")) or _as_text(chunk.get("url"))
        title = _as_text(chunk.get("title")) or _as_text(chunk.get("file_name")) or source_url or "Knowledge Entry"
        page_type = _as_text(chunk.get("page_type")) or infer_page_type_from_url(source_url, title, exact_text)
        priority = _priority_for_page(page_type, chunk.get("priority"))
        tags = _infer_tags(title, source_url, exact_text, chunk.get("tags"))
        if page_type in ["blog_page", "article_page"]:
            tags = [
                t for t in tags
                if t not in [
                    "product",
                    "products",
                    "pricing",
                    "catalog",
                    "catalogue",
                    "pipe",
                    "pipes",
                    "fittings",
                ]
            ]
        images = _normalize_url_list(chunk.get("images"), limit=20)
        important_links = _important_links(chunk, source_url, page_type)

        # Typed helper strings are metadata-style fields for later retrieval/prompt logic.
        # index_builder currently embeds chunk['text']; keep it exact and clean.
        semantic_chunk = exact_text
        typed_chunk = f"{page_type} | {title} | {exact_text}"
        ai_keyword_chunk = " ".join(tags)
        if page_type == "contact_page":
            intent_chunk = "contact phone email address office whatsapp location support"
            priority = 100

        elif page_type == "product_page":
            intent_chunk = "product specification material installation catalog dimensions pricing images"
            priority = 80

        elif page_type == "about_page":
            intent_chunk = "company about profile experience certification infrastructure"
            priority = 50

        # elif page_type == "service_page":
        #     intent_chunk = "service support installation maintenance solution"
        #     priority = 70

        # else:
        #     intent_chunk = "general business information support"
        #     priority = 40
        # section_chunk = title

        elif page_type == "service_page":
            intent_chunk = "service support installation maintenance solution"
            priority = 70

        elif page_type in ["blog_page", "article_page"]:
            intent_chunk = "blog article guide educational information"
            priority = 20

        else:
            intent_chunk = "general business information support"
            priority = 40
        section_chunk = title
        chunk.update({
            "text": exact_text,
            "raw_text": exact_text,
            "exact_knowledge_text": exact_text,
            "semantic_chunk": semantic_chunk,
            "typed_chunk": typed_chunk,
            "ai_keyword_chunk": ai_keyword_chunk,
            "intent_chunk": intent_chunk,
            "section_chunk": section_chunk,
            "source_key": source_key,
            "source_hash": source_hash,
            "title": title,
            "page_type": page_type,
            "priority": priority,
            "source_url": source_url,
            "url": source_url,
            "tags": tags,
            "images": images,
            "important_links": important_links,
            "links": important_links,
            "images_count": len(images),
            "links_count": len(important_links),
        })

        # Re-hash after making customer-safe text final.
        chunk["text_hash"] = sha256_text(
            "||".join([
                source_key or "",
                source_hash or "",
                source_url or "",
                title or "",
                str(chunk.get("chunk_id") or ""),
                exact_text,
            ])
        )
        final_chunks.append(chunk)

    return final_chunks


# -----------------------------------------------------------------------------
# website_data.json normalization
# -----------------------------------------------------------------------------

def normalize_website_json(data, content_type: str = "Website") -> List[Dict]:
    """
    Supports common website_data.json shapes:
    1) [{url, text, title}, ...]
    2) {pages: [{url, text}, ...]}
    3) {url: text, url2: text2}
    4) plain string/list/dict fallback
    """
    docs = []

    if isinstance(data, dict) and isinstance(data.get("pages"), list):
        data = data["pages"]

    if isinstance(data, list):
        for idx, item in enumerate(data):
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("body") or json.dumps(item, ensure_ascii=False)
                url = item.get("source_url") or item.get("url")
                title = item.get("title") or url or f"Website Page {idx + 1}"
                page_type = item.get("page_type") or infer_page_type_from_url(url, title, text)
                docs.append({
                    "source_type": item.get("source_type") or "website_json",
                    "content_type": item.get("content_type") or content_type,
                    "file_name": item.get("file_name") or "website_data.json",
                    "url": url,
                    "source_url": url,
                    "title": title,
                    "page_type": page_type,
                    "images": item.get("images") or item.get("image_urls") or [],
                    "links": item.get("links") or item.get("link_urls") or item.get("important_links") or [],
                    "important_links": item.get("important_links") or item.get("links") or item.get("link_urls") or [],
                    "priority": _priority_for_page(page_type, item.get("priority")),
                    "tags": item.get("tags") or item.get("labels") or [],
                    "text": text,
                })
            else:
                docs.append({
                    "source_type": "website_json",
                    "content_type": content_type,
                    "file_name": "website_data.json",
                    "url": None,
                    "source_url": None,
                    "title": f"Website Data {idx + 1}",
                    "page_type": "website_page",
                    "priority": PAGE_TYPE_PRIORITY["website_page"],
                    "images": [],
                    "links": [],
                    "important_links": [],
                    "tags": [],
                    "text": str(item),
                })
        return docs

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)
            url = key if str(key).startswith("http") else None
            title = str(key)
            page_type = infer_page_type_from_url(url or "", title, text)
            docs.append({
                "source_type": "website_json",
                "content_type": content_type,
                "file_name": "website_data.json",
                "url": url,
                "source_url": url,
                "title": title,
                "page_type": page_type,
                "images": [],
                "links": [],
                "important_links": [url] if url and page_type in {"product_page", "service_page", "contact_page"} else [],
                "priority": _priority_for_page(page_type, 0),
                "tags": [],
                "text": text,
            })
        return docs

    return [{
        "source_type": "website_json",
        "content_type": content_type,
        "file_name": "website_data.json",
        "url": None,
        "source_url": None,
        "title": "website_data.json",
        "page_type": "website_page",
        "priority": PAGE_TYPE_PRIORITY["website_page"],
        "images": [],
        "links": [],
        "important_links": [],
        "tags": [],
        "text": str(data),
    }]
