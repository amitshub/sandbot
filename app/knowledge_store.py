import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from app.tokenizer import clean_text, infer_tags
from app.utils import DATA_DIR, safe_filename, save_json, load_json

KNOWLEDGE_DIR = DATA_DIR / "knowledge"


def _tenant_dir(tenant_id) -> Path:
    path = KNOWLEDGE_DIR / str(tenant_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _entries_path(tenant_id) -> Path:
    return _tenant_dir(tenant_id) / "entries.json"


def _text_dir(tenant_id) -> Path:
    path = _tenant_dir(tenant_id) / "texts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _preview(text: str, limit: int = 280) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    return value[:limit] + ("..." if len(value) > limit else "")


def _load_entries(tenant_id) -> List[Dict]:
    data = load_json(_entries_path(tenant_id), default=[])
    return data if isinstance(data, list) else []


def _save_entries(tenant_id, entries: List[Dict]) -> None:
    save_json(_entries_path(tenant_id), entries)


def _unique_keep_order(values) -> List[str]:
    seen = set()
    output = []
    for value in values or []:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output



def _extract_content_from_text_file(raw: str) -> str:
    marker = "Content:"
    return raw.split(marker, 1)[1].strip() if marker in raw else (raw or "").strip()


def _read_entry_full_text(tenant_id, item: Dict) -> str:
    text_file = item.get("text_file") or ""
    if not text_file:
        return ""
    path = _text_dir(tenant_id) / text_file
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return _extract_content_from_text_file(raw)


def _entry_with_text(tenant_id, item: Dict) -> Dict:
    entry = dict(item)
    full_text = _read_entry_full_text(tenant_id, item)
    entry["text"] = full_text
    if full_text:
        entry["text_length"] = len(full_text)
        entry["preview"] = _preview(full_text)
    return entry


def save_knowledge_documents(
    tenant_id,
    documents: List[Dict],
    source_key: str,
    source_hash: str,
    default_source_type: str = "training",
    tags: Optional[List[str]] = None,
) -> List[Dict]:
    saved_entries = []
    entries = _load_entries(tenant_id)

    existing_hashes = {
        item.get("source_hash")
        for item in entries
        if item.get("source_hash")
    }

    if source_hash in existing_hashes:
        return []

    existing_urls = {
        str(item.get("url") or "").strip().rstrip("/").lower()
        for item in entries
        if item.get("url")
    }

    existing_titles = {
        str(item.get("title") or "").strip().lower()
        for item in entries
        if item.get("title")
    }

    seen_urls = set()
    seen_titles = set()
    seen_text_hashes = set()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_tags = tags or []

    for index, doc in enumerate(documents or [], start=1):
        raw_text = doc.get("text") or ""
        text = clean_text(raw_text)

        if not text:
            continue

        text_hash = re.sub(r"\s+", " ", text).strip().lower()

        url_key = str(doc.get("url") or "").strip().rstrip("/").lower()
        title = (
            doc.get("title")
            or doc.get("file_name")
            or doc.get("url")
            or f"Training Entry {index}"
        )
        title_key = str(title or "").strip().lower()

        if url_key and (url_key in existing_urls or url_key in seen_urls):
            continue

        if title_key and (title_key in existing_titles or title_key in seen_titles):
            continue

        if text_hash in seen_text_hashes:
            continue

        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        seen_text_hashes.add(text_hash)

        images = _unique_keep_order(doc.get("images") or [])
        links = _unique_keep_order(doc.get("links") or [])
        source_type = doc.get("source_type") or default_source_type
        content_type = doc.get("content_type") or "Mixed Content"
        entry_tags = _unique_keep_order([
            source_type,
            content_type,
            doc.get("page_type") or "website_page",
            *base_tags,
            *infer_tags(doc, text),
        ])
        entry_id = uuid4().hex

        filename_title = safe_filename(str(title))[:80]
        txt_filename = f"{timestamp}_{index}_{filename_title}.txt"
        txt_path = _text_dir(tenant_id) / txt_filename

        header = [
            f"Title: {title}",
            f"Source Type: {source_type}",
            f"Content Type: {content_type}",
            f"Page Type: {doc.get('page_type') or 'website_page'}",
            f"Priority: {int(doc.get('priority') or 0)}",
            f"URL: {doc.get('url') or ''}",
            f"File Name: {doc.get('file_name') or ''}",
            f"Images Count: {len(images)}",
            f"Links Count: {len(links)}",
            f"Tags: {', '.join(entry_tags)}",
            f"Saved At: {_now_iso()}",
            "",
        ]

        if images:
            header.append("Image URLs:")
            header.extend(images)
            header.append("")

        if links:
            header.append("Page Links:")
            header.extend(links[:100])
            header.append("")

        header.extend([
            "Content:",
            text,
            "",
        ])

        txt_path.write_text("\n".join(header), encoding="utf-8")

        entry = {
            "id": entry_id,
            "tenant_id": tenant_id,
            "title": str(title),
            "source_type": source_type,
            "content_type": content_type,
            "page_type": doc.get("page_type") or "website_page",
            "priority": int(doc.get("priority") or 0),
            "is_disabled": bool(doc.get("is_disabled") or False),
            "url": doc.get("url"),
            "file_name": doc.get("file_name"),
            "source_key": source_key,
            "source_hash": source_hash,
            "text_file": txt_filename,
            "text_length": len(text),
            "images_count": len(images),
            "links_count": len(links),
            "images": images,
            "links": links[:100],
            "preview": _preview(text),
            "tags": entry_tags,
            "status": "active",
            "created_at": _now_iso(),
        }

        entries.append(entry)
        saved_entries.append(entry)

    _save_entries(tenant_id, entries)
    rebuild_combined_training_file(tenant_id)
    return saved_entries

# def save_knowledge_documents(
#     tenant_id,
#     documents: List[Dict],
#     source_key: str,
#     source_hash: str,
#     default_source_type: str = "training",
#     tags: Optional[List[str]] = None,
# ) -> List[Dict]:
#     """
#     Save readable text files for the same documents that go into FAISS.
#     This does not replace FAISS. It only creates human-readable proof of training.
#     Now it also records image/link counts and URL lists extracted from website pages.
#     """
#     saved_entries = []
#     entries = _load_entries(tenant_id)
#     existing_hashes = {item.get("source_hash") for item in entries if item.get("source_hash")}

#     # If the exact same source hash was already saved, avoid duplicate visible entries.
#     if source_hash in existing_hashes:
#         return []

#     timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
#     base_tags = tags or []

#     for index, doc in enumerate(documents or [], start=1):
#         raw_text = doc.get("text") or ""
#         text = clean_text(raw_text)
#         if not text:
#             continue

#         images = _unique_keep_order(doc.get("images") or [])
#         links = _unique_keep_order(doc.get("links") or [])

#         title = (
#             doc.get("title")
#             or doc.get("file_name")
#             or doc.get("url")
#             or f"Training Entry {index}"
#         )
#         source_type = doc.get("source_type") or default_source_type
#         content_type = doc.get("content_type") or "Mixed Content"
#         entry_id = uuid4().hex
#         filename_title = safe_filename(str(title))[:80]
#         txt_filename = f"{timestamp}_{index}_{filename_title}.txt"
#         txt_path = _text_dir(tenant_id) / txt_filename

#         header = [
#             f"Title: {title}",
#             f"Source Type: {source_type}",
#             f"Content Type: {content_type}",
#             f"URL: {doc.get('url') or ''}",
#             f"File Name: {doc.get('file_name') or ''}",
#             f"Images Count: {len(images)}",
#             f"Links Count: {len(links)}",
#             f"Saved At: {_now_iso()}",
#             "",
#         ]

#         if images:
#             header.append("Image URLs:")
#             header.extend(images)
#             header.append("")

#         if links:
#             header.append("Page Links:")
#             header.extend(links[:100])
#             header.append("")

#         header.extend([
#             "Content:",
#             text,
#             "",
#         ])
#         txt_path.write_text("\n".join(header), encoding="utf-8")

#         entry = {
#             "id": entry_id,
#             "tenant_id": tenant_id,
#             "title": str(title),
#             "source_type": source_type,
#             "content_type": content_type,
#             "url": doc.get("url"),
#             "file_name": doc.get("file_name"),
#             "source_key": source_key,
#             "source_hash": source_hash,
#             "text_file": txt_filename,
#             "text_length": len(text),
#             "images_count": len(images),
#             "links_count": len(links),
#             "preview": _preview(text),
#             "tags": list(dict.fromkeys([source_type, content_type, doc.get("page_type") or "website_page", *base_tags])),
#             "status": "active",
#             "created_at": _now_iso(),
#         }
#         entries.append(entry)
#         saved_entries.append(entry)

#     _save_entries(tenant_id, entries)
#     rebuild_combined_training_file(tenant_id)
#     return saved_entries


def list_knowledge_entries(tenant_id, search: str = "") -> List[Dict]:
    entries = _load_entries(tenant_id)
    search = (search or "").strip().lower()

    # List view stays lightweight, but search also checks the full text file so
    # users can find content that is not present in the short preview.
    if not search:
        return sorted(entries, key=lambda x: x.get("created_at", ""), reverse=True)

    filtered = []
    for item in entries:
        full_text = _read_entry_full_text(tenant_id, item)
        haystack = " ".join([
            str(item.get("title") or ""),
            str(item.get("preview") or ""),
            str(full_text or ""),
            str(item.get("source_type") or ""),
            " ".join(item.get("tags") or []),
        ]).lower()
        if search in haystack:
            filtered.append(item)
    return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)


