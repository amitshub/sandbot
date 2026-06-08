# from typing import List, Optional, Union, Dict, Any
# from uuid import uuid4

# import os
# import pymysql
# from fastapi import APIRouter, Depends, HTTPException
# from pydantic import BaseModel

# from app.auth import get_current_user


# router = APIRouter(prefix="/product-query", tags=["Product Query Bot"])


# # ==========================================================
# # MAIN DB CONNECTION
# # This is your Railway/app DB where t_integration is stored.
# # Uses MAIN_DB_* first, with DB_* fallback.
# # ==========================================================
# def get_main_db_connection():
#     return pymysql.connect(
#         host=os.getenv("MAIN_DB_HOST") or os.getenv("DB_HOST"),
#         user=os.getenv("MAIN_DB_USER") or os.getenv("DB_USER"),
#         password=os.getenv("MAIN_DB_PASSWORD") or os.getenv("DB_PASSWORD"),
#         database=os.getenv("MAIN_DB_NAME") or os.getenv("DB_NAME"),
#         port=int(os.getenv("MAIN_DB_PORT") or os.getenv("DB_PORT") or 3306),
#         cursorclass=pymysql.cursors.DictCursor,
#         autocommit=True,
#     )


# def get_latest_integration_for_tenant(tenant_id: int, agent_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
#     """
#     Reads DB connection details saved from Integration page.
#     This table lives in your MAIN Railway DB.
#     """
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT
#                     id,
#                     tenant_id,
#                     tenant_slug,
#                     company_name,
#                     platform,
#                     db_host,
#                     db_port,
#                     db_user,
#                     db_password,
#                     db_name,
#                     website_url,
#                     status
#                 FROM t_integration
#                 WHERE tenant_id = %s
#                   AND (status IS NULL OR status = 'active')
#                 ORDER BY id DESC
#                 LIMIT 1
#                 """,
#                 (tenant_id,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()


# def get_tenant_product_db_connection(tenant_id: int, agent_id: Optional[int] = None):
#     """
#     Connects to the tenant/product DB using details saved in t_integration.
#     """
#     integration = get_latest_integration_for_tenant(tenant_id, agent_id=agent_id)

#     if not integration:
#         raise HTTPException(
#             status_code=404,
#             detail="No integration DB details found for this tenant. Please save Integration details first.",
#         )

#     required_fields = ["db_host", "db_user", "db_name"]
#     missing = [field for field in required_fields if not integration.get(field)]
#     if missing:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Integration DB details incomplete. Missing: {', '.join(missing)}",
#         )

#     try:
#         return pymysql.connect(
#             host=integration["db_host"],
#             user=integration["db_user"],
#             password=integration.get("db_password") or "",
#             database=integration["db_name"],
#             port=int(integration.get("db_port") or 3306),
#             cursorclass=pymysql.cursors.DictCursor,
#             autocommit=True,
#             connect_timeout=10,
#             read_timeout=20,
#             write_timeout=20,
#         )
#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Could not connect to tenant integration DB: {str(exc)}",
#         )


# def fetch_all_from_tenant_db(tenant_id: int, query: str, params: tuple = (), agent_id: Optional[int] = None):
#     conn = get_tenant_product_db_connection(tenant_id, agent_id=agent_id)
#     try:
#         with conn.cursor() as cur:
#             cur.execute(query, params)
#             return cur.fetchall()
#     finally:
#         conn.close()




# def get_tenant_by_slug(tenant_slug: str) -> Optional[Dict[str, Any]]:
#     tenant_slug = (tenant_slug or "").strip()
#     if not tenant_slug:
#         return None
#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             cur.execute(
#                 """
#                 SELECT id, slug, tenant_name, status
#                 FROM tenants
#                 WHERE slug = %s AND status = 'active'
#                 LIMIT 1
#                 """,
#                 (tenant_slug,),
#             )
#             return cur.fetchone()
#     finally:
#         conn.close()

# class ProductChatRequest(BaseModel):
#     query: str
#     session_id: Optional[str] = "default"


# class ProductChatResponse(BaseModel):
#     responses: List[str]
#     step: Union[int, float]
#     lookup_type: Optional[str] = None
#     selected_ticket_id: Optional[str] = None
#     selected_site_id: Optional[int] = None


# sessions: Dict[str, Dict[str, Any]] = {}

# PRODUCT_REDIRECT_LINK = "https://store1.desithread.co.in/update_model"

# BASE_ITEM_SELECT = """
#     SELECT
#         item_id,
#         barcode AS Barcode,
#         size AS Size,
#         color AS Color,
#         product_qty AS Qty,
#         item_name AS model
#     FROM item
# """


# def make_session_key(tenant_id: int, session_id: str):
#     return f"tenant_{tenant_id}::{session_id or 'default'}"


# def get_session(tenant_id: int, session_id: str):
#     key = make_session_key(tenant_id, session_id)
#     if key not in sessions:
#         sessions[key] = {
#             "step": 1,
#             "lookup_type": None,
#             "last_results": [],
#             "last_model": None,
#             "last_barcode": None,
#             "selected_ticket_id": None,
#             "selected_site_id": None,
#         }
#     return sessions[key]


# def reset_session(session):
#     session["step"] = 1
#     session["lookup_type"] = None
#     session["last_results"] = []
#     session["last_model"] = None
#     session["last_barcode"] = None
#     session["selected_ticket_id"] = None
#     session["selected_site_id"] = None


# def value_or_na(value):
#     if value is None or value == "":
#         return "N/A"
#     return value


# def search_items_by_model(tenant_id: int, model_number: str, agent_id: Optional[int] = None):
#     """
#     User enters model number.
#     Searches item.item_name and also barcode prefix, because barcode's first 4 digits are model number.
#     """
#     model_number = str(model_number).strip()
#     like_model = f"%{model_number}%"
#     barcode_prefix = f"{model_number}%"

#     query = BASE_ITEM_SELECT + """
#         WHERE item_name LIKE %s
#            OR barcode LIKE %s
#         ORDER BY item_id DESC
#         LIMIT 50
#     """
#     return fetch_all_from_tenant_db(tenant_id, query, (like_model, barcode_prefix), agent_id=agent_id)


