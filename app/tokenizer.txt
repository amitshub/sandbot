# import hashlib
# import re


# def clean_text(text: str) -> str:
#     if not text:
#         return ""

#     text = text.replace("\x00", " ")
#     text = re.sub(r"\s+", " ", text)
#     text = text.strip()

#     junk_patterns = [
#         r"cookie policy",
#         r"accept cookies",
#         r"all rights reserved",
#         r"privacy policy",
#         r"terms and conditions",
#         r"subscribe to our newsletter",
#     ]

#     # Light junk cleanup. Do not over-delete useful business content.
#     for pattern in junk_patterns:
#         text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def _unique_keep_order(values):
#     seen = set()
#     output = []
#     for value in values or []:
#         key = str(value or "").strip()
#         if not key or key in seen:
#             continue
#         seen.add(key)
#         output.append(key)
#     return output


# def _hash_text(text: str) -> str:
#     return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


# def chunk_text(text: str, chunk_size: int = 250, overlap: int = 50):
#     words = text.split()
#     chunks = []
#     start = 0

#     if not words:
#         return chunks

#     if overlap >= chunk_size:
#         overlap = max(0, chunk_size // 5)

#     while start < len(words):
#         end = start + chunk_size
#         chunk = " ".join(words[start:end]).strip()

#         if chunk:
#             chunks.append(chunk)

#         start += chunk_size - overlap

#     return chunks


# def create_chunks(documents, chunk_size: int = 250, overlap: int = 50):
#     chunked_docs = []
#     seen_chunk_hashes = set()

#     for doc_index, doc in enumerate(documents or []):
#         text = doc.get("text", "")
#         parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

#         images = _unique_keep_order(doc.get("images") or [])
#         links = _unique_keep_order(doc.get("links") or [])

#         for chunk_index, chunk in enumerate(parts):
#             chunk_hash = _hash_text(chunk)

#             # Avoid duplicate chunks created by repeated website menus/footer/header text.
#             if chunk_hash in seen_chunk_hashes:
#                 continue
#             seen_chunk_hashes.add(chunk_hash)

#             chunked_docs.append(
#                 {
#                     "chunk_id": f"doc_{doc_index}_chunk_{chunk_index}",
#                     "text": chunk,
#                     "text_hash": chunk_hash,
#                     "source_type": doc.get("source_type"),
#                     "content_type": doc.get("content_type"),
#                     "url": doc.get("url"),
#                     "file_name": doc.get("file_name"),
#                     "title": doc.get("title"),
#                     # These are metadata only. FAISS embeds text, but chunks.json stores these URLs.
#                     "images": images,
#                     "links": links,
#                     "images_count": len(images),
#                     "links_count": len(links),
#                 }
#             )

#     return chunked_docs

import hashlib
import re


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    junk_patterns = [
        r"cookie policy",
        r"accept cookies",
        r"all rights reserved",
        r"privacy policy",
        r"terms and conditions",
        r"subscribe to our newsletter",
    ]

    # Light junk cleanup. Do not over-delete useful business content.
    for pattern in junk_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def _unique_keep_order(values):
    seen = set()
    output = []
    for value in values or []:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def chunk_text(text: str, chunk_size: int = 250, overlap: int = 50):
    words = text.split()
    chunks = []
    start = 0

    if not words:
        return chunks

    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def create_chunks(documents, chunk_size: int = 250, overlap: int = 50):
    chunked_docs = []
    seen_chunk_hashes = set()

    for doc_index, doc in enumerate(documents or []):
        text = doc.get("text", "")
        parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        images = _unique_keep_order(doc.get("images") or [])
        links = _unique_keep_order(doc.get("links") or [])

        for chunk_index, chunk in enumerate(parts):
            chunk_hash = _hash_text(chunk)

            # Avoid duplicate chunks created by repeated website menus/footer/header text.
            if chunk_hash in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(chunk_hash)

            chunked_docs.append(
                {
                    "chunk_id": f"doc_{doc_index}_chunk_{chunk_index}",
                    "text": chunk,
                    "text_hash": chunk_hash,
                    "source_type": doc.get("source_type"),
                    "content_type": doc.get("content_type"),
                    "page_type": doc.get("page_type", "website_page"),
                    "priority": int(doc.get("priority") or 0),
                    "is_disabled": bool(doc.get("is_disabled") or False),
                    "kb_entry_id": doc.get("kb_entry_id"),
                    "url": doc.get("url"),
                    "file_name": doc.get("file_name"),
                    "title": doc.get("title"),
                    # These are metadata only. FAISS embeds text, but chunks.json stores these URLs.
                    "images": images,
                    "links": links,
                    "images_count": len(images),
                    "links_count": len(links),
                }
            )

    return chunked_docs

