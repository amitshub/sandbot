# # # # from fastapi.staticfiles import StaticFiles
# # # # from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
# # # # from app.auth import router as auth_router, get_current_user
# # # # from fastapi import Depends
# # # # from dotenv import load_dotenv
# # # # load_dotenv()
# # # # import json
# # # # import os
# # # # import re
# # # # import secrets
# # # # import string
# # # # from typing import List, Optional
# # # # from uuid import uuid4

# # # # from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
# # # # from fastapi.middleware.cors import CORSMiddleware
# # # # from pydantic import BaseModel

# # # # from app.chatbot import chat_with_agent
# # # # from app.db import get_main_db_connection
# # # # from app.file_parser import parse_uploaded_file
# # # # from app.index_builder import add_chunks_to_faiss
# # # # from app.integration import router as integration_router
# # # # from app.product_query_bot import router as product_query_router
# # # # from app.knowledge_store import (
# # # #     get_combined_training_path,
# # # #     get_entry_text_path,
# # # #     get_knowledge_entry,
# # # #     list_knowledge_entries,
# # # #     save_knowledge_documents,
# # # # )
# # # # from app.whatsapp import (
# # # #     get_tenant_whatsapp_config,
# # # #     handle_incoming_text_and_reply,
# # # #     normalize_phone,
# # # #     send_whatsapp_media,
# # # #     send_whatsapp_text,
# # # # )
# # # # from app.scraper import scrape_by_request
# # # # from app.training_registry import (
# # # #     docs_to_chunks,
# # # #     is_done,
# # # #     mark_done,
# # # #     mark_failed,
# # # #     mark_processing,
# # # #     normalize_website_json,
# # # #     sha256_bytes,
# # # #     sha256_text,
# # # # )
# # # # from app.utils import (
# # # #     DATA_DIR,
# # # #     DONE_SCRAPED_DIR,
# # # #     DONE_UPLOAD_DIR,
# # # #     FAILED_DIR,
# # # #     PENDING_SCRAPED_DIR,
# # # #     PENDING_UPLOAD_DIR,
# # # #     safe_filename,
# # # #     save_json,
# # # #     move_file_safely,
# # # # )

# # # # app = FastAPI(title="Agent Training + WhatsApp Chat Backend", version="2.1.0")

# # # # # Railway / production friendly CORS.
# # # # # Set CORS_ORIGINS in Railway like:
# # # # # CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com
# # # # _raw_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
# # # # _cors_origins = ["*"] if _raw_cors_origins == "*" else [origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()]

# # # # app.add_middleware(
# # # #     CORSMiddleware,
# # # #     allow_origins=_cors_origins,
# # # #     allow_credentials=True,
# # # #     allow_methods=["*"],
# # # #     allow_headers=["*"],
# # # # )

# # # # app.include_router(auth_router)
# # # # app.include_router(integration_router)
# # # # app.include_router(product_query_router)

# # # # class ChatRequest(BaseModel):
# # # #     message: str
# # # #     session_id: Optional[str] = None
# # # #     top_k: Optional[int] = 2


# # # # class PublicChatRequest(BaseModel):
# # # #     message: str
# # # #     session_id: Optional[str] = None
# # # #     top_k: Optional[int] = 2
# # # #     customer_name: Optional[str] = None
# # # #     customer_email: Optional[str] = None
# # # #     customer_phone: Optional[str] = None


# # # # class PublicLinkUpdateRequest(BaseModel):
# # # #     sweet_name: Optional[str] = None


# # # # class ActiveAgentTypeRequest(BaseModel):
# # # #     active_agent_type: str


# # # # def get_tenant_by_slug(tenant_slug: str):
# # # #     tenant_slug = (tenant_slug or "").strip()
# # # #     if not tenant_slug:
# # # #         return None
    
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT id, slug, tenant_name, status, active_agent_type
# # # #                 FROM tenants
# # # #                 WHERE slug=%s AND status='active'
# # # #                 LIMIT 1
                
# # # #                 """,
# # # #                 (tenant_slug,),
# # # #             )
# # # #             return cur.fetchone()
# # # #     finally:
# # # #         conn.close()


# # # # def upsert_tenant_customer(
# # # #     tenant_id: int,
# # # #     session_id: str,
# # # #     name: str = None,
# # # #     email: str = None,
# # # #     phone: str = None,
# # # #     message: str = None,
# # # #     request: Request = None,
# # # # ):
# # # #     name = (name or "").strip() or None
# # # #     email = (email or "").strip().lower() or None
# # # #     phone = (phone or "").strip() or None
# # # #     message = (message or "").strip() or None

# # # #     user_agent = None
# # # #     ip_address = None

# # # #     if request is not None:
# # # #         user_agent = request.headers.get("user-agent")
# # # #         if request.client:
# # # #             ip_address = request.client.host

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 INSERT INTO tenant_customers
# # # #                     (tenant_id, session_id, name, email, phone, first_message, last_message,
# # # #                      source, status, user_agent, ip_address, last_seen_at)
# # # #                 VALUES
# # # #                     (%s, %s, %s, %s, %s, %s, %s, 'public_chat', 'active', %s, %s, NOW())
# # # #                 ON DUPLICATE KEY UPDATE
# # # #                     name = COALESCE(VALUES(name), name),
# # # #                     email = COALESCE(VALUES(email), email),
# # # #                     phone = COALESCE(VALUES(phone), phone),
# # # #                     first_message = COALESCE(first_message, VALUES(first_message)),
# # # #                     last_message = VALUES(last_message),
# # # #                     user_agent = COALESCE(VALUES(user_agent), user_agent),
# # # #                     ip_address = COALESCE(VALUES(ip_address), ip_address),
# # # #                     status = IF(status='new', 'active', status),
# # # #                     last_seen_at = NOW(),
# # # #                     updated_at = NOW()
# # # #                 """,
# # # #                 (
# # # #                     tenant_id,
# # # #                     session_id,
# # # #                     name,
# # # #                     email,
# # # #                     phone,
# # # #                     message,
# # # #                     message,
# # # #                     user_agent,
# # # #                     ip_address,
# # # #                 ),
# # # #             )

# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT id, tenant_id, session_id, name, email, phone, status
# # # #                 FROM tenant_customers
# # # #                 WHERE tenant_id=%s AND session_id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id, session_id),
# # # #             )
# # # #             return cur.fetchone()
# # # #     finally:
# # # #         conn.close()


# # # # # ==========================================================
# # # # # Serve React Frontend on Railway
# # # # # Required folder structure:
# # # # # backend/
# # # # #   main.py
# # # # #   build/
# # # # #     index.html
# # # # #     static/
# # # # # ==========================================================
# # # # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # # # BUILD_DIR = os.path.join(BASE_DIR, "build")
# # # # STATIC_DIR = os.path.join(BUILD_DIR, "static")

# # # # if os.path.exists(STATIC_DIR):
# # # #     app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# # # # @app.get("/")
# # # # def serve_react_app():
# # # #     index_path = os.path.join(BUILD_DIR, "index.html")

# # # #     if os.path.exists(index_path):
# # # #         return FileResponse(index_path)

# # # #     return {
# # # #         "status": "ok",
# # # #         "message": "Backend running, but React build/index.html was not found.",
# # # #         "required_folder": "Place React build folder beside main.py as ./build",
# # # #         "training_endpoint": "/train-agent",
# # # #         "protected_chat_endpoint": "/chat",
# # # #         "public_chat_endpoint": "/chat/{tenant_slug} or /chat_{tenant_slug}",
# # # #     }

# # # # # ==========================================================
# # # # # Knowledge Base readable text APIs
# # # # # These APIs let a tenant user see/download the exact text that was extracted
# # # # # and sent for FAISS training.
# # # # # ==========================================================
# # # # @app.get("/knowledge")
# # # # def get_knowledge_entries(search: Optional[str] = "", current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     entries = list_knowledge_entries(tenant_id, search=search or "")
# # # #     return {
# # # #         "success": True,
# # # #         "count": len(entries),
# # # #         "entries": entries,
# # # #     }


# # # # @app.get("/knowledge/download")
# # # # def download_all_knowledge(current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     path = get_combined_training_path(tenant_id)
# # # #     if not path.exists():
# # # #         raise HTTPException(status_code=404, detail="No knowledge text found for this tenant.")
# # # #     return FileResponse(
# # # #         str(path),
# # # #         media_type="text/plain",
# # # #         filename=f"tenant_{tenant_id}_all_training_data.txt",
# # # #     )


# # # # @app.get("/knowledge/{entry_id}")
# # # # def get_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     entry = get_knowledge_entry(tenant_id, entry_id)
# # # #     if not entry:
# # # #         raise HTTPException(status_code=404, detail="Knowledge entry not found.")
# # # #     return {"success": True, "entry": entry}


# # # # @app.get("/knowledge/{entry_id}/download")
# # # # def download_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     entry = get_knowledge_entry(tenant_id, entry_id)
# # # #     path = get_entry_text_path(tenant_id, entry_id)
# # # #     if not entry or not path:
# # # #         raise HTTPException(status_code=404, detail="Knowledge text file not found.")
# # # #     safe_title = safe_filename(entry.get("title") or entry_id)
# # # #     return FileResponse(
# # # #         str(path),
# # # #         media_type="text/plain",
# # # #         filename=f"{safe_title}.txt",
# # # #     )


# # # # # @app.post("/train-agent")
# # # # # async def train_agent(
# # # # #     website_url: Optional[str] = Form(default=""),
# # # # #     sitemap_url: Optional[str] = Form(default=""),
# # # # #     crawl_type: str = Form(default="single_page"),
# # # # #     content_type: str = Form(default="Mixed Content"),
# # # # #     files: List[UploadFile] = File(default=[]),
# # # # # ):
# # # # @app.post("/train-agent")
# # # # async def train_agent(
# # # #     website_url: Optional[str] = Form(default=""),
# # # #     sitemap_url: Optional[str] = Form(default=""),
# # # #     crawl_type: str = Form(default="single_page"),
# # # #     content_type: str = Form(default="Mixed Content"),
# # # #     files: List[UploadFile] = File(default=[]),
# # # #     current_user: dict = Depends(get_current_user),
# # # # ):
# # # #     website_url = (website_url or "").strip()
# # # #     sitemap_url = (sitemap_url or "").strip()
# # # #     crawl_type = (crawl_type or "single_page").strip()
# # # #     content_type = (content_type or "Mixed Content").strip()
# # # #     tenant_id = current_user["tenant_id"]

# # # #     existing_website_json = DATA_DIR / "website_data.json"

# # # #     if not website_url and not sitemap_url and not files and not existing_website_json.exists():
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# # # #         )

# # # #     all_new_chunks = []
# # # #     skipped_sources = []
# # # #     processed_sources = []
# # # #     failed_sources = []
# # # #     uploaded_documents_count = 0
# # # #     website_documents_count = 0

# # # #     # 1. Existing data/website_data.json support
# # # #     if existing_website_json.exists():
# # # #         try:
# # # #             raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# # # #             source_hash = sha256_text(raw_text)
# # # #             source_key = f"tenant::{tenant_id}::website_data.json"

# # # #             if is_done(source_key, source_hash):
# # # #                 skipped_sources.append(source_key)
# # # #             else:
# # # #                 mark_processing(source_key, source_hash, {"source_type": "website_json"})

# # # #                 data = json.loads(raw_text)
# # # #                 docs = normalize_website_json(data, content_type="Website")
# # # #                 chunks = docs_to_chunks(
# # # #                     docs,
# # # #                     source_key=source_key,
# # # #                     source_hash=source_hash,
# # # #                 )
# # # #                 save_knowledge_documents(
# # # #                     tenant_id=tenant_id,
# # # #                     documents=docs,
# # # #                     source_key=source_key,
# # # #                     source_hash=source_hash,
# # # #                     default_source_type="website_json",
# # # #                     tags=["website", "training"],
# # # #                 )

# # # #                 all_new_chunks.extend(chunks)
# # # #                 website_documents_count += len(docs)

# # # #                 mark_done(
# # # #                     source_key,
# # # #                     source_hash,
# # # #                     len(chunks),
# # # #                     {
# # # #                         "documents": len(docs),
# # # #                         "source_type": "website_json",
# # # #                     },
# # # #                 )

# # # #                 processed_sources.append(source_key)

# # # #         except Exception as exc:
# # # #             mark_failed(
# # # #                 "website_data.json",
# # # #                 "unknown",
# # # #                 str(exc),
# # # #                 {"source_type": "website_json"},
# # # #             )
# # # #             failed_sources.append({
# # # #                 "source": "website_data.json",
# # # #                 "error": str(exc),
# # # #             })

# # # #     # 2. Scrape website / sitemap
# # # #     if website_url or sitemap_url:
# # # #         scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"

# # # #         try:
# # # #             scraped_documents = scrape_by_request(
# # # #                 website_url=website_url,
# # # #                 sitemap_url=sitemap_url,
# # # #                 crawl_type=crawl_type,
# # # #                 content_type=content_type,
# # # #             )

# # # #             raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# # # #             source_hash = sha256_text(raw_scrape_text)

# # # #             if is_done(scrape_key, source_hash):
# # # #                 skipped_sources.append(scrape_key)
# # # #             else:
# # # #                 mark_processing(scrape_key, source_hash, {"source_type": "scrape"})

# # # #                 raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# # # #                 save_json(raw_scrape_file, scraped_documents)
# # # #                 move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# # # #                 chunks = docs_to_chunks(
# # # #                     scraped_documents,
# # # #                     source_key=scrape_key,
# # # #                     source_hash=source_hash,
# # # #                 )
# # # #                 save_knowledge_documents(
# # # #                     tenant_id=tenant_id,
# # # #                     documents=scraped_documents,
# # # #                     source_key=scrape_key,
# # # #                     source_hash=source_hash,
# # # #                     default_source_type="website",
# # # #                     tags=["website", crawl_type, "training"],
# # # #                 )

# # # #                 all_new_chunks.extend(chunks)
# # # #                 website_documents_count += len(scraped_documents)

# # # #                 mark_done(
# # # #                     scrape_key,
# # # #                     source_hash,
# # # #                     len(chunks),
# # # #                     {
# # # #                         "documents": len(scraped_documents),
# # # #                         "source_type": "scrape",
# # # #                     },
# # # #                 )

# # # #                 processed_sources.append(scrape_key)

# # # #         except Exception as exc:
# # # #             error_file = FAILED_DIR / "scrape_error.txt"
# # # #             error_file.write_text(str(exc), encoding="utf-8")

# # # #             mark_failed(
# # # #                 scrape_key,
# # # #                 "unknown",
# # # #                 str(exc),
# # # #                 {"source_type": "scrape"},
# # # #             )

# # # #             failed_sources.append({
# # # #                 "source": scrape_key,
# # # #                 "error": str(exc),
# # # #             })

# # # #     # 3. Uploaded files
# # # #     for upload in files:
# # # #         original_name = upload.filename or "uploaded_file"
# # # #         file_name = safe_filename(original_name)
# # # #         pending_path = PENDING_UPLOAD_DIR / file_name

# # # #         try:
# # # #             content = await upload.read()
# # # #             source_hash = sha256_bytes(content)
# # # #             source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# # # #             if is_done(source_key, source_hash):
# # # #                 skipped_sources.append(original_name)
# # # #                 continue

# # # #             mark_processing(
# # # #                 source_key,
# # # #                 source_hash,
# # # #                 {
# # # #                     "file_name": original_name,
# # # #                     "source_type": "file",
# # # #                 },
# # # #             )

# # # #             pending_path.write_bytes(content)

# # # #             parsed_doc = parse_uploaded_file(
# # # #                 file_path=pending_path,
# # # #                 original_name=original_name,
# # # #                 content_type=content_type,
# # # #             )

# # # #             if parsed_doc and parsed_doc.get("text"):
# # # #                 chunks = docs_to_chunks(
# # # #                     [parsed_doc],
# # # #                     source_key=source_key,
# # # #                     source_hash=source_hash,
# # # #                 )
# # # #                 save_knowledge_documents(
# # # #                     tenant_id=tenant_id,
# # # #                     documents=[parsed_doc],
# # # #                     source_key=source_key,
# # # #                     source_hash=source_hash,
# # # #                     default_source_type="file",
# # # #                     tags=["file", "training"],
# # # #                 )

# # # #                 all_new_chunks.extend(chunks)
# # # #                 uploaded_documents_count += 1

# # # #                 move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)

# # # #                 mark_done(
# # # #                     source_key,
# # # #                     source_hash,
# # # #                     len(chunks),
# # # #                     {
# # # #                         "file_name": original_name,
# # # #                         "source_type": "file",
# # # #                     },
# # # #                 )

# # # #                 processed_sources.append(original_name)

# # # #             else:
# # # #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# # # #                 mark_failed(
# # # #                     source_key,
# # # #                     source_hash,
# # # #                     "No text extracted",
# # # #                     {
# # # #                         "file_name": original_name,
# # # #                         "source_type": "file",
# # # #                     },
# # # #                 )

# # # #                 failed_sources.append({
# # # #                     "source": original_name,
# # # #                     "error": "No text extracted",
# # # #                 })

# # # #         except Exception as exc:
# # # #             if pending_path.exists():
# # # #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# # # #             mark_failed(
# # # #                 f"file::{file_name}",
# # # #                 "unknown",
# # # #                 str(exc),
# # # #                 {
# # # #                     "file_name": original_name,
# # # #                     "source_type": "file",
# # # #                 },
# # # #             )

# # # #             failed_sources.append({
# # # #                 "source": original_name,
# # # #                 "error": str(exc),
# # # #             })

# # # #     if not all_new_chunks and not skipped_sources:
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="No new text could be extracted from the provided source.",
# # # #         )

# # # #     index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# # # #     if all_new_chunks:
# # # #         save_json(DATA_DIR / "latest_new_chunks.json", all_new_chunks)

# # # #     return {
# # # #         "success": True,
# # # #         "message": "Agent training completed. New content was added and duplicate content was skipped.",
# # # #         "content_type": content_type,
# # # #         "crawl_type": crawl_type,
# # # #         "website_documents": website_documents_count,
# # # #         "uploaded_documents": uploaded_documents_count,
# # # #         "chunks_created": len(all_new_chunks),
# # # #         "processed_sources": processed_sources,
# # # #         "skipped_sources": skipped_sources,
# # # #         "failed_sources": failed_sources,
# # # #         "faiss_index_path": index_info.get("index_path"),
# # # #         "metadata_path": index_info.get("metadata_path"),
# # # #         "total_vectors": index_info.get("total_vectors"),
# # # #     }


# # # # @app.post("/chat")
# # # # def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
# # # #     message = (request.message or "").strip()

# # # #     if not message:
# # # #         raise HTTPException(status_code=400, detail="Message is required.")

# # # #     session_id = request.session_id or str(uuid4())

# # # #     try:
# # # #         return chat_with_agent(
# # # #             session_id=session_id,
# # # #             message=message,
# # # #             tenant_id=current_user["tenant_id"],
# # # #             top_k=request.top_k or 2,
# # # #         )

# # # #     except FileNotFoundError:
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="Please train the agent first. FAISS index is missing.",
# # # #         )

# # # #     except Exception as exc:
# # # #         raise HTTPException(status_code=500, detail=str(exc))

# # # # def _public_chat_response(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # # #     tenant = get_tenant_by_slug(tenant_slug)

# # # #     if not tenant:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# # # #     message = (request_body.message or "").strip()
# # # #     if not message:
# # # #         raise HTTPException(status_code=400, detail="Message is required.")

# # # #     session_id = request_body.session_id or str(uuid4())

# # # #     customer = upsert_tenant_customer(
# # # #         tenant_id=tenant["id"],
# # # #         session_id=session_id,
# # # #         name=request_body.customer_name,
# # # #         email=request_body.customer_email,
# # # #         phone=request_body.customer_phone,
# # # #         message=message,
# # # #         request=request,
# # # #     )

# # # #     try:
# # # #         chat_result = chat_with_agent(
# # # #             session_id=session_id,
# # # #             message=message,
# # # #             tenant_id=tenant["id"],
# # # #             top_k=request_body.top_k or 2,
# # # #         )

# # # #         chat_result["tenant"] = {
# # # #             "id": tenant["id"],
# # # #             "slug": tenant["slug"],
# # # #             "tenant_name": tenant["tenant_name"],
# # # #         }
# # # #         chat_result["customer"] = {
# # # #             "id": customer.get("id") if customer else None,
# # # #             "name": customer.get("name") if customer else request_body.customer_name,
# # # #             "email": customer.get("email") if customer else request_body.customer_email,
# # # #         }
# # # #         return chat_result

# # # #     except FileNotFoundError:
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="Please train this tenant agent first. FAISS index is missing.",
# # # #         )

# # # #     except Exception as exc:
# # # #         raise HTTPException(status_code=500, detail=str(exc))




# # # # @app.post("/public-chat/customer/{tenant_slug}")
# # # # def save_public_chat_customer(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # # #     tenant = get_tenant_by_slug(tenant_slug)
# # # #     if not tenant:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
# # # #     session_id = request_body.session_id or str(uuid4())
# # # #     customer = upsert_tenant_customer(
# # # #         tenant_id=tenant["id"],
# # # #         session_id=session_id,
# # # #         name=request_body.customer_name,
# # # #         email=request_body.customer_email,
# # # #         phone=request_body.customer_phone,
# # # #         message=request_body.message or "",
# # # #         request=request,
# # # #     )
# # # #     return {"success": True, "session_id": session_id, "customer": customer}


# # # # @app.post("/chat/{tenant_slug}")
# # # # def public_chat_by_path(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # # #     return _public_chat_response(tenant_slug, request_body, request)


# # # # @app.post("/chat_{tenant_slug}")
# # # # def public_chat_by_underscore(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # # #     return _public_chat_response(tenant_slug, request_body, request)


# # # # # ==========================================================
# # # # # Clean Public URL APIs
# # # # # Example:
# # # # #   /instapress -> /chat_t3
# # # # #   /A8X9K2PQ   -> /chat_t3
# # # # # ==========================================================
# # # # PUBLIC_CODE_LENGTH = 8
# # # # PUBLIC_CODE_ALPHABET = string.ascii_uppercase + string.digits
# # # # SWEET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,49}$")

# # # # # These names are already used by backend/frontend routes and must not be taken as sweet names.
# # # # RESERVED_PUBLIC_NAMES = {
# # # #     "api", "auth", "chat", "contacts", "dashboard", "docs", "health",
# # # #     "knowledge", "login", "logout", "openapi.json", "public-chat",
# # # #     "review-agent", "static", "train", "train-agent", "whatsapp",
# # # # }


# # # # def _get_base_url(request: Request) -> str:
# # # #     """Build correct production base URL behind Railway/proxy."""
# # # #     proto = request.headers.get("x-forwarded-proto") or request.url.scheme
# # # #     host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
# # # #     return f"{proto}://{host}".rstrip("/")


# # # # def _normalize_sweet_name(value: Optional[str]) -> Optional[str]:
# # # #     value = (value or "").strip().strip("/")
# # # #     if not value:
# # # #         return None
# # # #     # Keep URLs clean and predictable.
# # # #     value = value.lower()
# # # #     return value


# # # # def _validate_sweet_name(value: Optional[str]) -> Optional[str]:
# # # #     value = _normalize_sweet_name(value)
# # # #     if not value:
# # # #         return None

# # # #     if value in RESERVED_PUBLIC_NAMES or value.startswith("chat_"):
# # # #         raise HTTPException(status_code=400, detail="This name is reserved. Please choose another name.")

# # # #     if not SWEET_NAME_PATTERN.match(value):
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="Sweet name must be 3-50 characters and can use letters, numbers, hyphen, or underscore.",
# # # #         )

# # # #     return value


# # # # def _generate_public_code() -> str:
# # # #     return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


# # # # def _get_tenant_slug_by_id(tenant_id: int) -> str:
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT slug
# # # #                 FROM tenants
# # # #                 WHERE id=%s AND status='active'
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             row = cur.fetchone()
# # # #     finally:
# # # #         conn.close()

# # # #     if not row:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# # # #     return row["slug"]


# # # # def _get_or_create_public_link(tenant_id: int) -> dict:
# # # #     tenant_slug = _get_tenant_slug_by_id(tenant_id)
# # # #     target_path = f"/chat_{tenant_slug}"

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # # #                 FROM tenant_public_links
# # # #                 WHERE tenant_id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             row = cur.fetchone()

# # # #             if row:
# # # #                 # Keep tenant slug/path updated if tenant slug ever changes.
# # # #                 if row.get("tenant_slug") != tenant_slug or row.get("target_path") != target_path:
# # # #                     cur.execute(
# # # #                         """
# # # #                         UPDATE tenant_public_links
# # # #                         SET tenant_slug=%s, target_path=%s, updated_at=NOW()
# # # #                         WHERE tenant_id=%s
# # # #                         """,
# # # #                         (tenant_slug, target_path, tenant_id),
# # # #                     )
# # # #                     row["tenant_slug"] = tenant_slug
# # # #                     row["target_path"] = target_path
# # # #                 return row

# # # #             # Table is empty for new tenant: create permanent hidden 8-char code.
# # # #             for _ in range(20):
# # # #                 short_code = _generate_public_code()
# # # #                 try:
# # # #                     cur.execute(
# # # #                         """
# # # #                         INSERT INTO tenant_public_links
# # # #                             (tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active)
# # # #                         VALUES
# # # #                             (%s, %s, %s, NULL, %s, 1)
# # # #                         """,
# # # #                         (tenant_id, tenant_slug, short_code, target_path),
# # # #                     )
# # # #                     cur.execute(
# # # #                         """
# # # #                         SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # # #                         FROM tenant_public_links
# # # #                         WHERE tenant_id=%s
# # # #                         LIMIT 1
# # # #                         """,
# # # #                         (tenant_id,),
# # # #                     )
# # # #                     return cur.fetchone()
# # # #                 except Exception as exc:
# # # #                     # Retry only when short_code collision happens. Otherwise raise original DB error.
# # # #                     if "Duplicate" not in str(exc) and "duplicate" not in str(exc):
# # # #                         raise

# # # #     finally:
# # # #         conn.close()

# # # #     raise HTTPException(status_code=500, detail="Could not generate unique public link. Please try again.")


# # # # def _format_public_link_response(row: dict, request: Request) -> dict:
# # # #     base_url = _get_base_url(request)
# # # #     public_name = row.get("sweet_name") or row.get("short_code")

# # # #     return {
# # # #         "success": True,
# # # #         "tenant_id": row.get("tenant_id"),
# # # #         "tenant_slug": row.get("tenant_slug"),
# # # #         "short_code": row.get("short_code"),
# # # #         "sweet_name": row.get("sweet_name"),
# # # #         "public_name": public_name,
# # # #         "target_path": row.get("target_path"),
# # # #         "original_url": f"{base_url}{row.get('target_path')}",
# # # #         "public_url": f"{base_url}/{public_name}",
# # # #         "fallback_public_url": f"{base_url}/{row.get('short_code')}",
# # # #     }


# # # # @app.get("/public-link")
# # # # def get_public_link(request: Request, current_user: dict = Depends(get_current_user)):
# # # #     row = _get_or_create_public_link(current_user["tenant_id"])
# # # #     return _format_public_link_response(row, request)


# # # # @app.post("/public-link")
# # # # def update_public_link(
# # # #     request_body: PublicLinkUpdateRequest,
# # # #     request: Request,
# # # #     current_user: dict = Depends(get_current_user),
# # # # ):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     sweet_name = _validate_sweet_name(request_body.sweet_name)

# # # #     # Ensure row exists before update.
# # # #     _get_or_create_public_link(tenant_id)

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             if sweet_name:
# # # #                 cur.execute(
# # # #                     """
# # # #                     SELECT tenant_id
# # # #                     FROM tenant_public_links
# # # #                     WHERE sweet_name=%s AND tenant_id<>%s
# # # #                     LIMIT 1
# # # #                     """,
# # # #                     (sweet_name, tenant_id),
# # # #                 )
# # # #                 existing = cur.fetchone()
# # # #                 if existing:
# # # #                     raise HTTPException(status_code=409, detail="This sweet name is already taken. Please choose another.")

# # # #             cur.execute(
# # # #                 """
# # # #                 UPDATE tenant_public_links
# # # #                 SET sweet_name=%s, updated_at=NOW()
# # # #                 WHERE tenant_id=%s
# # # #                 """,
# # # #                 (sweet_name, tenant_id),
# # # #             )

# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # # #                 FROM tenant_public_links
# # # #                 WHERE tenant_id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             row = cur.fetchone()
# # # #     finally:
# # # #         conn.close()

# # # #     return _format_public_link_response(row, request)


# # # # def _resolve_public_name(public_name: str) -> Optional[dict]:
# # # #     public_name = (public_name or "").strip().strip("/")
# # # #     if not public_name:
# # # #         return None

# # # #     normalized_name = public_name.lower()

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT
# # # #                     tpl.tenant_id,
# # # #                     tpl.tenant_slug,
# # # #                     tpl.short_code,
# # # #                     tpl.sweet_name,
# # # #                     tpl.target_path,
# # # #                     tpl.is_active,
# # # #                     COALESCE(t.active_agent_type, 'chat') AS active_agent_type
# # # #                 FROM tenant_public_links tpl
# # # #                 JOIN tenants t ON t.id = tpl.tenant_id
# # # #                 WHERE tpl.is_active = 1
# # # #                   AND t.status = 'active'
# # # #                   AND (LOWER(tpl.sweet_name) = %s OR tpl.short_code = %s)
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (normalized_name, public_name.upper()),
# # # #             )
# # # #             return cur.fetchone()
# # # #     finally:
# # # #         conn.close()


# # # # # ==========================================================
# # # # # Live Training Progress API
# # # # # Added for frontend step tracking while tenant training runs.
# # # # # This does NOT remove or break your existing /train-agent endpoint.
# # # # # Frontend should call /train-agent/start, then poll /train-agent/status/{job_id}.
# # # # # ==========================================================
# # # # from fastapi import BackgroundTasks

# # # # TRAINING_JOBS = {}

# # # # TRAINING_STEP_ORDER = [
# # # #     "scanning",
# # # #     "analyzing",
# # # #     "chunking",
# # # #     "building_knowledge_base",
# # # #     "generating_chat_experience",
# # # # ]

# # # # TRAINING_STEP_LABELS = {
# # # #     "scanning": "Scanning your website / uploaded files",
# # # #     "analyzing": "Analyzing your business content",
# # # #     "chunking": "Chunking and cleaning knowledge",
# # # #     "building_knowledge_base": "Building knowledge base / AI brain",
# # # #     "generating_chat_experience": "Generating chat experience",
# # # # }


# # # # def _new_training_job(job_id: str, tenant_id: int, website_url: str = ""):
# # # #     TRAINING_JOBS[job_id] = {
# # # #         "job_id": job_id,
# # # #         "tenant_id": tenant_id,
# # # #         "status": "queued",
# # # #         "current_step": "queued",
# # # #         "current_step_index": 0,
# # # #         "progress": 0,
# # # #         "message": "Training queued.",
# # # #         "website_url": website_url,
# # # #         "steps": [
# # # #             {
# # # #                 "key": key,
# # # #                 "label": TRAINING_STEP_LABELS[key],
# # # #                 "status": "pending",
# # # #             }
# # # #             for key in TRAINING_STEP_ORDER
# # # #         ],
# # # #         "result": None,
# # # #         "error": None,
# # # #     }
# # # #     return TRAINING_JOBS[job_id]


# # # # def _set_training_step(job_id: str, step_key: str, message: str = ""):
# # # #     job = TRAINING_JOBS.get(job_id)
# # # #     if not job:
# # # #         return

# # # #     if step_key not in TRAINING_STEP_ORDER:
# # # #         return

# # # #     step_index = TRAINING_STEP_ORDER.index(step_key)
# # # #     total = len(TRAINING_STEP_ORDER)

# # # #     for index, item in enumerate(job["steps"]):
# # # #         if index < step_index:
# # # #             item["status"] = "done"
# # # #         elif index == step_index:
# # # #             item["status"] = "active"
# # # #         else:
# # # #             item["status"] = "pending"

# # # #     job["status"] = "running"
# # # #     job["current_step"] = step_key
# # # #     job["current_step_index"] = step_index + 1
# # # #     job["progress"] = int((step_index / total) * 100)
# # # #     job["message"] = message or TRAINING_STEP_LABELS[step_key]


# # # # def _complete_training_job(job_id: str, result: dict):
# # # #     job = TRAINING_JOBS.get(job_id)
# # # #     if not job:
# # # #         return

# # # #     for item in job["steps"]:
# # # #         item["status"] = "done"

# # # #     job["status"] = "completed"
# # # #     job["current_step"] = "completed"
# # # #     job["current_step_index"] = len(TRAINING_STEP_ORDER)
# # # #     job["progress"] = 100
# # # #     job["message"] = "Agent trained successfully."
# # # #     job["result"] = result
# # # #     job["error"] = None

# # # #     # Save latest training result so Customize page can show real backend data.
# # # #     try:
# # # #         _upsert_agent_settings_last_training_summary(job.get("tenant_id"), result)
# # # #     except Exception:
# # # #         # Never fail the training job only because settings persistence failed.
# # # #         pass


# # # # def _fail_training_job(job_id: str, error: str):
# # # #     job = TRAINING_JOBS.get(job_id)
# # # #     if not job:
# # # #         return

# # # #     for item in job["steps"]:
# # # #         if item["status"] == "active":
# # # #             item["status"] = "failed"

# # # #     job["status"] = "failed"
# # # #     job["progress"] = job.get("progress", 0)
# # # #     job["message"] = "Training failed."
# # # #     job["error"] = error


# # # # def _run_training_job(
# # # #     job_id: str,
# # # #     tenant_id: int,
# # # #     website_url: str,
# # # #     sitemap_url: str,
# # # #     crawl_type: str,
# # # #     content_type: str,
# # # #     uploaded_files_payload: list,
# # # # ):
# # # #     """
# # # #     Background training runner.
# # # #     It mirrors your existing /train-agent logic but updates TRAINING_JOBS after each phase.
# # # #     """
# # # #     try:
# # # #         all_new_chunks = []
# # # #         skipped_sources = []
# # # #         processed_sources = []
# # # #         failed_sources = []
# # # #         uploaded_documents_count = 0
# # # #         website_documents_count = 0

# # # #         existing_website_json = DATA_DIR / "website_data.json"

# # # #         if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# # # #             raise ValueError(
# # # #                 "Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/."
# # # #             )

# # # #         # 1. Scanning source content
# # # #         _set_training_step(job_id, "scanning", "Scanning website, sitemap, and uploaded files...")

# # # #         # Existing website_data.json support
# # # #         if existing_website_json.exists():
# # # #             try:
# # # #                 raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# # # #                 source_hash = sha256_text(raw_text)
# # # #                 source_key = f"tenant::{tenant_id}::website_data.json"

# # # #                 if is_done(source_key, source_hash):
# # # #                     skipped_sources.append(source_key)
# # # #                 else:
# # # #                     mark_processing(source_key, source_hash, {"source_type": "website_json"})
# # # #                     data = json.loads(raw_text)
# # # #                     docs = normalize_website_json(data, content_type="Website")

# # # #                     _set_training_step(job_id, "analyzing", "Analyzing website_data.json content...")
# # # #                     chunks = docs_to_chunks(docs, source_key=source_key, source_hash=source_hash)
# # # #                     save_knowledge_documents(
# # # #                         tenant_id=tenant_id,
# # # #                         documents=docs,
# # # #                         source_key=source_key,
# # # #                         source_hash=source_hash,
# # # #                         default_source_type="website_json",
# # # #                         tags=["website", "training"],
# # # #                     )

# # # #                     all_new_chunks.extend(chunks)
# # # #                     website_documents_count += len(docs)

# # # #                     mark_done(
# # # #                         source_key,
# # # #                         source_hash,
# # # #                         len(chunks),
# # # #                         {"documents": len(docs), "source_type": "website_json"},
# # # #                     )
# # # #                     processed_sources.append(source_key)
# # # #             except Exception as exc:
# # # #                 mark_failed("website_data.json", "unknown", str(exc), {"source_type": "website_json"})
# # # #                 failed_sources.append({"source": "website_data.json", "error": str(exc)})

# # # #         # Scrape website / sitemap
# # # #         if website_url or sitemap_url:
# # # #             scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"
# # # #             try:
# # # #                 _set_training_step(job_id, "scanning", "Scanning website pages...")
# # # #                 scraped_documents = scrape_by_request(
# # # #                     website_url=website_url,
# # # #                     sitemap_url=sitemap_url,
# # # #                     crawl_type=crawl_type,
# # # #                     content_type=content_type,
# # # #                 )

# # # #                 raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# # # #                 source_hash = sha256_text(raw_scrape_text)

# # # #                 if is_done(scrape_key, source_hash):
# # # #                     skipped_sources.append(scrape_key)
# # # #                 else:
# # # #                     mark_processing(scrape_key, source_hash, {"source_type": "scrape"})
# # # #                     raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# # # #                     save_json(raw_scrape_file, scraped_documents)
# # # #                     move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# # # #                     _set_training_step(job_id, "analyzing", "Analyzing scanned website content...")
# # # #                     chunks = docs_to_chunks(scraped_documents, source_key=scrape_key, source_hash=source_hash)
# # # #                     save_knowledge_documents(
# # # #                         tenant_id=tenant_id,
# # # #                         documents=scraped_documents,
# # # #                         source_key=scrape_key,
# # # #                         source_hash=source_hash,
# # # #                         default_source_type="website",
# # # #                         tags=["website", crawl_type, "training"],
# # # #                     )

# # # #                     all_new_chunks.extend(chunks)
# # # #                     website_documents_count += len(scraped_documents)

# # # #                     mark_done(
# # # #                         scrape_key,
# # # #                         source_hash,
# # # #                         len(chunks),
# # # #                         {"documents": len(scraped_documents), "source_type": "scrape"},
# # # #                     )
# # # #                     processed_sources.append(scrape_key)
# # # #             except Exception as exc:
# # # #                 error_file = FAILED_DIR / "scrape_error.txt"
# # # #                 error_file.write_text(str(exc), encoding="utf-8")
# # # #                 mark_failed(scrape_key, "unknown", str(exc), {"source_type": "scrape"})
# # # #                 failed_sources.append({"source": scrape_key, "error": str(exc)})

# # # #         # Uploaded files
# # # #         for item in uploaded_files_payload:
# # # #             original_name = item.get("filename") or "uploaded_file"
# # # #             file_name = safe_filename(original_name)
# # # #             pending_path = PENDING_UPLOAD_DIR / file_name
# # # #             content = item.get("content") or b""
# # # #             upload_content_type = item.get("content_type") or content_type

# # # #             try:
# # # #                 _set_training_step(job_id, "scanning", f"Scanning uploaded file: {original_name}")
# # # #                 source_hash = sha256_bytes(content)
# # # #                 source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# # # #                 if is_done(source_key, source_hash):
# # # #                     skipped_sources.append(original_name)
# # # #                     continue

