"""Railway volume path helper.
Use this pattern inside your existing app/utils.py and app/index_builder.py.
Mount a Railway Volume at /data, then keep FAISS/index/uploads under /data.
"""
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
FAISS_DIR = Path(os.getenv("FAISS_DIR", str(DATA_DIR / "faiss")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))

PENDING_UPLOAD_DIR = UPLOAD_DIR / "pending_uploads"
DONE_UPLOAD_DIR = UPLOAD_DIR / "done_uploads"
PENDING_SCRAPED_DIR = DATA_DIR / "pending_scraped"
DONE_SCRAPED_DIR = DATA_DIR / "done_scraped"
FAILED_DIR = DATA_DIR / "failed"

for path in [DATA_DIR, FAISS_DIR, UPLOAD_DIR, PENDING_UPLOAD_DIR, DONE_UPLOAD_DIR, PENDING_SCRAPED_DIR, DONE_SCRAPED_DIR, FAILED_DIR]:
    path.mkdir(parents=True, exist_ok=True)
