# import hashlib
# import json
# from pathlib import Path
# from typing import Dict, List, Tuple

# from app.tokenizer import clean_text, create_chunks
# from app.utils import FAISS_DIR, load_json, save_json

# PROCESSED_FILES_PATH = FAISS_DIR / "processed_files.json"


def infer_page_type_from_url(url: str = "", title: str = "") -> str:
    value = f"{url or ''} {title or ''}".lower()
    if any(x in value for x in ["privacy", "terms", "cookie", "blog", "article"]):
        return "blog"
    if any(x in value for x in ["product", "products", "catalog", "catalogue", "shop", "item", "model", "category"]):
        return "product_page"
    if any(x in value for x in ["service", "support"]):
        return "service_page"
    if any(x in value for x in ["about", "contact", "company"]):
        return "company_page"
    return "website_page"


# def sha256_bytes(content: bytes) -> str:
#     return hashlib.sha256(content).hexdigest()


# def sha256_text(text: str) -> str:
#     return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


# def get_registry() -> Dict:
#     data = load_json(PROCESSED_FILES_PATH, default={})
#     return data if isinstance(data, dict) else {}


# def save_registry(registry: Dict):
#     save_json(PROCESSED_FILES_PATH, registry)


# def is_done(source_key: str, source_hash: str) -> bool:
#     item = get_registry().get(source_key)
#     return bool(item and item.get("hash") == source_hash and item.get("status") == "done")


# def mark_processing(source_key: str, source_hash: str, extra: Dict = None):
#     registry = get_registry()
#     registry[source_key] = {
#         "hash": source_hash,
#         "status": "processing",
#         **(extra or {}),
#     }
#     save_registry(registry)


# def mark_done(source_key: str, source_hash: str, chunks_count: int, extra: Dict = None):
#     registry = get_registry()
#     registry[source_key] = {
#         "hash": source_hash,
#         "status": "done",
#         "chunks": chunks_count,
#         **(extra or {}),
#     }
#     save_registry(registry)


# def mark_failed(source_key: str, source_hash: str, error: str, extra: Dict = None):
#     registry = get_registry()
#     registry[source_key] = {
#         "hash": source_hash,
#         "status": "failed",
#         "error": error,
#         **(extra or {}),
#     }
#     save_registry(registry)


# def docs_to_chunks(documents: List[Dict], source_key: str, source_hash: str, chunk_size: int = 250, overlap: int = 50) -> List[Dict]:
#     cleaned_documents = []
#     for doc in documents:
#         text = clean_text(doc.get("text", ""))
#         if not text:
#             continue
#         cleaned_doc = dict(doc)
#         cleaned_doc["text"] = text
#         cleaned_doc["source_key"] = source_key
#         cleaned_doc["source_hash"] = source_hash
#         cleaned_documents.append(cleaned_doc)

#     chunks = create_chunks(cleaned_documents, chunk_size=chunk_size, overlap=overlap)
#     for chunk in chunks:
#         chunk["source_key"] = source_key
#         chunk["source_hash"] = source_hash
#     return chunks


# def normalize_website_json(data, content_type: str = "Website") -> List[Dict]:
#     """
#     Supports common website_data.json shapes:
#     1) [{url, text, title}, ...]
#     2) {pages: [{url, text}, ...]}
#     3) {url: text, url2: text2}
#     4) plain string/list/dict fallback
#     """
#     docs = []

#     if isinstance(data, dict) and isinstance(data.get("pages"), list):
#         data = data["pages"]

#     if isinstance(data, list):
#         for idx, item in enumerate(data):
#             if isinstance(item, dict):
#                 text = item.get("text") or item.get("content") or item.get("body") or json.dumps(item, ensure_ascii=False)
#                 docs.append({
#                     "source_type": item.get("source_type") or "website_json",
#                     "content_type": item.get("content_type") or content_type,
#                     "file_name": "website_data.json",
#                     "url": item.get("url"),
#                     "title": item.get("title") or item.get("url") or f"Website Page {idx + 1}",
#                     "text": text,
#                 })
#             else:
#                 docs.append({
#                     "source_type": "website_json",
#                     "content_type": content_type,
#                     "file_name": "website_data.json",
#                     "url": None,
#                     "title": f"Website Data {idx + 1}",
#                     "text": str(item),
#                 })
#         return docs

