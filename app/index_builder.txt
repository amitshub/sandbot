from typing import Dict, List
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.utils import FAISS_DIR, load_json, save_json

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_INDEX_CACHE = {}
_METADATA_CACHE = {}


def get_text_from_chunk(item: Dict) -> str:
    """
    Supports old/new chunk formats.
    Main key should be text, but fallback keys help recover old metadata.
    """
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


def get_embedding_model():
    global _model

    if _model is None:
        print("[EMBEDDING] Loading model:", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        print("[EMBEDDING] Model loaded")

    return _model


def get_tenant_faiss_dir(tenant_id):
    path = FAISS_DIR / str(tenant_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_index_path(tenant_id):
    return get_tenant_faiss_dir(tenant_id) / "index.faiss"


def get_metadata_path(tenant_id):
    return get_tenant_faiss_dir(tenant_id) / "chunks.json"


def clear_tenant_faiss_data(tenant_id):
    """Delete tenant FAISS index + metadata so it can be rebuilt from editable KB."""
    index_path = get_index_path(tenant_id)
    metadata_path = get_metadata_path(tenant_id)
    if index_path.exists():
        index_path.unlink()
    if metadata_path.exists():
        metadata_path.unlink()
    clear_tenant_cache(tenant_id)
    return {"index_path": str(index_path), "metadata_path": str(metadata_path), "cleared": True}


def clear_tenant_cache(tenant_id):
    tenant_key = str(tenant_id)
    _INDEX_CACHE.pop(tenant_key, None)
    _METADATA_CACHE.pop(tenant_key, None)
    print("[FAISS CACHE] cleared for tenant:", tenant_id)


def _normalize(embeddings: np.ndarray) -> np.ndarray:
    embeddings = np.array(embeddings).astype("float32")
    faiss.normalize_L2(embeddings)
    return embeddings


def load_metadata(tenant_id) -> List[Dict]:
    metadata_path = get_metadata_path(tenant_id)
    data = load_json(metadata_path, default=[])
    return data if isinstance(data, list) else []


def load_or_create_index(index_path, dimension: int):
    if index_path.exists():
        try:
            print("[FAISS] Loading existing index:", index_path)
            return faiss.read_index(str(index_path))
        except Exception as exc:
            print("[FAISS] Failed to load existing index, creating new:", repr(exc))

    print("[FAISS] Creating new index:", index_path)
    return faiss.IndexFlatIP(dimension)


def load_tenant_index_and_metadata(tenant_id):
    tenant_key = str(tenant_id)
    index_path = get_index_path(tenant_id)
    metadata_path = get_metadata_path(tenant_id)

    if tenant_key in _INDEX_CACHE and tenant_key in _METADATA_CACHE:
        print("[FAISS CACHE] using cached index for tenant:", tenant_id)
        return _INDEX_CACHE[tenant_key], _METADATA_CACHE[tenant_key]

    print("[FAISS LOAD] tenant_id:", tenant_id)
    print("[FAISS LOAD] index_path:", index_path)
    print("[FAISS LOAD] metadata_path:", metadata_path)

    if not index_path.exists():
        raise FileNotFoundError("FAISS index not found. Please train the agent first.")

    if not metadata_path.exists():
        raise FileNotFoundError("FAISS metadata not found. Please train the agent first.")

    index = faiss.read_index(str(index_path))
    metadata = load_metadata(tenant_id)

    print("[FAISS LOAD] metadata_count:", len(metadata))
    print("[FAISS LOAD] index_vectors:", index.ntotal)

    _INDEX_CACHE[tenant_key] = index
    _METADATA_CACHE[tenant_key] = metadata

    return index, metadata


def add_chunks_to_faiss(chunks: List[Dict], tenant_id) -> Dict:
    index_path = get_index_path(tenant_id)
    metadata_path = get_metadata_path(tenant_id)

    if not chunks:
        total = len(load_metadata(tenant_id))
        print("[FAISS ADD] No chunks received")
        print("[FAISS ADD] tenant_id:", tenant_id)
        print("[FAISS ADD] total_vectors:", total)

        return {
            "index_path": str(index_path),
            "metadata_path": str(metadata_path),
            "vectors_added": 0,
            "total_vectors": total,
        }

    existing_metadata = load_metadata(tenant_id)
    existing_text_hashes = {
        (item.get("text_hash") or "")
        for item in existing_metadata
        if item.get("text_hash")
    }
    existing_texts = {get_text_from_chunk(item) for item in existing_metadata if get_text_from_chunk(item)}

    valid_chunks = []
    for item in chunks:
        text = get_text_from_chunk(item)
        if not text:
            continue
        text_hash = item.get("text_hash")
        if text_hash and text_hash in existing_text_hashes:
            continue
        if not text_hash and text in existing_texts:
            continue
        valid_chunks.append(item)

    texts = [get_text_from_chunk(item) for item in valid_chunks]

    if not texts:
        total = len(load_metadata(tenant_id))
        print("[FAISS ADD] No valid text chunks")
        print("[FAISS ADD] tenant_id:", tenant_id)
        print("[FAISS ADD] total_vectors:", total)

        return {
            "index_path": str(index_path),
            "metadata_path": str(metadata_path),
            "vectors_added": 0,
            "total_vectors": total,
        }

    model = get_embedding_model()

    print("[FAISS ADD] tenant_id:", tenant_id)
    print("[FAISS ADD] incoming_chunks:", len(chunks))
    print("[FAISS ADD] valid_chunks:", len(valid_chunks))
    print("[FAISS ADD] sample_text:", texts[0][:300])
    print("[FAISS ADD] index_path:", index_path)
    print("[FAISS ADD] metadata_path:", metadata_path)

    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = _normalize(embeddings)

    dimension = embeddings.shape[1]
    index = load_or_create_index(index_path, dimension)

    # existing_metadata is loaded before filtering so repeated training skips duplicate chunks.
    start_vector_id = len(existing_metadata)

    print("[FAISS ADD] old_vectors:", start_vector_id)
    print("[FAISS ADD] old_index_vectors:", index.ntotal)

    index.add(embeddings)
    faiss.write_index(index, str(index_path))

    new_metadata = []

    for i, item in enumerate(valid_chunks):
        text = get_text_from_chunk(item)

        new_metadata.append(
            {
                "vector_id": start_vector_id + i,
                "tenant_id": tenant_id,
                "chunk_id": item.get("chunk_id"),
                "text": text,
                "source_key": item.get("source_key"),
                "source_hash": item.get("source_hash"),
                "source_type": item.get("source_type"),
                "content_type": item.get("content_type"),
                "page_type": item.get("page_type") or "website_page",
                "priority": int(item.get("priority") or 0),
                "is_disabled": bool(item.get("is_disabled") or False),
                "kb_entry_id": item.get("kb_entry_id"),
                "url": item.get("url"),
                "file_name": item.get("file_name"),
                "title": item.get("title"),
                "images": item.get("images") or [],
                "links": item.get("links") or [],
                "images_count": len(item.get("images") or []),
                "links_count": len(item.get("links") or []),
                "text_hash": item.get("text_hash"),
            }
        )

    metadata = existing_metadata + new_metadata
    save_json(metadata_path, metadata)

    clear_tenant_cache(tenant_id)

    print("[FAISS ADD] new_vectors:", len(new_metadata))
    print("[FAISS ADD] total_vectors:", len(metadata))
    print("[FAISS ADD] final_index_vectors:", index.ntotal)

    return {
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
        "vectors_added": len(new_metadata),
        "total_vectors": len(metadata),
    }


def build_faiss_index(chunks, tenant_id):
    return add_chunks_to_faiss(chunks, tenant_id)


def _query_wants_product_or_catalog(query: str) -> bool:
    value = (query or "").lower()
    return any(word in value for word in [
        "product", "products", "catalog", "catalogue", "item", "items",
        "model", "models", "range", "category", "categories", "sell", "provide",
        "image", "images", "photo", "picture", "link", "page",
    ])


def _product_page_boost(item: Dict, query: str) -> float:
    """Boost tenant-specific product/catalog KB entries, labels, images, and links."""
    url = str(item.get("url") or "").lower()
    title = str(item.get("title") or "").lower()
    page_type = str(item.get("page_type") or "").lower()
    text = get_text_from_chunk(item).lower()
    tags = " ".join([str(x).lower() for x in item.get("tags") or []])
    links = " ".join([str(x).lower() for x in item.get("links") or []])
    haystack = f"{url} {title} {page_type} {tags} {links} {text[:600]}"
    query_value = (query or "").lower()
    query_tokens = [t for t in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9&./-]{2,}", query_value) if len(t) >= 3]

    boost = 0.0
    wants_assets_or_product = _query_wants_product_or_catalog(query) or any(
        x in query_value for x in ["image", "photo", "picture", "show", "link", "url", "website", "buy"]
    )

    if page_type in {"product_page", "catalog", "catalogue", "service_page"}:
        boost += 0.18
    if any(x in haystack for x in ["product", "products", "catalog", "catalogue", "shop", "item", "model", "category", "buy"]):
        boost += 0.12
    if wants_assets_or_product and item.get("images"):
        boost += 0.10
    if wants_assets_or_product and item.get("links"):
        boost += 0.08
    if any(token in title or token in tags or token in url for token in query_tokens):
        boost += 0.18
    else:
        matching = sum(1 for token in query_tokens if token in haystack)
        boost += min(0.20, matching * 0.04)

    try:
        boost += min(0.20, max(0.0, float(item.get("priority") or 0)) / 100.0)
    except Exception:
        pass

    if any(x in haystack for x in ["privacy", "terms", "cookie", "blog", "article"]):
        boost -= 0.25
    return boost


def search_faiss(query: str, tenant_id, top_k: int = 5) -> List[Dict]:
    query = (query or "").strip()

    if not query:
        return []

    index, metadata = load_tenant_index_and_metadata(tenant_id)

    if not metadata:
        print("[FAISS SEARCH] metadata empty for tenant:", tenant_id)
        return []

    model = get_embedding_model()

    query_embedding = model.encode([query])
    query_embedding = _normalize(query_embedding)

    candidate_limit = max(top_k * 4, 20)
    limit = min(candidate_limit, len(metadata))
    scores, ids = index.search(query_embedding, limit)

    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or idx >= len(metadata):
            continue

        item = dict(metadata[idx])
        if item.get("is_disabled"):
            continue
        item["score"] = float(score)
        item["base_score"] = float(score)
        item["boost_score"] = _product_page_boost(item, query)
        item["rank_score"] = item["base_score"] + item["boost_score"]
        item["text"] = get_text_from_chunk(item)
        results.append(item)

    results = sorted(results, key=lambda x: x.get("rank_score", x.get("score", 0)), reverse=True)

    print("[FAISS SEARCH] tenant_id:", tenant_id)
    print("[FAISS SEARCH] query:", query)
    print("[FAISS SEARCH] metadata_count:", len(metadata))
    print("[FAISS SEARCH] index_vectors:", index.ntotal)
    print("[FAISS SEARCH] results_count:", len(results))
    print("[FAISS SEARCH] top_score:", results[0]["score"] if results else None)
    print("[FAISS SEARCH] top_text_len:", len(results[0].get("text", "")) if results else 0)
    print("[FAISS SEARCH] top_text_sample:", results[0].get("text", "")[:250] if results else "")

    return results[:top_k]