def get_knowledge_entry(tenant_id, entry_id: str) -> Optional[Dict]:
    for item in _load_entries(tenant_id):
        if item.get("id") == entry_id:
            return _entry_with_text(tenant_id, item)
    return None


def get_entry_text_path(tenant_id, entry_id: str) -> Optional[Path]:
    entry = get_knowledge_entry(tenant_id, entry_id)
    if not entry:
        return None
    path = _text_dir(tenant_id) / entry.get("text_file", "")
    return path if path.exists() else None


def update_knowledge_entry(tenant_id, entry_id: str, updates: Dict) -> Optional[Dict]:
    """Edit KB metadata/text without changing frontend flow. Call rebuild FAISS after this."""
    entries = _load_entries(tenant_id)
    updated = None
    allowed_meta = {"title", "page_type", "priority", "is_disabled", "tags", "url", "images", "links"}

    for item in entries:
        if item.get("id") != entry_id:
            continue

        for key in allowed_meta:
            if key in updates:
                if key == "priority":
                    item[key] = int(updates.get(key) or 0)
                elif key == "is_disabled":
                    item[key] = bool(updates.get(key))
                    item["status"] = "disabled" if item[key] else "active"
                elif key == "tags":
                    item[key] = _unique_keep_order(updates.get(key) or [])
                elif key in {"images", "links"}:
                    item[key] = _unique_keep_order(updates.get(key) or [])
                    item[f"{key}_count"] = len(item[key])
                else:
                    item[key] = updates.get(key)

        if "text" in updates and updates.get("text") is not None:
            text = clean_text(updates.get("text") or "")
            if text:
                path = _text_dir(tenant_id) / item.get("text_file", "")
                header = [
                    f"Title: {item.get('title') or ''}",
                    f"Source Type: {item.get('source_type') or ''}",
                    f"Content Type: {item.get('content_type') or ''}",
                    f"Page Type: {item.get('page_type') or ''}",
                    f"Priority: {int(item.get('priority') or 0)}",
                    f"URL: {item.get('url') or ''}",
                    f"File Name: {item.get('file_name') or ''}",
                    f"Edited At: {_now_iso()}",
                    "",
                    "Content:",
                    text,
                    "",
                ]
                path.write_text("\n".join(header), encoding="utf-8")
                item["text_length"] = len(text)
                item["preview"] = _preview(text)

        item["updated_at"] = _now_iso()
        updated = item
        break

    if updated:
        _save_entries(tenant_id, entries)
        rebuild_combined_training_file(tenant_id)
    return updated