# def search_items_by_barcode(tenant_id: int, barcode: str, agent_id: Optional[int] = None):
#     """
#     User enters barcode.
#     First 4 alphanumeric characters are used as model number.
#     """
#     clean_barcode = "".join(ch for ch in str(barcode).strip() if ch.isalnum())
#     model_number = clean_barcode[:4]

#     if len(model_number) < 4:
#         return [], model_number

#     return search_items_by_model(tenant_id, model_number, agent_id=agent_id), model_number


# def format_item_list(rows, model_number=None):
#     seen_barcodes = set()
#     unique_rows = []

#     for row in rows:
#         barcode = row.get("Barcode")
#         if barcode and barcode not in seen_barcodes:
#             seen_barcodes.add(barcode)
#             unique_rows.append(row)

#     lines = []

#     if model_number:
#         lines.append(f"✅ Model Number: {model_number}")

#     lines.append("📋 Items List")
#     lines.append("────────────────────")
#     lines.append("𝗡𝗼  𝗕𝗮𝗿𝗰𝗼𝗱𝗲   𝗦𝗶𝘇𝗲  𝗖𝗼𝗹𝗼𝗿   𝗤𝘁𝘆")
#     lines.append("────────────────────")

#     emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

#     for index, row in enumerate(unique_rows[:50], start=1):
#         no = emojis[index - 1] if index <= 10 else f"{index}."

#         barcode = str(value_or_na(row.get("Barcode"))).ljust(12)
#         size = str(value_or_na(row.get("Size"))).ljust(7)
#         color = str(value_or_na(row.get("Color"))).ljust(8)
#         qty = str(value_or_na(row.get("Qty")))

#         lines.append(f"{no}   {barcode}{size}{color}{qty}")

#     lines.append("")
#     lines.append("🔗 View Product List:")
#     lines.append(PRODUCT_REDIRECT_LINK)

#     return "\n".join(lines)


# def process_product_chat(query: str, session_id: str, tenant_id: int):
#     session = get_session(tenant_id, session_id)
#     user_query = (query or "").strip()
#     user_query_lower = user_query.lower()
#     responses = []

#     if not user_query:
#         return {
#             "responses": ["Please type your message."],
#             "step": session["step"],
#             "lookup_type": session.get("lookup_type"),
#             "selected_ticket_id": None,
#             "selected_site_id": None,
#         }

#     if session["step"] == 1:
#         if user_query_lower in ["yes", "y"]:
#             session["lookup_type"] = "model_number"
#             session["step"] = 2
#             responses.append("Please enter your Model Number")

#         elif user_query_lower in ["no", "n"]:
#             session["lookup_type"] = "barcode"
#             session["step"] = 2
#             responses.append(
#                 "Please enter Barcode. I will take first 4 numbers as Model Number and fetch the list."
#             )

#         else:
#             results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
#             session["last_model"] = user_query
#             session["last_results"] = results

#             if results:
#                 responses.append(format_item_list(results, user_query))
#             else:
#                 responses.append("No item found for this model number.")
#                 responses.append(f"🔗 View Product List:\n{PRODUCT_REDIRECT_LINK}")

#             session["step"] = 3

#     elif session["step"] == 2:
#         lookup_type = session.get("lookup_type")

#         if lookup_type == "barcode":
#             results, model_number = search_items_by_barcode(tenant_id, user_query, agent_id=agent_id)
#             session["last_barcode"] = user_query
#             session["last_model"] = model_number
#             session["last_results"] = results

#             if len(model_number) < 4:
#                 responses.append("Barcode should have at least 4 characters. Please enter valid Barcode.")
#                 session["step"] = 2

#             elif results:
#                 responses.append(f"Barcode received. Model Number: {model_number}")
#                 responses.append(format_item_list(results, model_number))
#                 session["step"] = 3

#             else:
#                 responses.append(f"No item found for Model Number: {model_number}")
#                 responses.append(f"🔗 View Product List:\n{PRODUCT_REDIRECT_LINK}")
#                 session["step"] = 3

#         else:
#             results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
#             session["last_model"] = user_query
#             session["last_results"] = results

#             if results:
#                 responses.append(format_item_list(results, user_query))
#             else:
#                 responses.append("No item found for this model number.")
#                 responses.append(f"🔗 View Product List:\n{PRODUCT_REDIRECT_LINK}")

#             session["step"] = 3

#     elif session["step"] == 3:
#         if user_query_lower in ["yes", "new search", "search again", "another", "new"]:
#             reset_session(session)
#             responses.append("New search started.")
#             responses.append("Do you have model number? Choose: Yes / No")

#         elif user_query_lower == "summary":
#             if session["last_results"]:
#                 responses.append(format_item_list(session["last_results"], session.get("last_model")))
#             else:
#                 responses.append("No result available.")

#         else:
#             results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
#             session["last_model"] = user_query
#             session["last_results"] = results

#             if results:
#                 responses.append(format_item_list(results, user_query))
#             else:
#                 responses.append("No item found for this model number.")
#                 responses.append(f"🔗 View Product List:\n{PRODUCT_REDIRECT_LINK}")

#             session["step"] = 3

#     else:
#         reset_session(session)
#         responses.append("Do you have model number? Choose: Yes / No")

#     return {
#         "responses": responses,
#         "step": session["step"],
#         "lookup_type": session.get("lookup_type"),
#         "selected_ticket_id": None,
#         "selected_site_id": None,
#     }


# @router.get("/health")
# def product_query_health(current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     integration = get_latest_integration_for_tenant(tenant_id, agent_id=agent_id)

#     return {
#         "success": True,
#         "online": True,
#         "tenant_id": tenant_id,
#         "integration_configured": bool(integration),
#     }


# @router.get("/item-list")
# def item_list(model: str, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     data = search_items_by_model(tenant_id, model.strip())
#     return {
#         "model": model,
#         "message": "Item data found" if data else "No item data found",
#         "redirect_link": PRODUCT_REDIRECT_LINK,
#         "items": data,
#     }


