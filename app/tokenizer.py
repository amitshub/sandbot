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

#     for doc_index, doc in enumerate(documents):
#         text = doc.get("text", "")
#         parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

#         for chunk_index, chunk in enumerate(parts):
#             chunked_docs.append(
#                 {
#                     "chunk_id": f"doc_{doc_index}_chunk_{chunk_index}",
#                     "text": chunk,
#                     "source_type": doc.get("source_type"),
#                     "content_type": doc.get("content_type"),
#                     "url": doc.get("url"),
#                     "file_name": doc.get("file_name"),
#                     "title": doc.get("title"),
#                 }
#             )

#     return chunked_docs

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

    for doc_index, doc in enumerate(documents):
        text = doc.get("text", "")
        parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        for chunk_index, chunk in enumerate(parts):
            chunked_docs.append(
                {
                    "chunk_id": f"doc_{doc_index}_chunk_{chunk_index}",
                    "text": chunk,
                    "source_type": doc.get("source_type"),
                    "content_type": doc.get("content_type"),
                    "url": doc.get("url"),
                    "file_name": doc.get("file_name"),
                    "title": doc.get("title"),
                }
            )

    return chunked_docs
