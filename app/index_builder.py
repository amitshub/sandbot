# from typing import Dict, List

# import faiss
# import numpy as np
# from sentence_transformers import SentenceTransformer

# from app.utils import FAISS_DIR, load_json, save_json

# MODEL_NAME = "all-MiniLM-L6-v2"

# _model = None


# def get_embedding_model():
#     global _model
#     if _model is None:
#         _model = SentenceTransformer(MODEL_NAME)
#     return _model


# def get_index_path(tenant_id):
#     return FAISS_DIR / f"index_{tenant_id}.faiss"


# def get_metadata_path(tenant_id):
#     return FAISS_DIR / f"metadata_{tenant_id}.json"


# def _normalize(embeddings: np.ndarray) -> np.ndarray:
#     embeddings = np.array(embeddings).astype("float32")
#     faiss.normalize_L2(embeddings)
#     return embeddings


# def load_metadata(tenant_id) -> List[Dict]:
#     metadata_path = get_metadata_path(tenant_id)
#     data = load_json(metadata_path, default=[])
#     return data if isinstance(data, list) else []


# def load_or_create_index(index_path, dimension: int):
#     if index_path.exists():
#         try:
#             return faiss.read_index(str(index_path))
#         except Exception:
#             pass

#     return faiss.IndexFlatIP(dimension)


# def add_chunks_to_faiss(chunks: List[Dict], tenant_id) -> Dict:
#     index_path = get_index_path(tenant_id)
#     metadata_path = get_metadata_path(tenant_id)

#     if not chunks:
#         return {
#             "index_path": str(index_path),
#             "metadata_path": str(metadata_path),
#             "vectors_added": 0,
#             "total_vectors": len(load_metadata(tenant_id)),
#         }

#     model = get_embedding_model()
#     texts = [item["text"] for item in chunks]

#     embeddings = model.encode(texts, show_progress_bar=True)
#     embeddings = _normalize(embeddings)

#     dimension = embeddings.shape[1]
#     index = load_or_create_index(index_path, dimension)

#     existing_metadata = load_metadata(tenant_id)
#     start_vector_id = len(existing_metadata)

#     index.add(embeddings)
#     faiss.write_index(index, str(index_path))

#     new_metadata = []

#     for i, item in enumerate(chunks):
#         new_metadata.append(
#             {
#                 "vector_id": start_vector_id + i,
#                 "tenant_id": tenant_id,
#                 "chunk_id": item.get("chunk_id"),
#                 "text": item.get("text"),
#                 "source_key": item.get("source_key"),
#                 "source_hash": item.get("source_hash"),
#                 "source_type": item.get("source_type"),
#                 "content_type": item.get("content_type"),
#                 "url": item.get("url"),
#                 "file_name": item.get("file_name"),
#                 "title": item.get("title"),
#             }
#         )

#     metadata = existing_metadata + new_metadata
#     save_json(metadata_path, metadata)

#     return {
#         "index_path": str(index_path),
#         "metadata_path": str(metadata_path),
#         "vectors_added": len(chunks),
#         "total_vectors": len(metadata),
#     }


# def build_faiss_index(chunks, tenant_id):
#     return add_chunks_to_faiss(chunks, tenant_id)


# def search_faiss(query: str, tenant_id, top_k: int = 5) -> List[Dict]:
#     index_path = get_index_path(tenant_id)
#     metadata_path = get_metadata_path(tenant_id)

#     if not index_path.exists() or not metadata_path.exists():
#         raise FileNotFoundError("FAISS index not found. Please train the agent first.")

#     metadata = load_metadata(tenant_id)

#     if not metadata:
#         return []

#     index = faiss.read_index(str(index_path))

#     model = get_embedding_model()
#     query_embedding = model.encode([query])
#     query_embedding = _normalize(query_embedding)

#     scores, ids = index.search(query_embedding, min(top_k, len(metadata)))

#     results = []

#     for score, idx in zip(scores[0], ids[0]):
#         if idx < 0 or idx >= len(metadata):
#             continue