# # # #                 mark_processing(
# # # #                     source_key,
# # # #                     source_hash,
# # # #                     {"file_name": original_name, "source_type": "file"},
# # # #                 )

# # # #                 pending_path.write_bytes(content)

# # # #                 _set_training_step(job_id, "analyzing", f"Extracting text from: {original_name}")
# # # #                 parsed_doc = parse_uploaded_file(
# # # #                     file_path=pending_path,
# # # #                     original_name=original_name,
# # # #                     content_type=upload_content_type,
# # # #                 )

# # # #                 if parsed_doc and parsed_doc.get("text"):
# # # #                     _set_training_step(job_id, "chunking", f"Chunking content from: {original_name}")
# # # #                     chunks = docs_to_chunks([parsed_doc], source_key=source_key, source_hash=source_hash)
# # # #                     save_knowledge_documents(
# # # #                         tenant_id=tenant_id,
# # # #                         documents=[parsed_doc],
# # # #                         source_key=source_key,
# # # #                         source_hash=source_hash,
# # # #                         default_source_type="file",
# # # #                         tags=["file", "training"],
# # # #                     )

# # # #                     all_new_chunks.extend(chunks)
# # # #                     uploaded_documents_count += 1

# # # #                     move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)
# # # #                     mark_done(
# # # #                         source_key,
# # # #                         source_hash,
# # # #                         len(chunks),
# # # #                         {"file_name": original_name, "source_type": "file"},
# # # #                     )
# # # #                     processed_sources.append(original_name)
# # # #                 else:
# # # #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# # # #                     mark_failed(
# # # #                         source_key,
# # # #                         source_hash,
# # # #                         "No text extracted",
# # # #                         {"file_name": original_name, "source_type": "file"},
# # # #                     )
# # # #                     failed_sources.append({"source": original_name, "error": "No text extracted"})

# # # #             except Exception as exc:
# # # #                 if pending_path.exists():
# # # #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# # # #                 mark_failed(
# # # #                     f"file::{file_name}",
# # # #                     "unknown",
# # # #                     str(exc),
# # # #                     {"file_name": original_name, "source_type": "file"},
# # # #                 )
# # # #                 failed_sources.append({"source": original_name, "error": str(exc)})

# # # #         if not all_new_chunks and not skipped_sources:
# # # #             raise ValueError("No new text could be extracted from the provided source.")

# # # #         # 3. Chunking summary phase
# # # #         _set_training_step(job_id, "chunking", "Cleaning and preparing chunks...")

# # # #         # 4. Build FAISS / knowledge base
# # # #         _set_training_step(job_id, "building_knowledge_base", "Building tenant knowledge base / AI brain...")
# # # #         index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# # # #         if all_new_chunks:
# # # #             save_json(DATA_DIR / f"latest_new_chunks_{tenant_id}.json", all_new_chunks)

# # # #         # 5. Generate chat experience
# # # #         _set_training_step(job_id, "generating_chat_experience", "Generating chat experience from trained data...")

# # # #         result = {
# # # #             "success": True,
# # # #             "message": "Agent training completed. New content was added and duplicate content was skipped.",
# # # #             "content_type": content_type,
# # # #             "crawl_type": crawl_type,
# # # #             "website_documents": website_documents_count,
# # # #             "uploaded_documents": uploaded_documents_count,
# # # #             "chunks_created": len(all_new_chunks),
# # # #             "processed_sources": processed_sources,
# # # #             "skipped_sources": skipped_sources,
# # # #             "failed_sources": failed_sources,
# # # #             "faiss_index_path": index_info.get("index_path"),
# # # #             "metadata_path": index_info.get("metadata_path"),
# # # #             "total_vectors": index_info.get("total_vectors"),
# # # #         }
# # # #         _complete_training_job(job_id, result)

# # # #     except Exception as exc:
# # # #         _fail_training_job(job_id, str(exc))


# # # # @app.post("/train-agent/start")
# # # # async def start_train_agent(
# # # #     background_tasks: BackgroundTasks,
# # # #     website_url: Optional[str] = Form(default=""),
# # # #     sitemap_url: Optional[str] = Form(default=""),
# # # #     crawl_type: str = Form(default="single_page"),
# # # #     content_type: str = Form(default="Mixed Content"),
# # # #     files: List[UploadFile] = File(default=[]),
# # # #     current_user: dict = Depends(get_current_user),
# # # # ):
# # # #     """
# # # #     Starts training in background and immediately returns a job_id.
# # # #     Frontend should poll GET /train-agent/status/{job_id}.
# # # #     """
# # # #     website_url = (website_url or "").strip()
# # # #     sitemap_url = (sitemap_url or "").strip()
# # # #     crawl_type = (crawl_type or "single_page").strip()
# # # #     content_type = (content_type or "Mixed Content").strip()

# # # #     uploaded_files_payload = []
# # # #     for upload in files:
# # # #         uploaded_files_payload.append(
# # # #             {
# # # #                 "filename": upload.filename or "uploaded_file",
# # # #                 "content_type": upload.content_type or content_type,
# # # #                 "content": await upload.read(),
# # # #             }
# # # #         )

# # # #     existing_website_json = DATA_DIR / "website_data.json"
# # # #     if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# # # #         )

# # # #     job_id = str(uuid4())
# # # #     tenant_id = current_user["tenant_id"]
# # # #     _new_training_job(job_id, tenant_id=tenant_id, website_url=website_url or sitemap_url)

# # # #     background_tasks.add_task(
# # # #         _run_training_job,
# # # #         job_id,
# # # #         tenant_id,
# # # #         website_url,
# # # #         sitemap_url,
# # # #         crawl_type,
# # # #         content_type,
# # # #         uploaded_files_payload,
# # # #     )

# # # #     return {
# # # #         "success": True,
# # # #         "job_id": job_id,
# # # #         "message": "Training started.",
# # # #         "status_url": f"/train-agent/status/{job_id}",
# # # #     }


# # # # @app.get("/train-agent/status/{job_id}")
# # # # def get_train_agent_status(job_id: str, current_user: dict = Depends(get_current_user)):
# # # #     job = TRAINING_JOBS.get(job_id)

# # # #     if not job:
# # # #         raise HTTPException(status_code=404, detail="Training job not found.")

# # # #     if int(job.get("tenant_id")) != int(current_user["tenant_id"]):
# # # #         raise HTTPException(status_code=403, detail="You cannot access this training job.")

# # # #     return job



# # # # # ==========================================================
# # # # # Tenant Agent Customize / Review Settings API
# # # # # Used by frontend ReviewAgentPage.js after training is completed.
# # # # # Requires table: tenant_agent_settings
# # # # # ==========================================================

# # # # class AgentConfigRequest(BaseModel):
# # # #     business_name: Optional[str] = None
# # # #     industry: Optional[str] = None
# # # #     business_type: Optional[str] = None
# # # #     business_description: Optional[str] = None
# # # #     greeting_message: Optional[str] = None
# # # #     starter_questions: Optional[List[str]] = None
# # # #     system_prompt: Optional[str] = None
# # # #     restriction_rules: Optional[str] = None
# # # #     support_hours: Optional[dict] = None


# # # # def _json_load(value, default=None):
# # # #     if value is None:
# # # #         return default
# # # #     if isinstance(value, (dict, list)):
# # # #         return value
# # # #     try:
# # # #         return json.loads(value)
# # # #     except Exception:
# # # #         return default


# # # # def _default_starter_questions():
# # # #     return [
# # # #         "Tell me about your services",
# # # #         "What products do you offer?",
# # # #         "How can I contact your team?",
# # # #         "Do you provide pricing details?",
# # # #     ]


# # # # def _default_restriction_rules():
# # # #     return """- Answer only using trained knowledge base.
# # # # - Do not invent prices, offers, phone numbers, addresses, or guarantees.
# # # # - If answer is not available, say: I will connect you with our team.
# # # # - Keep replies short, clear, and helpful."""


# # # # def _default_system_prompt(tenant_name: str = "this business"):
# # # #     return f"""You are a helpful business assistant for {tenant_name}.

# # # # Your job is to answer customer questions using only the trained knowledge base.
# # # # Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""


# # # # def _default_greeting(tenant_name: str = ""):
# # # #     if tenant_name:
# # # #         return f"Welcome to {tenant_name}! How can I help you today?"
# # # #     return "Welcome! How can I help you today?"


# # # # def _default_support_hours():
# # # #     return {
# # # #         "opening_time": "09:00 AM",
# # # #         "closing_time": "06:00 PM",
# # # #         "working_days": "Monday - Saturday",
# # # #     }


# # # # def _make_default_business_description(tenant_name: str, training_summary: dict = None):
# # # #     training_summary = training_summary or {}
# # # #     website_documents = training_summary.get("website_documents") or 0
# # # #     uploaded_documents = training_summary.get("uploaded_documents") or 0
# # # #     chunks_created = training_summary.get("chunks_created") or 0

# # # #     if website_documents or uploaded_documents or chunks_created:
# # # #         return (
# # # #             f"{tenant_name} has trained this AI agent with "
# # # #             f"{website_documents} website pages, {uploaded_documents} uploaded documents, "
# # # #             f"and {chunks_created} knowledge entries."
# # # #         )
# # # #     return f"{tenant_name} AI agent is ready to answer questions from the trained knowledge base."


# # # # def _get_agent_settings_row(tenant_id: int):
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT *
# # # #                 FROM tenant_agent_settings
# # # #                 WHERE tenant_id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             return cur.fetchone()
# # # #     finally:
# # # #         conn.close()


# # # # def _get_tenant_row_by_id(tenant_id: int):
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT id, slug, tenant_name, faiss_index_path, plan_name, status
# # # #                 FROM tenants
# # # #                 WHERE id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             return cur.fetchone()
# # # #     finally:
# # # #         conn.close()


# # # # def _upsert_agent_settings_last_training_summary(tenant_id: int, result: dict):
# # # #     if not tenant_id:
# # # #         return

# # # #     summary_json = json.dumps(result or {}, ensure_ascii=False)
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 INSERT INTO tenant_agent_settings
# # # #                     (tenant_id, last_training_summary)
# # # #                 VALUES
# # # #                     (%s, CAST(%s AS JSON))
# # # #                 ON DUPLICATE KEY UPDATE
# # # #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# # # #                     updated_at = NOW()
# # # #                 """,
# # # #                 (tenant_id, summary_json),
# # # #             )
# # # #     finally:
# # # #         conn.close()


# # # # def _normalize_agent_config(tenant: dict, row: dict = None):
# # # #     row = row or {}
# # # #     tenant_name = tenant.get("tenant_name") or "Your Business"
# # # #     training_summary = _json_load(row.get("last_training_summary"), default={}) or {}

# # # #     business_name = row.get("business_name") or tenant_name
# # # #     industry = row.get("industry") or "General Business"
# # # #     business_type = row.get("business_type") or "Business"
# # # #     business_description = row.get("business_description") or _make_default_business_description(
# # # #         business_name,
# # # #         training_summary,
# # # #     )

# # # #     greeting_message = row.get("greeting_message") or _default_greeting(business_name)
# # # #     starter_questions = _json_load(row.get("starter_questions"), default=None) or _default_starter_questions()
# # # #     system_prompt = row.get("system_prompt") or _default_system_prompt(business_name)
# # # #     restriction_rules = row.get("restriction_rules") or _default_restriction_rules()
# # # #     support_hours = _json_load(row.get("support_hours"), default=None) or _default_support_hours()

# # # #     return {
# # # #         "tenant": {
# # # #             "id": tenant.get("id"),
# # # #             "slug": tenant.get("slug"),
# # # #             "tenant_name": tenant_name,
# # # #             "plan_name": tenant.get("plan_name"),
# # # #             "status": tenant.get("status"),
# # # #         },
# # # #         "business": {
# # # #             "name": business_name,
# # # #             "industry": industry,
# # # #             "type": business_type,
# # # #             "description": business_description,
# # # #         },
# # # #         "training_summary": training_summary,
# # # #         "knowledge_base": {
# # # #             "entries": training_summary.get("chunks_created") or training_summary.get("total_vectors") or 0,
# # # #             "website_documents": training_summary.get("website_documents") or 0,
# # # #             "uploaded_documents": training_summary.get("uploaded_documents") or 0,
# # # #             "processed_sources": training_summary.get("processed_sources") or [],
# # # #             "skipped_sources": training_summary.get("skipped_sources") or [],
# # # #             "failed_sources": training_summary.get("failed_sources") or [],
# # # #             "total_vectors": training_summary.get("total_vectors") or 0,
# # # #         },
# # # #         "chat_experience": {
# # # #             "greeting_message": greeting_message,
# # # #             "starter_questions": starter_questions,
# # # #         },
# # # #         "behavior": {
# # # #             "system_prompt": system_prompt,
# # # #             "restriction_rules": restriction_rules,
# # # #         },
# # # #         "support_hours": support_hours,
# # # #     }


# # # # @app.get("/agent-config")
# # # # def get_agent_config(current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     tenant = _get_tenant_row_by_id(tenant_id)

# # # #     if not tenant:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found.")

# # # #     row = _get_agent_settings_row(tenant_id)
# # # #     return {
# # # #         "success": True,
# # # #         "config": _normalize_agent_config(tenant, row),
# # # #     }


# # # # @app.post("/agent-config")
# # # # def save_agent_config(req: AgentConfigRequest, current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     tenant = _get_tenant_row_by_id(tenant_id)

# # # #     if not tenant:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found.")

# # # #     row = _get_agent_settings_row(tenant_id)
# # # #     current_config = _normalize_agent_config(tenant, row)

# # # #     business_name = (req.business_name or current_config["business"]["name"] or tenant.get("tenant_name") or "").strip()
# # # #     industry = (req.industry or current_config["business"]["industry"] or "General Business").strip()
# # # #     business_type = (req.business_type or current_config["business"]["type"] or "Business").strip()
# # # #     business_description = (req.business_description or current_config["business"]["description"] or "").strip()
# # # #     greeting_message = (req.greeting_message or _default_greeting(business_name)).strip()

# # # #     starter_questions = req.starter_questions or current_config["chat_experience"]["starter_questions"] or _default_starter_questions()
# # # #     starter_questions = [str(q).strip() for q in starter_questions if str(q).strip()][:8]
# # # #     if not starter_questions:
# # # #         starter_questions = _default_starter_questions()

# # # #     system_prompt = (req.system_prompt or _default_system_prompt(business_name)).strip()
# # # #     restriction_rules = (req.restriction_rules or _default_restriction_rules()).strip()
# # # #     support_hours = req.support_hours or current_config.get("support_hours") or _default_support_hours()
# # # #     last_training_summary = current_config.get("training_summary") or {}

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 INSERT INTO tenant_agent_settings
# # # #                     (tenant_id, business_name, industry, business_type, business_description,
# # # #                      greeting_message, starter_questions, system_prompt, restriction_rules,
# # # #                      support_hours, last_training_summary)
# # # #                 VALUES
# # # #                     (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s, CAST(%s AS JSON), CAST(%s AS JSON))
# # # #                 ON DUPLICATE KEY UPDATE
# # # #                     business_name = VALUES(business_name),
# # # #                     industry = VALUES(industry),
# # # #                     business_type = VALUES(business_type),
# # # #                     business_description = VALUES(business_description),
# # # #                     greeting_message = VALUES(greeting_message),
# # # #                     starter_questions = CAST(VALUES(starter_questions) AS JSON),
# # # #                     system_prompt = VALUES(system_prompt),
# # # #                     restriction_rules = VALUES(restriction_rules),
# # # #                     support_hours = CAST(VALUES(support_hours) AS JSON),
# # # #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# # # #                     updated_at = NOW()
# # # #                 """,
# # # #                 (
# # # #                     tenant_id,
# # # #                     business_name,
# # # #                     industry,
# # # #                     business_type,
# # # #                     business_description,
# # # #                     greeting_message,
# # # #                     json.dumps(starter_questions, ensure_ascii=False),
# # # #                     system_prompt,
# # # #                     restriction_rules,
# # # #                     json.dumps(support_hours, ensure_ascii=False),
# # # #                     json.dumps(last_training_summary, ensure_ascii=False),
# # # #                 ),
# # # #             )

# # # #             cur.execute(
# # # #                 """
# # # #                 UPDATE tenant_users
# # # #                 SET name = %s,
# # # #                     industry = %s,
# # # #                     type = %s,
# # # #                     updated_at = NOW()
# # # #                 WHERE id = %s
# # # #                   AND tenant_id = %s
# # # #                 """,
# # # #                 (
# # # #                     business_name,
# # # #                     industry,
# # # #                     business_type,
# # # #                     current_user.get("user_id") or current_user.get("id"),
# # # #                     tenant_id,
# # # #                 ),
# # # #             )
# # # #     finally:
# # # #         conn.close()

# # # #     row = _get_agent_settings_row(tenant_id)
# # # #     return {
# # # #         "success": True,
# # # #         "message": "Agent settings saved successfully.",
# # # #         "config": _normalize_agent_config(tenant, row),
# # # #     }


# # # # # ==========================================================
# # # # # WhatsApp Connection + Auto Reply APIs
# # # # # Supports both Meta WhatsApp Cloud API and Twilio WhatsApp.
# # # # # ==========================================================

# # # # class WhatsAppConnectRequest(BaseModel):
# # # #     provider: str
# # # #     meta_access_token: Optional[str] = None
# # # #     meta_phone_number_id: Optional[str] = None
# # # #     meta_business_account_id: Optional[str] = None
# # # #     twilio_account_sid: Optional[str] = None
# # # #     twilio_auth_token: Optional[str] = None
# # # #     twilio_phone_number: Optional[str] = None
# # # #     whatsapp_number: Optional[str] = None
# # # #     whatsapp_verify_token: Optional[str] = None


# # # # class SendWhatsAppTextRequest(BaseModel):
# # # #     to_phone: str
# # # #     message: str


# # # # class SendWhatsAppMediaRequest(BaseModel):
# # # #     to_phone: str
# # # #     media_url: str
# # # #     caption: Optional[str] = ""


# # # # @app.get("/connect-whatsapp")
# # # # def get_whatsapp_connection(current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT whatsapp_provider, meta_phone_number_id, meta_business_account_id,
# # # #                        twilio_phone_number, whatsapp_number, whatsapp_verify_token,
# # # #                        CASE WHEN meta_access_token IS NULL OR meta_access_token='' THEN 0 ELSE 1 END AS has_meta_access_token,
# # # #                        CASE WHEN twilio_account_sid IS NULL OR twilio_account_sid='' THEN 0 ELSE 1 END AS has_twilio_account_sid,
# # # #                        CASE WHEN twilio_auth_token IS NULL OR twilio_auth_token='' THEN 0 ELSE 1 END AS has_twilio_auth_token
# # # #                 FROM tenants
# # # #                 WHERE id=%s
# # # #                 LIMIT 1
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )
# # # #             row = cur.fetchone() or {}
# # # #     finally:
# # # #         conn.close()

# # # #     return {"success": True, "config": row}


# # # # @app.post("/connect-whatsapp")
# # # # def save_whatsapp_connection(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]
# # # #     provider = (req.provider or "").strip().lower()

# # # #     if provider not in ["meta", "twilio"]:
# # # #         raise HTTPException(status_code=400, detail="Provider must be meta or twilio.")

# # # #     meta_access_token = (req.meta_access_token or "").strip() or None
# # # #     meta_phone_number_id = (req.meta_phone_number_id or "").strip() or None
# # # #     meta_business_account_id = (req.meta_business_account_id or "").strip() or None
# # # #     twilio_account_sid = (req.twilio_account_sid or "").strip() or None
# # # #     twilio_auth_token = (req.twilio_auth_token or "").strip() or None
# # # #     twilio_phone_number = normalize_phone(req.twilio_phone_number or "") or None
# # # #     whatsapp_number = normalize_phone(req.whatsapp_number or "") or None
# # # #     whatsapp_verify_token = (req.whatsapp_verify_token or "").strip() or None

# # # #     if provider == "meta" and not meta_phone_number_id:
# # # #         raise HTTPException(status_code=400, detail="Meta phone number ID is required.")

# # # #     if provider == "twilio":
# # # #         if not twilio_account_sid or not twilio_auth_token:
# # # #             raise HTTPException(
# # # #                 status_code=400,
# # # #                 detail="Twilio Account SID and Auth Token are required.",
# # # #             )

# # # #         if not twilio_phone_number and whatsapp_number:
# # # #             twilio_phone_number = whatsapp_number

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 UPDATE tenants
# # # #                 SET whatsapp_provider=%s,
# # # #                     meta_access_token=COALESCE(%s, meta_access_token),
# # # #                     meta_phone_number_id=%s,
# # # #                     meta_business_account_id=%s,
# # # #                     twilio_account_sid=COALESCE(%s, twilio_account_sid),
# # # #                     twilio_auth_token=COALESCE(%s, twilio_auth_token),
# # # #                     twilio_phone_number=%s,
# # # #                     whatsapp_number=%s,
# # # #                     whatsapp_verify_token=%s,
# # # #                     updated_at=NOW()
# # # #                 WHERE id=%s
# # # #                 """,
# # # #                 (
# # # #                     provider,
# # # #                     meta_access_token,
# # # #                     meta_phone_number_id,
# # # #                     meta_business_account_id,
# # # #                     twilio_account_sid,
# # # #                     twilio_auth_token,
# # # #                     twilio_phone_number,
# # # #                     whatsapp_number,
# # # #                     whatsapp_verify_token,
# # # #                     tenant_id,
# # # #                 ),
# # # #             )
# # # #     finally:
# # # #         conn.close()

# # # #     return {"success": True, "message": "WhatsApp connection saved successfully.", "provider": provider}




# # # # @app.get("/tenant/whatsapp-config")
# # # # def tenant_whatsapp_config(current_user: dict = Depends(get_current_user)):
# # # #     return get_whatsapp_connection(current_user)

# # # # @app.post("/tenant/active-agent-type")
# # # # def update_active_agent_type(
# # # #     req: ActiveAgentTypeRequest,
# # # #     current_user: dict = Depends(get_current_user),
# # # # ):
# # # #     agent_type = (req.active_agent_type or "").strip().lower()

# # # #     if agent_type not in ["chat", "product"]:
# # # #         raise HTTPException(
# # # #             status_code=400,
# # # #             detail="active_agent_type must be chat or product.",
# # # #         )

# # # #     tenant_id = current_user["tenant_id"]

# # # #     conn = get_main_db_connection()
# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 UPDATE tenants
# # # #                 SET active_agent_type=%s,
# # # #                     updated_at=NOW()
# # # #                 WHERE id=%s
# # # #                 """,
# # # #                 (agent_type, tenant_id),
# # # #             )
# # # #     finally:
# # # #         conn.close()

# # # #     return {
# # # #         "success": True,
# # # #         "active_agent_type": agent_type,
# # # #         "agent_type": agent_type,
# # # #     }


# # # # @app.get("/tenant/active-agent-type/{tenant_slug}")
# # # # def get_active_agent_type_public(tenant_slug: str):
# # # #     tenant = get_tenant_by_slug(tenant_slug)

# # # #     if not tenant:
# # # #         raise HTTPException(status_code=404, detail="Tenant not found")

# # # #     active_agent_type = tenant.get("active_agent_type") or "chat"

# # # #     return {
# # # #         "success": True,
# # # #         "tenant_slug": tenant["slug"],
# # # #         "active_agent_type": active_agent_type,
# # # #         "agent_type": active_agent_type,
# # # #     }

# # # # @app.post("/tenant/whatsapp-config")
# # # # def tenant_save_whatsapp_config(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# # # #     return save_whatsapp_connection(req, current_user)

# # # # @app.post("/send-whatsapp-message")
# # # # def send_whatsapp_message(req: SendWhatsAppTextRequest, current_user: dict = Depends(get_current_user)):
# # # #     if not req.to_phone or not req.message:
# # # #         raise HTTPException(status_code=400, detail="to_phone and message are required.")
# # # #     return send_whatsapp_text(current_user["tenant_id"], req.to_phone, req.message)


# # # # @app.post("/send-whatsapp-media")
# # # # def send_whatsapp_media_message(req: SendWhatsAppMediaRequest, current_user: dict = Depends(get_current_user)):
# # # #     if not req.to_phone or not req.media_url:
# # # #         raise HTTPException(status_code=400, detail="to_phone and media_url are required.")
# # # #     return send_whatsapp_media(current_user["tenant_id"], req.to_phone, req.media_url, req.caption or "")


# # # # @app.get("/webhook/whatsapp/{tenant_slug}")
# # # # @app.get("/webhooks/whatsapp/{tenant_slug}")
# # # # def verify_meta_webhook(tenant_slug: str, request: Request):
# # # #     # Meta webhook verification: hub.mode, hub.verify_token, hub.challenge
# # # #     mode = request.query_params.get("hub.mode")
# # # #     verify_token = request.query_params.get("hub.verify_token")
# # # #     challenge = request.query_params.get("hub.challenge")

# # # #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# # # #     expected_token = tenant.get("whatsapp_verify_token") or "agentive_verify_token_123"

# # # #     if mode == "subscribe" and verify_token == expected_token:
# # # #         return Response(content=str(challenge), media_type="text/plain")

# # # #     raise HTTPException(status_code=403, detail="Webhook verification failed.")


# # # # @app.post("/webhook/whatsapp/{tenant_slug}")
# # # # @app.post("/webhooks/whatsapp/{tenant_slug}")
# # # # async def whatsapp_webhook(tenant_slug: str, request: Request):
# # # #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# # # #     provider = tenant.get("whatsapp_provider")

# # # #     # Twilio sends form-urlencoded data. Meta sends JSON.
# # # #     content_type = request.headers.get("content-type", "")

# # # #     if provider == "twilio" or "application/x-www-form-urlencoded" in content_type:
# # # #         form = await request.form()
# # # #         customer_phone = str(form.get("From") or "").replace("whatsapp:", "")
# # # #         incoming_message = str(form.get("Body") or "").strip()

# # # #         if not customer_phone or not incoming_message:
# # # #             return {"success": True, "message": "No text message to process."}

# # # #         return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # # #     data = await request.json()

# # # #     try:
# # # #         entry = (data.get("entry") or [])[0]
# # # #         change = (entry.get("changes") or [])[0]
# # # #         value = change.get("value") or {}
# # # #         message_obj = (value.get("messages") or [])[0]
# # # #         customer_phone = message_obj.get("from")
# # # #         incoming_message = (message_obj.get("text") or {}).get("body", "").strip()
# # # #     except Exception:
# # # #         return {"success": True, "message": "No supported Meta message to process."}

# # # #     if not customer_phone or not incoming_message:
# # # #         return {"success": True, "message": "No text message to process."}

# # # #     return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # # # # ==========================================================
# # # # # Contacts API
# # # # # Must stay ABOVE React fallback route
# # # # # ==========================================================
# # # # @app.get("/api/contacts")
# # # # def get_contacts(current_user: dict = Depends(get_current_user)):
# # # #     tenant_id = current_user["tenant_id"]

# # # #     conn = get_main_db_connection()

# # # #     try:
# # # #         with conn.cursor() as cur:
# # # #             cur.execute(
# # # #                 """
# # # #                 SELECT
# # # #                     id,
# # # #                     tenant_id,
# # # #                     session_id,
# # # #                     name,
# # # #                     email,
# # # #                     phone,
# # # #                     first_message,
# # # #                     last_message,
# # # #                     source,
# # # #                     status,
# # # #                     user_agent,
# # # #                     ip_address,
# # # #                     created_at,
# # # #                     updated_at,
# # # #                     last_seen_at
# # # #                 FROM tenant_customers
# # # #                 WHERE tenant_id=%s
# # # #                 ORDER BY
# # # #                     last_seen_at DESC,
# # # #                     created_at DESC
# # # #                 """,
# # # #                 (tenant_id,),
# # # #             )

# # # #             contacts = cur.fetchall() or []

# # # #     finally:
# # # #         conn.close()

# # # #     return {
# # # #         "success": True,
# # # #         "total": len(contacts),
# # # #         "contacts": contacts,
# # # #     }

# # # # # ==========================================================
# # # # # Clean Public URL + React Frontend Route Fallback
# # # # # KEEP THESE AT THE VERY BOTTOM OF main.py
# # # # # ==========================================================

# # # # # @app.get("/public-link/resolve/{public_name}")
# # # # # def resolve_public_link(public_name: str):
# # # # #     resolved = _resolve_public_name(public_name)

# # # # #     if not resolved:
# # # # #         raise HTTPException(status_code=404, detail="Public link not found.")

# # # # #     return {
# # # # #         "success": True,
# # # # #         "tenant_slug": resolved["tenant_slug"],
# # # # #         "target_path": resolved["target_path"],
# # # # #     } 

# # # # @app.get("/public-link/resolve/{public_name}")
# # # # def resolve_public_link(public_name: str):
# # # #     resolved = _resolve_public_name(public_name)

# # # #     if not resolved:
# # # #         raise HTTPException(status_code=404, detail="Public link not found.")

# # # #     return {
# # # #         "success": True,
# # # #         "tenant_slug": resolved["tenant_slug"],
# # # #         "target_path": resolved["target_path"],
# # # #         "agent_type": resolved.get("active_agent_type") or "chat",
# # # #         "active_agent_type": resolved.get("active_agent_type") or "chat",
# # # #     }



# # # # # @app.get("/{public_name}")
# # # # # def open_clean_public_chat_url(public_name: str):
# # # # #     resolved = _resolve_public_name(public_name)
# # # # #     index_path = os.path.join(BUILD_DIR, "index.html")

# # # # #     if resolved:
# # # # #         if os.path.exists(index_path):
# # # # #             return FileResponse(index_path)

# # # # #         raise HTTPException(
# # # # #             status_code=404,
# # # # #             detail="React build index.html not found"
# # # # #         )

# # # # #     # IMPORTANT:
# # # # #     # if not a valid public link,
# # # # #     # do NOT return index here
# # # # #     raise HTTPException(status_code=404, detail="Page not found")



# # # # if os.path.exists(BUILD_DIR):

# # # #     @app.get("/{full_path:path}")
# # # #     def serve_react_routes(full_path: str):
# # # #         index_path = os.path.join(BUILD_DIR, "index.html")

# # # #         if os.path.exists(index_path):
# # # #             return FileResponse(index_path)

# # # #         raise HTTPException(status_code=404, detail="React build index.html not found")

# # # from fastapi.staticfiles import StaticFiles
# # # from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
# # # from app.auth import router as auth_router, get_current_user
# # # from fastapi import Depends
# # # from dotenv import load_dotenv
# # # load_dotenv()
# # # import json
# # # import os
# # # import re
# # # import secrets
# # # import string
# # # from typing import List, Optional
# # # from uuid import uuid4

# # # from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
# # # from fastapi.middleware.cors import CORSMiddleware
# # # from pydantic import BaseModel

# # # from app.chatbot import chat_with_agent
# # # from app.db import get_main_db_connection
# # # from app.file_parser import parse_uploaded_file
# # # from app.index_builder import add_chunks_to_faiss
# # # from app.integration import router as integration_router
# # # from app.product_query_bot import router as product_query_router, process_product_chat
# # # from app.knowledge_store import (
# # #     get_combined_training_path,
# # #     get_entry_text_path,
# # #     get_knowledge_entry,
# # #     list_knowledge_entries,
# # #     save_knowledge_documents,
# # # )
# # # from app.whatsapp import (
# # #     get_tenant_whatsapp_config,
# # #     handle_incoming_text_and_reply,
# # #     normalize_phone,
# # #     send_whatsapp_media,
# # #     send_whatsapp_text,
# # # )
# # # from app.scraper import scrape_by_request
# # # from app.training_registry import (
# # #     docs_to_chunks,
# # #     is_done,
# # #     mark_done,
# # #     mark_failed,
# # #     mark_processing,
# # #     normalize_website_json,
# # #     sha256_bytes,
# # #     sha256_text,
# # # )
# # # from app.utils import (
# # #     DATA_DIR,
# # #     DONE_SCRAPED_DIR,
# # #     DONE_UPLOAD_DIR,
# # #     FAILED_DIR,
# # #     PENDING_SCRAPED_DIR,
# # #     PENDING_UPLOAD_DIR,
# # #     safe_filename,
# # #     save_json,
# # #     move_file_safely,
# # # )

# # # app = FastAPI(title="Agent Training + WhatsApp Chat Backend", version="2.1.0")

# # # # Railway / production friendly CORS.
# # # # Set CORS_ORIGINS in Railway like:
# # # # CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com
# # # _raw_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
# # # _cors_origins = ["*"] if _raw_cors_origins == "*" else [origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()]

# # # app.add_middleware(
# # #     CORSMiddleware,
# # #     allow_origins=_cors_origins,
# # #     allow_credentials=True,
# # #     allow_methods=["*"],
# # #     allow_headers=["*"],
# # # )

# # # app.include_router(auth_router)
# # # app.include_router(integration_router)
# # # app.include_router(product_query_router)

# # # class ChatRequest(BaseModel):
# # #     message: str
# # #     session_id: Optional[str] = None
# # #     top_k: Optional[int] = 2


# # # class PublicChatRequest(BaseModel):
# # #     message: str
# # #     session_id: Optional[str] = None
# # #     top_k: Optional[int] = 2
# # #     customer_name: Optional[str] = None
# # #     customer_email: Optional[str] = None
# # #     customer_phone: Optional[str] = None


# # # class PublicLinkUpdateRequest(BaseModel):
# # #     sweet_name: Optional[str] = None


# # # class ActiveAgentTypeRequest(BaseModel):
# # #     active_agent_type: str


# # # def get_tenant_by_slug(tenant_slug: str):
# # #     tenant_slug = (tenant_slug or "").strip()
# # #     if not tenant_slug:
# # #         return None
    
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT id, slug, tenant_name, status, active_agent_type
# # #                 FROM tenants
# # #                 WHERE slug=%s AND status='active'
# # #                 LIMIT 1
                
# # #                 """,
# # #                 (tenant_slug,),
# # #             )
# # #             return cur.fetchone()
# # #     finally:
# # #         conn.close()


# # # def upsert_tenant_customer(
# # #     tenant_id: int,
# # #     session_id: str,
# # #     name: str = None,
# # #     email: str = None,
# # #     phone: str = None,
# # #     message: str = None,
# # #     request: Request = None,
# # # ):
# # #     name = (name or "").strip() or None
# # #     email = (email or "").strip().lower() or None
# # #     phone = (phone or "").strip() or None
# # #     message = (message or "").strip() or None

# # #     user_agent = None
# # #     ip_address = None

# # #     if request is not None:
# # #         user_agent = request.headers.get("user-agent")
# # #         if request.client:
# # #             ip_address = request.client.host

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 INSERT INTO tenant_customers
# # #                     (tenant_id, session_id, name, email, phone, first_message, last_message,
# # #                      source, status, user_agent, ip_address, last_seen_at)
# # #                 VALUES
# # #                     (%s, %s, %s, %s, %s, %s, %s, 'public_chat', 'active', %s, %s, NOW())
# # #                 ON DUPLICATE KEY UPDATE
# # #                     name = COALESCE(VALUES(name), name),
# # #                     email = COALESCE(VALUES(email), email),
# # #                     phone = COALESCE(VALUES(phone), phone),
# # #                     first_message = COALESCE(first_message, VALUES(first_message)),
# # #                     last_message = VALUES(last_message),
# # #                     user_agent = COALESCE(VALUES(user_agent), user_agent),
# # #                     ip_address = COALESCE(VALUES(ip_address), ip_address),
# # #                     status = IF(status='new', 'active', status),
# # #                     last_seen_at = NOW(),
# # #                     updated_at = NOW()
# # #                 """,
# # #                 (
# # #                     tenant_id,
# # #                     session_id,
# # #                     name,
# # #                     email,
# # #                     phone,
# # #                     message,
# # #                     message,
# # #                     user_agent,
# # #                     ip_address,
# # #                 ),
# # #             )

# # #             cur.execute(
# # #                 """
# # #                 SELECT id, tenant_id, session_id, name, email, phone, status
# # #                 FROM tenant_customers
# # #                 WHERE tenant_id=%s AND session_id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id, session_id),
# # #             )
# # #             return cur.fetchone()
# # #     finally:
# # #         conn.close()


# # # # ==========================================================
# # # # Serve React Frontend on Railway
# # # # Required folder structure:
# # # # backend/
# # # #   main.py
# # # #   build/
# # # #     index.html
# # # #     static/
# # # # ==========================================================
# # # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # # BUILD_DIR = os.path.join(BASE_DIR, "build")
# # # STATIC_DIR = os.path.join(BUILD_DIR, "static")

# # # if os.path.exists(STATIC_DIR):
# # #     app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# # # @app.get("/")
# # # def serve_react_app():
# # #     index_path = os.path.join(BUILD_DIR, "index.html")

# # #     if os.path.exists(index_path):
# # #         return FileResponse(index_path)

# # #     return {
# # #         "status": "ok",
# # #         "message": "Backend running, but React build/index.html was not found.",
# # #         "required_folder": "Place React build folder beside main.py as ./build",
# # #         "training_endpoint": "/train-agent",
# # #         "protected_chat_endpoint": "/chat",
# # #         "public_chat_endpoint": "/chat/{tenant_slug} or /chat_{tenant_slug}",
# # #     }

# # # # ==========================================================
# # # # Knowledge Base readable text APIs
# # # # These APIs let a tenant user see/download the exact text that was extracted
# # # # and sent for FAISS training.
# # # # ==========================================================
# # # @app.get("/knowledge")
# # # def get_knowledge_entries(search: Optional[str] = "", current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     entries = list_knowledge_entries(tenant_id, search=search or "")
# # #     return {
# # #         "success": True,
# # #         "count": len(entries),
# # #         "entries": entries,
# # #     }


# # # @app.get("/knowledge/download")
# # # def download_all_knowledge(current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     path = get_combined_training_path(tenant_id)
# # #     if not path.exists():
# # #         raise HTTPException(status_code=404, detail="No knowledge text found for this tenant.")
# # #     return FileResponse(
# # #         str(path),
# # #         media_type="text/plain",
# # #         filename=f"tenant_{tenant_id}_all_training_data.txt",
# # #     )


# # # @app.get("/knowledge/{entry_id}")
# # # def get_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     entry = get_knowledge_entry(tenant_id, entry_id)
# # #     if not entry:
# # #         raise HTTPException(status_code=404, detail="Knowledge entry not found.")
# # #     return {"success": True, "entry": entry}


# # # @app.get("/knowledge/{entry_id}/download")
# # # def download_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     entry = get_knowledge_entry(tenant_id, entry_id)
# # #     path = get_entry_text_path(tenant_id, entry_id)
# # #     if not entry or not path:
# # #         raise HTTPException(status_code=404, detail="Knowledge text file not found.")
# # #     safe_title = safe_filename(entry.get("title") or entry_id)
# # #     return FileResponse(
# # #         str(path),
# # #         media_type="text/plain",
# # #         filename=f"{safe_title}.txt",
# # #     )


