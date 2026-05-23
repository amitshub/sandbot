import hashlib
import re


PRODUCT_KEYWORDS = [
    "product", "products", "catalog", "catalogue", "shop", "item", "model",
    "price", "pricing", "rate", "cost", "stock", "available", "specification",
    "material", "size", "color", "finish", "warranty", "installation",
]



NOISY_LINE_PATTERNS = [
    r"width\s*=\s*device-width",
    r"initial-scale\s*=\s*1\.0",
    r"IE\s*=\s*edge",
    r"viewport",
    r"charset\s*=\s*utf-?8",
    r"<script.*?</script>",
    r"<style.*?</style>",
    r"javascript:",
    r"function\s*\(",
    r"var\s+[a-zA-Z_$]",
    r"\.css\b|\.js\b",
    r"cookie policy|accept cookies|manage cookies",
    r"privacy policy|terms and conditions|all rights reserved",
    r"subscribe to our newsletter|login\s+register|add to cart\s+wishlist",
]

LOW_VALUE_SINGLE_WORDS = {
    # These words often came from menu/sitemap/location spam in scraped pages.
    # They are removed only as standalone words, not inside normal sentences.
    "airport", "university", "road", "send", "rate",
}

LOW_VALUE_PHRASES = [
    "jammu airport", "bagdogra airport", "darbhanga airport", "udaipur airport",
    "agra airport", "mountain view hotel", "guru jambeshwor university",
    "mata pateswari university", "maa vindhyavasini university",
]


def clean_text(text: str) -> str:
    """
    Clean noisy website/PDF text before chunking and embedding.

    Important: this function is intentionally conservative. It removes clear HTML/meta/menu
    noise but keeps real product/support/company knowledge intact.
    """
    if not text:
        return ""

    text = str(text).replace("\x00", " ")
    text = text.replace("Â®", "®").replace("â€“", "-").replace("â€”", "-")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")

    # Remove full script/style blocks when raw HTML leaks through.
    for pattern in NOISY_LINE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE | re.DOTALL)

    # Remove common HTML/meta fragments and long attribute fragments.
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\b(?:class|id|style|href|src|alt|title)\s*=\s*['\"][^'\"]{0,120}['\"]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+\.(?:css|js)(?:\?\S+)?", " ", text, flags=re.IGNORECASE)

    # Remove sitemap/location spam phrases observed in the current KB screenshots.
    for phrase in LOW_VALUE_PHRASES:
        text = re.sub(re.escape(phrase), " ", text, flags=re.IGNORECASE)

    # Remove low-value standalone words only when they appear excessively.
    lower = text.lower()
    for word in LOW_VALUE_SINGLE_WORDS:
        if lower.count(word) >= 2:
            text = re.sub(rf"\b{re.escape(word)}\b", " ", text, flags=re.IGNORECASE)

    # Drop tiny navigation-like repeated fragments.
    text = re.sub(r"\b(home|menu|next|previous|read more|view more|click here)\b", " ", text, flags=re.IGNORECASE)
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


def _tokens(text: str):
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9&./-]{2,}", (text or "").lower())


def infer_tags(doc, text: str, limit: int = 12):
    explicit = doc.get("tags") or doc.get("labels") or []
    tags = [str(x).strip().lower() for x in explicit if str(x).strip() and str(x).strip().lower() not in LOW_VALUE_SINGLE_WORDS]
    haystack = " ".join([
        str(doc.get("title") or ""),
        str(doc.get("url") or ""),
        text[:1200],
    ]).lower()

    for word in PRODUCT_KEYWORDS:
        if word in haystack:
            tags.append(word)

    # Add high-value product-like phrases from titles/headings.
    title = str(doc.get("title") or "")
    for phrase in re.split(r"[-|:/]", title):
        phrase = phrase.strip().lower()
        if 3 <= len(phrase) <= 45:
            tags.append(phrase)

    # Add frequent nouns/product terms from this document.
    stop = {
        "the","and","for","with","from","this","that","your","our","you","are","can","will",
        "have","has","about","company","business","details","information","page","website",
        "contact","home","read","more","quality","best","provide","offer","offers","available",
        "solution","solutions","customer","support","online","india","policy","terms","privacy",
        "airport","university","road","send","rate","cookie","width","device","initial","scale",
    }
    freq = {}
    for token in _tokens(text[:3000]):
        if len(token) < 4 or token in stop or token.isdigit():
            continue
        freq[token] = freq.get(token, 0) + 1
    for token, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        if count >= 2:
            tags.append(token)
        if len(tags) >= limit * 2:
            break

    return _unique_keep_order(tags)[:limit]


def chunk_text(text: str, chunk_size: int = 220, overlap: int = 45):
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


def _build_embedding_text(doc, chunk: str, chunk_index: int, total_chunks: int, tags):
    """
    Build private searchable text for embeddings only.

    IMPORTANT:
    - This text helps FAISS match title/page type/tags/url.
    - It must NOT be shown to the LLM as answer context.
    - The LLM receives the clean raw knowledge text from `text`.
    """
    title = doc.get("title") or doc.get("file_name") or doc.get("url") or "Knowledge Entry"
    page_type = doc.get("page_type") or "website_page"
    url = doc.get("url") or ""
    priority = int(doc.get("priority") or 0)
    labels = ", ".join(tags or [])
    prefix = (
        f"Search hints only. Page type: {page_type}. "
        f"Title: {title}. "
        f"Tags: {labels}. "
        f"Source URL: {url}. "
        f"Priority: {priority}. "
        f"Chunk: {chunk_index + 1}/{total_chunks}. "
    )
    return f"{prefix}\nKnowledge: {chunk}".strip()


def create_chunks(documents, chunk_size: int = 220, overlap: int = 45):
    chunked_docs = []
    seen_chunk_hashes = set()

    for doc_index, doc in enumerate(documents or []):
        raw_text = doc.get("text", "")
        text = clean_text(raw_text)
        parts = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        images = _unique_keep_order(doc.get("images") or [])
        links = _unique_keep_order(doc.get("links") or [])
        tags = infer_tags(doc, text)

        for chunk_index, chunk in enumerate(parts):
            semantic_text = _build_embedding_text(doc, chunk, chunk_index, len(parts), tags)
            chunk_hash = _hash_text(semantic_text)

            # Avoid duplicate chunks created by repeated website menus/footer/header text.
            if chunk_hash in seen_chunk_hashes:
                continue
            seen_chunk_hashes.add(chunk_hash)

            chunked_docs.append(
                {
                    "chunk_id": f"doc_{doc_index}_chunk_{chunk_index}",
                    # Clean customer-facing knowledge used in LLM context.
                    # Do not put Title/Tags/URL/Priority here, otherwise the LLM may repeat them.
                    "text": chunk,
                    "raw_text": chunk,
                    # Private retrieval-only text used for embeddings/search quality.
                    "embedding_text": semantic_text,
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
                    "tags": tags,
                    # These are metadata only. FAISS embeds text, but chunks.json stores these URLs.
                    "images": images,
                    "links": links,
                    "images_count": len(images),
                    "links_count": len(links),
                }
            )

    return chunked_docs