#     if isinstance(data, dict):
#         for key, value in data.items():
#             if isinstance(value, str):
#                 text = value
#             else:
#                 text = json.dumps(value, ensure_ascii=False)
#             docs.append({
#                 "source_type": "website_json",
#                 "content_type": content_type,
#                 "file_name": "website_data.json",
#                 "url": key if str(key).startswith("http") else None,
#                 "title": str(key),
#                 "text": text,
#             })
#         return docs

#     return [{
#         "source_type": "website_json",
#         "content_type": content_type,
#         "file_name": "website_data.json",
#         "url": None,
#         "title": "website_data.json",
#         "text": str(data),
#     }]
 
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

from app.tokenizer import clean_text, create_chunks
from app.utils import FAISS_DIR, load_json, save_json

PROCESSED_FILES_PATH = FAISS_DIR / "processed_files.json"


def infer_page_type_from_url(url: str = "", title: str = "") -> str:
    value = f"{url or ''} {title or ''}".lower()
    if any(x in value for x in ["privacy", "terms", "cookie", "blog", "article"]):
        return "blog"
    if any(x in value for x in ["product", "products", "catalog", "catalogue", "shop", "item", "model", "category"]):
        return "product_page"
    if any(x in value for x in ["service", "support"]):
        return "service_page"
    if any(x in value for x in ["about", "contact", "company"]):
        return "company_page"
    return "website_page"


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


def docs_to_chunks(documents: List[Dict], source_key: str, source_hash: str, chunk_size: int = 250, overlap: int = 50) -> List[Dict]:
    cleaned_documents = []
    for doc in documents:
        text = clean_text(doc.get("text", ""))
        if not text:
            continue
        cleaned_doc = dict(doc)
        cleaned_doc["text"] = text
        cleaned_doc["source_key"] = source_key
        cleaned_doc["source_hash"] = source_hash
        cleaned_documents.append(cleaned_doc)

    chunks = create_chunks(cleaned_documents, chunk_size=chunk_size, overlap=overlap)
    for chunk in chunks:
        chunk["source_key"] = source_key
        chunk["source_hash"] = source_hash
    return chunks


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
                docs.append({
                    "source_type": item.get("source_type") or "website_json",
                    "content_type": item.get("content_type") or content_type,
                    "file_name": "website_data.json",
                    "url": item.get("url"),
                    "title": item.get("title") or item.get("url") or f"Website Page {idx + 1}",
                    "page_type": item.get("page_type") or infer_page_type_from_url(item.get("url"), item.get("title")),
                    "images": item.get("images") or item.get("image_urls") or [],
                    "links": item.get("links") or item.get("link_urls") or [],
                    "priority": int(item.get("priority") or 0),
                    "text": text,
                })
            else:
                docs.append({
                    "source_type": "website_json",
                    "content_type": content_type,
                    "file_name": "website_data.json",
                    "url": None,
                    "title": f"Website Data {idx + 1}",
                    "text": str(item),
                })
        return docs

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                text = value
            else:
                text = json.dumps(value, ensure_ascii=False)
            docs.append({
                "source_type": "website_json",
                "content_type": content_type,
                "file_name": "website_data.json",
                "url": key if str(key).startswith("http") else None,
                "title": str(key),
                "page_type": infer_page_type_from_url(key, str(key)),
                "images": [],
                "links": [],
                "priority": 0,
                "text": text,
            })
        return docs

    return [{
        "source_type": "website_json",
        "content_type": content_type,
        "file_name": "website_data.json",
        "url": None,
        "title": "website_data.json",
        "text": str(data),
    }]