# @router.get("/item-list-by-barcode")
# def item_list_by_barcode(barcode: str, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]
#     data, model_number = search_items_by_barcode(tenant_id, barcode.strip())
#     return {
#         "barcode": barcode,
#         "model_number": model_number,
#         "message": "Item data found" if data else "No item data found",
#         "redirect_link": PRODUCT_REDIRECT_LINK,
#         "items": data,
#     }


# @router.post("/chat", response_model=ProductChatResponse)
# def product_query_chat(request: ProductChatRequest, current_user: dict = Depends(get_current_user)):
#     tenant_id = current_user["tenant_id"]

#     if not request.session_id:
#         request.session_id = str(uuid4())

#     return process_product_chat(
#         query=request.query,
#         session_id=request.session_id,
#         tenant_id=tenant_id,
#     )


# @router.get("/public-health/{tenant_slug}")
# def public_product_query_health(tenant_slug: str):
#     tenant = get_tenant_by_slug(tenant_slug)
#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
#     integration = get_latest_integration_for_tenant(tenant["id"], agent_id=agent_id)
#     return {
#         "success": True,
#         "online": True,
#         "tenant_id": tenant["id"],
#         "tenant_slug": tenant["slug"],
#         "integration_configured": bool(integration),
#     }


# @router.post("/public-chat/{tenant_slug}", response_model=ProductChatResponse)
# def public_product_query_chat(tenant_slug: str, request: ProductChatRequest):
#     tenant = get_tenant_by_slug(tenant_slug)
#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
#     session_id = request.session_id or str(uuid4())
#     return process_product_chat(
#         query=request.query,
#         session_id=session_id,
#         tenant_id=tenant["id"],
#     )

from typing import List, Optional, Union, Dict, Any
from uuid import uuid4

import os
import re
import json
import pymysql
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.index_builder import search_faiss
from app.session_store import load_product_session, save_product_session
from app.product_handlers import get_product_handler


router = APIRouter(prefix="/product-query", tags=["Product Query Bot"])