# # # # @app.post("/train-agent")
# # # # async def train_agent(
# # # #     website_url: Optional[str] = Form(default=""),
# # # #     sitemap_url: Optional[str] = Form(default=""),
# # # #     crawl_type: str = Form(default="single_page"),
# # # #     content_type: str = Form(default="Mixed Content"),
# # # #     files: List[UploadFile] = File(default=[]),
# # # # ):
# # # @app.post("/train-agent")
# # # async def train_agent(
# # #     website_url: Optional[str] = Form(default=""),
# # #     sitemap_url: Optional[str] = Form(default=""),
# # #     crawl_type: str = Form(default="single_page"),
# # #     content_type: str = Form(default="Mixed Content"),
# # #     files: List[UploadFile] = File(default=[]),
# # #     current_user: dict = Depends(get_current_user),
# # # ):
# # #     website_url = (website_url or "").strip()
# # #     sitemap_url = (sitemap_url or "").strip()
# # #     crawl_type = (crawl_type or "single_page").strip()
# # #     content_type = (content_type or "Mixed Content").strip()
# # #     tenant_id = current_user["tenant_id"]

# # #     existing_website_json = DATA_DIR / "website_data.json"

# # #     if not website_url and not sitemap_url and not files and not existing_website_json.exists():
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# # #         )

# # #     all_new_chunks = []
# # #     skipped_sources = []
# # #     processed_sources = []
# # #     failed_sources = []
# # #     uploaded_documents_count = 0
# # #     website_documents_count = 0

# # #     # 1. Existing data/website_data.json support
# # #     if existing_website_json.exists():
# # #         try:
# # #             raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# # #             source_hash = sha256_text(raw_text)
# # #             source_key = f"tenant::{tenant_id}::website_data.json"

# # #             if is_done(source_key, source_hash):
# # #                 skipped_sources.append(source_key)
# # #             else:
# # #                 mark_processing(source_key, source_hash, {"source_type": "website_json"})

# # #                 data = json.loads(raw_text)
# # #                 docs = normalize_website_json(data, content_type="Website")
# # #                 chunks = docs_to_chunks(
# # #                     docs,
# # #                     source_key=source_key,
# # #                     source_hash=source_hash,
# # #                 )
# # #                 save_knowledge_documents(
# # #                     tenant_id=tenant_id,
# # #                     documents=docs,
# # #                     source_key=source_key,
# # #                     source_hash=source_hash,
# # #                     default_source_type="website_json",
# # #                     tags=["website", "training"],
# # #                 )

# # #                 all_new_chunks.extend(chunks)
# # #                 website_documents_count += len(docs)

# # #                 mark_done(
# # #                     source_key,
# # #                     source_hash,
# # #                     len(chunks),
# # #                     {
# # #                         "documents": len(docs),
# # #                         "source_type": "website_json",
# # #                     },
# # #                 )

# # #                 processed_sources.append(source_key)

# # #         except Exception as exc:
# # #             mark_failed(
# # #                 "website_data.json",
# # #                 "unknown",
# # #                 str(exc),
# # #                 {"source_type": "website_json"},
# # #             )
# # #             failed_sources.append({
# # #                 "source": "website_data.json",
# # #                 "error": str(exc),
# # #             })

# # #     # 2. Scrape website / sitemap
# # #     if website_url or sitemap_url:
# # #         scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"

# # #         try:
# # #             scraped_documents = scrape_by_request(
# # #                 website_url=website_url,
# # #                 sitemap_url=sitemap_url,
# # #                 crawl_type=crawl_type,
# # #                 content_type=content_type,
# # #             )

# # #             raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# # #             source_hash = sha256_text(raw_scrape_text)

# # #             if is_done(scrape_key, source_hash):
# # #                 skipped_sources.append(scrape_key)
# # #             else:
# # #                 mark_processing(scrape_key, source_hash, {"source_type": "scrape"})

# # #                 raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# # #                 save_json(raw_scrape_file, scraped_documents)
# # #                 move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# # #                 chunks = docs_to_chunks(
# # #                     scraped_documents,
# # #                     source_key=scrape_key,
# # #                     source_hash=source_hash,
# # #                 )
# # #                 save_knowledge_documents(
# # #                     tenant_id=tenant_id,
# # #                     documents=scraped_documents,
# # #                     source_key=scrape_key,
# # #                     source_hash=source_hash,
# # #                     default_source_type="website",
# # #                     tags=["website", crawl_type, "training"],
# # #                 )

# # #                 all_new_chunks.extend(chunks)
# # #                 website_documents_count += len(scraped_documents)

# # #                 mark_done(
# # #                     scrape_key,
# # #                     source_hash,
# # #                     len(chunks),
# # #                     {
# # #                         "documents": len(scraped_documents),
# # #                         "source_type": "scrape",
# # #                     },
# # #                 )

# # #                 processed_sources.append(scrape_key)

# # #         except Exception as exc:
# # #             error_file = FAILED_DIR / "scrape_error.txt"
# # #             error_file.write_text(str(exc), encoding="utf-8")

# # #             mark_failed(
# # #                 scrape_key,
# # #                 "unknown",
# # #                 str(exc),
# # #                 {"source_type": "scrape"},
# # #             )

# # #             failed_sources.append({
# # #                 "source": scrape_key,
# # #                 "error": str(exc),
# # #             })

# # #     # 3. Uploaded files
# # #     for upload in files:
# # #         original_name = upload.filename or "uploaded_file"
# # #         file_name = safe_filename(original_name)
# # #         pending_path = PENDING_UPLOAD_DIR / file_name

# # #         try:
# # #             content = await upload.read()
# # #             source_hash = sha256_bytes(content)
# # #             source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# # #             if is_done(source_key, source_hash):
# # #                 skipped_sources.append(original_name)
# # #                 continue

# # #             mark_processing(
# # #                 source_key,
# # #                 source_hash,
# # #                 {
# # #                     "file_name": original_name,
# # #                     "source_type": "file",
# # #                 },
# # #             )

# # #             pending_path.write_bytes(content)

# # #             parsed_doc = parse_uploaded_file(
# # #                 file_path=pending_path,
# # #                 original_name=original_name,
# # #                 content_type=content_type,
# # #             )

# # #             if parsed_doc and parsed_doc.get("text"):
# # #                 chunks = docs_to_chunks(
# # #                     [parsed_doc],
# # #                     source_key=source_key,
# # #                     source_hash=source_hash,
# # #                 )
# # #                 save_knowledge_documents(
# # #                     tenant_id=tenant_id,
# # #                     documents=[parsed_doc],
# # #                     source_key=source_key,
# # #                     source_hash=source_hash,
# # #                     default_source_type="file",
# # #                     tags=["file", "training"],
# # #                 )

# # #                 all_new_chunks.extend(chunks)
# # #                 uploaded_documents_count += 1

# # #                 move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)

# # #                 mark_done(
# # #                     source_key,
# # #                     source_hash,
# # #                     len(chunks),
# # #                     {
# # #                         "file_name": original_name,
# # #                         "source_type": "file",
# # #                     },
# # #                 )

# # #                 processed_sources.append(original_name)

# # #             else:
# # #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# # #                 mark_failed(
# # #                     source_key,
# # #                     source_hash,
# # #                     "No text extracted",
# # #                     {
# # #                         "file_name": original_name,
# # #                         "source_type": "file",
# # #                     },
# # #                 )

# # #                 failed_sources.append({
# # #                     "source": original_name,
# # #                     "error": "No text extracted",
# # #                 })

# # #         except Exception as exc:
# # #             if pending_path.exists():
# # #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# # #             mark_failed(
# # #                 f"file::{file_name}",
# # #                 "unknown",
# # #                 str(exc),
# # #                 {
# # #                     "file_name": original_name,
# # #                     "source_type": "file",
# # #                 },
# # #             )

# # #             failed_sources.append({
# # #                 "source": original_name,
# # #                 "error": str(exc),
# # #             })

# # #     if not all_new_chunks and not skipped_sources:
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="No new text could be extracted from the provided source.",
# # #         )

# # #     index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# # #     if all_new_chunks:
# # #         save_json(DATA_DIR / "latest_new_chunks.json", all_new_chunks)

# # #     return {
# # #         "success": True,
# # #         "message": "Agent training completed. New content was added and duplicate content was skipped.",
# # #         "content_type": content_type,
# # #         "crawl_type": crawl_type,
# # #         "website_documents": website_documents_count,
# # #         "uploaded_documents": uploaded_documents_count,
# # #         "chunks_created": len(all_new_chunks),
# # #         "processed_sources": processed_sources,
# # #         "skipped_sources": skipped_sources,
# # #         "failed_sources": failed_sources,
# # #         "faiss_index_path": index_info.get("index_path"),
# # #         "metadata_path": index_info.get("metadata_path"),
# # #         "total_vectors": index_info.get("total_vectors"),
# # #     }


# # # @app.post("/chat")
# # # def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
# # #     message = (request.message or "").strip()

# # #     if not message:
# # #         raise HTTPException(status_code=400, detail="Message is required.")

# # #     session_id = request.session_id or str(uuid4())

# # #     try:
# # #         return chat_with_agent(
# # #             session_id=session_id,
# # #             message=message,
# # #             tenant_id=current_user["tenant_id"],
# # #             top_k=request.top_k or 2,
# # #         )

# # #     except FileNotFoundError:
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="Please train the agent first. FAISS index is missing.",
# # #         )

# # #     except Exception as exc:
# # #         raise HTTPException(status_code=500, detail=str(exc))

# # # def _public_chat_response(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # #     tenant = get_tenant_by_slug(tenant_slug)

# # #     if not tenant:
# # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# # #     message = (request_body.message or "").strip()
# # #     if not message:
# # #         raise HTTPException(status_code=400, detail="Message is required.")

# # #     session_id = request_body.session_id or str(uuid4())

# # #     customer = upsert_tenant_customer(
# # #         tenant_id=tenant["id"],
# # #         session_id=session_id,
# # #         name=request_body.customer_name,
# # #         email=request_body.customer_email,
# # #         phone=request_body.customer_phone,
# # #         message=message,
# # #         request=request,
# # #     )

# # #     try:
# # #         active_agent_type = (tenant.get("active_agent_type") or "chat").strip().lower()

# # #         # Multi-tenant routing:
# # #         # - product tenants use the existing product DB flow
# # #         # - normal chat tenants use FAISS + LLM flow
# # #         if active_agent_type == "product":
# # #             product_result = process_product_chat(
# # #                 query=message,
# # #                 session_id=session_id,
# # #                 tenant_id=tenant["id"],
# # #             )
# # #             responses = product_result.get("responses") or []
# # #             chat_result = {
# # #                 "answer": "\n\n".join(responses),
# # #                 "responses": responses,
# # #                 "session_id": session_id,
# # #                 "images": [],
# # #                 "links": [],
# # #                 "sources": [],
# # #                 "images_count": 0,
# # #                 "links_count": 0,
# # #                 "history_count": 0,
# # #                 "agent_type": "product",
# # #                 "product_step": product_result.get("step"),
# # #                 "lookup_type": product_result.get("lookup_type"),
# # #             }
# # #         else:
# # #             chat_result = chat_with_agent(
# # #                 session_id=session_id,
# # #                 message=message,
# # #                 tenant_id=tenant["id"],
# # #                 top_k=request_body.top_k or 2,
# # #             )
# # #             chat_result["agent_type"] = "chat"

# # #         chat_result["tenant"] = {
# # #             "id": tenant["id"],
# # #             "slug": tenant["slug"],
# # #             "tenant_name": tenant["tenant_name"],
# # #             "active_agent_type": active_agent_type,
# # #         }
# # #         chat_result["customer"] = {
# # #             "id": customer.get("id") if customer else None,
# # #             "name": customer.get("name") if customer else request_body.customer_name,
# # #             "email": customer.get("email") if customer else request_body.customer_email,
# # #         }
# # #         return chat_result

# # #     except FileNotFoundError:
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="Please train this tenant agent first. FAISS index is missing.",
# # #         )

# # #     except Exception as exc:
# # #         raise HTTPException(status_code=500, detail=str(exc))




# # # @app.post("/public-chat/customer/{tenant_slug}")
# # # def save_public_chat_customer(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # #     tenant = get_tenant_by_slug(tenant_slug)
# # #     if not tenant:
# # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
# # #     session_id = request_body.session_id or str(uuid4())
# # #     customer = upsert_tenant_customer(
# # #         tenant_id=tenant["id"],
# # #         session_id=session_id,
# # #         name=request_body.customer_name,
# # #         email=request_body.customer_email,
# # #         phone=request_body.customer_phone,
# # #         message=request_body.message or "",
# # #         request=request,
# # #     )
# # #     return {"success": True, "session_id": session_id, "customer": customer}


# # # @app.post("/chat/{tenant_slug}")
# # # def public_chat_by_path(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # #     return _public_chat_response(tenant_slug, request_body, request)


# # # @app.post("/chat_{tenant_slug}")
# # # def public_chat_by_underscore(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# # #     return _public_chat_response(tenant_slug, request_body, request)


# # # # ==========================================================
# # # # Clean Public URL APIs
# # # # Example:
# # # #   /instapress -> /chat_t3
# # # #   /A8X9K2PQ   -> /chat_t3
# # # # ==========================================================
# # # PUBLIC_CODE_LENGTH = 8
# # # PUBLIC_CODE_ALPHABET = string.ascii_uppercase + string.digits
# # # SWEET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,49}$")

# # # # These names are already used by backend/frontend routes and must not be taken as sweet names.
# # # RESERVED_PUBLIC_NAMES = {
# # #     "api", "auth", "chat", "contacts", "dashboard", "docs", "health",
# # #     "knowledge", "login", "logout", "openapi.json", "public-chat",
# # #     "review-agent", "static", "train", "train-agent", "whatsapp",
# # # }


# # # def _get_base_url(request: Request) -> str:
# # #     """Build correct production base URL behind Railway/proxy."""
# # #     proto = request.headers.get("x-forwarded-proto") or request.url.scheme
# # #     host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
# # #     return f"{proto}://{host}".rstrip("/")


# # # def _normalize_sweet_name(value: Optional[str]) -> Optional[str]:
# # #     value = (value or "").strip().strip("/")
# # #     if not value:
# # #         return None
# # #     # Keep URLs clean and predictable.
# # #     value = value.lower()
# # #     return value


# # # def _validate_sweet_name(value: Optional[str]) -> Optional[str]:
# # #     value = _normalize_sweet_name(value)
# # #     if not value:
# # #         return None

# # #     if value in RESERVED_PUBLIC_NAMES or value.startswith("chat_"):
# # #         raise HTTPException(status_code=400, detail="This name is reserved. Please choose another name.")

# # #     if not SWEET_NAME_PATTERN.match(value):
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="Sweet name must be 3-50 characters and can use letters, numbers, hyphen, or underscore.",
# # #         )

# # #     return value


# # # def _generate_public_code() -> str:
# # #     return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


# # # def _get_tenant_slug_by_id(tenant_id: int) -> str:
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT slug
# # #                 FROM tenants
# # #                 WHERE id=%s AND status='active'
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             row = cur.fetchone()
# # #     finally:
# # #         conn.close()

# # #     if not row:
# # #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# # #     return row["slug"]


# # # def _get_or_create_public_link(tenant_id: int) -> dict:
# # #     tenant_slug = _get_tenant_slug_by_id(tenant_id)
# # #     target_path = f"/chat_{tenant_slug}"

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # #                 FROM tenant_public_links
# # #                 WHERE tenant_id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             row = cur.fetchone()

# # #             if row:
# # #                 # Keep tenant slug/path updated if tenant slug ever changes.
# # #                 if row.get("tenant_slug") != tenant_slug or row.get("target_path") != target_path:
# # #                     cur.execute(
# # #                         """
# # #                         UPDATE tenant_public_links
# # #                         SET tenant_slug=%s, target_path=%s, updated_at=NOW()
# # #                         WHERE tenant_id=%s
# # #                         """,
# # #                         (tenant_slug, target_path, tenant_id),
# # #                     )
# # #                     row["tenant_slug"] = tenant_slug
# # #                     row["target_path"] = target_path
# # #                 return row

# # #             # Table is empty for new tenant: create permanent hidden 8-char code.
# # #             for _ in range(20):
# # #                 short_code = _generate_public_code()
# # #                 try:
# # #                     cur.execute(
# # #                         """
# # #                         INSERT INTO tenant_public_links
# # #                             (tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active)
# # #                         VALUES
# # #                             (%s, %s, %s, NULL, %s, 1)
# # #                         """,
# # #                         (tenant_id, tenant_slug, short_code, target_path),
# # #                     )
# # #                     cur.execute(
# # #                         """
# # #                         SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # #                         FROM tenant_public_links
# # #                         WHERE tenant_id=%s
# # #                         LIMIT 1
# # #                         """,
# # #                         (tenant_id,),
# # #                     )
# # #                     return cur.fetchone()
# # #                 except Exception as exc:
# # #                     # Retry only when short_code collision happens. Otherwise raise original DB error.
# # #                     if "Duplicate" not in str(exc) and "duplicate" not in str(exc):
# # #                         raise

# # #     finally:
# # #         conn.close()

# # #     raise HTTPException(status_code=500, detail="Could not generate unique public link. Please try again.")


# # # def _format_public_link_response(row: dict, request: Request) -> dict:
# # #     base_url = _get_base_url(request)
# # #     public_name = row.get("sweet_name") or row.get("short_code")

# # #     return {
# # #         "success": True,
# # #         "tenant_id": row.get("tenant_id"),
# # #         "tenant_slug": row.get("tenant_slug"),
# # #         "short_code": row.get("short_code"),
# # #         "sweet_name": row.get("sweet_name"),
# # #         "public_name": public_name,
# # #         "target_path": row.get("target_path"),
# # #         "original_url": f"{base_url}{row.get('target_path')}",
# # #         "public_url": f"{base_url}/{public_name}",
# # #         "fallback_public_url": f"{base_url}/{row.get('short_code')}",
# # #     }


# # # @app.get("/public-link")
# # # def get_public_link(request: Request, current_user: dict = Depends(get_current_user)):
# # #     row = _get_or_create_public_link(current_user["tenant_id"])
# # #     return _format_public_link_response(row, request)


# # # @app.post("/public-link")
# # # def update_public_link(
# # #     request_body: PublicLinkUpdateRequest,
# # #     request: Request,
# # #     current_user: dict = Depends(get_current_user),
# # # ):
# # #     tenant_id = current_user["tenant_id"]
# # #     sweet_name = _validate_sweet_name(request_body.sweet_name)

# # #     # Ensure row exists before update.
# # #     _get_or_create_public_link(tenant_id)

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             if sweet_name:
# # #                 cur.execute(
# # #                     """
# # #                     SELECT tenant_id
# # #                     FROM tenant_public_links
# # #                     WHERE sweet_name=%s AND tenant_id<>%s
# # #                     LIMIT 1
# # #                     """,
# # #                     (sweet_name, tenant_id),
# # #                 )
# # #                 existing = cur.fetchone()
# # #                 if existing:
# # #                     raise HTTPException(status_code=409, detail="This sweet name is already taken. Please choose another.")

# # #             cur.execute(
# # #                 """
# # #                 UPDATE tenant_public_links
# # #                 SET sweet_name=%s, updated_at=NOW()
# # #                 WHERE tenant_id=%s
# # #                 """,
# # #                 (sweet_name, tenant_id),
# # #             )

# # #             cur.execute(
# # #                 """
# # #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# # #                 FROM tenant_public_links
# # #                 WHERE tenant_id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             row = cur.fetchone()
# # #     finally:
# # #         conn.close()

# # #     return _format_public_link_response(row, request)


# # # def _resolve_public_name(public_name: str) -> Optional[dict]:
# # #     public_name = (public_name or "").strip().strip("/")
# # #     if not public_name:
# # #         return None

# # #     normalized_name = public_name.lower()

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT
# # #                     tpl.tenant_id,
# # #                     tpl.tenant_slug,
# # #                     tpl.short_code,
# # #                     tpl.sweet_name,
# # #                     tpl.target_path,
# # #                     tpl.is_active,
# # #                     COALESCE(t.active_agent_type, 'chat') AS active_agent_type
# # #                 FROM tenant_public_links tpl
# # #                 JOIN tenants t ON t.id = tpl.tenant_id
# # #                 WHERE tpl.is_active = 1
# # #                   AND t.status = 'active'
# # #                   AND (LOWER(tpl.sweet_name) = %s OR tpl.short_code = %s)
# # #                 LIMIT 1
# # #                 """,
# # #                 (normalized_name, public_name.upper()),
# # #             )
# # #             return cur.fetchone()
# # #     finally:
# # #         conn.close()


# # # # ==========================================================
# # # # Live Training Progress API
# # # # Added for frontend step tracking while tenant training runs.
# # # # This does NOT remove or break your existing /train-agent endpoint.
# # # # Frontend should call /train-agent/start, then poll /train-agent/status/{job_id}.
# # # # ==========================================================
# # # from fastapi import BackgroundTasks

# # # TRAINING_JOBS = {}

# # # TRAINING_STEP_ORDER = [
# # #     "scanning",
# # #     "analyzing",
# # #     "chunking",
# # #     "building_knowledge_base",
# # #     "generating_chat_experience",
# # # ]

# # # TRAINING_STEP_LABELS = {
# # #     "scanning": "Scanning your website / uploaded files",
# # #     "analyzing": "Analyzing your business content",
# # #     "chunking": "Chunking and cleaning knowledge",
# # #     "building_knowledge_base": "Building knowledge base / AI brain",
# # #     "generating_chat_experience": "Generating chat experience",
# # # }


# # # def _new_training_job(job_id: str, tenant_id: int, website_url: str = ""):
# # #     TRAINING_JOBS[job_id] = {
# # #         "job_id": job_id,
# # #         "tenant_id": tenant_id,
# # #         "status": "queued",
# # #         "current_step": "queued",
# # #         "current_step_index": 0,
# # #         "progress": 0,
# # #         "message": "Training queued.",
# # #         "website_url": website_url,
# # #         "steps": [
# # #             {
# # #                 "key": key,
# # #                 "label": TRAINING_STEP_LABELS[key],
# # #                 "status": "pending",
# # #             }
# # #             for key in TRAINING_STEP_ORDER
# # #         ],
# # #         "result": None,
# # #         "error": None,
# # #     }
# # #     return TRAINING_JOBS[job_id]


# # # def _set_training_step(job_id: str, step_key: str, message: str = ""):
# # #     job = TRAINING_JOBS.get(job_id)
# # #     if not job:
# # #         return

# # #     if step_key not in TRAINING_STEP_ORDER:
# # #         return

# # #     step_index = TRAINING_STEP_ORDER.index(step_key)
# # #     total = len(TRAINING_STEP_ORDER)

# # #     for index, item in enumerate(job["steps"]):
# # #         if index < step_index:
# # #             item["status"] = "done"
# # #         elif index == step_index:
# # #             item["status"] = "active"
# # #         else:
# # #             item["status"] = "pending"

# # #     job["status"] = "running"
# # #     job["current_step"] = step_key
# # #     job["current_step_index"] = step_index + 1
# # #     job["progress"] = int((step_index / total) * 100)
# # #     job["message"] = message or TRAINING_STEP_LABELS[step_key]


# # # def _complete_training_job(job_id: str, result: dict):
# # #     job = TRAINING_JOBS.get(job_id)
# # #     if not job:
# # #         return

# # #     for item in job["steps"]:
# # #         item["status"] = "done"

# # #     job["status"] = "completed"
# # #     job["current_step"] = "completed"
# # #     job["current_step_index"] = len(TRAINING_STEP_ORDER)
# # #     job["progress"] = 100
# # #     job["message"] = "Agent trained successfully."
# # #     job["result"] = result
# # #     job["error"] = None

# # #     # Save latest training result so Customize page can show real backend data.
# # #     try:
# # #         _upsert_agent_settings_last_training_summary(job.get("tenant_id"), result)
# # #     except Exception:
# # #         # Never fail the training job only because settings persistence failed.
# # #         pass


# # # def _fail_training_job(job_id: str, error: str):
# # #     job = TRAINING_JOBS.get(job_id)
# # #     if not job:
# # #         return

# # #     for item in job["steps"]:
# # #         if item["status"] == "active":
# # #             item["status"] = "failed"

# # #     job["status"] = "failed"
# # #     job["progress"] = job.get("progress", 0)
# # #     job["message"] = "Training failed."
# # #     job["error"] = error


# # # def _run_training_job(
# # #     job_id: str,
# # #     tenant_id: int,
# # #     website_url: str,
# # #     sitemap_url: str,
# # #     crawl_type: str,
# # #     content_type: str,
# # #     uploaded_files_payload: list,
# # # ):
# # #     """
# # #     Background training runner.
# # #     It mirrors your existing /train-agent logic but updates TRAINING_JOBS after each phase.
# # #     """
# # #     try:
# # #         all_new_chunks = []
# # #         skipped_sources = []
# # #         processed_sources = []
# # #         failed_sources = []
# # #         uploaded_documents_count = 0
# # #         website_documents_count = 0

# # #         existing_website_json = DATA_DIR / "website_data.json"

# # #         if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# # #             raise ValueError(
# # #                 "Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/."
# # #             )

# # #         # 1. Scanning source content
# # #         _set_training_step(job_id, "scanning", "Scanning website, sitemap, and uploaded files...")

# # #         # Existing website_data.json support
# # #         if existing_website_json.exists():
# # #             try:
# # #                 raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# # #                 source_hash = sha256_text(raw_text)
# # #                 source_key = f"tenant::{tenant_id}::website_data.json"

# # #                 if is_done(source_key, source_hash):
# # #                     skipped_sources.append(source_key)
# # #                 else:
# # #                     mark_processing(source_key, source_hash, {"source_type": "website_json"})
# # #                     data = json.loads(raw_text)
# # #                     docs = normalize_website_json(data, content_type="Website")

# # #                     _set_training_step(job_id, "analyzing", "Analyzing website_data.json content...")
# # #                     chunks = docs_to_chunks(docs, source_key=source_key, source_hash=source_hash)
# # #                     save_knowledge_documents(
# # #                         tenant_id=tenant_id,
# # #                         documents=docs,
# # #                         source_key=source_key,
# # #                         source_hash=source_hash,
# # #                         default_source_type="website_json",
# # #                         tags=["website", "training"],
# # #                     )

# # #                     all_new_chunks.extend(chunks)
# # #                     website_documents_count += len(docs)

# # #                     mark_done(
# # #                         source_key,
# # #                         source_hash,
# # #                         len(chunks),
# # #                         {"documents": len(docs), "source_type": "website_json"},
# # #                     )
# # #                     processed_sources.append(source_key)
# # #             except Exception as exc:
# # #                 mark_failed("website_data.json", "unknown", str(exc), {"source_type": "website_json"})
# # #                 failed_sources.append({"source": "website_data.json", "error": str(exc)})

# # #         # Scrape website / sitemap
# # #         if website_url or sitemap_url:
# # #             scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"
# # #             try:
# # #                 _set_training_step(job_id, "scanning", "Scanning website pages...")
# # #                 scraped_documents = scrape_by_request(
# # #                     website_url=website_url,
# # #                     sitemap_url=sitemap_url,
# # #                     crawl_type=crawl_type,
# # #                     content_type=content_type,
# # #                 )

# # #                 raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# # #                 source_hash = sha256_text(raw_scrape_text)

# # #                 if is_done(scrape_key, source_hash):
# # #                     skipped_sources.append(scrape_key)
# # #                 else:
# # #                     mark_processing(scrape_key, source_hash, {"source_type": "scrape"})
# # #                     raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# # #                     save_json(raw_scrape_file, scraped_documents)
# # #                     move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# # #                     _set_training_step(job_id, "analyzing", "Analyzing scanned website content...")
# # #                     chunks = docs_to_chunks(scraped_documents, source_key=scrape_key, source_hash=source_hash)
# # #                     save_knowledge_documents(
# # #                         tenant_id=tenant_id,
# # #                         documents=scraped_documents,
# # #                         source_key=scrape_key,
# # #                         source_hash=source_hash,
# # #                         default_source_type="website",
# # #                         tags=["website", crawl_type, "training"],
# # #                     )

# # #                     all_new_chunks.extend(chunks)
# # #                     website_documents_count += len(scraped_documents)

# # #                     mark_done(
# # #                         scrape_key,
# # #                         source_hash,
# # #                         len(chunks),
# # #                         {"documents": len(scraped_documents), "source_type": "scrape"},
# # #                     )
# # #                     processed_sources.append(scrape_key)
# # #             except Exception as exc:
# # #                 error_file = FAILED_DIR / "scrape_error.txt"
# # #                 error_file.write_text(str(exc), encoding="utf-8")
# # #                 mark_failed(scrape_key, "unknown", str(exc), {"source_type": "scrape"})
# # #                 failed_sources.append({"source": scrape_key, "error": str(exc)})

# # #         # Uploaded files
# # #         for item in uploaded_files_payload:
# # #             original_name = item.get("filename") or "uploaded_file"
# # #             file_name = safe_filename(original_name)
# # #             pending_path = PENDING_UPLOAD_DIR / file_name
# # #             content = item.get("content") or b""
# # #             upload_content_type = item.get("content_type") or content_type

# # #             try:
# # #                 _set_training_step(job_id, "scanning", f"Scanning uploaded file: {original_name}")
# # #                 source_hash = sha256_bytes(content)
# # #                 source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# # #                 if is_done(source_key, source_hash):
# # #                     skipped_sources.append(original_name)
# # #                     continue

# # #                 mark_processing(
# # #                     source_key,
# # #                     source_hash,
# # #                     {"file_name": original_name, "source_type": "file"},
# # #                 )

# # #                 pending_path.write_bytes(content)

# # #                 _set_training_step(job_id, "analyzing", f"Extracting text from: {original_name}")
# # #                 parsed_doc = parse_uploaded_file(
# # #                     file_path=pending_path,
# # #                     original_name=original_name,
# # #                     content_type=upload_content_type,
# # #                 )

# # #                 if parsed_doc and parsed_doc.get("text"):
# # #                     _set_training_step(job_id, "chunking", f"Chunking content from: {original_name}")
# # #                     chunks = docs_to_chunks([parsed_doc], source_key=source_key, source_hash=source_hash)
# # #                     save_knowledge_documents(
# # #                         tenant_id=tenant_id,
# # #                         documents=[parsed_doc],
# # #                         source_key=source_key,
# # #                         source_hash=source_hash,
# # #                         default_source_type="file",
# # #                         tags=["file", "training"],
# # #                     )

# # #                     all_new_chunks.extend(chunks)
# # #                     uploaded_documents_count += 1

# # #                     move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)
# # #                     mark_done(
# # #                         source_key,
# # #                         source_hash,
# # #                         len(chunks),
# # #                         {"file_name": original_name, "source_type": "file"},
# # #                     )
# # #                     processed_sources.append(original_name)
# # #                 else:
# # #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# # #                     mark_failed(
# # #                         source_key,
# # #                         source_hash,
# # #                         "No text extracted",
# # #                         {"file_name": original_name, "source_type": "file"},
# # #                     )
# # #                     failed_sources.append({"source": original_name, "error": "No text extracted"})

# # #             except Exception as exc:
# # #                 if pending_path.exists():
# # #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# # #                 mark_failed(
# # #                     f"file::{file_name}",
# # #                     "unknown",
# # #                     str(exc),
# # #                     {"file_name": original_name, "source_type": "file"},
# # #                 )
# # #                 failed_sources.append({"source": original_name, "error": str(exc)})

# # #         if not all_new_chunks and not skipped_sources:
# # #             raise ValueError("No new text could be extracted from the provided source.")

# # #         # 3. Chunking summary phase
# # #         _set_training_step(job_id, "chunking", "Cleaning and preparing chunks...")

# # #         # 4. Build FAISS / knowledge base
# # #         _set_training_step(job_id, "building_knowledge_base", "Building tenant knowledge base / AI brain...")
# # #         index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# # #         if all_new_chunks:
# # #             save_json(DATA_DIR / f"latest_new_chunks_{tenant_id}.json", all_new_chunks)

# # #         # 5. Generate chat experience
# # #         _set_training_step(job_id, "generating_chat_experience", "Generating chat experience from trained data...")

# # #         result = {
# # #             "success": True,
# # #             "message": "Agent training completed. New content was added and duplicate content was skipped.",
# # #             "content_type": content_type,
# # #             "crawl_type": crawl_type,
# # #             "website_documents": website_documents_count,
# # #             "uploaded_documents": uploaded_documents_count,
# # #             "chunks_created": len(all_new_chunks),
# # #             "processed_sources": processed_sources,
# # #             "skipped_sources": skipped_sources,
# # #             "failed_sources": failed_sources,
# # #             "faiss_index_path": index_info.get("index_path"),
# # #             "metadata_path": index_info.get("metadata_path"),
# # #             "total_vectors": index_info.get("total_vectors"),
# # #         }
# # #         _complete_training_job(job_id, result)

# # #     except Exception as exc:
# # #         _fail_training_job(job_id, str(exc))


# # # @app.post("/train-agent/start")
# # # async def start_train_agent(
# # #     background_tasks: BackgroundTasks,
# # #     website_url: Optional[str] = Form(default=""),
# # #     sitemap_url: Optional[str] = Form(default=""),
# # #     crawl_type: str = Form(default="single_page"),
# # #     content_type: str = Form(default="Mixed Content"),
# # #     files: List[UploadFile] = File(default=[]),
# # #     current_user: dict = Depends(get_current_user),
# # # ):
# # #     """
# # #     Starts training in background and immediately returns a job_id.
# # #     Frontend should poll GET /train-agent/status/{job_id}.
# # #     """
# # #     website_url = (website_url or "").strip()
# # #     sitemap_url = (sitemap_url or "").strip()
# # #     crawl_type = (crawl_type or "single_page").strip()
# # #     content_type = (content_type or "Mixed Content").strip()

# # #     uploaded_files_payload = []
# # #     for upload in files:
# # #         uploaded_files_payload.append(
# # #             {
# # #                 "filename": upload.filename or "uploaded_file",
# # #                 "content_type": upload.content_type or content_type,
# # #                 "content": await upload.read(),
# # #             }
# # #         )

# # #     existing_website_json = DATA_DIR / "website_data.json"
# # #     if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# # #         )

# # #     job_id = str(uuid4())
# # #     tenant_id = current_user["tenant_id"]
# # #     _new_training_job(job_id, tenant_id=tenant_id, website_url=website_url or sitemap_url)

# # #     background_tasks.add_task(
# # #         _run_training_job,
# # #         job_id,
# # #         tenant_id,
# # #         website_url,
# # #         sitemap_url,
# # #         crawl_type,
# # #         content_type,
# # #         uploaded_files_payload,
# # #     )

# # #     return {
# # #         "success": True,
# # #         "job_id": job_id,
# # #         "message": "Training started.",
# # #         "status_url": f"/train-agent/status/{job_id}",
# # #     }


# # # @app.get("/train-agent/status/{job_id}")
# # # def get_train_agent_status(job_id: str, current_user: dict = Depends(get_current_user)):
# # #     job = TRAINING_JOBS.get(job_id)

# # #     if not job:
# # #         raise HTTPException(status_code=404, detail="Training job not found.")

# # #     if int(job.get("tenant_id")) != int(current_user["tenant_id"]):
# # #         raise HTTPException(status_code=403, detail="You cannot access this training job.")

# # #     return job



# # # # ==========================================================
# # # # Tenant Agent Customize / Review Settings API
# # # # Used by frontend ReviewAgentPage.js after training is completed.
# # # # Requires table: tenant_agent_settings
# # # # ==========================================================

# # # class AgentConfigRequest(BaseModel):
# # #     business_name: Optional[str] = None
# # #     industry: Optional[str] = None
# # #     business_type: Optional[str] = None
# # #     business_description: Optional[str] = None
# # #     greeting_message: Optional[str] = None
# # #     starter_questions: Optional[List[str]] = None
# # #     system_prompt: Optional[str] = None
# # #     restriction_rules: Optional[str] = None
# # #     support_hours: Optional[dict] = None


# # # def _json_load(value, default=None):
# # #     if value is None:
# # #         return default
# # #     if isinstance(value, (dict, list)):
# # #         return value
# # #     try:
# # #         return json.loads(value)
# # #     except Exception:
# # #         return default


# # # def _default_starter_questions():
# # #     return [
# # #         "Tell me about your services",
# # #         "What products do you offer?",
# # #         "How can I contact your team?",
# # #         "Do you provide pricing details?",
# # #     ]


# # # def _default_restriction_rules():
# # #     return """- Answer only using trained knowledge base.
# # # - Do not invent prices, offers, phone numbers, addresses, or guarantees.
# # # - If answer is not available, say: I will connect you with our team.
# # # - Keep replies short, clear, and helpful."""


# # # def _default_system_prompt(tenant_name: str = "this business"):
# # #     return f"""You are a helpful business assistant for {tenant_name}.

# # # Your job is to answer customer questions using only the trained knowledge base.
# # # Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""


# # # def _default_greeting(tenant_name: str = ""):
# # #     if tenant_name:
# # #         return f"Welcome to {tenant_name}! How can I help you today?"
# # #     return "Welcome! How can I help you today?"


# # # def _default_support_hours():
# # #     return {
# # #         "opening_time": "09:00 AM",
# # #         "closing_time": "06:00 PM",
# # #         "working_days": "Monday - Saturday",
# # #     }


# # # def _make_default_business_description(tenant_name: str, training_summary: dict = None):
# # #     training_summary = training_summary or {}
# # #     website_documents = training_summary.get("website_documents") or 0
# # #     uploaded_documents = training_summary.get("uploaded_documents") or 0
# # #     chunks_created = training_summary.get("chunks_created") or 0

# # #     if website_documents or uploaded_documents or chunks_created:
# # #         return (
# # #             f"{tenant_name} has trained this AI agent with "
# # #             f"{website_documents} website pages, {uploaded_documents} uploaded documents, "
# # #             f"and {chunks_created} knowledge entries."
# # #         )
# # #     return f"{tenant_name} AI agent is ready to answer questions from the trained knowledge base."


# # # def _get_agent_settings_row(tenant_id: int):
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT *
# # #                 FROM tenant_agent_settings
# # #                 WHERE tenant_id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             return cur.fetchone()
# # #     finally:
# # #         conn.close()


# # # def _get_tenant_row_by_id(tenant_id: int):
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT id, slug, tenant_name, faiss_index_path, plan_name, status
# # #                 FROM tenants
# # #                 WHERE id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             return cur.fetchone()
# # #     finally:
# # #         conn.close()


# # # def _upsert_agent_settings_last_training_summary(tenant_id: int, result: dict):
# # #     if not tenant_id:
# # #         return

