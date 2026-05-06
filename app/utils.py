# import json
# import re
# import shutil
# from pathlib import Path


# BASE_DIR = Path(__file__).resolve().parent.parent
# DATA_DIR = BASE_DIR / "data"

# PENDING_DIR = DATA_DIR / "pending"
# PENDING_UPLOAD_DIR = PENDING_DIR / "uploaded_files"
# PENDING_SCRAPED_DIR = PENDING_DIR / "scraped"

# DONE_DIR = DATA_DIR / "done_token"
# DONE_UPLOAD_DIR = DONE_DIR / "uploaded_files"
# DONE_SCRAPED_DIR = DONE_DIR / "scraped"

# FAILED_DIR = DATA_DIR / "failed"
# FAISS_DIR = DATA_DIR / "faiss_index"

# for folder in [
#     DATA_DIR,
#     PENDING_DIR,
#     PENDING_UPLOAD_DIR,
#     PENDING_SCRAPED_DIR,
#     DONE_DIR,
#     DONE_UPLOAD_DIR,
#     DONE_SCRAPED_DIR,
#     FAILED_DIR,
#     FAISS_DIR,
# ]:
#     folder.mkdir(parents=True, exist_ok=True)


# def safe_filename(filename: str) -> str:
#     filename = filename.replace("\\", "_").replace("/", "_")
#     filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
#     return filename or "uploaded_file"


# def save_json(path: Path, data):
#     path.parent.mkdir(parents=True, exist_ok=True)
#     path.write_text(
#         json.dumps(data, ensure_ascii=False, indent=2),
#         encoding="utf-8",
#     )


# def move_file_safely(src: Path, dst: Path):
#     dst.parent.mkdir(parents=True, exist_ok=True)

#     if not src.exists():
#         return

#     final_dst = dst
#     counter = 1

#     while final_dst.exists():
#         final_dst = dst.with_name(f"{dst.stem}_{counter}{dst.suffix}")
#         counter += 1

#     shutil.move(str(src), str(final_dst))


# def load_json(path: Path, default=None):
#     if not path.exists():
#         return default
#     try:
#         return json.loads(path.read_text(encoding="utf-8"))
#     except Exception:
#         return default


import os
import json
import re
import shutil
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
FAISS_DIR = Path(os.getenv("FAISS_DIR", str(DATA_DIR / "faiss")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(DATA_DIR / "uploads")))

PENDING_UPLOAD_DIR = UPLOAD_DIR / "pending_uploads"
DONE_UPLOAD_DIR = UPLOAD_DIR / "done_uploads"

PENDING_SCRAPED_DIR = DATA_DIR / "pending_scraped"
DONE_SCRAPED_DIR = DATA_DIR / "done_scraped"

FAILED_DIR = DATA_DIR / "failed"

for folder in [
    DATA_DIR,
    FAISS_DIR,
    UPLOAD_DIR,
    PENDING_UPLOAD_DIR,
    DONE_UPLOAD_DIR,
    PENDING_SCRAPED_DIR,
    DONE_SCRAPED_DIR,
    FAILED_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)