#         item = dict(metadata[idx])
#         item["score"] = float(score)
#         results.append(item)

#     return results 

from typing import Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.utils import FAISS_DIR, load_json, save_json

MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_INDEX_CACHE = {}
_METADATA_CACHE = {}


def get_embedding_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def get_index_path(tenant_id):
    return FAISS_DIR / f"index_{tenant_id}.faiss"


def get_metadata_path(tenant_id):
    return FAISS_DIR / f"metadata_{tenant_id}.json"


def clear_tenant_cache(tenant_id):
    tenant_key = str(tenant_id)
    _INDEX_CACHE.pop(tenant_key, None)
    _METADATA_CACHE.pop(tenant_key, None)


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
            return faiss.read_index(str(index_path))
        except Exception:
            pass

    return faiss.IndexFlatIP(dimension)


def load_tenant_index_and_metadata(tenant_id):
    tenant_key = str(tenant_id)

    if tenant_key in _INDEX_CACHE and tenant_key in _METADATA_CACHE:
        return _INDEX_CACHE[tenant_key], _METADATA_CACHE[tenant_key]

    index_path = get_index_path(tenant_id)

    if not index_path.exists():
        raise FileNotFoundError("FAISS index not found. Please train the agent first.")

    index = faiss.read_index(str(index_path))
    metadata = load_metadata(tenant_id)

    _INDEX_CACHE[tenant_key] = index
    _METADATA_CACHE[tenant_key] = metadata

    return index, metadata


def add_chunks_to_faiss(chunks: List[Dict], tenant_id) -> Dict:
    index_path = get_index_path(tenant_id)
    metadata_path = get_metadata_path(tenant_id)

    if not chunks:
        return {
            "index_path": str(index_path),
            "metadata_path": str(metadata_path),
            "vectors_added": 0,
            "total_vectors": len(load_metadata(tenant_id)),
        }

    model = get_embedding_model()

    texts = [
        item.get("text", "").strip()
        for item in chunks
        if item.get("text", "").strip()
    ]

    if not texts:
        return {
            "index_path": str(index_path),
            "metadata_path": str(metadata_path),
            "vectors_added": 0,
            "total_vectors": len(load_metadata(tenant_id)),
        }

    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = _normalize(embeddings)

    dimension = embeddings.shape[1]
    index = load_or_create_index(index_path, dimension)

    existing_metadata = load_metadata(tenant_id)
    start_vector_id = len(existing_metadata)

    index.add(embeddings)
    faiss.write_index(index, str(index_path))

    new_metadata = []

    valid_chunks = [
        item for item in chunks
        if item.get("text", "").strip()
    ]

    for i, item in enumerate(valid_chunks):
        new_metadata.append(
            {
                "vector_id": start_vector_id + i,
                "tenant_id": tenant_id,
                "chunk_id": item.get("chunk_id"),
                "text": item.get("text"),
                "source_key": item.get("source_key"),
                "source_hash": item.get("source_hash"),
                "source_type": item.get("source_type"),
                "content_type": item.get("content_type"),
                "url": item.get("url"),
                "file_name": item.get("file_name"),
                "title": item.get("title"),
            }
        )

    metadata = existing_metadata + new_metadata
    save_json(metadata_path, metadata)

    clear_tenant_cache(tenant_id)

    return {
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
        "vectors_added": len(new_metadata),
        "total_vectors": len(metadata),
    }


def build_faiss_index(chunks, tenant_id):
    return add_chunks_to_faiss(chunks, tenant_id)


def search_faiss(query: str, tenant_id, top_k: int = 5) -> List[Dict]:
    index, metadata = load_tenant_index_and_metadata(tenant_id)

    if not metadata:
        return []

    model = get_embedding_model()

    query_embedding = model.encode([query])
    query_embedding = _normalize(query_embedding)

    scores, ids = index.search(query_embedding, min(top_k, len(metadata)))

    results = []

    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or idx >= len(metadata):
            continue

        item = dict(metadata[idx])
        item["score"] = float(score)
        results.append(item)

    return results