# # #     summary_json = json.dumps(result or {}, ensure_ascii=False)
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 INSERT INTO tenant_agent_settings
# # #                     (tenant_id, last_training_summary)
# # #                 VALUES
# # #                     (%s, CAST(%s AS JSON))
# # #                 ON DUPLICATE KEY UPDATE
# # #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# # #                     updated_at = NOW()
# # #                 """,
# # #                 (tenant_id, summary_json),
# # #             )
# # #     finally:
# # #         conn.close()


# # # def _normalize_agent_config(tenant: dict, row: dict = None):
# # #     row = row or {}
# # #     tenant_name = tenant.get("tenant_name") or "Your Business"
# # #     training_summary = _json_load(row.get("last_training_summary"), default={}) or {}

# # #     business_name = row.get("business_name") or tenant_name
# # #     industry = row.get("industry") or "General Business"
# # #     business_type = row.get("business_type") or "Business"
# # #     business_description = row.get("business_description") or _make_default_business_description(
# # #         business_name,
# # #         training_summary,
# # #     )

# # #     greeting_message = row.get("greeting_message") or _default_greeting(business_name)
# # #     starter_questions = _json_load(row.get("starter_questions"), default=None) or _default_starter_questions()
# # #     system_prompt = row.get("system_prompt") or _default_system_prompt(business_name)
# # #     restriction_rules = row.get("restriction_rules") or _default_restriction_rules()
# # #     support_hours = _json_load(row.get("support_hours"), default=None) or _default_support_hours()

# # #     return {
# # #         "tenant": {
# # #             "id": tenant.get("id"),
# # #             "slug": tenant.get("slug"),
# # #             "tenant_name": tenant_name,
# # #             "plan_name": tenant.get("plan_name"),
# # #             "status": tenant.get("status"),
# # #         },
# # #         "business": {
# # #             "name": business_name,
# # #             "industry": industry,
# # #             "type": business_type,
# # #             "description": business_description,
# # #         },
# # #         "training_summary": training_summary,
# # #         "knowledge_base": {
# # #             "entries": training_summary.get("chunks_created") or training_summary.get("total_vectors") or 0,
# # #             "website_documents": training_summary.get("website_documents") or 0,
# # #             "uploaded_documents": training_summary.get("uploaded_documents") or 0,
# # #             "processed_sources": training_summary.get("processed_sources") or [],
# # #             "skipped_sources": training_summary.get("skipped_sources") or [],
# # #             "failed_sources": training_summary.get("failed_sources") or [],
# # #             "total_vectors": training_summary.get("total_vectors") or 0,
# # #         },
# # #         "chat_experience": {
# # #             "greeting_message": greeting_message,
# # #             "starter_questions": starter_questions,
# # #         },
# # #         "behavior": {
# # #             "system_prompt": system_prompt,
# # #             "restriction_rules": restriction_rules,
# # #         },
# # #         "support_hours": support_hours,
# # #     }


# # # @app.get("/agent-config")
# # # def get_agent_config(current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     tenant = _get_tenant_row_by_id(tenant_id)

# # #     if not tenant:
# # #         raise HTTPException(status_code=404, detail="Tenant not found.")

# # #     row = _get_agent_settings_row(tenant_id)
# # #     return {
# # #         "success": True,
# # #         "config": _normalize_agent_config(tenant, row),
# # #     }


# # # @app.post("/agent-config")
# # # def save_agent_config(req: AgentConfigRequest, current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     tenant = _get_tenant_row_by_id(tenant_id)

# # #     if not tenant:
# # #         raise HTTPException(status_code=404, detail="Tenant not found.")

# # #     row = _get_agent_settings_row(tenant_id)
# # #     current_config = _normalize_agent_config(tenant, row)

# # #     business_name = (req.business_name or current_config["business"]["name"] or tenant.get("tenant_name") or "").strip()
# # #     industry = (req.industry or current_config["business"]["industry"] or "General Business").strip()
# # #     business_type = (req.business_type or current_config["business"]["type"] or "Business").strip()
# # #     business_description = (req.business_description or current_config["business"]["description"] or "").strip()
# # #     greeting_message = (req.greeting_message or _default_greeting(business_name)).strip()

# # #     starter_questions = req.starter_questions or current_config["chat_experience"]["starter_questions"] or _default_starter_questions()
# # #     starter_questions = [str(q).strip() for q in starter_questions if str(q).strip()][:8]
# # #     if not starter_questions:
# # #         starter_questions = _default_starter_questions()

# # #     system_prompt = (req.system_prompt or _default_system_prompt(business_name)).strip()
# # #     restriction_rules = (req.restriction_rules or _default_restriction_rules()).strip()
# # #     support_hours = req.support_hours or current_config.get("support_hours") or _default_support_hours()
# # #     last_training_summary = current_config.get("training_summary") or {}

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 INSERT INTO tenant_agent_settings
# # #                     (tenant_id, business_name, industry, business_type, business_description,
# # #                      greeting_message, starter_questions, system_prompt, restriction_rules,
# # #                      support_hours, last_training_summary)
# # #                 VALUES
# # #                     (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s, CAST(%s AS JSON), CAST(%s AS JSON))
# # #                 ON DUPLICATE KEY UPDATE
# # #                     business_name = VALUES(business_name),
# # #                     industry = VALUES(industry),
# # #                     business_type = VALUES(business_type),
# # #                     business_description = VALUES(business_description),
# # #                     greeting_message = VALUES(greeting_message),
# # #                     starter_questions = CAST(VALUES(starter_questions) AS JSON),
# # #                     system_prompt = VALUES(system_prompt),
# # #                     restriction_rules = VALUES(restriction_rules),
# # #                     support_hours = CAST(VALUES(support_hours) AS JSON),
# # #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# # #                     updated_at = NOW()
# # #                 """,
# # #                 (
# # #                     tenant_id,
# # #                     business_name,
# # #                     industry,
# # #                     business_type,
# # #                     business_description,
# # #                     greeting_message,
# # #                     json.dumps(starter_questions, ensure_ascii=False),
# # #                     system_prompt,
# # #                     restriction_rules,
# # #                     json.dumps(support_hours, ensure_ascii=False),
# # #                     json.dumps(last_training_summary, ensure_ascii=False),
# # #                 ),
# # #             )

# # #             cur.execute(
# # #                 """
# # #                 UPDATE tenant_users
# # #                 SET name = %s,
# # #                     industry = %s,
# # #                     type = %s,
# # #                     updated_at = NOW()
# # #                 WHERE id = %s
# # #                   AND tenant_id = %s
# # #                 """,
# # #                 (
# # #                     business_name,
# # #                     industry,
# # #                     business_type,
# # #                     current_user.get("user_id") or current_user.get("id"),
# # #                     tenant_id,
# # #                 ),
# # #             )
# # #     finally:
# # #         conn.close()

# # #     row = _get_agent_settings_row(tenant_id)
# # #     return {
# # #         "success": True,
# # #         "message": "Agent settings saved successfully.",
# # #         "config": _normalize_agent_config(tenant, row),
# # #     }


# # # # ==========================================================
# # # # WhatsApp Connection + Auto Reply APIs
# # # # Supports both Meta WhatsApp Cloud API and Twilio WhatsApp.
# # # # ==========================================================

# # # class WhatsAppConnectRequest(BaseModel):
# # #     provider: str
# # #     meta_access_token: Optional[str] = None
# # #     meta_phone_number_id: Optional[str] = None
# # #     meta_business_account_id: Optional[str] = None
# # #     twilio_account_sid: Optional[str] = None
# # #     twilio_auth_token: Optional[str] = None
# # #     twilio_phone_number: Optional[str] = None
# # #     whatsapp_number: Optional[str] = None
# # #     whatsapp_verify_token: Optional[str] = None


# # # class SendWhatsAppTextRequest(BaseModel):
# # #     to_phone: str
# # #     message: str


# # # class SendWhatsAppMediaRequest(BaseModel):
# # #     to_phone: str
# # #     media_url: str
# # #     caption: Optional[str] = ""


# # # @app.get("/connect-whatsapp")
# # # def get_whatsapp_connection(current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT whatsapp_provider, meta_phone_number_id, meta_business_account_id,
# # #                        twilio_phone_number, whatsapp_number, whatsapp_verify_token,
# # #                        CASE WHEN meta_access_token IS NULL OR meta_access_token='' THEN 0 ELSE 1 END AS has_meta_access_token,
# # #                        CASE WHEN twilio_account_sid IS NULL OR twilio_account_sid='' THEN 0 ELSE 1 END AS has_twilio_account_sid,
# # #                        CASE WHEN twilio_auth_token IS NULL OR twilio_auth_token='' THEN 0 ELSE 1 END AS has_twilio_auth_token
# # #                 FROM tenants
# # #                 WHERE id=%s
# # #                 LIMIT 1
# # #                 """,
# # #                 (tenant_id,),
# # #             )
# # #             row = cur.fetchone() or {}
# # #     finally:
# # #         conn.close()

# # #     return {"success": True, "config": row}


# # # @app.post("/connect-whatsapp")
# # # def save_whatsapp_connection(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]
# # #     provider = (req.provider or "").strip().lower()

# # #     if provider not in ["meta", "twilio"]:
# # #         raise HTTPException(status_code=400, detail="Provider must be meta or twilio.")

# # #     meta_access_token = (req.meta_access_token or "").strip() or None
# # #     meta_phone_number_id = (req.meta_phone_number_id or "").strip() or None
# # #     meta_business_account_id = (req.meta_business_account_id or "").strip() or None
# # #     twilio_account_sid = (req.twilio_account_sid or "").strip() or None
# # #     twilio_auth_token = (req.twilio_auth_token or "").strip() or None
# # #     twilio_phone_number = normalize_phone(req.twilio_phone_number or "") or None
# # #     whatsapp_number = normalize_phone(req.whatsapp_number or "") or None
# # #     whatsapp_verify_token = (req.whatsapp_verify_token or "").strip() or None

# # #     if provider == "meta" and not meta_phone_number_id:
# # #         raise HTTPException(status_code=400, detail="Meta phone number ID is required.")

# # #     if provider == "twilio":
# # #         if not twilio_account_sid or not twilio_auth_token:
# # #             raise HTTPException(
# # #                 status_code=400,
# # #                 detail="Twilio Account SID and Auth Token are required.",
# # #             )

# # #         if not twilio_phone_number and whatsapp_number:
# # #             twilio_phone_number = whatsapp_number

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 UPDATE tenants
# # #                 SET whatsapp_provider=%s,
# # #                     meta_access_token=COALESCE(%s, meta_access_token),
# # #                     meta_phone_number_id=%s,
# # #                     meta_business_account_id=%s,
# # #                     twilio_account_sid=COALESCE(%s, twilio_account_sid),
# # #                     twilio_auth_token=COALESCE(%s, twilio_auth_token),
# # #                     twilio_phone_number=%s,
# # #                     whatsapp_number=%s,
# # #                     whatsapp_verify_token=%s,
# # #                     updated_at=NOW()
# # #                 WHERE id=%s
# # #                 """,
# # #                 (
# # #                     provider,
# # #                     meta_access_token,
# # #                     meta_phone_number_id,
# # #                     meta_business_account_id,
# # #                     twilio_account_sid,
# # #                     twilio_auth_token,
# # #                     twilio_phone_number,
# # #                     whatsapp_number,
# # #                     whatsapp_verify_token,
# # #                     tenant_id,
# # #                 ),
# # #             )
# # #     finally:
# # #         conn.close()

# # #     return {"success": True, "message": "WhatsApp connection saved successfully.", "provider": provider}




# # # @app.get("/tenant/whatsapp-config")
# # # def tenant_whatsapp_config(current_user: dict = Depends(get_current_user)):
# # #     return get_whatsapp_connection(current_user)

# # # @app.post("/tenant/active-agent-type")
# # # def update_active_agent_type(
# # #     req: ActiveAgentTypeRequest,
# # #     current_user: dict = Depends(get_current_user),
# # # ):
# # #     agent_type = (req.active_agent_type or "").strip().lower()

# # #     if agent_type not in ["chat", "product"]:
# # #         raise HTTPException(
# # #             status_code=400,
# # #             detail="active_agent_type must be chat or product.",
# # #         )

# # #     tenant_id = current_user["tenant_id"]

# # #     conn = get_main_db_connection()
# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 UPDATE tenants
# # #                 SET active_agent_type=%s,
# # #                     updated_at=NOW()
# # #                 WHERE id=%s
# # #                 """,
# # #                 (agent_type, tenant_id),
# # #             )
# # #     finally:
# # #         conn.close()

# # #     return {
# # #         "success": True,
# # #         "active_agent_type": agent_type,
# # #         "agent_type": agent_type,
# # #     }


# # # @app.get("/tenant/active-agent-type/{tenant_slug}")
# # # def get_active_agent_type_public(tenant_slug: str):
# # #     tenant = get_tenant_by_slug(tenant_slug)

# # #     if not tenant:
# # #         raise HTTPException(status_code=404, detail="Tenant not found")

# # #     active_agent_type = tenant.get("active_agent_type") or "chat"

# # #     return {
# # #         "success": True,
# # #         "tenant_slug": tenant["slug"],
# # #         "active_agent_type": active_agent_type,
# # #         "agent_type": active_agent_type,
# # #     }

# # # @app.post("/tenant/whatsapp-config")
# # # def tenant_save_whatsapp_config(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# # #     return save_whatsapp_connection(req, current_user)

# # # @app.post("/send-whatsapp-message")
# # # def send_whatsapp_message(req: SendWhatsAppTextRequest, current_user: dict = Depends(get_current_user)):
# # #     if not req.to_phone or not req.message:
# # #         raise HTTPException(status_code=400, detail="to_phone and message are required.")
# # #     return send_whatsapp_text(current_user["tenant_id"], req.to_phone, req.message)


# # # @app.post("/send-whatsapp-media")
# # # def send_whatsapp_media_message(req: SendWhatsAppMediaRequest, current_user: dict = Depends(get_current_user)):
# # #     if not req.to_phone or not req.media_url:
# # #         raise HTTPException(status_code=400, detail="to_phone and media_url are required.")
# # #     return send_whatsapp_media(current_user["tenant_id"], req.to_phone, req.media_url, req.caption or "")


# # # @app.get("/webhook/whatsapp/{tenant_slug}")
# # # @app.get("/webhooks/whatsapp/{tenant_slug}")
# # # def verify_meta_webhook(tenant_slug: str, request: Request):
# # #     # Meta webhook verification: hub.mode, hub.verify_token, hub.challenge
# # #     mode = request.query_params.get("hub.mode")
# # #     verify_token = request.query_params.get("hub.verify_token")
# # #     challenge = request.query_params.get("hub.challenge")

# # #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# # #     expected_token = tenant.get("whatsapp_verify_token") or "agentive_verify_token_123"

# # #     if mode == "subscribe" and verify_token == expected_token:
# # #         return Response(content=str(challenge), media_type="text/plain")

# # #     raise HTTPException(status_code=403, detail="Webhook verification failed.")


# # # @app.post("/webhook/whatsapp/{tenant_slug}")
# # # @app.post("/webhooks/whatsapp/{tenant_slug}")
# # # async def whatsapp_webhook(tenant_slug: str, request: Request):
# # #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# # #     provider = tenant.get("whatsapp_provider")

# # #     # Twilio sends form-urlencoded data. Meta sends JSON.
# # #     content_type = request.headers.get("content-type", "")

# # #     if provider == "twilio" or "application/x-www-form-urlencoded" in content_type:
# # #         form = await request.form()
# # #         customer_phone = str(form.get("From") or "").replace("whatsapp:", "")
# # #         incoming_message = str(form.get("Body") or "").strip()

# # #         if not customer_phone or not incoming_message:
# # #             return {"success": True, "message": "No text message to process."}

# # #         return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # #     data = await request.json()

# # #     try:
# # #         entry = (data.get("entry") or [])[0]
# # #         change = (entry.get("changes") or [])[0]
# # #         value = change.get("value") or {}
# # #         message_obj = (value.get("messages") or [])[0]
# # #         customer_phone = message_obj.get("from")
# # #         incoming_message = (message_obj.get("text") or {}).get("body", "").strip()
# # #     except Exception:
# # #         return {"success": True, "message": "No supported Meta message to process."}

# # #     if not customer_phone or not incoming_message:
# # #         return {"success": True, "message": "No text message to process."}

# # #     return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # # # ==========================================================
# # # # Contacts API
# # # # Must stay ABOVE React fallback route
# # # # ==========================================================
# # # @app.get("/api/contacts")
# # # def get_contacts(current_user: dict = Depends(get_current_user)):
# # #     tenant_id = current_user["tenant_id"]

# # #     conn = get_main_db_connection()

# # #     try:
# # #         with conn.cursor() as cur:
# # #             cur.execute(
# # #                 """
# # #                 SELECT
# # #                     id,
# # #                     tenant_id,
# # #                     session_id,
# # #                     name,
# # #                     email,
# # #                     phone,
# # #                     first_message,
# # #                     last_message,
# # #                     source,
# # #                     status,
# # #                     user_agent,
# # #                     ip_address,
# # #                     created_at,
# # #                     updated_at,
# # #                     last_seen_at
# # #                 FROM tenant_customers
# # #                 WHERE tenant_id=%s
# # #                 ORDER BY
# # #                     last_seen_at DESC,
# # #                     created_at DESC
# # #                 """,
# # #                 (tenant_id,),
# # #             )

# # #             contacts = cur.fetchall() or []

# # #     finally:
# # #         conn.close()

# # #     return {
# # #         "success": True,
# # #         "total": len(contacts),
# # #         "contacts": contacts,
# # #     }

# # # # ==========================================================
# # # # Clean Public URL + React Frontend Route Fallback
# # # # KEEP THESE AT THE VERY BOTTOM OF main.py
# # # # ==========================================================

# # # # @app.get("/public-link/resolve/{public_name}")
# # # # def resolve_public_link(public_name: str):
# # # #     resolved = _resolve_public_name(public_name)

# # # #     if not resolved:
# # # #         raise HTTPException(status_code=404, detail="Public link not found.")

# # # #     return {
# # # #         "success": True,
# # # #         "tenant_slug": resolved["tenant_slug"],
# # # #         "target_path": resolved["target_path"],
# # # #     } 

# # # @app.get("/public-link/resolve/{public_name}")
# # # def resolve_public_link(public_name: str):
# # #     resolved = _resolve_public_name(public_name)

# # #     if not resolved:
# # #         raise HTTPException(status_code=404, detail="Public link not found.")

# # #     return {
# # #         "success": True,
# # #         "tenant_slug": resolved["tenant_slug"],
# # #         "target_path": resolved["target_path"],
# # #         "agent_type": resolved.get("active_agent_type") or "chat",
# # #         "active_agent_type": resolved.get("active_agent_type") or "chat",
# # #     }



# # # # @app.get("/{public_name}")
# # # # def open_clean_public_chat_url(public_name: str):
# # # #     resolved = _resolve_public_name(public_name)
# # # #     index_path = os.path.join(BUILD_DIR, "index.html")

# # # #     if resolved:
# # # #         if os.path.exists(index_path):
# # # #             return FileResponse(index_path)

# # # #         raise HTTPException(
# # # #             status_code=404,
# # # #             detail="React build index.html not found"
# # # #         )

# # # #     # IMPORTANT:
# # # #     # if not a valid public link,
# # # #     # do NOT return index here
# # # #     raise HTTPException(status_code=404, detail="Page not found")



# # # if os.path.exists(BUILD_DIR):

# # #     @app.get("/{full_path:path}")
# # #     def serve_react_routes(full_path: str):
# # #         index_path = os.path.join(BUILD_DIR, "index.html")

# # #         if os.path.exists(index_path):
# # #             return FileResponse(index_path)

# # #         raise HTTPException(status_code=404, detail="React build index.html not found")

# # from fastapi.staticfiles import StaticFiles
# # from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
# # from app.auth import router as auth_router, get_current_user
# # from fastapi import Depends
# # from dotenv import load_dotenv
# # load_dotenv()
# # import json
# # import os
# # import re
# # import secrets
# # import string
# # from typing import List, Optional
# # from uuid import uuid4

# # from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
# # from fastapi.middleware.cors import CORSMiddleware
# # from pydantic import BaseModel

# # from app.chatbot import chat_with_agent
# # from app.db import get_main_db_connection
# # from app.file_parser import parse_uploaded_file
# # from app.index_builder import add_chunks_to_faiss
# # from app.integration import router as integration_router
# # from app.product_query_bot import router as product_query_router, process_product_chat
# # from app.knowledge_store import (
# #     get_combined_training_path,
# #     get_entry_text_path,
# #     get_knowledge_entry,
# #     list_knowledge_entries,
# #     save_knowledge_documents,
# # )
# # from app.whatsapp import (
# #     get_tenant_whatsapp_config,
# #     handle_incoming_text_and_reply,
# #     normalize_phone,
# #     send_whatsapp_media,
# #     send_whatsapp_text,
# # )
# # from app.scraper import scrape_by_request
# # from app.training_registry import (
# #     docs_to_chunks,
# #     is_done,
# #     mark_done,
# #     mark_failed,
# #     mark_processing,
# #     normalize_website_json,
# #     sha256_bytes,
# #     sha256_text,
# # )
# # from app.utils import (
# #     DATA_DIR,
# #     DONE_SCRAPED_DIR,
# #     DONE_UPLOAD_DIR,
# #     FAILED_DIR,
# #     PENDING_SCRAPED_DIR,
# #     PENDING_UPLOAD_DIR,
# #     safe_filename,
# #     save_json,
# #     move_file_safely,
# # )

# # app = FastAPI(title="Agent Training + WhatsApp Chat Backend", version="2.1.0")

# # # Railway / production friendly CORS.
# # # Set CORS_ORIGINS in Railway like:
# # # CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com
# # _raw_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
# # _cors_origins = ["*"] if _raw_cors_origins == "*" else [origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()]

# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=_cors_origins,
# #     allow_credentials=True,
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )

# # app.include_router(auth_router)
# # app.include_router(integration_router)
# # app.include_router(product_query_router)

# # class ChatRequest(BaseModel):
# #     message: str
# #     session_id: Optional[str] = None
# #     top_k: Optional[int] = 2


# # class PublicChatRequest(BaseModel):
# #     message: str
# #     session_id: Optional[str] = None
# #     top_k: Optional[int] = 2
# #     customer_name: Optional[str] = None
# #     customer_email: Optional[str] = None
# #     customer_phone: Optional[str] = None


# # class PublicLinkUpdateRequest(BaseModel):
# #     sweet_name: Optional[str] = None


# # class ActiveAgentTypeRequest(BaseModel):
# #     active_agent_type: str


# # def get_tenant_by_slug(tenant_slug: str):
# #     tenant_slug = (tenant_slug or "").strip()
# #     if not tenant_slug:
# #         return None
    
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT id, slug, tenant_name, status, active_agent_type
# #                 FROM tenants
# #                 WHERE slug=%s AND status='active'
# #                 LIMIT 1
                
# #                 """,
# #                 (tenant_slug,),
# #             )
# #             return cur.fetchone()
# #     finally:
# #         conn.close()


# # def upsert_tenant_customer(
# #     tenant_id: int,
# #     session_id: str,
# #     name: str = None,
# #     email: str = None,
# #     phone: str = None,
# #     message: str = None,
# #     request: Request = None,
# # ):
# #     name = (name or "").strip() or None
# #     email = (email or "").strip().lower() or None
# #     phone = (phone or "").strip() or None
# #     message = (message or "").strip() or None

# #     user_agent = None
# #     ip_address = None

# #     if request is not None:
# #         user_agent = request.headers.get("user-agent")
# #         if request.client:
# #             ip_address = request.client.host

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 INSERT INTO tenant_customers
# #                     (tenant_id, session_id, name, email, phone, first_message, last_message,
# #                      source, status, user_agent, ip_address, last_seen_at)
# #                 VALUES
# #                     (%s, %s, %s, %s, %s, %s, %s, 'public_chat', 'active', %s, %s, NOW())
# #                 ON DUPLICATE KEY UPDATE
# #                     name = COALESCE(VALUES(name), name),
# #                     email = COALESCE(VALUES(email), email),
# #                     phone = COALESCE(VALUES(phone), phone),
# #                     first_message = COALESCE(first_message, VALUES(first_message)),
# #                     last_message = VALUES(last_message),
# #                     user_agent = COALESCE(VALUES(user_agent), user_agent),
# #                     ip_address = COALESCE(VALUES(ip_address), ip_address),
# #                     status = IF(status='new', 'active', status),
# #                     last_seen_at = NOW(),
# #                     updated_at = NOW()
# #                 """,
# #                 (
# #                     tenant_id,
# #                     session_id,
# #                     name,
# #                     email,
# #                     phone,
# #                     message,
# #                     message,
# #                     user_agent,
# #                     ip_address,
# #                 ),
# #             )

# #             cur.execute(
# #                 """
# #                 SELECT id, tenant_id, session_id, name, email, phone, status
# #                 FROM tenant_customers
# #                 WHERE tenant_id=%s AND session_id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id, session_id),
# #             )
# #             return cur.fetchone()
# #     finally:
# #         conn.close()


# # # ==========================================================
# # # Serve React Frontend on Railway
# # # Required folder structure:
# # # backend/
# # #   main.py
# # #   build/
# # #     index.html
# # #     static/
# # # ==========================================================
# # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # BUILD_DIR = os.path.join(BASE_DIR, "build")
# # STATIC_DIR = os.path.join(BUILD_DIR, "static")

# # if os.path.exists(STATIC_DIR):
# #     app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# # @app.get("/")
# # def serve_react_app():
# #     index_path = os.path.join(BUILD_DIR, "index.html")

# #     if os.path.exists(index_path):
# #         return FileResponse(index_path)

# #     return {
# #         "status": "ok",
# #         "message": "Backend running, but React build/index.html was not found.",
# #         "required_folder": "Place React build folder beside main.py as ./build",
# #         "training_endpoint": "/train-agent",
# #         "protected_chat_endpoint": "/chat",
# #         "public_chat_endpoint": "/chat/{tenant_slug} or /chat_{tenant_slug}",
# #     }

# # # ==========================================================
# # # Knowledge Base readable text APIs
# # # These APIs let a tenant user see/download the exact text that was extracted
# # # and sent for FAISS training.
# # # ==========================================================
# # @app.get("/knowledge")
# # def get_knowledge_entries(search: Optional[str] = "", current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     entries = list_knowledge_entries(tenant_id, search=search or "")
# #     return {
# #         "success": True,
# #         "count": len(entries),
# #         "entries": entries,
# #     }


# # @app.get("/knowledge/download")
# # def download_all_knowledge(current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     path = get_combined_training_path(tenant_id)
# #     if not path.exists():
# #         raise HTTPException(status_code=404, detail="No knowledge text found for this tenant.")
# #     return FileResponse(
# #         str(path),
# #         media_type="text/plain",
# #         filename=f"tenant_{tenant_id}_all_training_data.txt",
# #     )


# # @app.get("/knowledge/{entry_id}")
# # def get_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     entry = get_knowledge_entry(tenant_id, entry_id)
# #     if not entry:
# #         raise HTTPException(status_code=404, detail="Knowledge entry not found.")
# #     return {"success": True, "entry": entry}


# # @app.get("/knowledge/{entry_id}/download")
# # def download_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     entry = get_knowledge_entry(tenant_id, entry_id)
# #     path = get_entry_text_path(tenant_id, entry_id)
# #     if not entry or not path:
# #         raise HTTPException(status_code=404, detail="Knowledge text file not found.")
# #     safe_title = safe_filename(entry.get("title") or entry_id)
# #     return FileResponse(
# #         str(path),
# #         media_type="text/plain",
# #         filename=f"{safe_title}.txt",
# #     )


# # # @app.post("/train-agent")
# # # async def train_agent(
# # #     website_url: Optional[str] = Form(default=""),
# # #     sitemap_url: Optional[str] = Form(default=""),
# # #     crawl_type: str = Form(default="single_page"),
# # #     content_type: str = Form(default="Mixed Content"),
# # #     files: List[UploadFile] = File(default=[]),
# # # ):
# # @app.post("/train-agent")
# # async def train_agent(
# #     website_url: Optional[str] = Form(default=""),
# #     sitemap_url: Optional[str] = Form(default=""),
# #     crawl_type: str = Form(default="single_page"),
# #     content_type: str = Form(default="Mixed Content"),
# #     files: List[UploadFile] = File(default=[]),
# #     current_user: dict = Depends(get_current_user),
# # ):
# #     website_url = (website_url or "").strip()
# #     sitemap_url = (sitemap_url or "").strip()
# #     crawl_type = (crawl_type or "single_page").strip()
# #     content_type = (content_type or "Mixed Content").strip()
# #     tenant_id = current_user["tenant_id"]

# #     existing_website_json = DATA_DIR / "website_data.json"

# #     if not website_url and not sitemap_url and not files and not existing_website_json.exists():
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# #         )

# #     all_new_chunks = []
# #     skipped_sources = []
# #     processed_sources = []
# #     failed_sources = []
# #     uploaded_documents_count = 0
# #     website_documents_count = 0

# #     # 1. Existing data/website_data.json support
# #     if existing_website_json.exists():
# #         try:
# #             raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# #             source_hash = sha256_text(raw_text)
# #             source_key = f"tenant::{tenant_id}::website_data.json"

# #             if is_done(source_key, source_hash):
# #                 skipped_sources.append(source_key)
# #             else:
# #                 mark_processing(source_key, source_hash, {"source_type": "website_json"})

# #                 data = json.loads(raw_text)
# #                 docs = normalize_website_json(data, content_type="Website")
# #                 chunks = docs_to_chunks(
# #                     docs,
# #                     source_key=source_key,
# #                     source_hash=source_hash,
# #                 )
# #                 save_knowledge_documents(
# #                     tenant_id=tenant_id,
# #                     documents=docs,
# #                     source_key=source_key,
# #                     source_hash=source_hash,
# #                     default_source_type="website_json",
# #                     tags=["website", "training"],
# #                 )

# #                 all_new_chunks.extend(chunks)
# #                 website_documents_count += len(docs)

# #                 mark_done(
# #                     source_key,
# #                     source_hash,
# #                     len(chunks),
# #                     {
# #                         "documents": len(docs),
# #                         "source_type": "website_json",
# #                     },
# #                 )

# #                 processed_sources.append(source_key)

# #         except Exception as exc:
# #             mark_failed(
# #                 "website_data.json",
# #                 "unknown",
# #                 str(exc),
# #                 {"source_type": "website_json"},
# #             )
# #             failed_sources.append({
# #                 "source": "website_data.json",
# #                 "error": str(exc),
# #             })

# #     # 2. Scrape website / sitemap
# #     if website_url or sitemap_url:
# #         scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"

# #         try:
# #             scraped_documents = scrape_by_request(
# #                 website_url=website_url,
# #                 sitemap_url=sitemap_url,
# #                 crawl_type=crawl_type,
# #                 content_type=content_type,
# #             )

# #             raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# #             source_hash = sha256_text(raw_scrape_text)

# #             if is_done(scrape_key, source_hash):
# #                 skipped_sources.append(scrape_key)
# #             else:
# #                 mark_processing(scrape_key, source_hash, {"source_type": "scrape"})

# #                 raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# #                 save_json(raw_scrape_file, scraped_documents)
# #                 move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# #                 chunks = docs_to_chunks(
# #                     scraped_documents,
# #                     source_key=scrape_key,
# #                     source_hash=source_hash,
# #                 )
# #                 save_knowledge_documents(
# #                     tenant_id=tenant_id,
# #                     documents=scraped_documents,
# #                     source_key=scrape_key,
# #                     source_hash=source_hash,
# #                     default_source_type="website",
# #                     tags=["website", crawl_type, "training"],
# #                 )

# #                 all_new_chunks.extend(chunks)
# #                 website_documents_count += len(scraped_documents)

# #                 mark_done(
# #                     scrape_key,
# #                     source_hash,
# #                     len(chunks),
# #                     {
# #                         "documents": len(scraped_documents),
# #                         "source_type": "scrape",
# #                     },
# #                 )

# #                 processed_sources.append(scrape_key)

# #         except Exception as exc:
# #             error_file = FAILED_DIR / "scrape_error.txt"
# #             error_file.write_text(str(exc), encoding="utf-8")

# #             mark_failed(
# #                 scrape_key,
# #                 "unknown",
# #                 str(exc),
# #                 {"source_type": "scrape"},
# #             )

# #             failed_sources.append({
# #                 "source": scrape_key,
# #                 "error": str(exc),
# #             })

# #     # 3. Uploaded files
# #     for upload in files:
# #         original_name = upload.filename or "uploaded_file"
# #         file_name = safe_filename(original_name)
# #         pending_path = PENDING_UPLOAD_DIR / file_name

# #         try:
# #             content = await upload.read()
# #             source_hash = sha256_bytes(content)
# #             source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# #             if is_done(source_key, source_hash):
# #                 skipped_sources.append(original_name)
# #                 continue

# #             mark_processing(
# #                 source_key,
# #                 source_hash,
# #                 {
# #                     "file_name": original_name,
# #                     "source_type": "file",
# #                 },
# #             )

# #             pending_path.write_bytes(content)

# #             parsed_doc = parse_uploaded_file(
# #                 file_path=pending_path,
# #                 original_name=original_name,
# #                 content_type=content_type,
# #             )

# #             if parsed_doc and parsed_doc.get("text"):
# #                 chunks = docs_to_chunks(
# #                     [parsed_doc],
# #                     source_key=source_key,
# #                     source_hash=source_hash,
# #                 )
# #                 save_knowledge_documents(
# #                     tenant_id=tenant_id,
# #                     documents=[parsed_doc],
# #                     source_key=source_key,
# #                     source_hash=source_hash,
# #                     default_source_type="file",
# #                     tags=["file", "training"],
# #                 )

# #                 all_new_chunks.extend(chunks)
# #                 uploaded_documents_count += 1

# #                 move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)

# #                 mark_done(
# #                     source_key,
# #                     source_hash,
# #                     len(chunks),
# #                     {
# #                         "file_name": original_name,
# #                         "source_type": "file",
# #                     },
# #                 )

# #                 processed_sources.append(original_name)

# #             else:
# #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# #                 mark_failed(
# #                     source_key,
# #                     source_hash,
# #                     "No text extracted",
# #                     {
# #                         "file_name": original_name,
# #                         "source_type": "file",
# #                     },
# #                 )

# #                 failed_sources.append({
# #                     "source": original_name,
# #                     "error": "No text extracted",
# #                 })

# #         except Exception as exc:
# #             if pending_path.exists():
# #                 move_file_safely(pending_path, FAILED_DIR / file_name)

# #             mark_failed(
# #                 f"file::{file_name}",
# #                 "unknown",
# #                 str(exc),
# #                 {
# #                     "file_name": original_name,
# #                     "source_type": "file",
# #                 },
# #             )

# #             failed_sources.append({
# #                 "source": original_name,
# #                 "error": str(exc),
# #             })

# #     if not all_new_chunks and not skipped_sources:
# #         raise HTTPException(
# #             status_code=400,
# #             detail="No new text could be extracted from the provided source.",
# #         )

# #     index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# #     if all_new_chunks:
# #         save_json(DATA_DIR / "latest_new_chunks.json", all_new_chunks)

# #     return {
# #         "success": True,
# #         "message": "Agent training completed. New content was added and duplicate content was skipped.",
# #         "content_type": content_type,
# #         "crawl_type": crawl_type,
# #         "website_documents": website_documents_count,
# #         "uploaded_documents": uploaded_documents_count,
# #         "chunks_created": len(all_new_chunks),
# #         "processed_sources": processed_sources,
# #         "skipped_sources": skipped_sources,
# #         "failed_sources": failed_sources,
# #         "faiss_index_path": index_info.get("index_path"),
# #         "metadata_path": index_info.get("metadata_path"),
# #         "total_vectors": index_info.get("total_vectors"),
# #     }


# # @app.post("/chat")
# # def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
# #     message = (request.message or "").strip()

# #     if not message:
# #         raise HTTPException(status_code=400, detail="Message is required.")

# #     session_id = request.session_id or str(uuid4())

# #     try:
# #         return chat_with_agent(
# #             session_id=session_id,
# #             message=message,
# #             tenant_id=current_user["tenant_id"],
# #             top_k=request.top_k or 2,
# #         )

# #     except FileNotFoundError:
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Please train the agent first. FAISS index is missing.",
# #         )

# #     except Exception as exc:
# #         raise HTTPException(status_code=500, detail=str(exc))

# # def _public_chat_response(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# #     tenant = get_tenant_by_slug(tenant_slug)

# #     if not tenant:
# #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# #     message = (request_body.message or "").strip()
# #     if not message:
# #         raise HTTPException(status_code=400, detail="Message is required.")

# #     session_id = request_body.session_id or str(uuid4())

# #     customer = upsert_tenant_customer(
# #         tenant_id=tenant["id"],
# #         session_id=session_id,
# #         name=request_body.customer_name,
# #         email=request_body.customer_email,
# #         phone=request_body.customer_phone,
# #         message=message,
# #         request=request,
# #     )

# #     try:
# #         active_agent_type = (tenant.get("active_agent_type") or "chat").strip().lower()

# #         # Multi-tenant routing:
# #         # - product tenants use the existing product DB flow
# #         # - normal chat tenants use FAISS + LLM flow
# #         if active_agent_type == "product":
# #             product_result = process_product_chat(
# #                 query=message,
# #                 session_id=session_id,
# #                 tenant_id=tenant["id"],
# #             )
# #             responses = product_result.get("responses") or []
# #             chat_result = {
# #                 "answer": "\n\n".join(responses),
# #                 "responses": responses,
# #                 "session_id": session_id,
# #                 "images": [],
# #                 "links": [],
# #                 "sources": [],
# #                 "images_count": 0,
# #                 "links_count": 0,
# #                 "history_count": 0,
# #                 "agent_type": "product",
# #                 "product_step": product_result.get("step"),
# #                 "lookup_type": product_result.get("lookup_type"),
# #             }
# #         else:
# #             chat_result = chat_with_agent(
# #                 session_id=session_id,
# #                 message=message,
# #                 tenant_id=tenant["id"],
# #                 top_k=request_body.top_k or 2,
# #             )
# #             chat_result["agent_type"] = "chat"

# #         chat_result["tenant"] = {
# #             "id": tenant["id"],
# #             "slug": tenant["slug"],
# #             "tenant_name": tenant["tenant_name"],
# #             "active_agent_type": active_agent_type,
# #         }
# #         chat_result["customer"] = {
# #             "id": customer.get("id") if customer else None,
# #             "name": customer.get("name") if customer else request_body.customer_name,
# #             "email": customer.get("email") if customer else request_body.customer_email,
# #         }
# #         return chat_result

# #     except FileNotFoundError:
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Please train this tenant agent first. FAISS index is missing.",
# #         )

# #     except Exception as exc:
# #         raise HTTPException(status_code=500, detail=str(exc))




