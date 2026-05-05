import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# 🔹 Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# 🔹 Load scraped data
with open("website_data.json", "r", encoding="utf-8") as f:
    raw_docs = json.load(f)

documents = []

# 🔹 Chunking function
def chunk_text(text, chunk_size=250, overlap=50):
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap

    return chunks


# 🔹 Create chunks
for doc in raw_docs:
    for chunk in chunk_text(doc["text"]):
        documents.append({
            "text": chunk,
            "url": doc["url"]
        })

print(f"Total chunks created: {len(documents)}")

# 🔹 Convert to embeddings
texts = [d["text"] for d in documents]

doc_embeddings = model.encode(texts)

# 🔹 Create FAISS index
dimension = len(doc_embeddings[0])
index = faiss.IndexFlatL2(dimension)
index.add(np.array(doc_embeddings))

print("FAISS index ready")

# 🔹 Retrieval function
def retrieve(query, k=3):
    query_vec = model.encode([query])

    distances, indices = index.search(np.array(query_vec), k)

    results = []
    for i in indices[0]:
        results.append({
            "text": documents[i]["text"],
            "url": documents[i]["url"]
        })

    return results