# ==========================================================
# MAIN DB CONNECTION
# This is your Railway/app DB where t_integration is stored.
# Uses MAIN_DB_* first, with DB_* fallback.
# ==========================================================
def get_main_db_connection():
    return pymysql.connect(
        host=os.getenv("MAIN_DB_HOST") or os.getenv("DB_HOST"),
        user=os.getenv("MAIN_DB_USER") or os.getenv("DB_USER"),
        password=os.getenv("MAIN_DB_PASSWORD") or os.getenv("DB_PASSWORD"),
        database=os.getenv("MAIN_DB_NAME") or os.getenv("DB_NAME"),
        port=int(os.getenv("MAIN_DB_PORT") or os.getenv("DB_PORT") or 3306),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def get_latest_integration_for_tenant(tenant_id: int, agent_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Reads DB connection details saved from Integration page.
    This table lives in your MAIN Railway DB.
    """
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    tenant_slug,
                    company_name,
                    platform,
                    db_host,
                    db_port,
                    db_user,
                    db_password,
                    db_name,
                    website_url,
                    agent_id,
                    status
                FROM t_integration
                WHERE tenant_id = %s
                  AND (%s IS NULL OR agent_id = %s)
                  AND (status IS NULL OR status = 'active')
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id, agent_id, agent_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_tenant_product_db_connection(tenant_id: int, agent_id: Optional[int] = None):
    """
    Connects to the tenant/product DB using details saved in t_integration.
    """
    integration = get_latest_integration_for_tenant(tenant_id, agent_id=agent_id)

    if not integration:
        raise HTTPException(
            status_code=404,
            detail="No integration DB details found for this tenant. Please save Integration details first.",
        )

    required_fields = ["db_host", "db_user", "db_name"]
    missing = [field for field in required_fields if not integration.get(field)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Integration DB details incomplete. Missing: {', '.join(missing)}",
        )

    try:
        return pymysql.connect(
            host=integration["db_host"],
            user=integration["db_user"],
            password=integration.get("db_password") or "",
            database=integration["db_name"],
            port=int(integration.get("db_port") or 3306),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=20,
            write_timeout=20,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not connect to tenant integration DB: {str(exc)}",
        )


def fetch_all_from_tenant_db(tenant_id: int, query: str, params: tuple = (), agent_id: Optional[int] = None):
    conn = get_tenant_product_db_connection(tenant_id, agent_id=agent_id)
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()




def get_tenant_by_slug(tenant_slug: str) -> Optional[Dict[str, Any]]:
    tenant_slug = (tenant_slug or "").strip()
    if not tenant_slug:
        return None
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, tenant_name, status
                FROM tenants
                WHERE slug = %s AND status = 'active'
                LIMIT 1
                """,
                (tenant_slug,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_agent_for_tenant(tenant_id: int, agent_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if not agent_id:
        return None
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, tenant_id, agent_type, agent_name, status, handler_key
                FROM tenant_agents
                WHERE tenant_id=%s AND id=%s
                LIMIT 1
                """,
                (tenant_id, agent_id),
            )
            return cur.fetchone()
    finally:
        conn.close()

class ProductChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"
    agent_id: Optional[int] = None


class ProductChatResponse(BaseModel):
    responses: List[str]
    step: Union[int, float]
    lookup_type: Optional[str] = None
    selected_ticket_id: Optional[str] = None
    selected_site_id: Optional[int] = None
    starter_questions: Optional[List[str]] = []
    tenant_name: Optional[str] = None
    agent_name: Optional[str] = None
    product_image: Optional[str] = None


PRODUCT_REDIRECT_LINK = os.getenv("PRODUCT_REDIRECT_LINK", "https://store1.desithread.co.in/update_model")

DEFAULT_PRODUCT_GREETING = "Hello, how can I help you today?"

# Sales enquiry is controlled from tenants.enable_sales_enquiry.
# Logged-in flow uses current_user["tenant_id"].
# Public URL flow resolves tenant_slug -> tenant_id, then uses the same check.


def _json_load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _get_table_columns(cur, table_name: str) -> set:
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name}")
        return {row.get("Field") for row in cur.fetchall() or []}
    except Exception:
        return set()


def get_product_agent_settings(tenant_id: int, agent_id: Optional[int] = None) -> Dict[str, Any]:
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant_cols = _get_table_columns(cur, "tenants")
            settings_cols = _get_table_columns(cur, "tenant_agent_settings")

            tenant_selects = ["t.tenant_name"]
            for col in ["support_phone", "phone", "support_email", "email", "website_url", "website", "address"]:
                if col in tenant_cols:
                    tenant_selects.append(f"t.{col}")

            settings_selects = []
            for col in [
                "business_name", "industry", "business_type", "business_description",
                "allowed_scope", "blocked_claims", "greeting_message", "starter_questions",
                "system_prompt", "restriction_rules", "support_hours",
            ]:
                settings_selects.append(f"tas.{col}" if col in settings_cols else f"NULL AS {col}")

            sql = f"""
                SELECT
                    {", ".join(settings_selects)},
                    {", ".join(tenant_selects)},
                    ta.agent_name AS agent_name
                FROM tenants t
                LEFT JOIN tenant_agents ta
                    ON ta.tenant_id = t.id
                   AND ta.id = %s
                LEFT JOIN tenant_agent_settings tas
                    ON tas.tenant_id = t.id
                   AND tas.agent_type = 'product'
                   AND (%s IS NULL OR tas.agent_id = %s)
                WHERE t.id=%s
                ORDER BY CASE WHEN tas.agent_id = %s THEN 0 WHEN tas.agent_id IS NULL THEN 1 ELSE 2 END
                LIMIT 1
            """
            cur.execute(sql, (agent_id, agent_id, agent_id, tenant_id, agent_id))
            row = cur.fetchone() or {}
    finally:
        conn.close()

    business_name = (row.get("business_name") or row.get("tenant_name") or "our team").strip()
    return {
        "business_name": business_name,
        "tenant_name": row.get("tenant_name") or business_name,
        "agent_name": row.get("agent_name") or business_name,
        "industry": row.get("industry") or "",
        "business_type": row.get("business_type") or "product_seller",
        "business_description": row.get("business_description") or "",
        "allowed_scope": row.get("allowed_scope") or "product information, specifications, availability guidance, catalogue details, and technical product support",
        "blocked_claims": row.get("blocked_claims") or "unconfirmed pricing, unconfirmed availability, unconfirmed warranty, and anything not present in trained data or product database",
        "greeting_message": (row.get("greeting_message") or "").strip(),
        "starter_questions": _json_load(row.get("starter_questions"), default=[]) or [],
        "system_prompt": row.get("system_prompt") or "",
        "restriction_rules": row.get("restriction_rules") or "",
    }


def get_text_from_result(item: Dict[str, Any]) -> str:
    return (
        item.get("text")
        or item.get("chunk_text")
        or item.get("content")
        or item.get("page_content")
        or item.get("body")
        or item.get("description")
        or ""
    ).strip()


def build_context(results: List[Dict[str, Any]], max_chars: int = 1800) -> str:
    parts = []
    total = 0
    for idx, item in enumerate(results or [], start=1):
        text = get_text_from_result(item)
        if not text:
            continue
        source = item.get("url") or item.get("file_name") or item.get("title") or "trained product data"
        block = f"[Source {idx}: {source}]\n{text}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def clean_ai_reply(reply: str) -> str:
    text = re.sub(r"\s+", " ", (reply or "").strip())
    text = re.sub(r"^(based on|according to) (the )?(context|provided information|knowledge base),?\s*", "", text, flags=re.I)
    return text.strip()


def looks_like_product_lookup_query(message: str) -> bool:
    value = (message or "").strip()
    if not value:
        return False
    lowered = value.lower()
    if lowered in {
        "1", "2",
        "yes", "y", "no", "n",
        "model", "model number", "model_number",
        "sales", "sale", "sales enquiry", "sales_enquiry",
        "summary", "new", "new search", "search again", "another"
    }:
        return True
    if any(mark in lowered for mark in ["?", "tell me", "what ", "how ", "why ", "which ", "recommend", "suggest"]):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{2,40}", value))


def is_sales_enquiry_enabled_for_tenant(tenant_id: int, agent_id: Optional[int] = None) -> bool:
    """
    Enable sales enquiry automatically for product tenants.
    No hardcoded slug.
    """

    conn = get_main_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.slug, ta.agent_type AS active_agent_type
                FROM tenants t
                LEFT JOIN tenant_agents ta ON ta.tenant_id=t.id AND ta.id=%s
                WHERE t.id = %s
                  AND t.status = 'active'
                LIMIT 1
                """,
                (agent_id, tenant_id),
            )

            row = cur.fetchone() or {}

            slug = (row.get("slug") or "").strip()
            agent_type = (row.get("active_agent_type") or "").strip().lower()

            if not agent_type:
                cur.execute("""
                    SELECT id
                    FROM t_integration
                    WHERE tenant_id=%s
                    ORDER BY id DESC
                    LIMIT 1
                """, (tenant_id,))
                if cur.fetchone():
                    agent_type = "product"
                else:
                    agent_type = "chat"

            print("[SALES FLOW]", tenant_id, slug, agent_type)

            # only product agents get sales enquiry
            return agent_type == "product"

    except Exception as exc:
        print("[SALES ENQUIRY ERROR]", repr(exc))
        return False

    finally:
        conn.close()

def build_product_welcome(settings: Dict[str, Any], sales_enquiry_enabled: bool = False) -> str:
    """
    Product bot first message.
    This should only use greeting saved from Customize screen.
    Do not append hardcoded options here.
    Starter questions are returned separately in starter_questions.
    """
    return (settings.get("greeting_message") or "").strip() or DEFAULT_PRODUCT_GREETING
# def build_product_welcome(settings: Dict[str, Any], sales_enquiry_enabled: bool = False) -> str:
#     """
#     Product bot first message.
#     The base greeting always comes from Customize screen (tenant_agent_settings.greeting_message).
#     Quick option labels are appended so ChatBot.js can show buttons.
#     """
#     greeting = (settings.get("greeting_message") or "").strip() or DEFAULT_PRODUCT_GREETING

#     if sales_enquiry_enabled:
#         return (
#             f"{greeting}\n\n"
#             "Please choose an option:\n"
#             "1. Model Number\n"
#             "2. Sales Enquiry"
#         )

#     return (
#         f"{greeting}\n\n"
#         "Please choose an option:\n"
#         "1. Model Number"
#     )


# def build_continue_options(sales_enquiry_enabled: bool = False) -> str:
#     if sales_enquiry_enabled:
#         return (
#             "Would you like to enquire again?\n"
#             "1. Model Number\n"
#             "2. Sales Enquiry"
#         )
#     return (
#         "Would you like to search another model?\n"
#         "1. Model Number"
#     )

def build_continue_options(sales_enquiry_enabled: bool = False):
    if sales_enquiry_enabled:
        return (
            "Would you like to enquire again?\n"
            "1. Model Details\n"
            "2. Model Sales"
        )
    return (
        "Would you like to search another model?\n"
        "1. Model Details"
    )


# def is_model_number_choice(value: str) -> bool:
#     return (value or "").strip().lower() in {
#         "1", "model", "model number", "model_number", "model no", "model no.", "yes", "y"
#     }
def is_model_number_choice(value: str) -> bool:
    return (value or "").strip().lower() in {
        "1", "model details", "model detail", "model", "model number",
        "model_number", "model no", "model no.", "yes", "y"
    }

# def is_sales_enquiry_choice(value: str) -> bool:
#     return (value or "").strip().lower() in {
#         "2", "sales", "sale", "sales enquiry", "sales_enquiry", "enquiry", "inquiry"
#     }
def is_sales_enquiry_choice(value: str) -> bool:
    return (value or "").strip().lower() in {
        "2", "model sales", "model sale", "sales", "sale",
        "sales enquiry", "sales_enquiry", "enquiry", "inquiry"
    }


def build_product_sales_reply(message: str, tenant_id: int, settings: Dict[str, Any], history: List[Dict[str, str]] = None) -> str:
    context = ""
    try:
        results = search_faiss(message, tenant_id=tenant_id, top_k=8)
        context = build_context(results)
    except Exception as exc:
        print("[PRODUCT FAISS ERROR]", repr(exc))

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        if context:
            return clean_ai_reply(get_text_from_result({"text": context})[:450])
        return "Please share the product name, model number, or requirement, and I will guide you with the right details."

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    business_name = settings.get("business_name") or "our team"
    prompt = f"""
You are a helpful sales and technical product assistant for {business_name}.
Represent only this tenant/company. Do not use hardcoded company facts.

Tenant business controls:
- Industry: {settings.get("industry") or "General"}
- Business type: {settings.get("business_type") or "product_seller"}
- Business description: {settings.get("business_description") or ""}
- Allowed scope: {settings.get("allowed_scope") or ""}
- Blocked claims: {settings.get("blocked_claims") or ""}

Rules:
- Use the FAISS trained reference below when available.
- Also respect the product database lookup flow; if the customer has a model number or barcode, ask them to share it.
- Do not invent prices, stock, warranty, delivery, or specifications.
- Do not mention AI, FAISS, tenant, knowledge base, or context.
- Keep the answer short, practical, and sales-helpful.
- If trained reference is missing for exact details, ask one useful follow-up question or say you will check with the team.

Tenant custom instructions:
{settings.get("system_prompt") or ""}

Tenant restriction rules:
{settings.get("restriction_rules") or ""}

Private FAISS trained reference:
{context if context else "[NO MATCHING TRAINED REFERENCE FOUND]"}

Customer message:
{message}

Write the best short reply.
""".strip()
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are a safe product sales and technical assistant for {business_name}. Use tenant FAISS reference and never invent business facts."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 150,
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        return clean_ai_reply(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    except Exception as exc:
        print("[PRODUCT GROQ ERROR]", repr(exc))
        return "Please share the model number, barcode, or product requirement, and I will help you find the right details."

BASE_ITEM_SELECT = """
    SELECT
        i.item_id,
        i.barcode AS Barcode,

        COALESCE(ms.name, i.size) AS Size,

        COALESCE(mc.name, i.color) AS Color,

        COALESCE(i.product_qty, 0) AS Qty,
        i.item_name AS model,
        i.is_feature_item AS is_feature_item,
        i.item_simage AS item_simage

    FROM item i

    LEFT JOIN master ms
        ON i.size = ms.id
       AND ms.title = 'size'

    LEFT JOIN master mc
        ON i.color = mc.id
       AND mc.title = 'color'
"""


def default_product_session():
    return {
        "step": 1,
        "intent": None,
        "lookup_type": None,
        "last_results": [],
        "last_model": None,
        "last_barcode": None,
        "selected_ticket_id": None,
        "selected_site_id": None,
    }


def get_session(tenant_id: int, session_id: str, agent_id: Optional[int] = None):
    return load_product_session(tenant_id, session_id or "default", default_product_session(), agent_id=agent_id)


def persist_session(tenant_id: int, session_id: str, session: Dict[str, Any], agent_id: Optional[int] = None) -> None:
    save_product_session(tenant_id, session_id or "default", session, agent_id=agent_id)


def reset_session(session):
    session["step"] = 1
    session["intent"] = None
    session["lookup_type"] = None
    session["last_results"] = []
    session["last_model"] = None
    session["last_barcode"] = None
    session["selected_ticket_id"] = None
    session["selected_site_id"] = None


def get_product_greeting_message(tenant_id: int) -> str:
    """Fetch product-bot greeting saved from Customize screen for this tenant."""
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT greeting_message
                FROM tenant_agent_settings
                WHERE tenant_id = %s
                  AND agent_type = 'product'
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone() or {}
            return (row.get("greeting_message") or "").strip()
    except Exception as exc:
        print("[PRODUCT GREETING ERROR]", repr(exc))
        return ""
    finally:
        conn.close()


def get_product_redirect_link(tenant_id: int, agent_id: Optional[int] = None) -> str:
    integration = get_latest_integration_for_tenant(tenant_id, agent_id=agent_id)
    website_url = (integration or {}).get("website_url")
    return (website_url or PRODUCT_REDIRECT_LINK).strip()


def value_or_na(value):
    if value is None or value == "":
        return "0"
    return value


def get_agent_handler_key(tenant_id: int, agent_id: Optional[int] = None) -> str:
    """Fetch handler_key for the selected product agent.

    The handler_key decides which product handler file is used, for example:
    - desipos -> app/product_handlers/desipos.py
    - desithread -> app/product_handlers/desithread.py
    """
    agent = get_agent_for_tenant(tenant_id, agent_id) if agent_id else None
    return str((agent or {}).get("handler_key") or "").strip().lower()


def get_feature_product_image(rows, handler_key: Optional[str] = None):
    """Return full feature image URL using the selected product handler.

    product_query_bot.py stays generic. The handler builds tenant/agent-specific
    image URLs from .env, based on handler_key.
    """
    handler = get_product_handler(handler_key)
    return handler.get_feature_product_image(rows)


def should_show_product_link(handler_key: Optional[str] = None) -> bool:
    """Ask selected handler whether product list link should be shown.

    This keeps product_query_bot.py generic. No tenant/agent name is hardcoded here.
    """
    handler = get_product_handler(handler_key)
    return handler.should_show_product_link()


def search_items_by_model(tenant_id: int, model_number: str, agent_id: Optional[int] = None):
    """
    User enters model number.
    Searches item.item_name and also barcode prefix, because barcode's first 4 digits are model number.
    """
    model_number = str(model_number).strip()
    like_model = f"%{model_number}%"
    barcode_prefix = f"{model_number}%"

    query = BASE_ITEM_SELECT + """
    WHERE i.item_name LIKE %s
       OR i.barcode LIKE %s
    ORDER BY i.item_id DESC
    LIMIT 50
    """
    return fetch_all_from_tenant_db(tenant_id, query, (like_model, barcode_prefix), agent_id=agent_id)


def search_items_by_barcode(tenant_id: int, barcode: str, agent_id: Optional[int] = None):
    """
    User enters barcode.
    First 4 alphanumeric characters are used as model number.
    """
    clean_barcode = "".join(ch for ch in str(barcode).strip() if ch.isalnum())
    model_number = clean_barcode[:4]

    if len(model_number) < 4:
        return [], model_number

    return search_items_by_model(tenant_id, model_number, agent_id=agent_id), model_number
# def format_item_list(rows, model_number=None, redirect_link=""):
#     if not rows:
#         return "No matching items found."

#     emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
#               "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

#     lines = []

#     if model_number:
#         lines.append(f"✅ Model Number: {model_number}")
#         lines.append("")

#     lines.append("📋 Items List")
#     lines.append("")

#     for idx, row in enumerate(rows, start=1):
#         emoji = emojis[idx - 1] if idx <= len(emojis) else f"{idx}."

#         barcode = str(row.get("Barcode") or "N/A")
#         size = str(row.get("Size") or "N/A")
#         color = str(row.get("Color") or "N/A")
#         qty = str(row.get("Qty") or "0")

#         lines.append(f"{emoji} Barcode: {barcode}")
#         lines.append(f"   Size: {size} | Color: {color} | Qty: {qty}")

#     lines.append("")
#     lines.append("🔗 View Product List:")
#     lines.append(redirect_link or PRODUCT_REDIRECT_LINK)

#     return "\n".join(lines)

# def format_item_list(rows, model_number=None, redirect_link=""):
#     if not rows:
#         return "No matching items found."

#     lines = []

#     # Model Number
#     if model_number:
#         lines.append(f"✅ Model: {model_number}")
#         lines.append("")

#     # Title
#     lines.append("📋 Items")
#     lines.append("────────────────────────")

#     # Compact Header
#     lines.append("No  Barcode   Size  Qty")
#     lines.append("────────────────────────")

#     # Rows
#     for idx, row in enumerate(rows, start=1):

#         barcode = str(row.get("Barcode") or "N/A")
#         size = str(row.get("Size") or "N/A")
#         qty = str(row.get("Qty") or "0")

#         lines.append(
#             f"{idx:<3} {barcode:<9} {size:<5} {qty:>3}"
#         )

#     # Link
#     lines.append("────────────────────────")
#     lines.append("🔗 Product List")
#     lines.append(redirect_link or PRODUCT_REDIRECT_LINK)

#     return "\n".join(lines)

def format_item_list(rows, model_number=None, redirect_link: str = "", show_product_link: bool = True):
    unique_rows = rows or []

    lines = []

    if model_number:
        lines.append(f"✅ Model Number: {model_number}")

    lines.append("📋 Items List")
    lines.append("──────────────────────────────────────")
    lines.append("No   Barcode      Size    Color     Qty")
    lines.append("──────────────────────────────────────")

    for index, row in enumerate(unique_rows[:50], start=1):
        no = str(index)

        barcode = str(value_or_na(row.get("Barcode")))[:10]
        size = str(value_or_na(row.get("Size")))[:6]
        color = str(value_or_na(row.get("Color")))[:8]
        qty = str(value_or_na(row.get("Qty")))

        lines.append(
            f"{no:<4}{barcode:<12}{size:<8}{color:<9}{qty:>3}"
        )

    if show_product_link:
        lines.append("")
        lines.append("🔗 View Product List:")
        lines.append(redirect_link or PRODUCT_REDIRECT_LINK)

    return "\n".join(lines)



def search_last_10_sales_by_model(tenant_id: int, model_number: str, agent_id: Optional[int] = None):
    """
    Finds last 10 sold rows for a model number.
    Model number is matched as barcode prefix, e.g. 2020 -> 2020%.
    Uses bill_details.bill_date, with date_created fallback.
    """
    model_number = str(model_number or "").strip()
    if not model_number:
        return []

    barcode_prefix = f"{model_number}%"

    query = """
        SELECT
            COALESCE(bd.bill_date, DATE(bd.date_created)) AS Date,
            bd.bill_number AS BillNo,
            i.barcode AS Barcode,
            COALESCE(ms.name, i.size) AS Size,
            COALESCE(mc.name, i.color) AS Color,
            bi.item_qty AS Qty
        FROM bill_items bi

        JOIN bill_details bd
            ON bi.bill_id = bd.bill_id

        JOIN item i
            ON bi.item_id = i.item_id

        LEFT JOIN master ms
            ON i.size = ms.id
           AND ms.title = 'size'

        LEFT JOIN master mc
            ON i.color = mc.id
           AND mc.title = 'color'

        WHERE i.barcode LIKE %s

        ORDER BY COALESCE(bd.bill_date, DATE(bd.date_created)) DESC,
                 bi.tbl_id DESC

        LIMIT 10
    """
    return fetch_all_from_tenant_db(tenant_id, query, (barcode_prefix,), agent_id=agent_id)


def format_sales_list(rows, model_number=None):
    lines = []

    if model_number:
        lines.append(f"✅ Last 10 Sales for Model Number: {model_number}")

    lines.append("📋 Sales List")
    lines.append("──────────────────────────────────────────────────────────────")
    lines.append(
        f"{'No':<4}{'Date':<12}{'Bill No':<14}{'Barcode':<12}{'Size':<8}{'Color':<9}{'Qty':>3}"
    )
    lines.append("──────────────────────────────────────────────────────────────")

    for index, row in enumerate((rows or [])[:10], start=1):
        no = str(index)

        sale_date = str(value_or_na(row.get("Date")))[:10]
        bill_no = str(value_or_na(row.get("BillNo")))[:13]
        barcode = str(value_or_na(row.get("Barcode")))[:10]
        size = str(value_or_na(row.get("Size")))[:6]
        color = str(value_or_na(row.get("Color")))[:8]
        qty = str(value_or_na(row.get("Qty")))

        lines.append(
            f"{no:<4}{sale_date:<12}{bill_no:<14}{barcode:<12}{size:<8}{color:<9}{qty:>3}"
        )

    return "\n".join(lines)

def process_product_chat(query: str, session_id: str, tenant_id: int, agent_id: Optional[int] = None):
    session = get_session(tenant_id, session_id, agent_id=agent_id)
    redirect_link = get_product_redirect_link(tenant_id, agent_id=agent_id)
    settings = get_product_agent_settings(tenant_id, agent_id=agent_id)
    handler_key = get_agent_handler_key(tenant_id, agent_id=agent_id)
    show_product_link = should_show_product_link(handler_key)
    sales_enquiry_enabled = is_sales_enquiry_enabled_for_tenant(tenant_id, agent_id=agent_id)
    user_query = (query or "").strip()
    user_query_lower = user_query.lower()
    responses = []
    product_image = ""
    if user_query == "__welcome__":
        reset_session(session)
        persist_session(tenant_id, session_id, session, agent_id=agent_id)

        # return {
        #     "responses": [build_product_welcome(settings, sales_enquiry_enabled)],
        #     "step": session["step"],
        #     "lookup_type": session.get("lookup_type"),
        #     "selected_ticket_id": None,
        #     "selected_site_id": None,
        # }
        return {
        "responses": [build_product_welcome(settings, sales_enquiry_enabled)],
        "starter_questions": settings.get("starter_questions", []),
        "tenant_name": settings.get("tenant_name"),
        "agent_name": settings.get("agent_name"),
        "step": session["step"],
        "lookup_type": session.get("lookup_type"),
        "selected_ticket_id": None,
        "selected_site_id": None,
        "product_image": None,
    }

    if not user_query:
        return {
            "responses": ["Please type your message."],
            "step": session["step"],
            "lookup_type": session.get("lookup_type"),
            "selected_ticket_id": None,
            "selected_site_id": None,
            "product_image": None,
        }

    if session["step"] == 1:
        if is_model_number_choice(user_query):
            session["lookup_type"] = "model_number"
            session["step"] = 2
            responses.append("Please enter your Model Number")

        elif is_sales_enquiry_choice(user_query) and sales_enquiry_enabled:
            session["lookup_type"] = "sales"
            session["intent"] = "sales_enquiry"
            session["step"] = 2
            responses.append("Please enter Model Number to check last 10 sales")

        elif is_sales_enquiry_choice(user_query) and not sales_enquiry_enabled:
            responses.append("Sales enquiry is not enabled for this product agent. Please choose Model Number.")

        elif user_query_lower in ["no", "n", "barcode"]:
            session["lookup_type"] = "barcode"
            session["step"] = 2
            responses.append(
                "Please enter Barcode. I will take first 4 numbers as Model Number and fetch the list."
            )

        elif not looks_like_product_lookup_query(user_query):
            responses.append(build_product_sales_reply(user_query, tenant_id, settings))

        else:
            results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
            session["last_model"] = user_query
            session["last_results"] = results
            product_image = get_feature_product_image(results, handler_key)

            if results:
                responses.append(format_item_list(results, user_query, redirect_link, show_product_link))
            else:
                responses.append("No item found for this model number.")
                if show_product_link:
                    responses.append(f"🔗 View Product List:\n{redirect_link}")

            reset_session(session)
            responses.append(build_continue_options(sales_enquiry_enabled))

    elif session["step"] == 2:
        lookup_type = session.get("lookup_type")

        if lookup_type == "sales" and sales_enquiry_enabled:
            results = search_last_10_sales_by_model(tenant_id, user_query, agent_id=agent_id)
            session["last_model"] = user_query
            session["last_results"] = results

            # Sales query does not return item_simage, so fetch matching item rows
            # only to build the feature product image dynamically.
            image_rows = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
            product_image = get_feature_product_image(image_rows, handler_key)

            if results:
                responses.append(format_sales_list(results, user_query))
            else:
                responses.append(f"No sales found for Model Number: {user_query}")

            reset_session(session)
            responses.append(build_continue_options(sales_enquiry_enabled))

        elif lookup_type == "barcode":
            results, model_number = search_items_by_barcode(tenant_id, user_query, agent_id=agent_id)
            session["last_barcode"] = user_query
            session["last_model"] = model_number
            session["last_results"] = results
            product_image = get_feature_product_image(results, handler_key)

            if len(model_number) < 4:
                responses.append("Barcode should have at least 4 characters. Please enter valid Barcode.")
                session["step"] = 2

            elif results:
                responses.append(f"Barcode received. Model Number: {model_number}")
                responses.append(format_item_list(results, model_number, redirect_link, show_product_link))
                reset_session(session)
                responses.append(build_continue_options(sales_enquiry_enabled))

            else:
                responses.append(f"No item found for Model Number: {model_number}")
                if show_product_link:
                    responses.append(f"🔗 View Product List:\n{redirect_link}")
                reset_session(session)
                responses.append(build_continue_options(sales_enquiry_enabled))

        else:
            results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
            session["last_model"] = user_query
            session["last_results"] = results
            product_image = get_feature_product_image(results, handler_key)

            if results:
                responses.append(format_item_list(results, user_query, redirect_link, show_product_link))
            else:
                responses.append("No item found for this model number.")
                if show_product_link:
                    responses.append(f"🔗 View Product List:\n{redirect_link}")

            reset_session(session)
            responses.append(build_continue_options(sales_enquiry_enabled))

    elif session["step"] == 3:
        if user_query_lower in ["yes", "new search", "search again", "another", "new"]:
            reset_session(session)
            responses.append("New search started.")
            responses.append(build_product_welcome(settings, sales_enquiry_enabled))

        elif user_query_lower == "summary":
            if session["last_results"]:
                product_image = get_feature_product_image(session["last_results"], handler_key)
                responses.append(format_item_list(session["last_results"], session.get("last_model"), redirect_link, show_product_link))
            else:
                responses.append("No result available.")

        elif not looks_like_product_lookup_query(user_query):
            responses.append(build_product_sales_reply(user_query, tenant_id, settings))

        else:
            results = search_items_by_model(tenant_id, user_query, agent_id=agent_id)
            session["last_model"] = user_query
            session["last_results"] = results
            product_image = get_feature_product_image(results, handler_key)

            if results:
                responses.append(format_item_list(results, user_query, redirect_link, show_product_link))
            else:
                responses.append("No item found for this model number.")
                if show_product_link:
                    responses.append(f"🔗 View Product List:\n{redirect_link}")

            reset_session(session)
            responses.append(build_continue_options(sales_enquiry_enabled))

    else:
        reset_session(session)
        responses.append(build_product_welcome(settings, sales_enquiry_enabled))

    persist_session(tenant_id, session_id, session, agent_id=agent_id)

    return {
        "responses": responses,
        "step": session["step"],
        "lookup_type": session.get("lookup_type"),
        "selected_ticket_id": None,
        "selected_site_id": None,
        "product_image": product_image or None,
    }


@router.get("/health")
def product_query_health(agent_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    integration = get_latest_integration_for_tenant(tenant_id, agent_id=agent_id)

    return {
        "success": True,
        "online": True,
        "tenant_id": tenant_id,
        "integration_configured": bool(integration),
    }


@router.get("/item-list")
def item_list(model: str, agent_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    data = search_items_by_model(tenant_id, model.strip(), agent_id=agent_id)
    redirect_link = get_product_redirect_link(tenant_id, agent_id=agent_id)
    return {
        "model": model,
        "message": "Item data found" if data else "No item data found",
        "redirect_link": redirect_link,
        "product_image": get_feature_product_image(data, get_agent_handler_key(tenant_id, agent_id=agent_id)),
        "items": data,
    }



@router.get("/last-10-sales")
def last_10_sales(model: str, agent_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    if not is_sales_enquiry_enabled_for_tenant(tenant_id, agent_id=agent_id):
        raise HTTPException(status_code=403, detail="Sales enquiry is not enabled for this tenant.")
    data = search_last_10_sales_by_model(tenant_id, model.strip(), agent_id=agent_id)
    return {
        "model": model,
        "message": "Sales data found" if data else "No sales data found",
        "items": data,
    }

@router.get("/item-list-by-barcode")
def item_list_by_barcode(barcode: str, agent_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    data, model_number = search_items_by_barcode(tenant_id, barcode.strip(), agent_id=agent_id)
    redirect_link = get_product_redirect_link(tenant_id, agent_id=agent_id)
    return {
        "barcode": barcode,
        "model_number": model_number,
        "message": "Item data found" if data else "No item data found",
        "redirect_link": redirect_link,
        "product_image": get_feature_product_image(data, get_agent_handler_key(tenant_id, agent_id=agent_id)),
        "items": data,
    }


@router.post("/chat", response_model=ProductChatResponse)
def product_query_chat(request: ProductChatRequest, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]

    if not request.session_id:
        request.session_id = str(uuid4())

    return process_product_chat(
        query=request.query,
        session_id=request.session_id,
        tenant_id=tenant_id,
        agent_id=request.agent_id,
    )


@router.get("/public-health/{tenant_slug}")
def public_product_query_health(tenant_slug: str, agent_id: Optional[int] = None):
    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
    integration = get_latest_integration_for_tenant(tenant["id"], agent_id=agent_id)
    return {
        "success": True,
        "online": True,
        "tenant_id": tenant["id"],
        "tenant_slug": tenant["slug"],
        "integration_configured": bool(integration),
    }


@router.post("/public-chat/{tenant_slug}", response_model=ProductChatResponse)
def public_product_query_chat(tenant_slug: str, request: ProductChatRequest):
    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

    selected_agent = get_agent_for_tenant(tenant["id"], request.agent_id) if request.agent_id else None
    if request.agent_id and (not selected_agent or (selected_agent.get("status") or "").strip().lower() != "active"):
        raise HTTPException(status_code=404, detail="This agent is inactive.")

    session_id = request.session_id or str(uuid4())
    return process_product_chat(
        query=request.query,
        session_id=session_id,
        tenant_id=tenant["id"],
        agent_id=request.agent_id,
    )