# # @app.post("/public-chat/customer/{tenant_slug}")
# # def save_public_chat_customer(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# #     tenant = get_tenant_by_slug(tenant_slug)
# #     if not tenant:
# #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
# #     session_id = request_body.session_id or str(uuid4())
# #     customer = upsert_tenant_customer(
# #         tenant_id=tenant["id"],
# #         session_id=session_id,
# #         name=request_body.customer_name,
# #         email=request_body.customer_email,
# #         phone=request_body.customer_phone,
# #         message=request_body.message or "",
# #         request=request,
# #     )
# #     return {"success": True, "session_id": session_id, "customer": customer}


# # @app.post("/chat/{tenant_slug}")
# # def public_chat_by_path(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# #     return _public_chat_response(tenant_slug, request_body, request)


# # @app.post("/chat_{tenant_slug}")
# # def public_chat_by_underscore(tenant_slug: str, request_body: PublicChatRequest, request: Request):
# #     return _public_chat_response(tenant_slug, request_body, request)


# # # ==========================================================
# # # Clean Public URL APIs
# # # Example:
# # #   /instapress -> /chat_t3
# # #   /A8X9K2PQ   -> /chat_t3
# # # ==========================================================
# # PUBLIC_CODE_LENGTH = 8
# # PUBLIC_CODE_ALPHABET = string.ascii_uppercase + string.digits
# # SWEET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,49}$")

# # # These names are already used by backend/frontend routes and must not be taken as sweet names.
# # RESERVED_PUBLIC_NAMES = {
# #     "api", "auth", "chat", "contacts", "dashboard", "docs", "health",
# #     "knowledge", "login", "logout", "openapi.json", "public-chat",
# #     "review-agent", "static", "train", "train-agent", "whatsapp",
# # }


# # def _get_base_url(request: Request) -> str:
# #     """Build correct production base URL behind Railway/proxy."""
# #     proto = request.headers.get("x-forwarded-proto") or request.url.scheme
# #     host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
# #     return f"{proto}://{host}".rstrip("/")


# # def _normalize_sweet_name(value: Optional[str]) -> Optional[str]:
# #     value = (value or "").strip().strip("/")
# #     if not value:
# #         return None
# #     # Keep URLs clean and predictable.
# #     value = value.lower()
# #     return value


# # def _validate_sweet_name(value: Optional[str]) -> Optional[str]:
# #     value = _normalize_sweet_name(value)
# #     if not value:
# #         return None

# #     if value in RESERVED_PUBLIC_NAMES or value.startswith("chat_"):
# #         raise HTTPException(status_code=400, detail="This name is reserved. Please choose another name.")

# #     if not SWEET_NAME_PATTERN.match(value):
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Sweet name must be 3-50 characters and can use letters, numbers, hyphen, or underscore.",
# #         )

# #     return value


# # def _generate_public_code() -> str:
# #     return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


# # def _get_tenant_slug_by_id(tenant_id: int) -> str:
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT slug
# #                 FROM tenants
# #                 WHERE id=%s AND status='active'
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             row = cur.fetchone()
# #     finally:
# #         conn.close()

# #     if not row:
# #         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

# #     return row["slug"]


# # def _get_or_create_public_link(tenant_id: int) -> dict:
# #     tenant_slug = _get_tenant_slug_by_id(tenant_id)
# #     target_path = f"/chat_{tenant_slug}"

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# #                 FROM tenant_public_links
# #                 WHERE tenant_id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             row = cur.fetchone()

# #             if row:
# #                 # Keep tenant slug/path updated if tenant slug ever changes.
# #                 if row.get("tenant_slug") != tenant_slug or row.get("target_path") != target_path:
# #                     cur.execute(
# #                         """
# #                         UPDATE tenant_public_links
# #                         SET tenant_slug=%s, target_path=%s, updated_at=NOW()
# #                         WHERE tenant_id=%s
# #                         """,
# #                         (tenant_slug, target_path, tenant_id),
# #                     )
# #                     row["tenant_slug"] = tenant_slug
# #                     row["target_path"] = target_path
# #                 return row

# #             # Table is empty for new tenant: create permanent hidden 8-char code.
# #             for _ in range(20):
# #                 short_code = _generate_public_code()
# #                 try:
# #                     cur.execute(
# #                         """
# #                         INSERT INTO tenant_public_links
# #                             (tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active)
# #                         VALUES
# #                             (%s, %s, %s, NULL, %s, 1)
# #                         """,
# #                         (tenant_id, tenant_slug, short_code, target_path),
# #                     )
# #                     cur.execute(
# #                         """
# #                         SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# #                         FROM tenant_public_links
# #                         WHERE tenant_id=%s
# #                         LIMIT 1
# #                         """,
# #                         (tenant_id,),
# #                     )
# #                     return cur.fetchone()
# #                 except Exception as exc:
# #                     # Retry only when short_code collision happens. Otherwise raise original DB error.
# #                     if "Duplicate" not in str(exc) and "duplicate" not in str(exc):
# #                         raise

# #     finally:
# #         conn.close()

# #     raise HTTPException(status_code=500, detail="Could not generate unique public link. Please try again.")


# # def _format_public_link_response(row: dict, request: Request) -> dict:
# #     base_url = _get_base_url(request)
# #     public_name = row.get("sweet_name") or row.get("short_code")

# #     return {
# #         "success": True,
# #         "tenant_id": row.get("tenant_id"),
# #         "tenant_slug": row.get("tenant_slug"),
# #         "short_code": row.get("short_code"),
# #         "sweet_name": row.get("sweet_name"),
# #         "public_name": public_name,
# #         "target_path": row.get("target_path"),
# #         "original_url": f"{base_url}{row.get('target_path')}",
# #         "public_url": f"{base_url}/{public_name}",
# #         "fallback_public_url": f"{base_url}/{row.get('short_code')}",
# #     }


# # @app.get("/public-link")
# # def get_public_link(request: Request, current_user: dict = Depends(get_current_user)):
# #     row = _get_or_create_public_link(current_user["tenant_id"])
# #     return _format_public_link_response(row, request)


# # @app.post("/public-link")
# # def update_public_link(
# #     request_body: PublicLinkUpdateRequest,
# #     request: Request,
# #     current_user: dict = Depends(get_current_user),
# # ):
# #     tenant_id = current_user["tenant_id"]
# #     sweet_name = _validate_sweet_name(request_body.sweet_name)

# #     # Ensure row exists before update.
# #     _get_or_create_public_link(tenant_id)

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             if sweet_name:
# #                 cur.execute(
# #                     """
# #                     SELECT tenant_id
# #                     FROM tenant_public_links
# #                     WHERE sweet_name=%s AND tenant_id<>%s
# #                     LIMIT 1
# #                     """,
# #                     (sweet_name, tenant_id),
# #                 )
# #                 existing = cur.fetchone()
# #                 if existing:
# #                     raise HTTPException(status_code=409, detail="This sweet name is already taken. Please choose another.")

# #             cur.execute(
# #                 """
# #                 UPDATE tenant_public_links
# #                 SET sweet_name=%s, updated_at=NOW()
# #                 WHERE tenant_id=%s
# #                 """,
# #                 (sweet_name, tenant_id),
# #             )

# #             cur.execute(
# #                 """
# #                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
# #                 FROM tenant_public_links
# #                 WHERE tenant_id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             row = cur.fetchone()
# #     finally:
# #         conn.close()

# #     return _format_public_link_response(row, request)


# # def _resolve_public_name(public_name: str) -> Optional[dict]:
# #     public_name = (public_name or "").strip().strip("/")
# #     if not public_name:
# #         return None

# #     normalized_name = public_name.lower()

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT
# #                     tpl.tenant_id,
# #                     tpl.tenant_slug,
# #                     tpl.short_code,
# #                     tpl.sweet_name,
# #                     tpl.target_path,
# #                     tpl.is_active,
# #                     COALESCE(t.active_agent_type, 'chat') AS active_agent_type
# #                 FROM tenant_public_links tpl
# #                 JOIN tenants t ON t.id = tpl.tenant_id
# #                 WHERE tpl.is_active = 1
# #                   AND t.status = 'active'
# #                   AND (LOWER(tpl.sweet_name) = %s OR tpl.short_code = %s)
# #                 LIMIT 1
# #                 """,
# #                 (normalized_name, public_name.upper()),
# #             )
# #             return cur.fetchone()
# #     finally:
# #         conn.close()


# # # ==========================================================
# # # Live Training Progress API
# # # Added for frontend step tracking while tenant training runs.
# # # This does NOT remove or break your existing /train-agent endpoint.
# # # Frontend should call /train-agent/start, then poll /train-agent/status/{job_id}.
# # # ==========================================================
# # from fastapi import BackgroundTasks

# # TRAINING_JOBS = {}

# # TRAINING_STEP_ORDER = [
# #     "scanning",
# #     "analyzing",
# #     "chunking",
# #     "building_knowledge_base",
# #     "generating_chat_experience",
# # ]

# # TRAINING_STEP_LABELS = {
# #     "scanning": "Scanning your website / uploaded files",
# #     "analyzing": "Analyzing your business content",
# #     "chunking": "Chunking and cleaning knowledge",
# #     "building_knowledge_base": "Building knowledge base / AI brain",
# #     "generating_chat_experience": "Generating chat experience",
# # }


# # def _new_training_job(job_id: str, tenant_id: int, website_url: str = ""):
# #     TRAINING_JOBS[job_id] = {
# #         "job_id": job_id,
# #         "tenant_id": tenant_id,
# #         "status": "queued",
# #         "current_step": "queued",
# #         "current_step_index": 0,
# #         "progress": 0,
# #         "message": "Training queued.",
# #         "website_url": website_url,
# #         "steps": [
# #             {
# #                 "key": key,
# #                 "label": TRAINING_STEP_LABELS[key],
# #                 "status": "pending",
# #             }
# #             for key in TRAINING_STEP_ORDER
# #         ],
# #         "result": None,
# #         "error": None,
# #     }
# #     return TRAINING_JOBS[job_id]


# # def _set_training_step(job_id: str, step_key: str, message: str = ""):
# #     job = TRAINING_JOBS.get(job_id)
# #     if not job:
# #         return

# #     if step_key not in TRAINING_STEP_ORDER:
# #         return

# #     step_index = TRAINING_STEP_ORDER.index(step_key)
# #     total = len(TRAINING_STEP_ORDER)

# #     for index, item in enumerate(job["steps"]):
# #         if index < step_index:
# #             item["status"] = "done"
# #         elif index == step_index:
# #             item["status"] = "active"
# #         else:
# #             item["status"] = "pending"

# #     job["status"] = "running"
# #     job["current_step"] = step_key
# #     job["current_step_index"] = step_index + 1
# #     job["progress"] = int((step_index / total) * 100)
# #     job["message"] = message or TRAINING_STEP_LABELS[step_key]


# # def _complete_training_job(job_id: str, result: dict):
# #     job = TRAINING_JOBS.get(job_id)
# #     if not job:
# #         return

# #     for item in job["steps"]:
# #         item["status"] = "done"

# #     job["status"] = "completed"
# #     job["current_step"] = "completed"
# #     job["current_step_index"] = len(TRAINING_STEP_ORDER)
# #     job["progress"] = 100
# #     job["message"] = "Agent trained successfully."
# #     job["result"] = result
# #     job["error"] = None

# #     # Save latest training result so Customize page can show real backend data.
# #     try:
# #         _upsert_agent_settings_last_training_summary(job.get("tenant_id"), result)
# #     except Exception:
# #         # Never fail the training job only because settings persistence failed.
# #         pass


# # def _fail_training_job(job_id: str, error: str):
# #     job = TRAINING_JOBS.get(job_id)
# #     if not job:
# #         return

# #     for item in job["steps"]:
# #         if item["status"] == "active":
# #             item["status"] = "failed"

# #     job["status"] = "failed"
# #     job["progress"] = job.get("progress", 0)
# #     job["message"] = "Training failed."
# #     job["error"] = error


# # def _run_training_job(
# #     job_id: str,
# #     tenant_id: int,
# #     website_url: str,
# #     sitemap_url: str,
# #     crawl_type: str,
# #     content_type: str,
# #     uploaded_files_payload: list,
# # ):
# #     """
# #     Background training runner.
# #     It mirrors your existing /train-agent logic but updates TRAINING_JOBS after each phase.
# #     """
# #     try:
# #         all_new_chunks = []
# #         skipped_sources = []
# #         processed_sources = []
# #         failed_sources = []
# #         uploaded_documents_count = 0
# #         website_documents_count = 0

# #         existing_website_json = DATA_DIR / "website_data.json"

# #         if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# #             raise ValueError(
# #                 "Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/."
# #             )

# #         # 1. Scanning source content
# #         _set_training_step(job_id, "scanning", "Scanning website, sitemap, and uploaded files...")

# #         # Existing website_data.json support
# #         if existing_website_json.exists():
# #             try:
# #                 raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
# #                 source_hash = sha256_text(raw_text)
# #                 source_key = f"tenant::{tenant_id}::website_data.json"

# #                 if is_done(source_key, source_hash):
# #                     skipped_sources.append(source_key)
# #                 else:
# #                     mark_processing(source_key, source_hash, {"source_type": "website_json"})
# #                     data = json.loads(raw_text)
# #                     docs = normalize_website_json(data, content_type="Website")

# #                     _set_training_step(job_id, "analyzing", "Analyzing website_data.json content...")
# #                     chunks = docs_to_chunks(docs, source_key=source_key, source_hash=source_hash)
# #                     save_knowledge_documents(
# #                         tenant_id=tenant_id,
# #                         documents=docs,
# #                         source_key=source_key,
# #                         source_hash=source_hash,
# #                         default_source_type="website_json",
# #                         tags=["website", "training"],
# #                     )

# #                     all_new_chunks.extend(chunks)
# #                     website_documents_count += len(docs)

# #                     mark_done(
# #                         source_key,
# #                         source_hash,
# #                         len(chunks),
# #                         {"documents": len(docs), "source_type": "website_json"},
# #                     )
# #                     processed_sources.append(source_key)
# #             except Exception as exc:
# #                 mark_failed("website_data.json", "unknown", str(exc), {"source_type": "website_json"})
# #                 failed_sources.append({"source": "website_data.json", "error": str(exc)})

# #         # Scrape website / sitemap
# #         if website_url or sitemap_url:
# #             scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"
# #             try:
# #                 _set_training_step(job_id, "scanning", "Scanning website pages...")
# #                 scraped_documents = scrape_by_request(
# #                     website_url=website_url,
# #                     sitemap_url=sitemap_url,
# #                     crawl_type=crawl_type,
# #                     content_type=content_type,
# #                 )

# #                 raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
# #                 source_hash = sha256_text(raw_scrape_text)

# #                 if is_done(scrape_key, source_hash):
# #                     skipped_sources.append(scrape_key)
# #                 else:
# #                     mark_processing(scrape_key, source_hash, {"source_type": "scrape"})
# #                     raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
# #                     save_json(raw_scrape_file, scraped_documents)
# #                     move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

# #                     _set_training_step(job_id, "analyzing", "Analyzing scanned website content...")
# #                     chunks = docs_to_chunks(scraped_documents, source_key=scrape_key, source_hash=source_hash)
# #                     save_knowledge_documents(
# #                         tenant_id=tenant_id,
# #                         documents=scraped_documents,
# #                         source_key=scrape_key,
# #                         source_hash=source_hash,
# #                         default_source_type="website",
# #                         tags=["website", crawl_type, "training"],
# #                     )

# #                     all_new_chunks.extend(chunks)
# #                     website_documents_count += len(scraped_documents)

# #                     mark_done(
# #                         scrape_key,
# #                         source_hash,
# #                         len(chunks),
# #                         {"documents": len(scraped_documents), "source_type": "scrape"},
# #                     )
# #                     processed_sources.append(scrape_key)
# #             except Exception as exc:
# #                 error_file = FAILED_DIR / "scrape_error.txt"
# #                 error_file.write_text(str(exc), encoding="utf-8")
# #                 mark_failed(scrape_key, "unknown", str(exc), {"source_type": "scrape"})
# #                 failed_sources.append({"source": scrape_key, "error": str(exc)})

# #         # Uploaded files
# #         for item in uploaded_files_payload:
# #             original_name = item.get("filename") or "uploaded_file"
# #             file_name = safe_filename(original_name)
# #             pending_path = PENDING_UPLOAD_DIR / file_name
# #             content = item.get("content") or b""
# #             upload_content_type = item.get("content_type") or content_type

# #             try:
# #                 _set_training_step(job_id, "scanning", f"Scanning uploaded file: {original_name}")
# #                 source_hash = sha256_bytes(content)
# #                 source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

# #                 if is_done(source_key, source_hash):
# #                     skipped_sources.append(original_name)
# #                     continue

# #                 mark_processing(
# #                     source_key,
# #                     source_hash,
# #                     {"file_name": original_name, "source_type": "file"},
# #                 )

# #                 pending_path.write_bytes(content)

# #                 _set_training_step(job_id, "analyzing", f"Extracting text from: {original_name}")
# #                 parsed_doc = parse_uploaded_file(
# #                     file_path=pending_path,
# #                     original_name=original_name,
# #                     content_type=upload_content_type,
# #                 )

# #                 if parsed_doc and parsed_doc.get("text"):
# #                     _set_training_step(job_id, "chunking", f"Chunking content from: {original_name}")
# #                     chunks = docs_to_chunks([parsed_doc], source_key=source_key, source_hash=source_hash)
# #                     save_knowledge_documents(
# #                         tenant_id=tenant_id,
# #                         documents=[parsed_doc],
# #                         source_key=source_key,
# #                         source_hash=source_hash,
# #                         default_source_type="file",
# #                         tags=["file", "training"],
# #                     )

# #                     all_new_chunks.extend(chunks)
# #                     uploaded_documents_count += 1

# #                     move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)
# #                     mark_done(
# #                         source_key,
# #                         source_hash,
# #                         len(chunks),
# #                         {"file_name": original_name, "source_type": "file"},
# #                     )
# #                     processed_sources.append(original_name)
# #                 else:
# #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# #                     mark_failed(
# #                         source_key,
# #                         source_hash,
# #                         "No text extracted",
# #                         {"file_name": original_name, "source_type": "file"},
# #                     )
# #                     failed_sources.append({"source": original_name, "error": "No text extracted"})

# #             except Exception as exc:
# #                 if pending_path.exists():
# #                     move_file_safely(pending_path, FAILED_DIR / file_name)
# #                 mark_failed(
# #                     f"file::{file_name}",
# #                     "unknown",
# #                     str(exc),
# #                     {"file_name": original_name, "source_type": "file"},
# #                 )
# #                 failed_sources.append({"source": original_name, "error": str(exc)})

# #         if not all_new_chunks and not skipped_sources:
# #             raise ValueError("No new text could be extracted from the provided source.")

# #         # 3. Chunking summary phase
# #         _set_training_step(job_id, "chunking", "Cleaning and preparing chunks...")

# #         # 4. Build FAISS / knowledge base
# #         _set_training_step(job_id, "building_knowledge_base", "Building tenant knowledge base / AI brain...")
# #         index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

# #         if all_new_chunks:
# #             save_json(DATA_DIR / f"latest_new_chunks_{tenant_id}.json", all_new_chunks)

# #         # 5. Generate chat experience
# #         _set_training_step(job_id, "generating_chat_experience", "Generating chat experience from trained data...")

# #         result = {
# #             "success": True,
# #             "message": "Agent training completed. New content was added and duplicate content was skipped.",
# #             "content_type": content_type,
# #             "crawl_type": crawl_type,
# #             "website_documents": website_documents_count,
# #             "uploaded_documents": uploaded_documents_count,
# #             "chunks_created": len(all_new_chunks),
# #             "processed_sources": processed_sources,
# #             "skipped_sources": skipped_sources,
# #             "failed_sources": failed_sources,
# #             "faiss_index_path": index_info.get("index_path"),
# #             "metadata_path": index_info.get("metadata_path"),
# #             "total_vectors": index_info.get("total_vectors"),
# #         }
# #         _complete_training_job(job_id, result)

# #     except Exception as exc:
# #         _fail_training_job(job_id, str(exc))


# # @app.post("/train-agent/start")
# # async def start_train_agent(
# #     background_tasks: BackgroundTasks,
# #     website_url: Optional[str] = Form(default=""),
# #     sitemap_url: Optional[str] = Form(default=""),
# #     crawl_type: str = Form(default="single_page"),
# #     content_type: str = Form(default="Mixed Content"),
# #     files: List[UploadFile] = File(default=[]),
# #     current_user: dict = Depends(get_current_user),
# # ):
# #     """
# #     Starts training in background and immediately returns a job_id.
# #     Frontend should poll GET /train-agent/status/{job_id}.
# #     """
# #     website_url = (website_url or "").strip()
# #     sitemap_url = (sitemap_url or "").strip()
# #     crawl_type = (crawl_type or "single_page").strip()
# #     content_type = (content_type or "Mixed Content").strip()

# #     uploaded_files_payload = []
# #     for upload in files:
# #         uploaded_files_payload.append(
# #             {
# #                 "filename": upload.filename or "uploaded_file",
# #                 "content_type": upload.content_type or content_type,
# #                 "content": await upload.read(),
# #             }
# #         )

# #     existing_website_json = DATA_DIR / "website_data.json"
# #     if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
# #         raise HTTPException(
# #             status_code=400,
# #             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
# #         )

# #     job_id = str(uuid4())
# #     tenant_id = current_user["tenant_id"]
# #     _new_training_job(job_id, tenant_id=tenant_id, website_url=website_url or sitemap_url)

# #     background_tasks.add_task(
# #         _run_training_job,
# #         job_id,
# #         tenant_id,
# #         website_url,
# #         sitemap_url,
# #         crawl_type,
# #         content_type,
# #         uploaded_files_payload,
# #     )

# #     return {
# #         "success": True,
# #         "job_id": job_id,
# #         "message": "Training started.",
# #         "status_url": f"/train-agent/status/{job_id}",
# #     }


# # @app.get("/train-agent/status/{job_id}")
# # def get_train_agent_status(job_id: str, current_user: dict = Depends(get_current_user)):
# #     job = TRAINING_JOBS.get(job_id)

# #     if not job:
# #         raise HTTPException(status_code=404, detail="Training job not found.")

# #     if int(job.get("tenant_id")) != int(current_user["tenant_id"]):
# #         raise HTTPException(status_code=403, detail="You cannot access this training job.")

# #     return job



# # # ==========================================================
# # # Tenant Agent Customize / Review Settings API
# # # Used by frontend ReviewAgentPage.js after training is completed.
# # # Requires table: tenant_agent_settings
# # # ==========================================================

# # class AgentConfigRequest(BaseModel):
# #     business_name: Optional[str] = None
# #     industry: Optional[str] = None
# #     business_type: Optional[str] = None
# #     business_description: Optional[str] = None
# #     greeting_message: Optional[str] = None
# #     starter_questions: Optional[List[str]] = None
# #     system_prompt: Optional[str] = None
# #     restriction_rules: Optional[str] = None
# #     support_hours: Optional[dict] = None


# # def _json_load(value, default=None):
# #     if value is None:
# #         return default
# #     if isinstance(value, (dict, list)):
# #         return value
# #     try:
# #         return json.loads(value)
# #     except Exception:
# #         return default


# # def _default_starter_questions():
# #     return [
# #         "Tell me about your services",
# #         "What products do you offer?",
# #         "How can I contact your team?",
# #         "Do you provide pricing details?",
# #     ]


# # def _default_restriction_rules():
# #     return """- Answer only using trained knowledge base.
# # - Do not invent prices, offers, phone numbers, addresses, or guarantees.
# # - If answer is not available, say: I will connect you with our team.
# # - Keep replies short, clear, and helpful."""


# # def _default_system_prompt(tenant_name: str = "this business"):
# #     return f"""You are a helpful business assistant for {tenant_name}.

# # Your job is to answer customer questions using only the trained knowledge base.
# # Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""


# # def _default_greeting(tenant_name: str = ""):
# #     if tenant_name:
# #         return f"Welcome to {tenant_name}! How can I help you today?"
# #     return "Welcome! How can I help you today?"


# # def _default_support_hours():
# #     return {
# #         "opening_time": "09:00 AM",
# #         "closing_time": "06:00 PM",
# #         "working_days": "Monday - Saturday",
# #     }


# # def _make_default_business_description(tenant_name: str, training_summary: dict = None):
# #     training_summary = training_summary or {}
# #     website_documents = training_summary.get("website_documents") or 0
# #     uploaded_documents = training_summary.get("uploaded_documents") or 0
# #     chunks_created = training_summary.get("chunks_created") or 0

# #     if website_documents or uploaded_documents or chunks_created:
# #         return (
# #             f"{tenant_name} has trained this AI agent with "
# #             f"{website_documents} website pages, {uploaded_documents} uploaded documents, "
# #             f"and {chunks_created} knowledge entries."
# #         )
# #     return f"{tenant_name} AI agent is ready to answer questions from the trained knowledge base."


# # def _get_agent_settings_row(tenant_id: int):
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT *
# #                 FROM tenant_agent_settings
# #                 WHERE tenant_id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             return cur.fetchone()
# #     finally:
# #         conn.close()


# # def _get_tenant_row_by_id(tenant_id: int):
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT id, slug, tenant_name, faiss_index_path, plan_name, status
# #                 FROM tenants
# #                 WHERE id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             return cur.fetchone()
# #     finally:
# #         conn.close()


# # def _upsert_agent_settings_last_training_summary(tenant_id: int, result: dict):
# #     if not tenant_id:
# #         return

# #     summary_json = json.dumps(result or {}, ensure_ascii=False)
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 INSERT INTO tenant_agent_settings
# #                     (tenant_id, last_training_summary)
# #                 VALUES
# #                     (%s, CAST(%s AS JSON))
# #                 ON DUPLICATE KEY UPDATE
# #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# #                     updated_at = NOW()
# #                 """,
# #                 (tenant_id, summary_json),
# #             )
# #     finally:
# #         conn.close()


# # def _normalize_agent_config(tenant: dict, row: dict = None):
# #     row = row or {}
# #     tenant_name = tenant.get("tenant_name") or "Your Business"
# #     training_summary = _json_load(row.get("last_training_summary"), default={}) or {}

# #     business_name = row.get("business_name") or tenant_name
# #     industry = row.get("industry") or "General Business"
# #     business_type = row.get("business_type") or "Business"
# #     business_description = row.get("business_description") or _make_default_business_description(
# #         business_name,
# #         training_summary,
# #     )

# #     greeting_message = row.get("greeting_message") or _default_greeting(business_name)
# #     starter_questions = _json_load(row.get("starter_questions"), default=None) or _default_starter_questions()
# #     system_prompt = row.get("system_prompt") or _default_system_prompt(business_name)
# #     restriction_rules = row.get("restriction_rules") or _default_restriction_rules()
# #     support_hours = _json_load(row.get("support_hours"), default=None) or _default_support_hours()

# #     return {
# #         "tenant": {
# #             "id": tenant.get("id"),
# #             "slug": tenant.get("slug"),
# #             "tenant_name": tenant_name,
# #             "plan_name": tenant.get("plan_name"),
# #             "status": tenant.get("status"),
# #         },
# #         "business": {
# #             "name": business_name,
# #             "industry": industry,
# #             "type": business_type,
# #             "description": business_description,
# #         },
# #         "training_summary": training_summary,
# #         "knowledge_base": {
# #             "entries": training_summary.get("chunks_created") or training_summary.get("total_vectors") or 0,
# #             "website_documents": training_summary.get("website_documents") or 0,
# #             "uploaded_documents": training_summary.get("uploaded_documents") or 0,
# #             "processed_sources": training_summary.get("processed_sources") or [],
# #             "skipped_sources": training_summary.get("skipped_sources") or [],
# #             "failed_sources": training_summary.get("failed_sources") or [],
# #             "total_vectors": training_summary.get("total_vectors") or 0,
# #         },
# #         "chat_experience": {
# #             "greeting_message": greeting_message,
# #             "starter_questions": starter_questions,
# #         },
# #         "behavior": {
# #             "system_prompt": system_prompt,
# #             "restriction_rules": restriction_rules,
# #         },
# #         "support_hours": support_hours,
# #     }


# # @app.get("/agent-config")
# # def get_agent_config(current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     tenant = _get_tenant_row_by_id(tenant_id)

# #     if not tenant:
# #         raise HTTPException(status_code=404, detail="Tenant not found.")

# #     row = _get_agent_settings_row(tenant_id)
# #     return {
# #         "success": True,
# #         "config": _normalize_agent_config(tenant, row),
# #     }


# # @app.post("/agent-config")
# # def save_agent_config(req: AgentConfigRequest, current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     tenant = _get_tenant_row_by_id(tenant_id)

# #     if not tenant:
# #         raise HTTPException(status_code=404, detail="Tenant not found.")

# #     row = _get_agent_settings_row(tenant_id)
# #     current_config = _normalize_agent_config(tenant, row)

# #     business_name = (req.business_name or current_config["business"]["name"] or tenant.get("tenant_name") or "").strip()
# #     industry = (req.industry or current_config["business"]["industry"] or "General Business").strip()
# #     business_type = (req.business_type or current_config["business"]["type"] or "Business").strip()
# #     business_description = (req.business_description or current_config["business"]["description"] or "").strip()
# #     greeting_message = (req.greeting_message or _default_greeting(business_name)).strip()

# #     starter_questions = req.starter_questions or current_config["chat_experience"]["starter_questions"] or _default_starter_questions()
# #     starter_questions = [str(q).strip() for q in starter_questions if str(q).strip()][:8]
# #     if not starter_questions:
# #         starter_questions = _default_starter_questions()

# #     system_prompt = (req.system_prompt or _default_system_prompt(business_name)).strip()
# #     restriction_rules = (req.restriction_rules or _default_restriction_rules()).strip()
# #     support_hours = req.support_hours or current_config.get("support_hours") or _default_support_hours()
# #     last_training_summary = current_config.get("training_summary") or {}

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 INSERT INTO tenant_agent_settings
# #                     (tenant_id, business_name, industry, business_type, business_description,
# #                      greeting_message, starter_questions, system_prompt, restriction_rules,
# #                      support_hours, last_training_summary)
# #                 VALUES
# #                     (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s, CAST(%s AS JSON), CAST(%s AS JSON))
# #                 ON DUPLICATE KEY UPDATE
# #                     business_name = VALUES(business_name),
# #                     industry = VALUES(industry),
# #                     business_type = VALUES(business_type),
# #                     business_description = VALUES(business_description),
# #                     greeting_message = VALUES(greeting_message),
# #                     starter_questions = CAST(VALUES(starter_questions) AS JSON),
# #                     system_prompt = VALUES(system_prompt),
# #                     restriction_rules = VALUES(restriction_rules),
# #                     support_hours = CAST(VALUES(support_hours) AS JSON),
# #                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
# #                     updated_at = NOW()
# #                 """,
# #                 (
# #                     tenant_id,
# #                     business_name,
# #                     industry,
# #                     business_type,
# #                     business_description,
# #                     greeting_message,
# #                     json.dumps(starter_questions, ensure_ascii=False),
# #                     system_prompt,
# #                     restriction_rules,
# #                     json.dumps(support_hours, ensure_ascii=False),
# #                     json.dumps(last_training_summary, ensure_ascii=False),
# #                 ),
# #             )

# #             cur.execute(
# #                 """
# #                 UPDATE tenant_users
# #                 SET name = %s,
# #                     industry = %s,
# #                     type = %s,
# #                     updated_at = NOW()
# #                 WHERE id = %s
# #                   AND tenant_id = %s
# #                 """,
# #                 (
# #                     business_name,
# #                     industry,
# #                     business_type,
# #                     current_user.get("user_id") or current_user.get("id"),
# #                     tenant_id,
# #                 ),
# #             )
# #     finally:
# #         conn.close()

# #     row = _get_agent_settings_row(tenant_id)
# #     return {
# #         "success": True,
# #         "message": "Agent settings saved successfully.",
# #         "config": _normalize_agent_config(tenant, row),
# #     }


# # # ==========================================================
# # # WhatsApp Connection + Auto Reply APIs
# # # Supports both Meta WhatsApp Cloud API and Twilio WhatsApp.
# # # ==========================================================

# # class WhatsAppConnectRequest(BaseModel):
# #     provider: str
# #     meta_access_token: Optional[str] = None
# #     meta_phone_number_id: Optional[str] = None
# #     meta_business_account_id: Optional[str] = None
# #     twilio_account_sid: Optional[str] = None
# #     twilio_auth_token: Optional[str] = None
# #     twilio_phone_number: Optional[str] = None
# #     whatsapp_number: Optional[str] = None
# #     whatsapp_verify_token: Optional[str] = None


# # class SendWhatsAppTextRequest(BaseModel):
# #     to_phone: str
# #     message: str


# # class SendWhatsAppMediaRequest(BaseModel):
# #     to_phone: str
# #     media_url: str
# #     caption: Optional[str] = ""


# # @app.get("/connect-whatsapp")
# # def get_whatsapp_connection(current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT whatsapp_provider, meta_phone_number_id, meta_business_account_id,
# #                        twilio_phone_number, whatsapp_number, whatsapp_verify_token,
# #                        CASE WHEN meta_access_token IS NULL OR meta_access_token='' THEN 0 ELSE 1 END AS has_meta_access_token,
# #                        CASE WHEN twilio_account_sid IS NULL OR twilio_account_sid='' THEN 0 ELSE 1 END AS has_twilio_account_sid,
# #                        CASE WHEN twilio_auth_token IS NULL OR twilio_auth_token='' THEN 0 ELSE 1 END AS has_twilio_auth_token
# #                 FROM tenants
# #                 WHERE id=%s
# #                 LIMIT 1
# #                 """,
# #                 (tenant_id,),
# #             )
# #             row = cur.fetchone() or {}
# #     finally:
# #         conn.close()

# #     return {"success": True, "config": row}


# # @app.post("/connect-whatsapp")
# # def save_whatsapp_connection(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]
# #     provider = (req.provider or "").strip().lower()

# #     if provider not in ["meta", "twilio"]:
# #         raise HTTPException(status_code=400, detail="Provider must be meta or twilio.")

# #     meta_access_token = (req.meta_access_token or "").strip() or None
# #     meta_phone_number_id = (req.meta_phone_number_id or "").strip() or None
# #     meta_business_account_id = (req.meta_business_account_id or "").strip() or None
# #     twilio_account_sid = (req.twilio_account_sid or "").strip() or None
# #     twilio_auth_token = (req.twilio_auth_token or "").strip() or None
# #     twilio_phone_number = normalize_phone(req.twilio_phone_number or "") or None
# #     whatsapp_number = normalize_phone(req.whatsapp_number or "") or None
# #     whatsapp_verify_token = (req.whatsapp_verify_token or "").strip() or None

# #     if provider == "meta" and not meta_phone_number_id:
# #         raise HTTPException(status_code=400, detail="Meta phone number ID is required.")

# #     if provider == "twilio":
# #         if not twilio_account_sid or not twilio_auth_token:
# #             raise HTTPException(
# #                 status_code=400,
# #                 detail="Twilio Account SID and Auth Token are required.",
# #             )

# #         if not twilio_phone_number and whatsapp_number:
# #             twilio_phone_number = whatsapp_number

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 UPDATE tenants
# #                 SET whatsapp_provider=%s,
# #                     meta_access_token=COALESCE(%s, meta_access_token),
# #                     meta_phone_number_id=%s,
# #                     meta_business_account_id=%s,
# #                     twilio_account_sid=COALESCE(%s, twilio_account_sid),
# #                     twilio_auth_token=COALESCE(%s, twilio_auth_token),
# #                     twilio_phone_number=%s,
# #                     whatsapp_number=%s,
# #                     whatsapp_verify_token=%s,
# #                     updated_at=NOW()
# #                 WHERE id=%s
# #                 """,
# #                 (
# #                     provider,
# #                     meta_access_token,
# #                     meta_phone_number_id,
# #                     meta_business_account_id,
# #                     twilio_account_sid,
# #                     twilio_auth_token,
# #                     twilio_phone_number,
# #                     whatsapp_number,
# #                     whatsapp_verify_token,
# #                     tenant_id,
# #                 ),
# #             )
# #     finally:
# #         conn.close()

# #     return {"success": True, "message": "WhatsApp connection saved successfully.", "provider": provider}




# # @app.get("/tenant/whatsapp-config")
# # def tenant_whatsapp_config(current_user: dict = Depends(get_current_user)):
# #     return get_whatsapp_connection(current_user)

# # @app.post("/tenant/active-agent-type")
# # def update_active_agent_type(
# #     req: ActiveAgentTypeRequest,
# #     current_user: dict = Depends(get_current_user),
# # ):
# #     agent_type = (req.active_agent_type or "").strip().lower()

# #     if agent_type not in ["chat", "product"]:
# #         raise HTTPException(
# #             status_code=400,
# #             detail="active_agent_type must be chat or product.",
# #         )

# #     tenant_id = current_user["tenant_id"]

# #     conn = get_main_db_connection()
# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 UPDATE tenants
# #                 SET active_agent_type=%s,
# #                     updated_at=NOW()
# #                 WHERE id=%s
# #                 """,
# #                 (agent_type, tenant_id),
# #             )
# #     finally:
# #         conn.close()

# #     return {
# #         "success": True,
# #         "active_agent_type": agent_type,
# #         "agent_type": agent_type,
# #     }


# # @app.get("/tenant/active-agent-type/{tenant_slug}")
# # def get_active_agent_type_public(tenant_slug: str):
# #     tenant = get_tenant_by_slug(tenant_slug)

# #     if not tenant:
# #         raise HTTPException(status_code=404, detail="Tenant not found")

# #     active_agent_type = tenant.get("active_agent_type") or "chat"

# #     return {
# #         "success": True,
# #         "tenant_slug": tenant["slug"],
# #         "active_agent_type": active_agent_type,
# #         "agent_type": active_agent_type,
# #     }

# # @app.post("/tenant/whatsapp-config")
# # def tenant_save_whatsapp_config(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
# #     return save_whatsapp_connection(req, current_user)

# # @app.post("/send-whatsapp-message")
# # def send_whatsapp_message(req: SendWhatsAppTextRequest, current_user: dict = Depends(get_current_user)):
# #     if not req.to_phone or not req.message:
# #         raise HTTPException(status_code=400, detail="to_phone and message are required.")
# #     return send_whatsapp_text(current_user["tenant_id"], req.to_phone, req.message)


# # @app.post("/send-whatsapp-media")
# # def send_whatsapp_media_message(req: SendWhatsAppMediaRequest, current_user: dict = Depends(get_current_user)):
# #     if not req.to_phone or not req.media_url:
# #         raise HTTPException(status_code=400, detail="to_phone and media_url are required.")
# #     return send_whatsapp_media(current_user["tenant_id"], req.to_phone, req.media_url, req.caption or "")


