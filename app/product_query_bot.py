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


# def get_latest_integration_for_tenant(tenant_id: int) -> Optional[Dict[str, Any]]:
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


# def get_tenant_product_db_connection(tenant_id: int):
#     """
#     Connects to the tenant/product DB using details saved in t_integration.
#     """
#     integration = get_latest_integration_for_tenant(tenant_id)

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


# def fetch_all_from_tenant_db(tenant_id: int, query: str, params: tuple = ()):
#     conn = get_tenant_product_db_connection(tenant_id)
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


# def search_items_by_model(tenant_id: int, model_number: str):
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
#     return fetch_all_from_tenant_db(tenant_id, query, (like_model, barcode_prefix))


# def search_items_by_barcode(tenant_id: int, barcode: str):
#     """
#     User enters barcode.
#     First 4 alphanumeric characters are used as model number.
#     """
#     clean_barcode = "".join(ch for ch in str(barcode).strip() if ch.isalnum())
#     model_number = clean_barcode[:4]

#     if len(model_number) < 4:
#         return [], model_number

#     return search_items_by_model(tenant_id, model_number), model_number


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
#             results = search_items_by_model(tenant_id, user_query)
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
#             results, model_number = search_items_by_barcode(tenant_id, user_query)
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
#             results = search_items_by_model(tenant_id, user_query)
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
#             results = search_items_by_model(tenant_id, user_query)
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
#     integration = get_latest_integration_for_tenant(tenant_id)

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
#     integration = get_latest_integration_for_tenant(tenant["id"])
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
import pymysql
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.session_store import load_product_session, save_product_session


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


def get_latest_integration_for_tenant(tenant_id: int) -> Optional[Dict[str, Any]]:
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
                    status
                FROM t_integration
                WHERE tenant_id = %s
                  AND (status IS NULL OR status = 'active')
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_tenant_product_db_connection(tenant_id: int):
    """
    Connects to the tenant/product DB using details saved in t_integration.
    """
    integration = get_latest_integration_for_tenant(tenant_id)

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


def fetch_all_from_tenant_db(tenant_id: int, query: str, params: tuple = ()):
    conn = get_tenant_product_db_connection(tenant_id)
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

class ProductChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"


class ProductChatResponse(BaseModel):
    responses: List[str]
    step: Union[int, float]
    lookup_type: Optional[str] = None
    selected_ticket_id: Optional[str] = None
    selected_site_id: Optional[int] = None


PRODUCT_REDIRECT_LINK = os.getenv("PRODUCT_REDIRECT_LINK", "https://store1.desithread.co.in/update_model")