def delete_knowledge_entry(tenant_id, entry_id: str) -> bool:
    entries = _load_entries(tenant_id)
    kept = [item for item in entries if item.get("id") != entry_id]
    if len(kept) == len(entries):
        return False
    _save_entries(tenant_id, kept)
    rebuild_combined_training_file(tenant_id)
    return True


def load_active_knowledge_documents(tenant_id) -> List[Dict]:
    """Return active editable KB entries as docs for a full FAISS rebuild."""
    docs = []
    for item in _load_entries(tenant_id):
        if item.get("is_disabled") or item.get("status") == "disabled":
            continue
        path = _text_dir(tenant_id) / item.get("text_file", "")
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = _extract_content_from_text_file(raw)
        if not text:
            continue
        docs.append({
            "source_type": item.get("source_type") or "knowledge",
            "content_type": item.get("content_type") or "Mixed Content",
            "page_type": item.get("page_type") or "website_page",
            "priority": int(item.get("priority") or 0),
            "is_disabled": False,
            "kb_entry_id": item.get("id"),
            "url": item.get("url"),
            "file_name": item.get("file_name"),
            "title": item.get("title"),
            "text": text,
            "images": item.get("images") or [],
            "links": item.get("links") or [],
            "tags": item.get("tags") or [],
        })
    return docs


def rebuild_combined_training_file(tenant_id) -> Path:
    combined_path = _tenant_dir(tenant_id) / "all_training_data.txt"
    entries = sorted(_load_entries(tenant_id), key=lambda x: x.get("created_at", ""))
    parts = []

    for item in entries:
        if item.get("is_disabled") or item.get("status") == "disabled":
            continue
        path = _text_dir(tenant_id) / item.get("text_file", "")
        if path.exists():
            parts.append("=" * 80)
            parts.append(f"ENTRY ID: {item.get('id')}")
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))

    combined_path.write_text("\n\n".join(parts), encoding="utf-8")
    return combined_path


def get_combined_training_path(tenant_id) -> Path:
    path = _tenant_dir(tenant_id) / "all_training_data.txt"
    if not path.exists():
        rebuild_combined_training_file(tenant_id)
    return path