# # @app.get("/webhook/whatsapp/{tenant_slug}")
# # @app.get("/webhooks/whatsapp/{tenant_slug}")
# # def verify_meta_webhook(tenant_slug: str, request: Request):
# #     # Meta webhook verification: hub.mode, hub.verify_token, hub.challenge
# #     mode = request.query_params.get("hub.mode")
# #     verify_token = request.query_params.get("hub.verify_token")
# #     challenge = request.query_params.get("hub.challenge")

# #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# #     expected_token = tenant.get("whatsapp_verify_token") or "agentive_verify_token_123"

# #     if mode == "subscribe" and verify_token == expected_token:
# #         return Response(content=str(challenge), media_type="text/plain")

# #     raise HTTPException(status_code=403, detail="Webhook verification failed.")


# # @app.post("/webhook/whatsapp/{tenant_slug}")
# # @app.post("/webhooks/whatsapp/{tenant_slug}")
# # async def whatsapp_webhook(tenant_slug: str, request: Request):
# #     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
# #     provider = tenant.get("whatsapp_provider")

# #     # Twilio sends form-urlencoded data. Meta sends JSON.
# #     content_type = request.headers.get("content-type", "")

# #     if provider == "twilio" or "application/x-www-form-urlencoded" in content_type:
# #         form = await request.form()
# #         customer_phone = str(form.get("From") or "").replace("whatsapp:", "")
# #         incoming_message = str(form.get("Body") or "").strip()

# #         if not customer_phone or not incoming_message:
# #             return {"success": True, "message": "No text message to process."}

# #         return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# #     data = await request.json()

# #     try:
# #         entry = (data.get("entry") or [])[0]
# #         change = (entry.get("changes") or [])[0]
# #         value = change.get("value") or {}
# #         message_obj = (value.get("messages") or [])[0]
# #         customer_phone = message_obj.get("from")
# #         incoming_message = (message_obj.get("text") or {}).get("body", "").strip()
# #     except Exception:
# #         return {"success": True, "message": "No supported Meta message to process."}

# #     if not customer_phone or not incoming_message:
# #         return {"success": True, "message": "No text message to process."}

# #     return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # # ==========================================================
# # # Contacts API
# # # Must stay ABOVE React fallback route
# # # ==========================================================
# # @app.get("/api/contacts")
# # def get_contacts(current_user: dict = Depends(get_current_user)):
# #     tenant_id = current_user["tenant_id"]

# #     conn = get_main_db_connection()

# #     try:
# #         with conn.cursor() as cur:
# #             cur.execute(
# #                 """
# #                 SELECT
# #                     id,
# #                     tenant_id,
# #                     session_id,
# #                     name,
# #                     email,
# #                     phone,
# #                     first_message,
# #                     last_message,
# #                     source,
# #                     status,
# #                     user_agent,
# #                     ip_address,
# #                     created_at,
# #                     updated_at,
# #                     last_seen_at
# #                 FROM tenant_customers
# #                 WHERE tenant_id=%s
# #                 ORDER BY
# #                     last_seen_at DESC,
# #                     created_at DESC
# #                 """,
# #                 (tenant_id,),
# #             )

# #             contacts = cur.fetchall() or []

# #     finally:
# #         conn.close()

# #     return {
# #         "success": True,
# #         "total": len(contacts),
# #         "contacts": contacts,
# #     }

# # # ==========================================================
# # # Clean Public URL + React Frontend Route Fallback
# # # KEEP THESE AT THE VERY BOTTOM OF main.py
# # # ==========================================================

# # # @app.get("/public-link/resolve/{public_name}")
# # # def resolve_public_link(public_name: str):
# # #     resolved = _resolve_public_name(public_name)

# # #     if not resolved:
# # #         raise HTTPException(status_code=404, detail="Public link not found.")

# # #     return {
# # #         "success": True,
# # #         "tenant_slug": resolved["tenant_slug"],
# # #         "target_path": resolved["target_path"],
# # #     } 

# # @app.get("/public-link/resolve/{public_name}")
# # def resolve_public_link(public_name: str):
# #     resolved = _resolve_public_name(public_name)

# #     if not resolved:
# #         raise HTTPException(status_code=404, detail="Public link not found.")

# #     return {
# #         "success": True,
# #         "tenant_slug": resolved["tenant_slug"],
# #         "target_path": resolved["target_path"],
# #         "agent_type": resolved.get("active_agent_type") or "chat",
# #         "active_agent_type": resolved.get("active_agent_type") or "chat",
# #     }



# # # @app.get("/{public_name}")
# # # def open_clean_public_chat_url(public_name: str):
# # #     resolved = _resolve_public_name(public_name)
# # #     index_path = os.path.join(BUILD_DIR, "index.html")

# # #     if resolved:
# # #         if os.path.exists(index_path):
# # #             return FileResponse(index_path)

# # #         raise HTTPException(
# # #             status_code=404,
# # #             detail="React build index.html not found"
# # #         )

# # #     # IMPORTANT:
# # #     # if not a valid public link,
# # #     # do NOT return index here
# # #     raise HTTPException(status_code=404, detail="Page not found")



# # if os.path.exists(BUILD_DIR):

# #     @app.get("/{full_path:path}")
# #     def serve_react_routes(full_path: str):
# #         index_path = os.path.join(BUILD_DIR, "index.html")

# #         if os.path.exists(index_path):
# #             return FileResponse(index_path)

# #         raise HTTPException(status_code=404, detail="React build index.html not found")

# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
# from app.auth import router as auth_router, get_current_user
# from fastapi import Depends
# from dotenv import load_dotenv
# load_dotenv()
# import json
# import os
# import re
# import secrets
# import string
# from typing import List, Optional
# from uuid import uuid4

# from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from app.chatbot import chat_with_agent
# from app.db import get_main_db_connection
# from app.file_parser import parse_uploaded_file
# from app.index_builder import add_chunks_to_faiss
# from app.integration import router as integration_router
# from app.product_query_bot import router as product_query_router, process_product_chat
# from app.knowledge_store import (
#     get_combined_training_path,
#     get_entry_text_path,
#     get_knowledge_entry,
#     list_knowledge_entries,
#     save_knowledge_documents,
# )
# from app.whatsapp import (
#     get_tenant_whatsapp_config,
#     handle_incoming_text_and_reply,
#     normalize_phone,
#     send_whatsapp_media,
#     send_whatsapp_text,
# )
# from app.scraper import scrape_by_request
# from app.training_registry import (
#     docs_to_chunks,
#     is_done,
#     mark_done,
#     mark_failed,
#     mark_processing,
#     normalize_website_json,
#     sha256_bytes,
#     sha256_text,
# )
# from app.utils import (
#     DATA_DIR,
#     DONE_SCRAPED_DIR,
#     DONE_UPLOAD_DIR,
#     FAILED_DIR,
#     PENDING_SCRAPED_DIR,
#     PENDING_UPLOAD_DIR,
#     safe_filename,
#     save_json,
#     move_file_safely,
# )

# app = FastAPI(title="Agent Training + WhatsApp Chat Backend", version="2.1.0")

# # Railway / production friendly CORS.
# # Set CORS_ORIGINS in Railway like:
# # CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com
# _raw_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
# _cors_origins = ["*"] if _raw_cors_origins == "*" else [origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=_cors_origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(auth_router)
# app.include_router(integration_router)
# app.include_router(product_query_router)

# class ChatRequest(BaseModel):
#     message: str
#     session_id: Optional[str] = None
#     top_k: Optional[int] = 2


# class PublicChatRequest(BaseModel):
#     message: str
#     session_id: Optional[str] = None
#     top_k: Optional[int] = 2
#     customer_name: Optional[str] = None
#     customer_email: Optional[str] = None
#     customer_phone: Optional[str] = None


# class PublicLinkUpdateRequest(BaseModel):
#     sweet_name: Optional[str] = None


# class ActiveAgentTypeRequest(BaseModel):
#     active_agent_type: str


# def get_tenant_by_slug(tenant_slug: str):
#     tenant_slug = (tenant_slug or "").strip()
#     if not tenant_slug:
#         return None
    
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT id, slug, tenant_name, status, active_agent_type
#                 FROM tenants
#                 WHERE slug=%s AND status='active'
#                 LIMIT 1
                
#                 """,
#                 (tenant_slug,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# def upsert_tenant_customer(
#     tenant_id: int,
#     session_id: str,
#     name: str = None,
#     email: str = None,
#     phone: str = None,
#     message: str = None,
#     request: Request = None,
# ):
#     name = (name or "").strip() or None
#     email = (email or "").strip().lower() or None
#     phone = (phone or "").strip() or None
#     message = (message or "").strip() or None

#     user_agent = None
#     ip_address = None

#     if request is not None:
#         user_agent = request.headers.get("user-agent")
#         if request.client:
#             ip_address = request.client.host

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO tenant_customers
#                     (tenant_id, session_id, name, email, phone, first_message, last_message,
#                      source, status, user_agent, ip_address, last_seen_at)
#                 VALUES
#                     (%s, %s, %s, %s, %s, %s, %s, 'public_chat', 'active', %s, %s, NOW())
#                 ON DUPLICATE KEY UPDATE
#                     name = COALESCE(VALUES(name), name),
#                     email = COALESCE(VALUES(email), email),
#                     phone = COALESCE(VALUES(phone), phone),
#                     first_message = COALESCE(first_message, VALUES(first_message)),
#                     last_message = VALUES(last_message),
#                     user_agent = COALESCE(VALUES(user_agent), user_agent),
#                     ip_address = COALESCE(VALUES(ip_address), ip_address),
#                     status = IF(status='new', 'active', status),
#                     last_seen_at = NOW(),
#                     updated_at = NOW()
#                 """,
#                 (
#                     tenant_id,
#                     session_id,
#                     name,
#                     email,
#                     phone,
#                     message,
#                     message,
#                     user_agent,
#                     ip_address,
#                 ),
#             )

#             cur.execute(
#                 """
#                 SELECT id, tenant_id, session_id, name, email, phone, status
#                 FROM tenant_customers
#                 WHERE tenant_id=%s AND session_id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id, session_id),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# # ==========================================================
# # Serve React Frontend on Railway
# # Required folder structure:
# # backend/
# #   main.py
# #   build/
# #     index.html
# #     static/
# # ==========================================================
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# BUILD_DIR = os.path.join(BASE_DIR, "build")
# STATIC_DIR = os.path.join(BUILD_DIR, "static")

# if os.path.exists(STATIC_DIR):
#     app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# @app.get("/")
# def serve_react_app():
#     index_path = os.path.join(BUILD_DIR, "index.html")

#     if os.path.exists(index_path):
#         return FileResponse(index_path)

#     return {
#         "status": "ok",
#         "message": "Backend running, but React build/index.html was not found.",
#         "required_folder": "Place React build folder beside main.py as ./build",
#         "training_endpoint": "/train-agent",
#         "protected_chat_endpoint": "/chat",
#         "public_chat_endpoint": "/chat/{tenant_slug} or /chat_{tenant_slug}",
#     }

# # ==========================================================
# # Knowledge Base readable text APIs
# # These APIs let a tenant user see/download the exact text that was extracted
# # and sent for FAISS training.
# # ==========================================================
# @app.get("/knowledge")
# def get_knowledge_entries(search: Optional[str] = "", current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     entries = list_knowledge_entries(tenant_id, search=search or "")
#     return {
#         "success": True,
#         "count": len(entries),
#         "entries": entries,
#     }


# @app.get("/knowledge/download")
# def download_all_knowledge(current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     path = get_combined_training_path(tenant_id)
#     if not path.exists():
#         raise HTTPException(status_code=404, detail="No knowledge text found for this tenant.")
#     return FileResponse(
#         str(path),
#         media_type="text/plain",
#         filename=f"tenant_{tenant_id}_all_training_data.txt",
#     )


# @app.get("/knowledge/{entry_id}")
# def get_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     entry = get_knowledge_entry(tenant_id, entry_id)
#     if not entry:
#         raise HTTPException(status_code=404, detail="Knowledge entry not found.")
#     return {"success": True, "entry": entry}


# @app.get("/knowledge/{entry_id}/download")
# def download_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     entry = get_knowledge_entry(tenant_id, entry_id)
#     path = get_entry_text_path(tenant_id, entry_id)
#     if not entry or not path:
#         raise HTTPException(status_code=404, detail="Knowledge text file not found.")
#     safe_title = safe_filename(entry.get("title") or entry_id)
#     return FileResponse(
#         str(path),
#         media_type="text/plain",
#         filename=f"{safe_title}.txt",
#     )


# # @app.post("/train-agent")
# # async def train_agent(
# #     website_url: Optional[str] = Form(default=""),
# #     sitemap_url: Optional[str] = Form(default=""),
# #     crawl_type: str = Form(default="single_page"),
# #     content_type: str = Form(default="Mixed Content"),
# #     files: List[UploadFile] = File(default=[]),
# # ):
# @app.post("/train-agent")
# async def train_agent(
#     website_url: Optional[str] = Form(default=""),
#     sitemap_url: Optional[str] = Form(default=""),
#     crawl_type: str = Form(default="single_page"),
#     content_type: str = Form(default="Mixed Content"),
#     files: List[UploadFile] = File(default=[]),
#     current_user: dict = Depends(get_current_user),
# ):
#     website_url = (website_url or "").strip()
#     sitemap_url = (sitemap_url or "").strip()
#     crawl_type = (crawl_type or "single_page").strip()
#     content_type = (content_type or "Mixed Content").strip()
#     tenant_id = current_user["tenant_id"]

#     existing_website_json = DATA_DIR / "website_data.json"

#     if not website_url and not sitemap_url and not files and not existing_website_json.exists():
#         raise HTTPException(
#             status_code=400,
#             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
#         )

#     all_new_chunks = []
#     skipped_sources = []
#     processed_sources = []
#     failed_sources = []
#     uploaded_documents_count = 0
#     website_documents_count = 0

#     # 1. Existing data/website_data.json support
#     if existing_website_json.exists():
#         try:
#             raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
#             source_hash = sha256_text(raw_text)
#             source_key = f"tenant::{tenant_id}::website_data.json"

#             if is_done(source_key, source_hash):
#                 skipped_sources.append(source_key)
#             else:
#                 mark_processing(source_key, source_hash, {"source_type": "website_json"})

#                 data = json.loads(raw_text)
#                 docs = normalize_website_json(data, content_type="Website")
#                 chunks = docs_to_chunks(
#                     docs,
#                     source_key=source_key,
#                     source_hash=source_hash,
#                 )
#                 save_knowledge_documents(
#                     tenant_id=tenant_id,
#                     documents=docs,
#                     source_key=source_key,
#                     source_hash=source_hash,
#                     default_source_type="website_json",
#                     tags=["website", "training"],
#                 )

#                 all_new_chunks.extend(chunks)
#                 website_documents_count += len(docs)

#                 mark_done(
#                     source_key,
#                     source_hash,
#                     len(chunks),
#                     {
#                         "documents": len(docs),
#                         "source_type": "website_json",
#                     },
#                 )

#                 processed_sources.append(source_key)

#         except Exception as exc:
#             mark_failed(
#                 "website_data.json",
#                 "unknown",
#                 str(exc),
#                 {"source_type": "website_json"},
#             )
#             failed_sources.append({
#                 "source": "website_data.json",
#                 "error": str(exc),
#             })

#     # 2. Scrape website / sitemap
#     if website_url or sitemap_url:
#         scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"

#         try:
#             scraped_documents = scrape_by_request(
#                 website_url=website_url,
#                 sitemap_url=sitemap_url,
#                 crawl_type=crawl_type,
#                 content_type=content_type,
#             )

#             raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
#             source_hash = sha256_text(raw_scrape_text)

#             if is_done(scrape_key, source_hash):
#                 skipped_sources.append(scrape_key)
#             else:
#                 mark_processing(scrape_key, source_hash, {"source_type": "scrape"})

#                 raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
#                 save_json(raw_scrape_file, scraped_documents)
#                 move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

#                 chunks = docs_to_chunks(
#                     scraped_documents,
#                     source_key=scrape_key,
#                     source_hash=source_hash,
#                 )
#                 save_knowledge_documents(
#                     tenant_id=tenant_id,
#                     documents=scraped_documents,
#                     source_key=scrape_key,
#                     source_hash=source_hash,
#                     default_source_type="website",
#                     tags=["website", crawl_type, "training"],
#                 )

#                 all_new_chunks.extend(chunks)
#                 website_documents_count += len(scraped_documents)

#                 mark_done(
#                     scrape_key,
#                     source_hash,
#                     len(chunks),
#                     {
#                         "documents": len(scraped_documents),
#                         "source_type": "scrape",
#                     },
#                 )

#                 processed_sources.append(scrape_key)

#         except Exception as exc:
#             error_file = FAILED_DIR / "scrape_error.txt"
#             error_file.write_text(str(exc), encoding="utf-8")

#             mark_failed(
#                 scrape_key,
#                 "unknown",
#                 str(exc),
#                 {"source_type": "scrape"},
#             )

#             failed_sources.append({
#                 "source": scrape_key,
#                 "error": str(exc),
#             })

#     # 3. Uploaded files
#     for upload in files:
#         original_name = upload.filename or "uploaded_file"
#         file_name = safe_filename(original_name)
#         pending_path = PENDING_UPLOAD_DIR / file_name

#         try:
#             content = await upload.read()
#             source_hash = sha256_bytes(content)
#             source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

#             if is_done(source_key, source_hash):
#                 skipped_sources.append(original_name)
#                 continue

#             mark_processing(
#                 source_key,
#                 source_hash,
#                 {
#                     "file_name": original_name,
#                     "source_type": "file",
#                 },
#             )

#             pending_path.write_bytes(content)

#             parsed_doc = parse_uploaded_file(
#                 file_path=pending_path,
#                 original_name=original_name,
#                 content_type=content_type,
#             )

#             if parsed_doc and parsed_doc.get("text"):
#                 chunks = docs_to_chunks(
#                     [parsed_doc],
#                     source_key=source_key,
#                     source_hash=source_hash,
#                 )
#                 save_knowledge_documents(
#                     tenant_id=tenant_id,
#                     documents=[parsed_doc],
#                     source_key=source_key,
#                     source_hash=source_hash,
#                     default_source_type="file",
#                     tags=["file", "training"],
#                 )

#                 all_new_chunks.extend(chunks)
#                 uploaded_documents_count += 1

#                 move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)

#                 mark_done(
#                     source_key,
#                     source_hash,
#                     len(chunks),
#                     {
#                         "file_name": original_name,
#                         "source_type": "file",
#                     },
#                 )

#                 processed_sources.append(original_name)

#             else:
#                 move_file_safely(pending_path, FAILED_DIR / file_name)

#                 mark_failed(
#                     source_key,
#                     source_hash,
#                     "No text extracted",
#                     {
#                         "file_name": original_name,
#                         "source_type": "file",
#                     },
#                 )

#                 failed_sources.append({
#                     "source": original_name,
#                     "error": "No text extracted",
#                 })

#         except Exception as exc:
#             if pending_path.exists():
#                 move_file_safely(pending_path, FAILED_DIR / file_name)

#             mark_failed(
#                 f"file::{file_name}",
#                 "unknown",
#                 str(exc),
#                 {
#                     "file_name": original_name,
#                     "source_type": "file",
#                 },
#             )

#             failed_sources.append({
#                 "source": original_name,
#                 "error": str(exc),
#             })

#     if not all_new_chunks and not skipped_sources:
#         raise HTTPException(
#             status_code=400,
#             detail="No new text could be extracted from the provided source.",
#         )

#     index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

#     if all_new_chunks:
#         save_json(DATA_DIR / "latest_new_chunks.json", all_new_chunks)

#     return {
#         "success": True,
#         "message": "Agent training completed. New content was added and duplicate content was skipped.",
#         "content_type": content_type,
#         "crawl_type": crawl_type,
#         "website_documents": website_documents_count,
#         "uploaded_documents": uploaded_documents_count,
#         "chunks_created": len(all_new_chunks),
#         "processed_sources": processed_sources,
#         "skipped_sources": skipped_sources,
#         "failed_sources": failed_sources,
#         "faiss_index_path": index_info.get("index_path"),
#         "metadata_path": index_info.get("metadata_path"),
#         "total_vectors": index_info.get("total_vectors"),
#     }


# @app.post("/chat")
# def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
#     message = (request.message or "").strip()

#     if not message:
#         raise HTTPException(status_code=400, detail="Message is required.")

#     session_id = request.session_id or str(uuid4())

#     try:
#         return chat_with_agent(
#             session_id=session_id,
#             message=message,
#             tenant_id=current_user["tenant_id"],
#             top_k=request.top_k or 2,
#         )

#     except FileNotFoundError:
#         raise HTTPException(
#             status_code=400,
#             detail="Please train the agent first. FAISS index is missing.",
#         )

#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))

# def _public_chat_response(tenant_slug: str, request_body: PublicChatRequest, request: Request):
#     tenant = get_tenant_by_slug(tenant_slug)

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

#     message = (request_body.message or "").strip()
#     if not message:
#         raise HTTPException(status_code=400, detail="Message is required.")

#     session_id = request_body.session_id or str(uuid4())

#     customer = upsert_tenant_customer(
#         tenant_id=tenant["id"],
#         session_id=session_id,
#         name=request_body.customer_name,
#         email=request_body.customer_email,
#         phone=request_body.customer_phone,
#         message=message,
#         request=request,
#     )

#     try:
#         active_agent_type = (tenant.get("active_agent_type") or "chat").strip().lower()

#         # Multi-tenant routing:
#         # - product tenants use the existing product DB flow
#         # - normal chat tenants use FAISS + LLM flow
#         if active_agent_type == "product":
#             product_result = process_product_chat(
#                 query=message,
#                 session_id=session_id,
#                 tenant_id=tenant["id"],
#             )
#             responses = product_result.get("responses") or []
#             chat_result = {
#                 "answer": "\n\n".join(responses),
#                 "responses": responses,
#                 "session_id": session_id,
#                 "images": [],
#                 "links": [],
#                 "sources": [],
#                 "images_count": 0,
#                 "links_count": 0,
#                 "history_count": 0,
#                 "agent_type": "product",
#                 "product_step": product_result.get("step"),
#                 "lookup_type": product_result.get("lookup_type"),
#             }
#         else:
#             chat_result = chat_with_agent(
#                 session_id=session_id,
#                 message=message,
#                 tenant_id=tenant["id"],
#                 top_k=request_body.top_k or 2,
#             )
#             chat_result["agent_type"] = "chat"

#         chat_result["tenant"] = {
#             "id": tenant["id"],
#             "slug": tenant["slug"],
#             "tenant_name": tenant["tenant_name"],
#             "active_agent_type": active_agent_type,
#         }
#         chat_result["customer"] = {
#             "id": customer.get("id") if customer else None,
#             "name": customer.get("name") if customer else request_body.customer_name,
#             "email": customer.get("email") if customer else request_body.customer_email,
#         }
#         return chat_result

#     except FileNotFoundError:
#         raise HTTPException(
#             status_code=400,
#             detail="Please train this tenant agent first. FAISS index is missing.",
#         )

#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))




# @app.post("/public-chat/customer/{tenant_slug}")
# def save_public_chat_customer(tenant_slug: str, request_body: PublicChatRequest, request: Request):
#     tenant = get_tenant_by_slug(tenant_slug)
#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
#     session_id = request_body.session_id or str(uuid4())
#     customer = upsert_tenant_customer(
#         tenant_id=tenant["id"],
#         session_id=session_id,
#         name=request_body.customer_name,
#         email=request_body.customer_email,
#         phone=request_body.customer_phone,
#         message=request_body.message or "",
#         request=request,
#     )
#     return {"success": True, "session_id": session_id, "customer": customer}


# @app.post("/chat/{tenant_slug}")
# def public_chat_by_path(tenant_slug: str, request_body: PublicChatRequest, request: Request):
#     return _public_chat_response(tenant_slug, request_body, request)


# @app.post("/chat_{tenant_slug}")
# def public_chat_by_underscore(tenant_slug: str, request_body: PublicChatRequest, request: Request):
#     return _public_chat_response(tenant_slug, request_body, request)


# # ==========================================================
# # Clean Public URL APIs
# # Example:
# #   /instapress -> /chat_t3
# #   /A8X9K2PQ   -> /chat_t3
# # ==========================================================
# PUBLIC_CODE_LENGTH = 8
# PUBLIC_CODE_ALPHABET = string.ascii_uppercase + string.digits
# SWEET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,49}$")

# # These names are already used by backend/frontend routes and must not be taken as sweet names.
# RESERVED_PUBLIC_NAMES = {
#     "api", "auth", "chat", "contacts", "dashboard", "docs", "health",
#     "knowledge", "login", "logout", "openapi.json", "public-chat",
#     "review-agent", "static", "train", "train-agent", "whatsapp",
# }


# def _get_base_url(request: Request) -> str:
#     """Build correct production base URL behind Railway/proxy."""
#     proto = request.headers.get("x-forwarded-proto") or request.url.scheme
#     host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
#     return f"{proto}://{host}".rstrip("/")


# def _normalize_sweet_name(value: Optional[str]) -> Optional[str]:
#     value = (value or "").strip().strip("/")
#     if not value:
#         return None
#     # Keep URLs clean and predictable.
#     value = value.lower()
#     return value


# def _validate_sweet_name(value: Optional[str]) -> Optional[str]:
#     value = _normalize_sweet_name(value)
#     if not value:
#         return None

#     if value in RESERVED_PUBLIC_NAMES or value.startswith("chat_"):
#         raise HTTPException(status_code=400, detail="This name is reserved. Please choose another name.")

#     if not SWEET_NAME_PATTERN.match(value):
#         raise HTTPException(
#             status_code=400,
#             detail="Sweet name must be 3-50 characters and can use letters, numbers, hyphen, or underscore.",
#         )

#     return value


# def _generate_public_code() -> str:
#     return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


# def _get_tenant_slug_by_id(tenant_id: int) -> str:
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT slug
#                 FROM tenants
#                 WHERE id=%s AND status='active'
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             row = cur.fetchone()
#     finally:
#         conn.close()

#     if not row:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

#     return row["slug"]


# def _get_or_create_public_link(tenant_id: int) -> dict:
#     tenant_slug = _get_tenant_slug_by_id(tenant_id)
#     target_path = f"/chat_{tenant_slug}"

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
#                 FROM tenant_public_links
#                 WHERE tenant_id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             row = cur.fetchone()

#             if row:
#                 # Keep tenant slug/path updated if tenant slug ever changes.
#                 if row.get("tenant_slug") != tenant_slug or row.get("target_path") != target_path:
#                     cur.execute(
#                         """
#                         UPDATE tenant_public_links
#                         SET tenant_slug=%s, target_path=%s, updated_at=NOW()
#                         WHERE tenant_id=%s
#                         """,
#                         (tenant_slug, target_path, tenant_id),
#                     )
#                     row["tenant_slug"] = tenant_slug
#                     row["target_path"] = target_path
#                 return row

#             # Table is empty for new tenant: create permanent hidden 8-char code.
#             for _ in range(20):
#                 short_code = _generate_public_code()
#                 try:
#                     cur.execute(
#                         """
#                         INSERT INTO tenant_public_links
#                             (tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active)
#                         VALUES
#                             (%s, %s, %s, NULL, %s, 1)
#                         """,
#                         (tenant_id, tenant_slug, short_code, target_path),
#                     )
#                     cur.execute(
#                         """
#                         SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
#                         FROM tenant_public_links
#                         WHERE tenant_id=%s
#                         LIMIT 1
#                         """,
#                         (tenant_id,),
#                     )
#                     return cur.fetchone()
#                 except Exception as exc:
#                     # Retry only when short_code collision happens. Otherwise raise original DB error.
#                     if "Duplicate" not in str(exc) and "duplicate" not in str(exc):
#                         raise

#     finally:
#         conn.close()

#     raise HTTPException(status_code=500, detail="Could not generate unique public link. Please try again.")


# def _format_public_link_response(row: dict, request: Request) -> dict:
#     base_url = _get_base_url(request)
#     public_name = row.get("sweet_name") or row.get("short_code")

#     return {
#         "success": True,
#         "tenant_id": row.get("tenant_id"),
#         "tenant_slug": row.get("tenant_slug"),
#         "short_code": row.get("short_code"),
#         "sweet_name": row.get("sweet_name"),
#         "public_name": public_name,
#         "target_path": row.get("target_path"),
#         "original_url": f"{base_url}{row.get('target_path')}",
#         "public_url": f"{base_url}/{public_name}",
#         "fallback_public_url": f"{base_url}/{row.get('short_code')}",
#     }


# @app.get("/public-link")
# def get_public_link(request: Request, current_user: dict = Depends(get_current_user)):
#     row = _get_or_create_public_link(current_user["tenant_id"])
#     return _format_public_link_response(row, request)


# @app.post("/public-link")
# def update_public_link(
#     request_body: PublicLinkUpdateRequest,
#     request: Request,
#     current_user: dict = Depends(get_current_user),
# ):
#     tenant_id = current_user["tenant_id"]
#     sweet_name = _validate_sweet_name(request_body.sweet_name)

#     # Ensure row exists before update.
#     _get_or_create_public_link(tenant_id)

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             if sweet_name:
#                 cur.execute(
#                     """
#                     SELECT tenant_id
#                     FROM tenant_public_links
#                     WHERE sweet_name=%s AND tenant_id<>%s
#                     LIMIT 1
#                     """,
#                     (sweet_name, tenant_id),
#                 )
#                 existing = cur.fetchone()
#                 if existing:
#                     raise HTTPException(status_code=409, detail="This sweet name is already taken. Please choose another.")

#             cur.execute(
#                 """
#                 UPDATE tenant_public_links
#                 SET sweet_name=%s, updated_at=NOW()
#                 WHERE tenant_id=%s
#                 """,
#                 (sweet_name, tenant_id),
#             )

#             cur.execute(
#                 """
#                 SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
#                 FROM tenant_public_links
#                 WHERE tenant_id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             row = cur.fetchone()
#     finally:
#         conn.close()

#     return _format_public_link_response(row, request)


# def _resolve_public_name(public_name: str) -> Optional[dict]:
#     public_name = (public_name or "").strip().strip("/")
#     if not public_name:
#         return None

#     normalized_name = public_name.lower()

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT
#                     tpl.tenant_id,
#                     tpl.tenant_slug,
#                     tpl.short_code,
#                     tpl.sweet_name,
#                     tpl.target_path,
#                     tpl.is_active,
#                     COALESCE(t.active_agent_type, 'chat') AS active_agent_type
#                 FROM tenant_public_links tpl
#                 JOIN tenants t ON t.id = tpl.tenant_id
#                 WHERE tpl.is_active = 1
#                   AND t.status = 'active'
#                   AND (LOWER(tpl.sweet_name) = %s OR tpl.short_code = %s)
#                 LIMIT 1
#                 """,
#                 (normalized_name, public_name.upper()),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# # ==========================================================
# # Live Training Progress API
# # Added for frontend step tracking while tenant training runs.
# # This does NOT remove or break your existing /train-agent endpoint.
# # Frontend should call /train-agent/start, then poll /train-agent/status/{job_id}.
# # ==========================================================
# from fastapi import BackgroundTasks

# TRAINING_JOBS = {}

# TRAINING_STEP_ORDER = [
#     "scanning",
#     "analyzing",
#     "chunking",
#     "building_knowledge_base",
#     "generating_chat_experience",
# ]

# TRAINING_STEP_LABELS = {
#     "scanning": "Scanning your website / uploaded files",
#     "analyzing": "Analyzing your business content",
#     "chunking": "Chunking and cleaning knowledge",
#     "building_knowledge_base": "Building knowledge base / AI brain",
#     "generating_chat_experience": "Generating chat experience",
# }


# def _new_training_job(job_id: str, tenant_id: int, website_url: str = ""):
#     TRAINING_JOBS[job_id] = {
#         "job_id": job_id,
#         "tenant_id": tenant_id,
#         "status": "queued",
#         "current_step": "queued",
#         "current_step_index": 0,
#         "progress": 0,
#         "message": "Training queued.",
#         "website_url": website_url,
#         "steps": [
#             {
#                 "key": key,
#                 "label": TRAINING_STEP_LABELS[key],
#                 "status": "pending",
#             }
#             for key in TRAINING_STEP_ORDER
#         ],
#         "result": None,
#         "error": None,
#     }
#     return TRAINING_JOBS[job_id]


# def _set_training_step(job_id: str, step_key: str, message: str = ""):
#     job = TRAINING_JOBS.get(job_id)
#     if not job:
#         return

#     if step_key not in TRAINING_STEP_ORDER:
#         return

#     step_index = TRAINING_STEP_ORDER.index(step_key)
#     total = len(TRAINING_STEP_ORDER)

#     for index, item in enumerate(job["steps"]):
#         if index < step_index:
#             item["status"] = "done"
#         elif index == step_index:
#             item["status"] = "active"
#         else:
#             item["status"] = "pending"

#     job["status"] = "running"
#     job["current_step"] = step_key
#     job["current_step_index"] = step_index + 1
#     job["progress"] = int((step_index / total) * 100)
#     job["message"] = message or TRAINING_STEP_LABELS[step_key]


# def _complete_training_job(job_id: str, result: dict):
#     job = TRAINING_JOBS.get(job_id)
#     if not job:
#         return

#     for item in job["steps"]:
#         item["status"] = "done"

#     job["status"] = "completed"
#     job["current_step"] = "completed"
#     job["current_step_index"] = len(TRAINING_STEP_ORDER)
#     job["progress"] = 100
#     job["message"] = "Agent trained successfully."
#     job["result"] = result
#     job["error"] = None

#     # Save latest training result so Customize page can show real backend data.
#     try:
#         _upsert_agent_settings_last_training_summary(job.get("tenant_id"), result)
#     except Exception:
#         # Never fail the training job only because settings persistence failed.
#         pass


# def _fail_training_job(job_id: str, error: str):
#     job = TRAINING_JOBS.get(job_id)
#     if not job:
#         return

#     for item in job["steps"]:
#         if item["status"] == "active":
#             item["status"] = "failed"

#     job["status"] = "failed"
#     job["progress"] = job.get("progress", 0)
#     job["message"] = "Training failed."
#     job["error"] = error


# def _run_training_job(
#     job_id: str,
#     tenant_id: int,
#     website_url: str,
#     sitemap_url: str,
#     crawl_type: str,
#     content_type: str,
#     uploaded_files_payload: list,
# ):
#     """
#     Background training runner.
#     It mirrors your existing /train-agent logic but updates TRAINING_JOBS after each phase.
#     """
#     try:
#         all_new_chunks = []
#         skipped_sources = []
#         processed_sources = []
#         failed_sources = []
#         uploaded_documents_count = 0
#         website_documents_count = 0

#         existing_website_json = DATA_DIR / "website_data.json"

#         if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
#             raise ValueError(
#                 "Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/."
#             )

#         # 1. Scanning source content
#         _set_training_step(job_id, "scanning", "Scanning website, sitemap, and uploaded files...")

#         # Existing website_data.json support
#         if existing_website_json.exists():
#             try:
#                 raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
#                 source_hash = sha256_text(raw_text)
#                 source_key = f"tenant::{tenant_id}::website_data.json"

#                 if is_done(source_key, source_hash):
#                     skipped_sources.append(source_key)
#                 else:
#                     mark_processing(source_key, source_hash, {"source_type": "website_json"})
#                     data = json.loads(raw_text)
#                     docs = normalize_website_json(data, content_type="Website")

#                     _set_training_step(job_id, "analyzing", "Analyzing website_data.json content...")
#                     chunks = docs_to_chunks(docs, source_key=source_key, source_hash=source_hash)
#                     save_knowledge_documents(
#                         tenant_id=tenant_id,
#                         documents=docs,
#                         source_key=source_key,
#                         source_hash=source_hash,
#                         default_source_type="website_json",
#                         tags=["website", "training"],
#                     )

#                     all_new_chunks.extend(chunks)
#                     website_documents_count += len(docs)

#                     mark_done(
#                         source_key,
#                         source_hash,
#                         len(chunks),
#                         {"documents": len(docs), "source_type": "website_json"},
#                     )
#                     processed_sources.append(source_key)
#             except Exception as exc:
#                 mark_failed("website_data.json", "unknown", str(exc), {"source_type": "website_json"})
#                 failed_sources.append({"source": "website_data.json", "error": str(exc)})

#         # Scrape website / sitemap
#         if website_url or sitemap_url:
#             scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"
#             try:
#                 _set_training_step(job_id, "scanning", "Scanning website pages...")
#                 scraped_documents = scrape_by_request(
#                     website_url=website_url,
#                     sitemap_url=sitemap_url,
#                     crawl_type=crawl_type,
#                     content_type=content_type,
#                 )

#                 raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
#                 source_hash = sha256_text(raw_scrape_text)

#                 if is_done(scrape_key, source_hash):
#                     skipped_sources.append(scrape_key)
#                 else:
#                     mark_processing(scrape_key, source_hash, {"source_type": "scrape"})
#                     raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
#                     save_json(raw_scrape_file, scraped_documents)
#                     move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

#                     _set_training_step(job_id, "analyzing", "Analyzing scanned website content...")
#                     chunks = docs_to_chunks(scraped_documents, source_key=scrape_key, source_hash=source_hash)
#                     save_knowledge_documents(
#                         tenant_id=tenant_id,
#                         documents=scraped_documents,
#                         source_key=scrape_key,
#                         source_hash=source_hash,
#                         default_source_type="website",
#                         tags=["website", crawl_type, "training"],
#                     )

#                     all_new_chunks.extend(chunks)
#                     website_documents_count += len(scraped_documents)

#                     mark_done(
#                         scrape_key,
#                         source_hash,
#                         len(chunks),
#                         {"documents": len(scraped_documents), "source_type": "scrape"},
#                     )
#                     processed_sources.append(scrape_key)
#             except Exception as exc:
#                 error_file = FAILED_DIR / "scrape_error.txt"
#                 error_file.write_text(str(exc), encoding="utf-8")
#                 mark_failed(scrape_key, "unknown", str(exc), {"source_type": "scrape"})
#                 failed_sources.append({"source": scrape_key, "error": str(exc)})

#         # Uploaded files
#         for item in uploaded_files_payload:
#             original_name = item.get("filename") or "uploaded_file"
#             file_name = safe_filename(original_name)
#             pending_path = PENDING_UPLOAD_DIR / file_name
#             content = item.get("content") or b""
#             upload_content_type = item.get("content_type") or content_type

#             try:
#                 _set_training_step(job_id, "scanning", f"Scanning uploaded file: {original_name}")
#                 source_hash = sha256_bytes(content)
#                 source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

#                 if is_done(source_key, source_hash):
#                     skipped_sources.append(original_name)
#                     continue

#                 mark_processing(
#                     source_key,
#                     source_hash,
#                     {"file_name": original_name, "source_type": "file"},
#                 )

#                 pending_path.write_bytes(content)