BASE_ITEM_SELECT = """
    SELECT
        i.item_id,
        i.barcode AS Barcode,

        COALESCE(ms.name, i.size) AS Size,

        COALESCE(mc.name, i.color) AS Color,

        i.product_qty AS Qty,
        i.item_name AS model

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
        "lookup_type": None,
        "last_results": [],
        "last_model": None,
        "last_barcode": None,
        "selected_ticket_id": None,
        "selected_site_id": None,
    }


def get_session(tenant_id: int, session_id: str):
    return load_product_session(tenant_id, session_id or "default", default_product_session())


def persist_session(tenant_id: int, session_id: str, session: Dict[str, Any]) -> None:
    save_product_session(tenant_id, session_id or "default", session)


def reset_session(session):
    session["step"] = 1
    session["lookup_type"] = None
    session["last_results"] = []
    session["last_model"] = None
    session["last_barcode"] = None
    session["selected_ticket_id"] = None
    session["selected_site_id"] = None


def get_product_redirect_link(tenant_id: int) -> str:
    integration = get_latest_integration_for_tenant(tenant_id)
    website_url = (integration or {}).get("website_url")
    return (website_url or PRODUCT_REDIRECT_LINK).strip()


def value_or_na(value):
    if value is None or value == "":
        return "N/A"
    return value


def search_items_by_model(tenant_id: int, model_number: str):
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
    return fetch_all_from_tenant_db(tenant_id, query, (like_model, barcode_prefix))


def search_items_by_barcode(tenant_id: int, barcode: str):
    """
    User enters barcode.
    First 4 alphanumeric characters are used as model number.
    """
    clean_barcode = "".join(ch for ch in str(barcode).strip() if ch.isalnum())
    model_number = clean_barcode[:4]

    if len(model_number) < 4:
        return [], model_number

    return search_items_by_model(tenant_id, model_number), model_number


def format_item_list(rows, model_number=None, redirect_link: str = ""):
    unique_rows = rows

    lines = []

    if model_number:
        lines.append(f"✅ Model Number: {model_number}")

    lines.append("📋 Items List")
    lines.append("────────────────────")
    lines.append("𝗡𝗼  𝗕𝗮𝗿𝗰𝗼𝗱𝗲   𝗦𝗶𝘇𝗲  𝗖𝗼𝗹𝗼𝗿   𝗤𝘁𝘆")
    lines.append("────────────────────")

    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for index, row in enumerate(unique_rows[:50], start=1):
        no = emojis[index - 1] if index <= 10 else f"{index}."

        barcode = str(value_or_na(row.get("Barcode"))).ljust(12)
        size = str(value_or_na(row.get("Size"))).ljust(7)
        color = str(value_or_na(row.get("Color"))).ljust(8)
        qty = str(value_or_na(row.get("Qty")))

        lines.append(f"{no}   {barcode}{size}{color}{qty}")

    lines.append("")
    lines.append("🔗 View Product List:")
    lines.append(redirect_link or PRODUCT_REDIRECT_LINK)

    return "\n".join(lines)


def process_product_chat(query: str, session_id: str, tenant_id: int):
    session = get_session(tenant_id, session_id)
    redirect_link = get_product_redirect_link(tenant_id)
    user_query = (query or "").strip()
    user_query_lower = user_query.lower()
    responses = []

    if not user_query:
        return {
            "responses": ["Please type your message."],
            "step": session["step"],
            "lookup_type": session.get("lookup_type"),
            "selected_ticket_id": None,
            "selected_site_id": None,
        }

    if session["step"] == 1:
        if user_query_lower in ["yes", "y"]:
            session["lookup_type"] = "model_number"
            session["step"] = 2
            responses.append("Please enter your Model Number")

        elif user_query_lower in ["no", "n"]:
            session["lookup_type"] = "barcode"
            session["step"] = 2
            responses.append(
                "Please enter Barcode. I will take first 4 numbers as Model Number and fetch the list."
            )

        else:
            results = search_items_by_model(tenant_id, user_query)
            session["last_model"] = user_query
            session["last_results"] = results

            if results:
                responses.append(format_item_list(results, user_query, redirect_link))
            else:
                responses.append("No item found for this model number.")
                responses.append(f"🔗 View Product List:\n{redirect_link}")

            session["step"] = 3

    elif session["step"] == 2:
        lookup_type = session.get("lookup_type")

        if lookup_type == "barcode":
            results, model_number = search_items_by_barcode(tenant_id, user_query)
            session["last_barcode"] = user_query
            session["last_model"] = model_number
            session["last_results"] = results

            if len(model_number) < 4:
                responses.append("Barcode should have at least 4 characters. Please enter valid Barcode.")
                session["step"] = 2

            elif results:
                responses.append(f"Barcode received. Model Number: {model_number}")
                responses.append(format_item_list(results, model_number, redirect_link))
                session["step"] = 3

            else:
                responses.append(f"No item found for Model Number: {model_number}")
                responses.append(f"🔗 View Product List:\n{redirect_link}")
                session["step"] = 3

        else:
            results = search_items_by_model(tenant_id, user_query)
            session["last_model"] = user_query
            session["last_results"] = results

            if results:
                responses.append(format_item_list(results, user_query, redirect_link))
            else:
                responses.append("No item found for this model number.")
                responses.append(f"🔗 View Product List:\n{redirect_link}")

            session["step"] = 3

    elif session["step"] == 3:
        if user_query_lower in ["yes", "new search", "search again", "another", "new"]:
            reset_session(session)
            responses.append("New search started.")
            responses.append("Do you have model number? Choose: Yes / No")

        elif user_query_lower == "summary":
            if session["last_results"]:
                responses.append(format_item_list(session["last_results"], session.get("last_model"), redirect_link))
            else:
                responses.append("No result available.")

        else:
            results = search_items_by_model(tenant_id, user_query)
            session["last_model"] = user_query
            session["last_results"] = results

            if results:
                responses.append(format_item_list(results, user_query, redirect_link))
            else:
                responses.append("No item found for this model number.")
                responses.append(f"🔗 View Product List:\n{redirect_link}")

            session["step"] = 3

    else:
        reset_session(session)
        responses.append("Do you have model number? Choose: Yes / No")

    persist_session(tenant_id, session_id, session)

    return {
        "responses": responses,
        "step": session["step"],
        "lookup_type": session.get("lookup_type"),
        "selected_ticket_id": None,
        "selected_site_id": None,
    }


@router.get("/health")
def product_query_health(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    integration = get_latest_integration_for_tenant(tenant_id)

    return {
        "success": True,
        "online": True,
        "tenant_id": tenant_id,
        "integration_configured": bool(integration),
    }


@router.get("/item-list")
def item_list(model: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    data = search_items_by_model(tenant_id, model.strip())
    redirect_link = get_product_redirect_link(tenant_id)
    return {
        "model": model,
        "message": "Item data found" if data else "No item data found",
        "redirect_link": redirect_link,
        "items": data,
    }


@router.get("/item-list-by-barcode")
def item_list_by_barcode(barcode: str, current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]
    data, model_number = search_items_by_barcode(tenant_id, barcode.strip())
    redirect_link = get_product_redirect_link(tenant_id)
    return {
        "barcode": barcode,
        "model_number": model_number,
        "message": "Item data found" if data else "No item data found",
        "redirect_link": redirect_link,
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
    )


@router.get("/public-health/{tenant_slug}")
def public_product_query_health(tenant_slug: str):
    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")
    integration = get_latest_integration_for_tenant(tenant["id"])
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
    session_id = request.session_id or str(uuid4())
    return process_product_chat(
        query=request.query,
        session_id=session_id,
        tenant_id=tenant["id"],
    )
