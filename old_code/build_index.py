import json
import os
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


INPUT_FILE = "website_data.json"
OUTPUT_DOCS = "documents.json"
OUTPUT_EMB = "embeddings.npy"
INDEX_FILE = "faiss.index"
PROGRESS_FILE = "progress.json"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

model = SentenceTransformer(EMBEDDING_MODEL)


JUNK_PHRASES = [
    "Home About Services",
    "Need help? Talk to an expert",
    "Twitter Facebook Instagram",
    "Mon - Sat 10am - 7pm",
    "search here X",
    "Hour Minutes AM PM",
    "GET A QUICK QUOTE",
    "send a message",
    "Visit Our Office",
    "Visit Out Offices",
    "What’s Happening THE SANDLUS INDIA BLOG",
    "Mission is to Protect your Businesses",
    "Experience you can trust",
    "Service quality you can easily count on",
]


def clean_text(text: str) -> str:
    text = str(text or "")

    # Remove junk fixed phrases
    for phrase in JUNK_PHRASES:
        text = text.replace(phrase, " ")

    # Remove time picker junk like 1 2 3 4 ... 55 SET
    text = re.sub(
        r"\b1\s+2\s+3\s+4\s+5\s+6\s+7\s+8\s+9\s+10\s+11\s+12\b.*?\bSET\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Remove repeated whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove very small useless separators
    text = text.replace("|", " ")

    return text.strip()


def chunk_text(text, chunk_size=150, overlap=30):
    words = clean_text(text).split()

    if not words:
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()

        if len(chunk.split()) >= 30:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    raw_docs = json.load(f)

start_index = 0
documents = []

if os.path.exists(PROGRESS_FILE):
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        progress = json.load(f)
        start_index = progress.get("last_index", 0)
        documents = progress.get("documents", [])

    print(f"🔁 Resuming from page {start_index + 1}/{len(raw_docs)}")


for i in range(start_index, len(raw_docs)):
    doc = raw_docs[i]

    try:
        url = doc.get("url", "")
        text = doc.get("text", "")

        chunks = chunk_text(text)

        print(f"\nProcessing {i + 1}/{len(raw_docs)}")
        print(f"URL: {url}")
        print(f"Chunks created: {len(chunks)}")

        for chunk in chunks:
            documents.append({
                "text": chunk,
                "url": url
            })

        # Save progress after successful page
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_index": i + 1,
                "documents": documents
            }, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"❌ Error at page {i + 1}: {doc.get('url', '')}")
        print(str(e))
        break


print(f"\nTotal chunks ready: {len(documents)}")

if not documents:
    raise ValueError("No chunks created. Check website_data.json.")

texts = [d["text"] for d in documents]

embeddings = model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=True
).astype("float32")

faiss.normalize_L2(embeddings)

np.save(OUTPUT_EMB, embeddings)

with open(OUTPUT_DOCS, "w", encoding="utf-8") as f:
    json.dump(documents, f, ensure_ascii=False, indent=2)

index = faiss.IndexFlatIP(embeddings.shape[1])
index.add(embeddings)

faiss.write_index(index, INDEX_FILE)

print("\n✅ Index built successfully")
print(f"Saved: {OUTPUT_DOCS}")
print(f"Saved: {OUTPUT_EMB}")
print(f"Saved: {INDEX_FILE}")