#                 _set_training_step(job_id, "analyzing", f"Extracting text from: {original_name}")
#                 parsed_doc = parse_uploaded_file(
#                     file_path=pending_path,
#                     original_name=original_name,
#                     content_type=upload_content_type,
#                 )

#                 if parsed_doc and parsed_doc.get("text"):
#                     _set_training_step(job_id, "chunking", f"Chunking content from: {original_name}")
#                     chunks = docs_to_chunks([parsed_doc], source_key=source_key, source_hash=source_hash)
#                     save_knowledge_documents(
#                         tenant_id=tenant_id,
#                         documents=[parsed_doc],
#                         source_key=source_key,
#                         source_hash=source_hash,
#                         default_source_type="file",
#                         tags=["file", "training"],
#                     )

#                     all_new_chunks.extend(chunks)
#                     uploaded_documents_count += 1

#                     move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)
#                     mark_done(
#                         source_key,
#                         source_hash,
#                         len(chunks),
#                         {"file_name": original_name, "source_type": "file"},
#                     )
#                     processed_sources.append(original_name)
#                 else:
#                     move_file_safely(pending_path, FAILED_DIR / file_name)
#                     mark_failed(
#                         source_key,
#                         source_hash,
#                         "No text extracted",
#                         {"file_name": original_name, "source_type": "file"},
#                     )
#                     failed_sources.append({"source": original_name, "error": "No text extracted"})

#             except Exception as exc:
#                 if pending_path.exists():
#                     move_file_safely(pending_path, FAILED_DIR / file_name)
#                 mark_failed(
#                     f"file::{file_name}",
#                     "unknown",
#                     str(exc),
#                     {"file_name": original_name, "source_type": "file"},
#                 )
#                 failed_sources.append({"source": original_name, "error": str(exc)})

#         if not all_new_chunks and not skipped_sources:
#             raise ValueError("No new text could be extracted from the provided source.")

#         # 3. Chunking summary phase
#         _set_training_step(job_id, "chunking", "Cleaning and preparing chunks...")

#         # 4. Build FAISS / knowledge base
#         _set_training_step(job_id, "building_knowledge_base", "Building tenant knowledge base / AI brain...")
#         index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

#         if all_new_chunks:
#             save_json(DATA_DIR / f"latest_new_chunks_{tenant_id}.json", all_new_chunks)

#         # 5. Generate chat experience
#         _set_training_step(job_id, "generating_chat_experience", "Generating chat experience from trained data...")

#         result = {
#             "success": True,
#             "message": "Agent training completed. New content was added and duplicate content was skipped.",
#             "content_type": content_type,
#             "crawl_type": crawl_type,
#             "website_documents": website_documents_count,
#             "uploaded_documents": uploaded_documents_count,
#             "chunks_created": len(all_new_chunks),
#             "processed_sources": processed_sources,
#             "skipped_sources": skipped_sources,
#             "failed_sources": failed_sources,
#             "faiss_index_path": index_info.get("index_path"),
#             "metadata_path": index_info.get("metadata_path"),
#             "total_vectors": index_info.get("total_vectors"),
#         }
#         _complete_training_job(job_id, result)

#     except Exception as exc:
#         _fail_training_job(job_id, str(exc))


# @app.post("/train-agent/start")
# async def start_train_agent(
#     background_tasks: BackgroundTasks,
#     website_url: Optional[str] = Form(default=""),
#     sitemap_url: Optional[str] = Form(default=""),
#     crawl_type: str = Form(default="single_page"),
#     content_type: str = Form(default="Mixed Content"),
#     files: List[UploadFile] = File(default=[]),
#     current_user: dict = Depends(get_current_user),
# ):
#     """
#     Starts training in background and immediately returns a job_id.
#     Frontend should poll GET /train-agent/status/{job_id}.
#     """
#     website_url = (website_url or "").strip()
#     sitemap_url = (sitemap_url or "").strip()
#     crawl_type = (crawl_type or "single_page").strip()
#     content_type = (content_type or "Mixed Content").strip()

#     uploaded_files_payload = []
#     for upload in files:
#         uploaded_files_payload.append(
#             {
#                 "filename": upload.filename or "uploaded_file",
#                 "content_type": upload.content_type or content_type,
#                 "content": await upload.read(),
#             }
#         )

#     existing_website_json = DATA_DIR / "website_data.json"
#     if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
#         raise HTTPException(
#             status_code=400,
#             detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
#         )

#     job_id = str(uuid4())
#     tenant_id = current_user["tenant_id"]
#     _new_training_job(job_id, tenant_id=tenant_id, website_url=website_url or sitemap_url)

#     background_tasks.add_task(
#         _run_training_job,
#         job_id,
#         tenant_id,
#         website_url,
#         sitemap_url,
#         crawl_type,
#         content_type,
#         uploaded_files_payload,
#     )

#     return {
#         "success": True,
#         "job_id": job_id,
#         "message": "Training started.",
#         "status_url": f"/train-agent/status/{job_id}",
#     }


# @app.get("/train-agent/status/{job_id}")
# def get_train_agent_status(job_id: str, current_user: dict = Depends(get_current_user)):
#     job = TRAINING_JOBS.get(job_id)

#     if not job:
#         raise HTTPException(status_code=404, detail="Training job not found.")

#     if int(job.get("tenant_id")) != int(current_user["tenant_id"]):
#         raise HTTPException(status_code=403, detail="You cannot access this training job.")

#     return job



# # ==========================================================
# # Tenant Agent Customize / Review Settings API
# # Used by frontend ReviewAgentPage.js after training is completed.
# # Requires table: tenant_agent_settings
# # ==========================================================

# class AgentConfigRequest(BaseModel):
#     business_name: Optional[str] = None
#     industry: Optional[str] = None
#     business_type: Optional[str] = None
#     business_description: Optional[str] = None
#     greeting_message: Optional[str] = None
#     starter_questions: Optional[List[str]] = None
#     system_prompt: Optional[str] = None
#     restriction_rules: Optional[str] = None
#     support_hours: Optional[dict] = None


# def _json_load(value, default=None):
#     if value is None:
#         return default
#     if isinstance(value, (dict, list)):
#         return value
#     try:
#         return json.loads(value)
#     except Exception:
#         return default


# def _default_starter_questions():
#     return [
#         "Tell me about your services",
#         "What products do you offer?",
#         "How can I contact your team?",
#         "Do you provide pricing details?",
#     ]


# def _default_restriction_rules():
#     return """- Answer only using trained knowledge base.
# - Do not invent prices, offers, phone numbers, addresses, or guarantees.
# - If answer is not available, say: I will connect you with our team.
# - Keep replies short, clear, and helpful."""


# def _default_system_prompt(tenant_name: str = "this business"):
#     return f"""You are a helpful business assistant for {tenant_name}.

# Your job is to answer customer questions using only the trained knowledge base.
# Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""


# def _default_greeting(tenant_name: str = ""):
#     if tenant_name:
#         return f"Welcome to {tenant_name}! How can I help you today?"
#     return "Welcome! How can I help you today?"


# def _default_support_hours():
#     return {
#         "opening_time": "09:00 AM",
#         "closing_time": "06:00 PM",
#         "working_days": "Monday - Saturday",
#     }


# def _make_default_business_description(tenant_name: str, training_summary: dict = None):
#     training_summary = training_summary or {}
#     website_documents = training_summary.get("website_documents") or 0
#     uploaded_documents = training_summary.get("uploaded_documents") or 0
#     chunks_created = training_summary.get("chunks_created") or 0

#     if website_documents or uploaded_documents or chunks_created:
#         return (
#             f"{tenant_name} has trained this AI agent with "
#             f"{website_documents} website pages, {uploaded_documents} uploaded documents, "
#             f"and {chunks_created} knowledge entries."
#         )
#     return f"{tenant_name} AI agent is ready to answer questions from the trained knowledge base."


# def _get_agent_settings_row(tenant_id: int):
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT *
#                 FROM tenant_agent_settings
#                 WHERE tenant_id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# def _get_tenant_row_by_id(tenant_id: int):
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT id, slug, tenant_name, faiss_index_path, plan_name, status
#                 FROM tenants
#                 WHERE id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# def _upsert_agent_settings_last_training_summary(tenant_id: int, result: dict):
#     if not tenant_id:
#         return

#     summary_json = json.dumps(result or {}, ensure_ascii=False)
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO tenant_agent_settings
#                     (tenant_id, last_training_summary)
#                 VALUES
#                     (%s, CAST(%s AS JSON))
#                 ON DUPLICATE KEY UPDATE
#                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
#                     updated_at = NOW()
#                 """,
#                 (tenant_id, summary_json),
#             )
#     finally:
#         conn.close()


# def _normalize_agent_config(tenant: dict, row: dict = None):
#     row = row or {}
#     tenant_name = tenant.get("tenant_name") or "Your Business"
#     training_summary = _json_load(row.get("last_training_summary"), default={}) or {}

#     business_name = row.get("business_name") or tenant_name
#     industry = row.get("industry") or "General Business"
#     business_type = row.get("business_type") or "Business"
#     business_description = row.get("business_description") or _make_default_business_description(
#         business_name,
#         training_summary,
#     )

#     greeting_message = row.get("greeting_message") or _default_greeting(business_name)
#     starter_questions = _json_load(row.get("starter_questions"), default=None) or _default_starter_questions()
#     system_prompt = row.get("system_prompt") or _default_system_prompt(business_name)
#     restriction_rules = row.get("restriction_rules") or _default_restriction_rules()
#     support_hours = _json_load(row.get("support_hours"), default=None) or _default_support_hours()

#     return {
#         "tenant": {
#             "id": tenant.get("id"),
#             "slug": tenant.get("slug"),
#             "tenant_name": tenant_name,
#             "plan_name": tenant.get("plan_name"),
#             "status": tenant.get("status"),
#         },
#         "business": {
#             "name": business_name,
#             "industry": industry,
#             "type": business_type,
#             "description": business_description,
#         },
#         "training_summary": training_summary,
#         "knowledge_base": {
#             "entries": training_summary.get("chunks_created") or training_summary.get("total_vectors") or 0,
#             "website_documents": training_summary.get("website_documents") or 0,
#             "uploaded_documents": training_summary.get("uploaded_documents") or 0,
#             "processed_sources": training_summary.get("processed_sources") or [],
#             "skipped_sources": training_summary.get("skipped_sources") or [],
#             "failed_sources": training_summary.get("failed_sources") or [],
#             "total_vectors": training_summary.get("total_vectors") or 0,
#         },
#         "chat_experience": {
#             "greeting_message": greeting_message,
#             "starter_questions": starter_questions,
#         },
#         "behavior": {
#             "system_prompt": system_prompt,
#             "restriction_rules": restriction_rules,
#         },
#         "support_hours": support_hours,
#     }


# @app.get("/agent-config")
# def get_agent_config(current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     tenant = _get_tenant_row_by_id(tenant_id)

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found.")

#     row = _get_agent_settings_row(tenant_id)
#     return {
#         "success": True,
#         "config": _normalize_agent_config(tenant, row),
#     }


# @app.post("/agent-config")
# def save_agent_config(req: AgentConfigRequest, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     tenant = _get_tenant_row_by_id(tenant_id)

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found.")

#     row = _get_agent_settings_row(tenant_id)
#     current_config = _normalize_agent_config(tenant, row)

#     business_name = (req.business_name or current_config["business"]["name"] or tenant.get("tenant_name") or "").strip()
#     industry = (req.industry or current_config["business"]["industry"] or "General Business").strip()
#     business_type = (req.business_type or current_config["business"]["type"] or "Business").strip()
#     business_description = (req.business_description or current_config["business"]["description"] or "").strip()
#     greeting_message = (req.greeting_message or _default_greeting(business_name)).strip()

#     starter_questions = req.starter_questions or current_config["chat_experience"]["starter_questions"] or _default_starter_questions()
#     starter_questions = [str(q).strip() for q in starter_questions if str(q).strip()][:8]
#     if not starter_questions:
#         starter_questions = _default_starter_questions()

#     system_prompt = (req.system_prompt or _default_system_prompt(business_name)).strip()
#     restriction_rules = (req.restriction_rules or _default_restriction_rules()).strip()
#     support_hours = req.support_hours or current_config.get("support_hours") or _default_support_hours()
#     last_training_summary = current_config.get("training_summary") or {}

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 INSERT INTO tenant_agent_settings
#                     (tenant_id, business_name, industry, business_type, business_description,
#                      greeting_message, starter_questions, system_prompt, restriction_rules,
#                      support_hours, last_training_summary)
#                 VALUES
#                     (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s, CAST(%s AS JSON), CAST(%s AS JSON))
#                 ON DUPLICATE KEY UPDATE
#                     business_name = VALUES(business_name),
#                     industry = VALUES(industry),
#                     business_type = VALUES(business_type),
#                     business_description = VALUES(business_description),
#                     greeting_message = VALUES(greeting_message),
#                     starter_questions = CAST(VALUES(starter_questions) AS JSON),
#                     system_prompt = VALUES(system_prompt),
#                     restriction_rules = VALUES(restriction_rules),
#                     support_hours = CAST(VALUES(support_hours) AS JSON),
#                     last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
#                     updated_at = NOW()
#                 """,
#                 (
#                     tenant_id,
#                     business_name,
#                     industry,
#                     business_type,
#                     business_description,
#                     greeting_message,
#                     json.dumps(starter_questions, ensure_ascii=False),
#                     system_prompt,
#                     restriction_rules,
#                     json.dumps(support_hours, ensure_ascii=False),
#                     json.dumps(last_training_summary, ensure_ascii=False),
#                 ),
#             )

#             cur.execute(
#                 """
#                 UPDATE tenant_users
#                 SET name = %s,
#                     industry = %s,
#                     type = %s,
#                     updated_at = NOW()
#                 WHERE id = %s
#                   AND tenant_id = %s
#                 """,
#                 (
#                     business_name,
#                     industry,
#                     business_type,
#                     current_user.get("user_id") or current_user.get("id"),
#                     tenant_id,
#                 ),
#             )
#     finally:
#         conn.close()

#     row = _get_agent_settings_row(tenant_id)
#     return {
#         "success": True,
#         "message": "Agent settings saved successfully.",
#         "config": _normalize_agent_config(tenant, row),
#     }


# # ==========================================================
# # WhatsApp Connection + Auto Reply APIs
# # Supports both Meta WhatsApp Cloud API and Twilio WhatsApp.
# # ==========================================================

# class WhatsAppConnectRequest(BaseModel):
#     provider: str
#     meta_access_token: Optional[str] = None
#     meta_phone_number_id: Optional[str] = None
#     meta_business_account_id: Optional[str] = None
#     twilio_account_sid: Optional[str] = None
#     twilio_auth_token: Optional[str] = None
#     twilio_phone_number: Optional[str] = None
#     whatsapp_number: Optional[str] = None
#     whatsapp_verify_token: Optional[str] = None


# class SendWhatsAppTextRequest(BaseModel):
#     to_phone: str
#     message: str


# class SendWhatsAppMediaRequest(BaseModel):
#     to_phone: str
#     media_url: str
#     caption: Optional[str] = ""


# @app.get("/connect-whatsapp")
# def get_whatsapp_connection(current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT whatsapp_provider, meta_phone_number_id, meta_business_account_id,
#                        twilio_phone_number, whatsapp_number, whatsapp_verify_token,
#                        CASE WHEN meta_access_token IS NULL OR meta_access_token='' THEN 0 ELSE 1 END AS has_meta_access_token,
#                        CASE WHEN twilio_account_sid IS NULL OR twilio_account_sid='' THEN 0 ELSE 1 END AS has_twilio_account_sid,
#                        CASE WHEN twilio_auth_token IS NULL OR twilio_auth_token='' THEN 0 ELSE 1 END AS has_twilio_auth_token
#                 FROM tenants
#                 WHERE id=%s
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             row = cur.fetchone() or {}
#     finally:
#         conn.close()

#     return {"success": True, "config": row}


# @app.post("/connect-whatsapp")
# def save_whatsapp_connection(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     provider = (req.provider or "").strip().lower()

#     if provider not in ["meta", "twilio"]:
#         raise HTTPException(status_code=400, detail="Provider must be meta or twilio.")

#     meta_access_token = (req.meta_access_token or "").strip() or None
#     meta_phone_number_id = (req.meta_phone_number_id or "").strip() or None
#     meta_business_account_id = (req.meta_business_account_id or "").strip() or None
#     twilio_account_sid = (req.twilio_account_sid or "").strip() or None
#     twilio_auth_token = (req.twilio_auth_token or "").strip() or None
#     twilio_phone_number = normalize_phone(req.twilio_phone_number or "") or None
#     whatsapp_number = normalize_phone(req.whatsapp_number or "") or None
#     whatsapp_verify_token = (req.whatsapp_verify_token or "").strip() or None

#     if provider == "meta" and not meta_phone_number_id:
#         raise HTTPException(status_code=400, detail="Meta phone number ID is required.")

#     if provider == "twilio":
#         if not twilio_account_sid or not twilio_auth_token:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Twilio Account SID and Auth Token are required.",
#             )

#         if not twilio_phone_number and whatsapp_number:
#             twilio_phone_number = whatsapp_number

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 UPDATE tenants
#                 SET whatsapp_provider=%s,
#                     meta_access_token=COALESCE(%s, meta_access_token),
#                     meta_phone_number_id=%s,
#                     meta_business_account_id=%s,
#                     twilio_account_sid=COALESCE(%s, twilio_account_sid),
#                     twilio_auth_token=COALESCE(%s, twilio_auth_token),
#                     twilio_phone_number=%s,
#                     whatsapp_number=%s,
#                     whatsapp_verify_token=%s,
#                     updated_at=NOW()
#                 WHERE id=%s
#                 """,
#                 (
#                     provider,
#                     meta_access_token,
#                     meta_phone_number_id,
#                     meta_business_account_id,
#                     twilio_account_sid,
#                     twilio_auth_token,
#                     twilio_phone_number,
#                     whatsapp_number,
#                     whatsapp_verify_token,
#                     tenant_id,
#                 ),
#             )
#     finally:
#         conn.close()

#     return {"success": True, "message": "WhatsApp connection saved successfully.", "provider": provider}




# @app.get("/tenant/whatsapp-config")
# def tenant_whatsapp_config(current_user: dict = Depends(get_current_user)):
#     return get_whatsapp_connection(current_user)

# @app.post("/tenant/active-agent-type")
# def update_active_agent_type(
#     req: ActiveAgentTypeRequest,
#     current_user: dict = Depends(get_current_user),
# ):
#     agent_type = (req.active_agent_type or "").strip().lower()

#     if agent_type not in ["chat", "product"]:
#         raise HTTPException(
#             status_code=400,
#             detail="active_agent_type must be chat or product.",
#         )

#     tenant_id = current_user["tenant_id"]

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 UPDATE tenants
#                 SET active_agent_type=%s,
#                     updated_at=NOW()
#                 WHERE id=%s
#                 """,
#                 (agent_type, tenant_id),
#             )
#     finally:
#         conn.close()

#     return {
#         "success": True,
#         "active_agent_type": agent_type,
#         "agent_type": agent_type,
#     }


# @app.get("/tenant/active-agent-type/{tenant_slug}")
# def get_active_agent_type_public(tenant_slug: str):
#     tenant = get_tenant_by_slug(tenant_slug)

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found")

#     active_agent_type = tenant.get("active_agent_type") or "chat"

#     return {
#         "success": True,
#         "tenant_slug": tenant["slug"],
#         "active_agent_type": active_agent_type,
#         "agent_type": active_agent_type,
#     }

# @app.post("/tenant/whatsapp-config")
# def tenant_save_whatsapp_config(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
#     return save_whatsapp_connection(req, current_user)

# @app.post("/send-whatsapp-message")
# def send_whatsapp_message(req: SendWhatsAppTextRequest, current_user: dict = Depends(get_current_user)):
#     if not req.to_phone or not req.message:
#         raise HTTPException(status_code=400, detail="to_phone and message are required.")
#     return send_whatsapp_text(current_user["tenant_id"], req.to_phone, req.message)


# @app.post("/send-whatsapp-media")
# def send_whatsapp_media_message(req: SendWhatsAppMediaRequest, current_user: dict = Depends(get_current_user)):
#     if not req.to_phone or not req.media_url:
#         raise HTTPException(status_code=400, detail="to_phone and media_url are required.")
#     return send_whatsapp_media(current_user["tenant_id"], req.to_phone, req.media_url, req.caption or "")


# @app.get("/webhook/whatsapp/{tenant_slug}")
# @app.get("/webhooks/whatsapp/{tenant_slug}")
# def verify_meta_webhook(tenant_slug: str, request: Request):
#     # Meta webhook verification: hub.mode, hub.verify_token, hub.challenge
#     mode = request.query_params.get("hub.mode")
#     verify_token = request.query_params.get("hub.verify_token")
#     challenge = request.query_params.get("hub.challenge")

#     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
#     expected_token = tenant.get("whatsapp_verify_token") or "agentive_verify_token_123"

#     if mode == "subscribe" and verify_token == expected_token:
#         return Response(content=str(challenge), media_type="text/plain")

#     raise HTTPException(status_code=403, detail="Webhook verification failed.")


# @app.post("/webhook/whatsapp/{tenant_slug}")
# @app.post("/webhooks/whatsapp/{tenant_slug}")
# async def whatsapp_webhook(tenant_slug: str, request: Request):
#     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
#     provider = tenant.get("whatsapp_provider")

#     # Twilio sends form-urlencoded data. Meta sends JSON.
#     content_type = request.headers.get("content-type", "")

#     if provider == "twilio" or "application/x-www-form-urlencoded" in content_type:
#         form = await request.form()
#         customer_phone = str(form.get("From") or "").replace("whatsapp:", "")
#         incoming_message = str(form.get("Body") or "").strip()

#         if not customer_phone or not incoming_message:
#             return {"success": True, "message": "No text message to process."}

#         return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

#     data = await request.json()

#     try:
#         entry = (data.get("entry") or [])[0]
#         change = (entry.get("changes") or [])[0]
#         value = change.get("value") or {}
#         message_obj = (value.get("messages") or [])[0]
#         customer_phone = message_obj.get("from")
#         incoming_message = (message_obj.get("text") or {}).get("body", "").strip()
#     except Exception:
#         return {"success": True, "message": "No supported Meta message to process."}

#     if not customer_phone or not incoming_message:
#         return {"success": True, "message": "No text message to process."}

#     return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# # ==========================================================
# # Contacts API
# # Must stay ABOVE React fallback route
# # ==========================================================
# @app.get("/api/contacts")
# def get_contacts(current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]

#     conn = get_main_db_connection()

#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT
#                     id,
#                     tenant_id,
#                     session_id,
#                     name,
#                     email,
#                     phone,
#                     first_message,
#                     last_message,
#                     source,
#                     status,
#                     user_agent,
#                     ip_address,
#                     created_at,
#                     updated_at,
#                     last_seen_at
#                 FROM tenant_customers
#                 WHERE tenant_id=%s
#                 ORDER BY
#                     last_seen_at DESC,
#                     created_at DESC
#                 """,
#                 (tenant_id,),
#             )

#             contacts = cur.fetchall() or []

#     finally:
#         conn.close()

#     return {
#         "success": True,
#         "total": len(contacts),
#         "contacts": contacts,
#     }

# # ==========================================================
# # Clean Public URL + React Frontend Route Fallback
# # KEEP THESE AT THE VERY BOTTOM OF main.py
# # ==========================================================

# # @app.get("/public-link/resolve/{public_name}")
# # def resolve_public_link(public_name: str):
# #     resolved = _resolve_public_name(public_name)

# #     if not resolved:
# #         raise HTTPException(status_code=404, detail="Public link not found.")

# #     return {
# #         "success": True,
# #         "tenant_slug": resolved["tenant_slug"],
# #         "target_path": resolved["target_path"],
# #     } 

# @app.get("/public-link/resolve/{public_name}")
# def resolve_public_link(public_name: str):
#     resolved = _resolve_public_name(public_name)

#     if not resolved:
#         raise HTTPException(status_code=404, detail="Public link not found.")

#     return {
#         "success": True,
#         "tenant_slug": resolved["tenant_slug"],
#         "target_path": resolved["target_path"],
#         "agent_type": resolved.get("active_agent_type") or "chat",
#         "active_agent_type": resolved.get("active_agent_type") or "chat",
#     }



# # @app.get("/{public_name}")
# # def open_clean_public_chat_url(public_name: str):
# #     resolved = _resolve_public_name(public_name)
# #     index_path = os.path.join(BUILD_DIR, "index.html")

# #     if resolved:
# #         if os.path.exists(index_path):
# #             return FileResponse(index_path)

# #         raise HTTPException(
# #             status_code=404,
# #             detail="React build index.html not found"
# #         )

# #     # IMPORTANT:
# #     # if not a valid public link,
# #     # do NOT return index here
# #     raise HTTPException(status_code=404, detail="Page not found")



# if os.path.exists(BUILD_DIR):

#     @app.get("/{full_path:path}")
#     def serve_react_routes(full_path: str):
#         index_path = os.path.join(BUILD_DIR, "index.html")

#         if os.path.exists(index_path):
#             return FileResponse(index_path)

#         raise HTTPException(status_code=404, detail="React build index.html not found")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from app.auth import router as auth_router, get_current_user
from fastapi import Depends
from dotenv import load_dotenv
load_dotenv()
import json
import os
import re
import secrets
import string
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.chatbot import chat_with_agent
from app.db import get_main_db_connection
from app.file_parser import parse_uploaded_file
from app.index_builder import add_chunks_to_faiss
from app.integration import router as integration_router
from app.product_query_bot import router as product_query_router, process_product_chat
from app.knowledge_store import (
    get_combined_training_path,
    get_entry_text_path,
    get_knowledge_entry,
    list_knowledge_entries,
    save_knowledge_documents,
)
from app.whatsapp import (
    get_tenant_whatsapp_config,
    handle_incoming_text_and_reply,
    normalize_phone,
    send_whatsapp_media,
    send_whatsapp_text,
)
from app.scraper import scrape_by_request
from app.training_registry import (
    docs_to_chunks,
    is_done,
    mark_done,
    mark_failed,
    mark_processing,
    normalize_website_json,
    sha256_bytes,
    sha256_text,
)
from app.utils import (
    DATA_DIR,
    DONE_SCRAPED_DIR,
    DONE_UPLOAD_DIR,
    FAILED_DIR,
    PENDING_SCRAPED_DIR,
    PENDING_UPLOAD_DIR,
    safe_filename,
    save_json,
    move_file_safely,
)

app = FastAPI(title="Agent Training + WhatsApp Chat Backend", version="2.1.0")

# Railway / production friendly CORS.
# Set CORS_ORIGINS in Railway like:
# CORS_ORIGINS=https://your-frontend.up.railway.app,https://yourdomain.com
_raw_cors_origins = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = ["*"] if _raw_cors_origins == "*" else [origin.strip() for origin in _raw_cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(integration_router)
app.include_router(product_query_router)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    top_k: Optional[int] = 2


class PublicChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    top_k: Optional[int] = 2
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


class PublicLinkUpdateRequest(BaseModel):
    sweet_name: Optional[str] = None


class ActiveAgentTypeRequest(BaseModel):
    active_agent_type: str


def get_tenant_by_slug(tenant_slug: str):
    tenant_slug = (tenant_slug or "").strip()
    if not tenant_slug:
        return None
    
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, tenant_name, status, active_agent_type
                FROM tenants
                WHERE slug=%s AND status='active'
                LIMIT 1
                
                """,
                (tenant_slug,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def upsert_tenant_customer(
    tenant_id: int,
    session_id: str,
    name: str = None,
    email: str = None,
    phone: str = None,
    message: str = None,
    request: Request = None,
):
    name = (name or "").strip() or None
    email = (email or "").strip().lower() or None
    phone = (phone or "").strip() or None
    message = (message or "").strip() or None

    user_agent = None
    ip_address = None

    if request is not None:
        user_agent = request.headers.get("user-agent")
        if request.client:
            ip_address = request.client.host

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_customers
                    (tenant_id, session_id, name, email, phone, first_message, last_message,
                     source, status, user_agent, ip_address, last_seen_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, 'public_chat', 'active', %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    name = COALESCE(VALUES(name), name),
                    email = COALESCE(VALUES(email), email),
                    phone = COALESCE(VALUES(phone), phone),
                    first_message = COALESCE(first_message, VALUES(first_message)),
                    last_message = VALUES(last_message),
                    user_agent = COALESCE(VALUES(user_agent), user_agent),
                    ip_address = COALESCE(VALUES(ip_address), ip_address),
                    status = IF(status='new', 'active', status),
                    last_seen_at = NOW(),
                    updated_at = NOW()
                """,
                (
                    tenant_id,
                    session_id,
                    name,
                    email,
                    phone,
                    message,
                    message,
                    user_agent,
                    ip_address,
                ),
            )

            cur.execute(
                """
                SELECT id, tenant_id, session_id, name, email, phone, status
                FROM tenant_customers
                WHERE tenant_id=%s AND session_id=%s
                LIMIT 1
                """,
                (tenant_id, session_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


# ==========================================================
# Serve React Frontend on Railway
# Required folder structure:
# backend/
#   main.py
#   build/
#     index.html
#     static/
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(BASE_DIR, "build")
STATIC_DIR = os.path.join(BUILD_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_react_app():
    index_path = os.path.join(BUILD_DIR, "index.html")

    if os.path.exists(index_path):
        return FileResponse(index_path)

    return {
        "status": "ok",
        "message": "Backend running, but React build/index.html was not found.",
        "required_folder": "Place React build folder beside main.py as ./build",
        "training_endpoint": "/train-agent",
        "protected_chat_endpoint": "/chat",
        "public_chat_endpoint": "/chat/{tenant_slug} or /chat_{tenant_slug}",
    }

# ==========================================================
# Knowledge Base readable text APIs
# These APIs let a tenant user see/download the exact text that was extracted
# and sent for FAISS training.
# ==========================================================
@app.get("/knowledge")
def get_knowledge_entries(search: Optional[str] = "", current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    entries = list_knowledge_entries(tenant_id, search=search or "")
    return {
        "success": True,
        "count": len(entries),
        "entries": entries,
    }


@app.get("/knowledge/download")
def download_all_knowledge(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    path = get_combined_training_path(tenant_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No knowledge text found for this tenant.")
    return FileResponse(
        str(path),
        media_type="text/plain",
        filename=f"tenant_{tenant_id}_all_training_data.txt",
    )


@app.get("/knowledge/{entry_id}")
def get_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    entry = get_knowledge_entry(tenant_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    return {"success": True, "entry": entry}


@app.get("/knowledge/{entry_id}/download")
def download_one_knowledge_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    entry = get_knowledge_entry(tenant_id, entry_id)
    path = get_entry_text_path(tenant_id, entry_id)
    if not entry or not path:
        raise HTTPException(status_code=404, detail="Knowledge text file not found.")
    safe_title = safe_filename(entry.get("title") or entry_id)
    return FileResponse(
        str(path),
        media_type="text/plain",
        filename=f"{safe_title}.txt",
    )


# @app.post("/train-agent")
# async def train_agent(
#     website_url: Optional[str] = Form(default=""),
#     sitemap_url: Optional[str] = Form(default=""),
#     crawl_type: str = Form(default="single_page"),
#     content_type: str = Form(default="Mixed Content"),
#     files: List[UploadFile] = File(default=[]),
# ):
@app.post("/train-agent")
async def train_agent(
    website_url: Optional[str] = Form(default=""),
    sitemap_url: Optional[str] = Form(default=""),
    crawl_type: str = Form(default="single_page"),
    content_type: str = Form(default="Mixed Content"),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
):
    website_url = (website_url or "").strip()
    sitemap_url = (sitemap_url or "").strip()
    crawl_type = (crawl_type or "single_page").strip()
    content_type = (content_type or "Mixed Content").strip()
    tenant_id = current_user["tenant_id"]

    existing_website_json = DATA_DIR / "website_data.json"

    if not website_url and not sitemap_url and not files and not existing_website_json.exists():
        raise HTTPException(
            status_code=400,
            detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
        )

    all_new_chunks = []
    skipped_sources = []
    processed_sources = []
    failed_sources = []
    uploaded_documents_count = 0
    website_documents_count = 0

    # 1. Existing data/website_data.json support
    if existing_website_json.exists():
        try:
            raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
            source_hash = sha256_text(raw_text)
            source_key = f"tenant::{tenant_id}::website_data.json"

            if is_done(source_key, source_hash):
                skipped_sources.append(source_key)
            else:
                mark_processing(source_key, source_hash, {"source_type": "website_json"})

                data = json.loads(raw_text)
                docs = normalize_website_json(data, content_type="Website")
                chunks = docs_to_chunks(
                    docs,
                    source_key=source_key,
                    source_hash=source_hash,
                )
                save_knowledge_documents(
                    tenant_id=tenant_id,
                    documents=docs,
                    source_key=source_key,
                    source_hash=source_hash,
                    default_source_type="website_json",
                    tags=["website", "training"],
                )

                all_new_chunks.extend(chunks)
                website_documents_count += len(docs)

                mark_done(
                    source_key,
                    source_hash,
                    len(chunks),
                    {
                        "documents": len(docs),
                        "source_type": "website_json",
                    },
                )

                processed_sources.append(source_key)

        except Exception as exc:
            mark_failed(
                "website_data.json",
                "unknown",
                str(exc),
                {"source_type": "website_json"},
            )
            failed_sources.append({
                "source": "website_data.json",
                "error": str(exc),
            })

    # 2. Scrape website / sitemap
    if website_url or sitemap_url:
        scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"

        try:
            scraped_documents = scrape_by_request(
                website_url=website_url,
                sitemap_url=sitemap_url,
                crawl_type=crawl_type,
                content_type=content_type,
            )

            raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
            source_hash = sha256_text(raw_scrape_text)

            if is_done(scrape_key, source_hash):
                skipped_sources.append(scrape_key)
            else:
                mark_processing(scrape_key, source_hash, {"source_type": "scrape"})

                raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
                save_json(raw_scrape_file, scraped_documents)
                move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

                chunks = docs_to_chunks(
                    scraped_documents,
                    source_key=scrape_key,
                    source_hash=source_hash,
                )
                save_knowledge_documents(
                    tenant_id=tenant_id,
                    documents=scraped_documents,
                    source_key=scrape_key,
                    source_hash=source_hash,
                    default_source_type="website",
                    tags=["website", crawl_type, "training"],
                )

                all_new_chunks.extend(chunks)
                website_documents_count += len(scraped_documents)

                mark_done(
                    scrape_key,
                    source_hash,
                    len(chunks),
                    {
                        "documents": len(scraped_documents),
                        "source_type": "scrape",
                    },
                )

                processed_sources.append(scrape_key)

        except Exception as exc:
            error_file = FAILED_DIR / "scrape_error.txt"
            error_file.write_text(str(exc), encoding="utf-8")

            mark_failed(
                scrape_key,
                "unknown",
                str(exc),
                {"source_type": "scrape"},
            )

            failed_sources.append({
                "source": scrape_key,
                "error": str(exc),
            })

    # 3. Uploaded files
    for upload in files:
        original_name = upload.filename or "uploaded_file"
        file_name = safe_filename(original_name)
        pending_path = PENDING_UPLOAD_DIR / file_name

        try:
            content = await upload.read()
            source_hash = sha256_bytes(content)
            source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

            if is_done(source_key, source_hash):
                skipped_sources.append(original_name)
                continue

            mark_processing(
                source_key,
                source_hash,
                {
                    "file_name": original_name,
                    "source_type": "file",
                },
            )

            pending_path.write_bytes(content)

            parsed_doc = parse_uploaded_file(
                file_path=pending_path,
                original_name=original_name,
                content_type=content_type,
            )

            if parsed_doc and parsed_doc.get("text"):
                chunks = docs_to_chunks(
                    [parsed_doc],
                    source_key=source_key,
                    source_hash=source_hash,
                )
                save_knowledge_documents(
                    tenant_id=tenant_id,
                    documents=[parsed_doc],
                    source_key=source_key,
                    source_hash=source_hash,
                    default_source_type="file",
                    tags=["file", "training"],
                )

                all_new_chunks.extend(chunks)
                uploaded_documents_count += 1

                move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)

                mark_done(
                    source_key,
                    source_hash,
                    len(chunks),
                    {
                        "file_name": original_name,
                        "source_type": "file",
                    },
                )

                processed_sources.append(original_name)

            else:
                move_file_safely(pending_path, FAILED_DIR / file_name)

                mark_failed(
                    source_key,
                    source_hash,
                    "No text extracted",
                    {
                        "file_name": original_name,
                        "source_type": "file",
                    },
                )

                failed_sources.append({
                    "source": original_name,
                    "error": "No text extracted",
                })

        except Exception as exc:
            if pending_path.exists():
                move_file_safely(pending_path, FAILED_DIR / file_name)

            mark_failed(
                f"file::{file_name}",
                "unknown",
                str(exc),
                {
                    "file_name": original_name,
                    "source_type": "file",
                },
            )

            failed_sources.append({
                "source": original_name,
                "error": str(exc),
            })

    if not all_new_chunks and not skipped_sources:
        raise HTTPException(
            status_code=400,
            detail="No new text could be extracted from the provided source.",
        )

    index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

    if all_new_chunks:
        save_json(DATA_DIR / "latest_new_chunks.json", all_new_chunks)

    return {
        "success": True,
        "message": "Agent training completed. New content was added and duplicate content was skipped.",
        "content_type": content_type,
        "crawl_type": crawl_type,
        "website_documents": website_documents_count,
        "uploaded_documents": uploaded_documents_count,
        "chunks_created": len(all_new_chunks),
        "processed_sources": processed_sources,
        "skipped_sources": skipped_sources,
        "failed_sources": failed_sources,
        "faiss_index_path": index_info.get("index_path"),
        "metadata_path": index_info.get("metadata_path"),
        "total_vectors": index_info.get("total_vectors"),
    }


@app.post("/chat")
def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    message = (request.message or "").strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    session_id = request.session_id or str(uuid4())

    try:
        return chat_with_agent(
            session_id=session_id,
            message=message,
            tenant_id=current_user["tenant_id"],
            top_k=request.top_k or 2,
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="Please train the agent first. FAISS index is missing.",
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

def _public_chat_response(tenant_slug: str, request_body: PublicChatRequest, request: Request):
    tenant = get_tenant_by_slug(tenant_slug)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

    message = (request_body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    session_id = request_body.session_id or str(uuid4())

    customer = upsert_tenant_customer(
        tenant_id=tenant["id"],
        session_id=session_id,
        name=request_body.customer_name,
        email=request_body.customer_email,
        phone=request_body.customer_phone,
        message=message,
        request=request,
    )

    try:
        active_agent_type = (tenant.get("active_agent_type") or "chat").strip().lower()

        # Multi-tenant routing:
        # - product tenants use the existing product DB flow
        # - normal chat tenants use FAISS + LLM flow
        if active_agent_type == "product":
            product_result = process_product_chat(
                query=message,
                session_id=session_id,
                tenant_id=tenant["id"],
            )
            responses = product_result.get("responses") or []
            chat_result = {
                "answer": "\n\n".join(responses),
                "responses": responses,
                "session_id": session_id,
                "images": [],
                "links": [],
                "sources": [],
                "images_count": 0,
                "links_count": 0,
                "history_count": 0,
                "agent_type": "product",
                "product_step": product_result.get("step"),
                "lookup_type": product_result.get("lookup_type"),
            }
        else:
            chat_result = chat_with_agent(
                session_id=session_id,
                message=message,
                tenant_id=tenant["id"],
                top_k=request_body.top_k or 2,
            )
            chat_result["agent_type"] = "chat"

        chat_result["tenant"] = {
            "id": tenant["id"],
            "slug": tenant["slug"],
            "tenant_name": tenant["tenant_name"],
            "active_agent_type": active_agent_type,
        }
        chat_result["customer"] = {
            "id": customer.get("id") if customer else None,
            "name": customer.get("name") if customer else request_body.customer_name,
            "email": customer.get("email") if customer else request_body.customer_email,
        }
        return chat_result

    except FileNotFoundError:
        raise HTTPException(
            status_code=400,
            detail="Please train this tenant agent first. FAISS index is missing.",
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))




@app.post("/public-chat/customer/{tenant_slug}")
def save_public_chat_customer(tenant_slug: str, request_body: PublicChatRequest, request: Request):
    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
    session_id = request_body.session_id or str(uuid4())
    customer = upsert_tenant_customer(
        tenant_id=tenant["id"],
        session_id=session_id,
        name=request_body.customer_name,
        email=request_body.customer_email,
        phone=request_body.customer_phone,
        message=request_body.message or "",
        request=request,
    )
    return {"success": True, "session_id": session_id, "customer": customer}


@app.post("/chat/{tenant_slug}")
def public_chat_by_path(tenant_slug: str, request_body: PublicChatRequest, request: Request):
    return _public_chat_response(tenant_slug, request_body, request)


@app.post("/chat_{tenant_slug}")
def public_chat_by_underscore(tenant_slug: str, request_body: PublicChatRequest, request: Request):
    return _public_chat_response(tenant_slug, request_body, request)


# ==========================================================
# Clean Public URL APIs
# Example:
#   /instapress -> /chat_t3
#   /A8X9K2PQ   -> /chat_t3
# ==========================================================
PUBLIC_CODE_LENGTH = 8
PUBLIC_CODE_ALPHABET = string.ascii_uppercase + string.digits
SWEET_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,49}$")

# These names are already used by backend/frontend routes and must not be taken as sweet names.
RESERVED_PUBLIC_NAMES = {
    "api", "auth", "chat", "contacts", "dashboard", "docs", "health",
    "knowledge", "login", "logout", "openapi.json", "public-chat",
    "review-agent", "static", "train", "train-agent", "whatsapp",
}


def _get_base_url(request: Request) -> str:
    """Build correct production base URL behind Railway/proxy."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def _normalize_sweet_name(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip().strip("/")
    if not value:
        return None
    # Keep URLs clean and predictable.
    value = value.lower()
    return value


def _validate_sweet_name(value: Optional[str]) -> Optional[str]:
    value = _normalize_sweet_name(value)
    if not value:
        return None

    if value in RESERVED_PUBLIC_NAMES or value.startswith("chat_"):
        raise HTTPException(status_code=400, detail="This name is reserved. Please choose another name.")

    if not SWEET_NAME_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail="Sweet name must be 3-50 characters and can use letters, numbers, hyphen, or underscore.",
        )

    return value


def _generate_public_code() -> str:
    return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


def _get_tenant_slug_by_id(tenant_id: int) -> str:
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug
                FROM tenants
                WHERE id=%s AND status='active'
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

    return row["slug"]


def _get_or_create_public_link(tenant_id: int) -> dict:
    tenant_slug = _get_tenant_slug_by_id(tenant_id)
    target_path = f"/chat_{tenant_slug}"

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
                FROM tenant_public_links
                WHERE tenant_id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone()

            if row:
                # Keep tenant slug/path updated if tenant slug ever changes.
                if row.get("tenant_slug") != tenant_slug or row.get("target_path") != target_path:
                    cur.execute(
                        """
                        UPDATE tenant_public_links
                        SET tenant_slug=%s, target_path=%s, updated_at=NOW()
                        WHERE tenant_id=%s
                        """,
                        (tenant_slug, target_path, tenant_id),
                    )
                    row["tenant_slug"] = tenant_slug
                    row["target_path"] = target_path
                return row

            # Table is empty for new tenant: create permanent hidden 8-char code.
            for _ in range(20):
                short_code = _generate_public_code()
                try:
                    cur.execute(
                        """
                        INSERT INTO tenant_public_links
                            (tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active)
                        VALUES
                            (%s, %s, %s, NULL, %s, 1)
                        """,
                        (tenant_id, tenant_slug, short_code, target_path),
                    )
                    cur.execute(
                        """
                        SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
                        FROM tenant_public_links
                        WHERE tenant_id=%s
                        LIMIT 1
                        """,
                        (tenant_id,),
                    )
                    return cur.fetchone()
                except Exception as exc:
                    # Retry only when short_code collision happens. Otherwise raise original DB error.
                    if "Duplicate" not in str(exc) and "duplicate" not in str(exc):
                        raise

    finally:
        conn.close()

    raise HTTPException(status_code=500, detail="Could not generate unique public link. Please try again.")


def _format_public_link_response(row: dict, request: Request) -> dict:
    base_url = _get_base_url(request)
    public_name = row.get("sweet_name") or row.get("short_code")

    return {
        "success": True,
        "tenant_id": row.get("tenant_id"),
        "tenant_slug": row.get("tenant_slug"),
        "short_code": row.get("short_code"),
        "sweet_name": row.get("sweet_name"),
        "public_name": public_name,
        "target_path": row.get("target_path"),
        "original_url": f"{base_url}{row.get('target_path')}",
        "public_url": f"{base_url}/{public_name}",
        "fallback_public_url": f"{base_url}/{row.get('short_code')}",
    }


@app.get("/public-link")
def get_public_link(request: Request, current_user: dict = Depends(get_current_user)):
    row = _get_or_create_public_link(current_user["tenant_id"])
    return _format_public_link_response(row, request)


@app.post("/public-link")
def update_public_link(
    request_body: PublicLinkUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user["tenant_id"]
    sweet_name = _validate_sweet_name(request_body.sweet_name)

    # Ensure row exists before update.
    _get_or_create_public_link(tenant_id)

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            if sweet_name:
                cur.execute(
                    """
                    SELECT tenant_id
                    FROM tenant_public_links
                    WHERE sweet_name=%s AND tenant_id<>%s
                    LIMIT 1
                    """,
                    (sweet_name, tenant_id),
                )
                existing = cur.fetchone()
                if existing:
                    raise HTTPException(status_code=409, detail="This sweet name is already taken. Please choose another.")

            cur.execute(
                """
                UPDATE tenant_public_links
                SET sweet_name=%s, updated_at=NOW()
                WHERE tenant_id=%s
                """,
                (sweet_name, tenant_id),
            )

            cur.execute(
                """
                SELECT id, tenant_id, tenant_slug, short_code, sweet_name, target_path, is_active
                FROM tenant_public_links
                WHERE tenant_id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    return _format_public_link_response(row, request)


def _resolve_public_name(public_name: str) -> Optional[dict]:
    public_name = (public_name or "").strip().strip("/")
    if not public_name:
        return None

    normalized_name = public_name.lower()

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    tpl.tenant_id,
                    tpl.tenant_slug,
                    tpl.short_code,
                    tpl.sweet_name,
                    tpl.target_path,
                    tpl.is_active,
                    COALESCE(t.active_agent_type, 'chat') AS active_agent_type
                FROM tenant_public_links tpl
                JOIN tenants t ON t.id = tpl.tenant_id
                WHERE tpl.is_active = 1
                  AND t.status = 'active'
                  AND (LOWER(tpl.sweet_name) = %s OR tpl.short_code = %s)
                LIMIT 1
                """,
                (normalized_name, public_name.upper()),
            )
            return cur.fetchone()
    finally:
        conn.close()


# ==========================================================
# Live Training Progress API
# Added for frontend step tracking while tenant training runs.
# This does NOT remove or break your existing /train-agent endpoint.
# Frontend should call /train-agent/start, then poll /train-agent/status/{job_id}.
# ==========================================================
from fastapi import BackgroundTasks

TRAINING_JOBS = {}

TRAINING_STEP_ORDER = [
    "scanning",
    "analyzing",
    "chunking",
    "building_knowledge_base",
    "generating_chat_experience",
]

TRAINING_STEP_LABELS = {
    "scanning": "Scanning your website / uploaded files",
    "analyzing": "Analyzing your business content",
    "chunking": "Chunking and cleaning knowledge",
    "building_knowledge_base": "Building knowledge base / AI brain",
    "generating_chat_experience": "Generating chat experience",
}


def _new_training_job(job_id: str, tenant_id: int, website_url: str = ""):
    TRAINING_JOBS[job_id] = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "status": "queued",
        "current_step": "queued",
        "current_step_index": 0,
        "progress": 0,
        "message": "Training queued.",
        "website_url": website_url,
        "steps": [
            {
                "key": key,
                "label": TRAINING_STEP_LABELS[key],
                "status": "pending",
            }
            for key in TRAINING_STEP_ORDER
        ],
        "result": None,
        "error": None,
    }
    return TRAINING_JOBS[job_id]


def _set_training_step(job_id: str, step_key: str, message: str = ""):
    job = TRAINING_JOBS.get(job_id)
    if not job:
        return

    if step_key not in TRAINING_STEP_ORDER:
        return

    step_index = TRAINING_STEP_ORDER.index(step_key)
    total = len(TRAINING_STEP_ORDER)

    for index, item in enumerate(job["steps"]):
        if index < step_index:
            item["status"] = "done"
        elif index == step_index:
            item["status"] = "active"
        else:
            item["status"] = "pending"

    job["status"] = "running"
    job["current_step"] = step_key
    job["current_step_index"] = step_index + 1
    job["progress"] = int((step_index / total) * 100)
    job["message"] = message or TRAINING_STEP_LABELS[step_key]


def _complete_training_job(job_id: str, result: dict):
    job = TRAINING_JOBS.get(job_id)
    if not job:
        return

    for item in job["steps"]:
        item["status"] = "done"

    job["status"] = "completed"
    job["current_step"] = "completed"
    job["current_step_index"] = len(TRAINING_STEP_ORDER)
    job["progress"] = 100
    job["message"] = "Agent trained successfully."
    job["result"] = result
    job["error"] = None

    # Save latest training result so Customize page can show real backend data.
    try:
        _upsert_agent_settings_last_training_summary(job.get("tenant_id"), result)
    except Exception:
        # Never fail the training job only because settings persistence failed.
        pass


def _fail_training_job(job_id: str, error: str):
    job = TRAINING_JOBS.get(job_id)
    if not job:
        return

    for item in job["steps"]:
        if item["status"] == "active":
            item["status"] = "failed"

    job["status"] = "failed"
    job["progress"] = job.get("progress", 0)
    job["message"] = "Training failed."
    job["error"] = error


def _run_training_job(
    job_id: str,
    tenant_id: int,
    website_url: str,
    sitemap_url: str,
    crawl_type: str,
    content_type: str,
    uploaded_files_payload: list,
):
    """
    Background training runner.
    It mirrors your existing /train-agent logic but updates TRAINING_JOBS after each phase.
    """
    try:
        all_new_chunks = []
        skipped_sources = []
        processed_sources = []
        failed_sources = []
        uploaded_documents_count = 0
        website_documents_count = 0

        existing_website_json = DATA_DIR / "website_data.json"

        if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
            raise ValueError(
                "Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/."
            )

        # 1. Scanning source content
        _set_training_step(job_id, "scanning", "Scanning website, sitemap, and uploaded files...")

        # Existing website_data.json support
        if existing_website_json.exists():
            try:
                raw_text = existing_website_json.read_text(encoding="utf-8", errors="ignore")
                source_hash = sha256_text(raw_text)
                source_key = f"tenant::{tenant_id}::website_data.json"

                if is_done(source_key, source_hash):
                    skipped_sources.append(source_key)
                else:
                    mark_processing(source_key, source_hash, {"source_type": "website_json"})
                    data = json.loads(raw_text)
                    docs = normalize_website_json(data, content_type="Website")

                    _set_training_step(job_id, "analyzing", "Analyzing website_data.json content...")
                    chunks = docs_to_chunks(docs, source_key=source_key, source_hash=source_hash)
                    save_knowledge_documents(
                        tenant_id=tenant_id,
                        documents=docs,
                        source_key=source_key,
                        source_hash=source_hash,
                        default_source_type="website_json",
                        tags=["website", "training"],
                    )

                    all_new_chunks.extend(chunks)
                    website_documents_count += len(docs)

                    mark_done(
                        source_key,
                        source_hash,
                        len(chunks),
                        {"documents": len(docs), "source_type": "website_json"},
                    )
                    processed_sources.append(source_key)
            except Exception as exc:
                mark_failed("website_data.json", "unknown", str(exc), {"source_type": "website_json"})
                failed_sources.append({"source": "website_data.json", "error": str(exc)})

        # Scrape website / sitemap
        if website_url or sitemap_url:
            scrape_key = f"tenant::{tenant_id}::scrape::{crawl_type}::{website_url or sitemap_url}"
            try:
                _set_training_step(job_id, "scanning", "Scanning website pages...")
                scraped_documents = scrape_by_request(
                    website_url=website_url,
                    sitemap_url=sitemap_url,
                    crawl_type=crawl_type,
                    content_type=content_type,
                )

                raw_scrape_text = json.dumps(scraped_documents, ensure_ascii=False)
                source_hash = sha256_text(raw_scrape_text)

                if is_done(scrape_key, source_hash):
                    skipped_sources.append(scrape_key)
                else:
                    mark_processing(scrape_key, source_hash, {"source_type": "scrape"})
                    raw_scrape_file = PENDING_SCRAPED_DIR / "scraped_raw_website.json"
                    save_json(raw_scrape_file, scraped_documents)
                    move_file_safely(raw_scrape_file, DONE_SCRAPED_DIR / raw_scrape_file.name)

                    _set_training_step(job_id, "analyzing", "Analyzing scanned website content...")
                    chunks = docs_to_chunks(scraped_documents, source_key=scrape_key, source_hash=source_hash)
                    save_knowledge_documents(
                        tenant_id=tenant_id,
                        documents=scraped_documents,
                        source_key=scrape_key,
                        source_hash=source_hash,
                        default_source_type="website",
                        tags=["website", crawl_type, "training"],
                    )

                    all_new_chunks.extend(chunks)
                    website_documents_count += len(scraped_documents)

                    mark_done(
                        scrape_key,
                        source_hash,
                        len(chunks),
                        {"documents": len(scraped_documents), "source_type": "scrape"},
                    )
                    processed_sources.append(scrape_key)
            except Exception as exc:
                error_file = FAILED_DIR / "scrape_error.txt"
                error_file.write_text(str(exc), encoding="utf-8")
                mark_failed(scrape_key, "unknown", str(exc), {"source_type": "scrape"})
                failed_sources.append({"source": scrape_key, "error": str(exc)})

        # Uploaded files
        for item in uploaded_files_payload:
            original_name = item.get("filename") or "uploaded_file"
            file_name = safe_filename(original_name)
            pending_path = PENDING_UPLOAD_DIR / file_name
            content = item.get("content") or b""
            upload_content_type = item.get("content_type") or content_type

            try:
                _set_training_step(job_id, "scanning", f"Scanning uploaded file: {original_name}")
                source_hash = sha256_bytes(content)
                source_key = f"tenant::{tenant_id}::file::{file_name}::{len(content)}"

                if is_done(source_key, source_hash):
                    skipped_sources.append(original_name)
                    continue

                mark_processing(
                    source_key,
                    source_hash,
                    {"file_name": original_name, "source_type": "file"},
                )

                pending_path.write_bytes(content)

                _set_training_step(job_id, "analyzing", f"Extracting text from: {original_name}")
                parsed_doc = parse_uploaded_file(
                    file_path=pending_path,
                    original_name=original_name,
                    content_type=upload_content_type,
                )

                if parsed_doc and parsed_doc.get("text"):
                    _set_training_step(job_id, "chunking", f"Chunking content from: {original_name}")
                    chunks = docs_to_chunks([parsed_doc], source_key=source_key, source_hash=source_hash)
                    save_knowledge_documents(
                        tenant_id=tenant_id,
                        documents=[parsed_doc],
                        source_key=source_key,
                        source_hash=source_hash,
                        default_source_type="file",
                        tags=["file", "training"],
                    )

                    all_new_chunks.extend(chunks)
                    uploaded_documents_count += 1

                    move_file_safely(pending_path, DONE_UPLOAD_DIR / file_name)
                    mark_done(
                        source_key,
                        source_hash,
                        len(chunks),
                        {"file_name": original_name, "source_type": "file"},
                    )
                    processed_sources.append(original_name)
                else:
                    move_file_safely(pending_path, FAILED_DIR / file_name)
                    mark_failed(
                        source_key,
                        source_hash,
                        "No text extracted",
                        {"file_name": original_name, "source_type": "file"},
                    )
                    failed_sources.append({"source": original_name, "error": "No text extracted"})

            except Exception as exc:
                if pending_path.exists():
                    move_file_safely(pending_path, FAILED_DIR / file_name)
                mark_failed(
                    f"file::{file_name}",
                    "unknown",
                    str(exc),
                    {"file_name": original_name, "source_type": "file"},
                )
                failed_sources.append({"source": original_name, "error": str(exc)})

        if not all_new_chunks and not skipped_sources:
            raise ValueError("No new text could be extracted from the provided source.")

        # 3. Chunking summary phase
        _set_training_step(job_id, "chunking", "Cleaning and preparing chunks...")

        # 4. Build FAISS / knowledge base
        _set_training_step(job_id, "building_knowledge_base", "Building tenant knowledge base / AI brain...")
        index_info = add_chunks_to_faiss(all_new_chunks, tenant_id)

        if all_new_chunks:
            save_json(DATA_DIR / f"latest_new_chunks_{tenant_id}.json", all_new_chunks)

        # 5. Generate chat experience
        _set_training_step(job_id, "generating_chat_experience", "Generating chat experience from trained data...")

        result = {
            "success": True,
            "message": "Agent training completed. New content was added and duplicate content was skipped.",
            "content_type": content_type,
            "crawl_type": crawl_type,
            "website_documents": website_documents_count,
            "uploaded_documents": uploaded_documents_count,
            "chunks_created": len(all_new_chunks),
            "processed_sources": processed_sources,
            "skipped_sources": skipped_sources,
            "failed_sources": failed_sources,
            "faiss_index_path": index_info.get("index_path"),
            "metadata_path": index_info.get("metadata_path"),
            "total_vectors": index_info.get("total_vectors"),
        }
        _complete_training_job(job_id, result)

    except Exception as exc:
        _fail_training_job(job_id, str(exc))


@app.post("/train-agent/start")
async def start_train_agent(
    background_tasks: BackgroundTasks,
    website_url: Optional[str] = Form(default=""),
    sitemap_url: Optional[str] = Form(default=""),
    crawl_type: str = Form(default="single_page"),
    content_type: str = Form(default="Mixed Content"),
    files: List[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
):
    """
    Starts training in background and immediately returns a job_id.
    Frontend should poll GET /train-agent/status/{job_id}.
    """
    website_url = (website_url or "").strip()
    sitemap_url = (sitemap_url or "").strip()
    crawl_type = (crawl_type or "single_page").strip()
    content_type = (content_type or "Mixed Content").strip()

    uploaded_files_payload = []
    for upload in files:
        uploaded_files_payload.append(
            {
                "filename": upload.filename or "uploaded_file",
                "content_type": upload.content_type or content_type,
                "content": await upload.read(),
            }
        )

    existing_website_json = DATA_DIR / "website_data.json"
    if not website_url and not sitemap_url and not uploaded_files_payload and not existing_website_json.exists():
        raise HTTPException(
            status_code=400,
            detail="Please provide website URL, sitemap URL, upload a file, or place website_data.json inside data/.",
        )

    job_id = str(uuid4())
    tenant_id = current_user["tenant_id"]
    _new_training_job(job_id, tenant_id=tenant_id, website_url=website_url or sitemap_url)

    background_tasks.add_task(
        _run_training_job,
        job_id,
        tenant_id,
        website_url,
        sitemap_url,
        crawl_type,
        content_type,
        uploaded_files_payload,
    )

    return {
        "success": True,
        "job_id": job_id,
        "message": "Training started.",
        "status_url": f"/train-agent/status/{job_id}",
    }


@app.get("/train-agent/status/{job_id}")
def get_train_agent_status(job_id: str, current_user: dict = Depends(get_current_user)):
    job = TRAINING_JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Training job not found.")

    if int(job.get("tenant_id")) != int(current_user["tenant_id"]):
        raise HTTPException(status_code=403, detail="You cannot access this training job.")

    return job



# ==========================================================
# Tenant Agent Customize / Review Settings API
# Used by frontend ReviewAgentPage.js after training is completed.
# Requires table: tenant_agent_settings
# ==========================================================

class AgentConfigRequest(BaseModel):
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_type: Optional[str] = None
    business_description: Optional[str] = None
    greeting_message: Optional[str] = None
    starter_questions: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    restriction_rules: Optional[str] = None
    support_hours: Optional[dict] = None


def _json_load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _default_starter_questions():
    return [
        "Tell me about your services",
        "What products do you offer?",
        "How can I contact your team?",
        "Do you provide pricing details?",
    ]


def _default_restriction_rules():
    return """- Answer only using trained knowledge base.
- Do not invent prices, offers, phone numbers, addresses, or guarantees.
- If answer is not available, say: I will connect you with our team.
- Keep replies short, clear, and helpful."""


def _default_system_prompt(tenant_name: str = "this business"):
    return f"""You are a helpful business assistant for {tenant_name}.

Your job is to answer customer questions using only the trained knowledge base.
Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""


def _default_greeting(tenant_name: str = ""):
    if tenant_name:
        return f"Welcome to {tenant_name}! How can I help you today?"
    return "Welcome! How can I help you today?"


def _default_support_hours():
    return {
        "opening_time": "09:00 AM",
        "closing_time": "06:00 PM",
        "working_days": "Monday - Saturday",
    }


def _make_default_business_description(tenant_name: str, training_summary: dict = None):
    training_summary = training_summary or {}
    website_documents = training_summary.get("website_documents") or 0
    uploaded_documents = training_summary.get("uploaded_documents") or 0
    chunks_created = training_summary.get("chunks_created") or 0

    if website_documents or uploaded_documents or chunks_created:
        return (
            f"{tenant_name} has trained this AI agent with "
            f"{website_documents} website pages, {uploaded_documents} uploaded documents, "
            f"and {chunks_created} knowledge entries."
        )
    return f"{tenant_name} AI agent is ready to answer questions from the trained knowledge base."


def _get_agent_settings_row(tenant_id: int):
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM tenant_agent_settings
                WHERE tenant_id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _get_tenant_row_by_id(tenant_id: int):
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, tenant_name, faiss_index_path, plan_name, status
                FROM tenants
                WHERE id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _upsert_agent_settings_last_training_summary(tenant_id: int, result: dict):
    if not tenant_id:
        return

    summary_json = json.dumps(result or {}, ensure_ascii=False)
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_agent_settings
                    (tenant_id, last_training_summary)
                VALUES
                    (%s, CAST(%s AS JSON))
                ON DUPLICATE KEY UPDATE
                    last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
                    updated_at = NOW()
                """,
                (tenant_id, summary_json),
            )
    finally:
        conn.close()


def _normalize_agent_config(tenant: dict, row: dict = None):
    row = row or {}
    tenant_name = tenant.get("tenant_name") or "Your Business"
    training_summary = _json_load(row.get("last_training_summary"), default={}) or {}

    business_name = row.get("business_name") or tenant_name
    industry = row.get("industry") or "General Business"
    business_type = row.get("business_type") or "Business"
    business_description = row.get("business_description") or _make_default_business_description(
        business_name,
        training_summary,
    )

    greeting_message = row.get("greeting_message") or _default_greeting(business_name)
    starter_questions = _json_load(row.get("starter_questions"), default=None) or _default_starter_questions()
    system_prompt = row.get("system_prompt") or _default_system_prompt(business_name)
    restriction_rules = row.get("restriction_rules") or _default_restriction_rules()
    support_hours = _json_load(row.get("support_hours"), default=None) or _default_support_hours()

    return {
        "tenant": {
            "id": tenant.get("id"),
            "slug": tenant.get("slug"),
            "tenant_name": tenant_name,
            "plan_name": tenant.get("plan_name"),
            "status": tenant.get("status"),
        },
        "business": {
            "name": business_name,
            "industry": industry,
            "type": business_type,
            "description": business_description,
        },
        "training_summary": training_summary,
        "knowledge_base": {
            "entries": training_summary.get("chunks_created") or training_summary.get("total_vectors") or 0,
            "website_documents": training_summary.get("website_documents") or 0,
            "uploaded_documents": training_summary.get("uploaded_documents") or 0,
            "processed_sources": training_summary.get("processed_sources") or [],
            "skipped_sources": training_summary.get("skipped_sources") or [],
            "failed_sources": training_summary.get("failed_sources") or [],
            "total_vectors": training_summary.get("total_vectors") or 0,
        },
        "chat_experience": {
            "greeting_message": greeting_message,
            "starter_questions": starter_questions,
        },
        "behavior": {
            "system_prompt": system_prompt,
            "restriction_rules": restriction_rules,
        },
        "support_hours": support_hours,
    }


@app.get("/agent-config")
def get_agent_config(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    tenant = _get_tenant_row_by_id(tenant_id)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    row = _get_agent_settings_row(tenant_id)
    return {
        "success": True,
        "config": _normalize_agent_config(tenant, row),
    }


@app.post("/agent-config")
def save_agent_config(req: AgentConfigRequest, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    tenant = _get_tenant_row_by_id(tenant_id)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    row = _get_agent_settings_row(tenant_id)
    current_config = _normalize_agent_config(tenant, row)

    business_name = (req.business_name or current_config["business"]["name"] or tenant.get("tenant_name") or "").strip()
    industry = (req.industry or current_config["business"]["industry"] or "General Business").strip()
    business_type = (req.business_type or current_config["business"]["type"] or "Business").strip()
    business_description = (req.business_description or current_config["business"]["description"] or "").strip()
    greeting_message = (req.greeting_message or _default_greeting(business_name)).strip()

    starter_questions = req.starter_questions or current_config["chat_experience"]["starter_questions"] or _default_starter_questions()
    starter_questions = [str(q).strip() for q in starter_questions if str(q).strip()][:8]
    if not starter_questions:
        starter_questions = _default_starter_questions()

    system_prompt = (req.system_prompt or _default_system_prompt(business_name)).strip()
    restriction_rules = (req.restriction_rules or _default_restriction_rules()).strip()
    support_hours = req.support_hours or current_config.get("support_hours") or _default_support_hours()
    last_training_summary = current_config.get("training_summary") or {}

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_agent_settings
                    (tenant_id, business_name, industry, business_type, business_description,
                     greeting_message, starter_questions, system_prompt, restriction_rules,
                     support_hours, last_training_summary)
                VALUES
                    (%s, %s, %s, %s, %s, %s, CAST(%s AS JSON), %s, %s, CAST(%s AS JSON), CAST(%s AS JSON))
                ON DUPLICATE KEY UPDATE
                    business_name = VALUES(business_name),
                    industry = VALUES(industry),
                    business_type = VALUES(business_type),
                    business_description = VALUES(business_description),
                    greeting_message = VALUES(greeting_message),
                    starter_questions = CAST(VALUES(starter_questions) AS JSON),
                    system_prompt = VALUES(system_prompt),
                    restriction_rules = VALUES(restriction_rules),
                    support_hours = CAST(VALUES(support_hours) AS JSON),
                    last_training_summary = CAST(VALUES(last_training_summary) AS JSON),
                    updated_at = NOW()
                """,
                (
                    tenant_id,
                    business_name,
                    industry,
                    business_type,
                    business_description,
                    greeting_message,
                    json.dumps(starter_questions, ensure_ascii=False),
                    system_prompt,
                    restriction_rules,
                    json.dumps(support_hours, ensure_ascii=False),
                    json.dumps(last_training_summary, ensure_ascii=False),
                ),
            )

            cur.execute(
                """
                UPDATE tenant_users
                SET name = %s,
                    industry = %s,
                    type = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (
                    business_name,
                    industry,
                    business_type,
                    current_user.get("user_id") or current_user.get("id"),
                    tenant_id,
                ),
            )
    finally:
        conn.close()

    row = _get_agent_settings_row(tenant_id)
    return {
        "success": True,
        "message": "Agent settings saved successfully.",
        "config": _normalize_agent_config(tenant, row),
    }


# ==========================================================
# WhatsApp Connection + Auto Reply APIs
# Supports both Meta WhatsApp Cloud API and Twilio WhatsApp.
# ==========================================================

class WhatsAppConnectRequest(BaseModel):
    provider: str
    meta_access_token: Optional[str] = None
    meta_phone_number_id: Optional[str] = None
    meta_business_account_id: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None


class SendWhatsAppTextRequest(BaseModel):
    to_phone: str
    message: str


class SendWhatsAppMediaRequest(BaseModel):
    to_phone: str
    media_url: str
    caption: Optional[str] = ""


@app.get("/connect-whatsapp")
def get_whatsapp_connection(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT whatsapp_provider, meta_phone_number_id, meta_business_account_id,
                       twilio_phone_number, whatsapp_number, whatsapp_verify_token,
                       CASE WHEN meta_access_token IS NULL OR meta_access_token='' THEN 0 ELSE 1 END AS has_meta_access_token,
                       CASE WHEN twilio_account_sid IS NULL OR twilio_account_sid='' THEN 0 ELSE 1 END AS has_twilio_account_sid,
                       CASE WHEN twilio_auth_token IS NULL OR twilio_auth_token='' THEN 0 ELSE 1 END AS has_twilio_auth_token
                FROM tenants
                WHERE id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone() or {}
    finally:
        conn.close()

    return {"success": True, "config": row}


@app.post("/connect-whatsapp")
def save_whatsapp_connection(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    provider = (req.provider or "").strip().lower()

    if provider not in ["meta", "twilio"]:
        raise HTTPException(status_code=400, detail="Provider must be meta or twilio.")

    meta_access_token = (req.meta_access_token or "").strip() or None
    meta_phone_number_id = (req.meta_phone_number_id or "").strip() or None
    meta_business_account_id = (req.meta_business_account_id or "").strip() or None
    twilio_account_sid = (req.twilio_account_sid or "").strip() or None
    twilio_auth_token = (req.twilio_auth_token or "").strip() or None
    twilio_phone_number = normalize_phone(req.twilio_phone_number or "") or None
    whatsapp_number = normalize_phone(req.whatsapp_number or "") or None
    whatsapp_verify_token = (req.whatsapp_verify_token or "").strip() or None

    if provider == "meta" and not meta_phone_number_id:
        raise HTTPException(status_code=400, detail="Meta phone number ID is required.")

    if provider == "twilio":
        if not twilio_account_sid or not twilio_auth_token:
            raise HTTPException(
                status_code=400,
                detail="Twilio Account SID and Auth Token are required.",
            )

        if not twilio_phone_number and whatsapp_number:
            twilio_phone_number = whatsapp_number

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants
                SET whatsapp_provider=%s,
                    meta_access_token=COALESCE(%s, meta_access_token),
                    meta_phone_number_id=%s,
                    meta_business_account_id=%s,
                    twilio_account_sid=COALESCE(%s, twilio_account_sid),
                    twilio_auth_token=COALESCE(%s, twilio_auth_token),
                    twilio_phone_number=%s,
                    whatsapp_number=%s,
                    whatsapp_verify_token=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (
                    provider,
                    meta_access_token,
                    meta_phone_number_id,
                    meta_business_account_id,
                    twilio_account_sid,
                    twilio_auth_token,
                    twilio_phone_number,
                    whatsapp_number,
                    whatsapp_verify_token,
                    tenant_id,
                ),
            )
    finally:
        conn.close()

    return {"success": True, "message": "WhatsApp connection saved successfully.", "provider": provider}




@app.get("/tenant/whatsapp-config")
def tenant_whatsapp_config(current_user: dict = Depends(get_current_user)):
    return get_whatsapp_connection(current_user)

@app.post("/tenant/active-agent-type")
def update_active_agent_type(
    req: ActiveAgentTypeRequest,
    current_user: dict = Depends(get_current_user),
):
    agent_type = (req.active_agent_type or "").strip().lower()

    if agent_type not in ["chat", "product"]:
        raise HTTPException(
            status_code=400,
            detail="active_agent_type must be chat or product.",
        )

    tenant_id = current_user["tenant_id"]

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants
                SET active_agent_type=%s,
                    updated_at=NOW()
                WHERE id=%s
                """,
                (agent_type, tenant_id),
            )
    finally:
        conn.close()

    return {
        "success": True,
        "active_agent_type": agent_type,
        "agent_type": agent_type,
    }


@app.get("/tenant/active-agent-type/{tenant_slug}")
def get_active_agent_type_public(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    active_agent_type = tenant.get("active_agent_type") or "chat"

    return {
        "success": True,
        "tenant_slug": tenant["slug"],
        "active_agent_type": active_agent_type,
        "agent_type": active_agent_type,
    }

@app.post("/tenant/whatsapp-config")
def tenant_save_whatsapp_config(req: WhatsAppConnectRequest, current_user: dict = Depends(get_current_user)):
    return save_whatsapp_connection(req, current_user)

@app.post("/send-whatsapp-message")
def send_whatsapp_message(req: SendWhatsAppTextRequest, current_user: dict = Depends(get_current_user)):
    if not req.to_phone or not req.message:
        raise HTTPException(status_code=400, detail="to_phone and message are required.")
    return send_whatsapp_text(current_user["tenant_id"], req.to_phone, req.message)


@app.post("/send-whatsapp-media")
def send_whatsapp_media_message(req: SendWhatsAppMediaRequest, current_user: dict = Depends(get_current_user)):
    if not req.to_phone or not req.media_url:
        raise HTTPException(status_code=400, detail="to_phone and media_url are required.")
    return send_whatsapp_media(current_user["tenant_id"], req.to_phone, req.media_url, req.caption or "")


@app.get("/webhook/whatsapp/{tenant_slug}")
@app.get("/webhooks/whatsapp/{tenant_slug}")
def verify_meta_webhook(tenant_slug: str, request: Request):
    # Meta webhook verification: hub.mode, hub.verify_token, hub.challenge
    mode = request.query_params.get("hub.mode")
    verify_token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
    expected_token = tenant.get("whatsapp_verify_token") or "agentive_verify_token_123"

    if mode == "subscribe" and verify_token == expected_token:
        return Response(content=str(challenge), media_type="text/plain")

    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@app.post("/webhook/whatsapp/{tenant_slug}")
@app.post("/webhooks/whatsapp/{tenant_slug}")
async def whatsapp_webhook(tenant_slug: str, request: Request):
    tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
    provider = tenant.get("whatsapp_provider")

    # Twilio sends form-urlencoded data. Meta sends JSON.
    content_type = request.headers.get("content-type", "")

    if provider == "twilio" or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        customer_phone = str(form.get("From") or "").replace("whatsapp:", "")
        incoming_message = str(form.get("Body") or "").strip()

        if not customer_phone or not incoming_message:
            return {"success": True, "message": "No text message to process."}

        return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

    data = await request.json()

    try:
        entry = (data.get("entry") or [])[0]
        change = (entry.get("changes") or [])[0]
        value = change.get("value") or {}
        message_obj = (value.get("messages") or [])[0]
        customer_phone = message_obj.get("from")
        incoming_message = (message_obj.get("text") or {}).get("body", "").strip()
    except Exception:
        return {"success": True, "message": "No supported Meta message to process."}

    if not customer_phone or not incoming_message:
        return {"success": True, "message": "No text message to process."}

    return handle_incoming_text_and_reply(tenant_slug, customer_phone, incoming_message)

# ==========================================================
# Contacts API
# Must stay ABOVE React fallback route
# ==========================================================
@app.get("/api/contacts")
def get_contacts(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]

    conn = get_main_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    session_id,
                    name,
                    email,
                    phone,
                    first_message,
                    last_message,
                    source,
                    status,
                    user_agent,
                    ip_address,
                    created_at,
                    updated_at,
                    last_seen_at
                FROM tenant_customers
                WHERE tenant_id=%s
                ORDER BY
                    last_seen_at DESC,
                    created_at DESC
                """,
                (tenant_id,),
            )

            contacts = cur.fetchall() or []

    finally:
        conn.close()

    return {
        "success": True,
        "total": len(contacts),
        "contacts": contacts,
    }

# ==========================================================
# Clean Public URL + React Frontend Route Fallback
# KEEP THESE AT THE VERY BOTTOM OF main.py
# ==========================================================

# @app.get("/public-link/resolve/{public_name}")
# def resolve_public_link(public_name: str):
#     resolved = _resolve_public_name(public_name)

#     if not resolved:
#         raise HTTPException(status_code=404, detail="Public link not found.")

#     return {
#         "success": True,
#         "tenant_slug": resolved["tenant_slug"],
#         "target_path": resolved["target_path"],
#     } 

@app.get("/public-link/resolve/{public_name}")
def resolve_public_link(public_name: str):
    resolved = _resolve_public_name(public_name)

    if not resolved:
        raise HTTPException(status_code=404, detail="Public link not found.")

    return {
        "success": True,
        "tenant_slug": resolved["tenant_slug"],
        "target_path": resolved["target_path"],
        "agent_type": resolved.get("active_agent_type") or "chat",
        "active_agent_type": resolved.get("active_agent_type") or "chat",
    }



# @app.get("/{public_name}")
# def open_clean_public_chat_url(public_name: str):
#     resolved = _resolve_public_name(public_name)
#     index_path = os.path.join(BUILD_DIR, "index.html")

#     if resolved:
#         if os.path.exists(index_path):
#             return FileResponse(index_path)

#         raise HTTPException(
#             status_code=404,
#             detail="React build index.html not found"
#         )

#     # IMPORTANT:
#     # if not a valid public link,
#     # do NOT return index here
#     raise HTTPException(status_code=404, detail="Page not found")



if os.path.exists(BUILD_DIR):

    @app.get("/{full_path:path}")
    def serve_react_routes(full_path: str):
        index_path = os.path.join(BUILD_DIR, "index.html")

        if os.path.exists(index_path):
            return FileResponse(index_path)

        raise HTTPException(status_code=404, detail="React build index.html not found")