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


def is_sales_enquiry_enabled_for_tenant(tenant_id: int) -> bool:
    """
    Sales enquiry popup is tenant-specific.
    Currently enabled only for tenant slug in SPECIAL_SALES_TENANT_SLUGS, e.g. desipos.
    """
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug
                FROM tenants
                WHERE id = %s
                  AND status = 'active'
                LIMIT 1
                """,
                (tenant_id,),
            )
            row = cur.fetchone() or {}
            slug = (row.get("slug") or "").strip().lower()
            return slug in SPECIAL_SALES_TENANT_SLUGS
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

# Sales enquiry popup is enabled only for these tenant slugs.
# Add more slugs here if you want the same flow for another product tenant.
SPECIAL_SALES_TENANT_SLUGS = ["desipos"]

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
        "intent": None,
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


def search_last_10_sales_by_model(tenant_id: int, model_number: str):
    """
    For DesiPos product agent sales enquiry.
    Finds last 10 sold bill items where item barcode starts with the model number.
    Tables used: bill_items, bill_details, item, master.
    """
    model_number = str(model_number).strip()
    barcode_prefix = f"{model_number}%"

    query = """
        SELECT
            COALESCE(bd.bill_date, DATE(bd.date_created)) AS Date,
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

    return fetch_all_from_tenant_db(tenant_id, query, (barcode_prefix,))
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

def format_item_list(rows, model_number=None, redirect_link: str = ""):
    unique_rows = rows

    lines = []

    if model_number:
        lines.append(f"✅ Model Number: {model_number}")

    lines.append("📋 Items List")
    lines.append("────────────────────────────────────")
    lines.append("𝗡𝗼  𝗕𝗮𝗿𝗰𝗼𝗱𝗲   𝗦𝗶𝘇𝗲  𝗖𝗼𝗹𝗼𝗿   𝗤𝘁𝘆")
    lines.append("────────────────────────────────────")

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




def format_sales_list(rows, model_number=None):
    lines = []

    if model_number:
        lines.append(f"✅ Last 10 Sales for Model Number: {model_number}")

    lines.append("📋 Sales List")
    lines.append("────────────────────────────────────────")
    lines.append("𝗡𝗼  𝗗𝗮𝘁𝗲        𝗕𝗮𝗿𝗰𝗼𝗱𝗲   𝗦𝗶𝘇𝗲  𝗖𝗼𝗹𝗼𝗿   𝗤𝘁𝘆")
    lines.append("────────────────────────────────────────")

    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for index, row in enumerate(rows[:10], start=1):
        no = emojis[index - 1] if index <= 10 else f"{index}."

        sale_date = str(value_or_na(row.get("Date"))).ljust(12)
        barcode = str(value_or_na(row.get("Barcode"))).ljust(11)
        size = str(value_or_na(row.get("Size"))).ljust(7)
        color = str(value_or_na(row.get("Color"))).ljust(8)
        qty = str(value_or_na(row.get("Qty")))

        lines.append(f"{no}   {sale_date}{barcode}{size}{color}{qty}")

    return "\n".join(lines)


def process_product_chat(query: str, session_id: str, tenant_id: int):
    session = get_session(tenant_id, session_id)
    redirect_link = get_product_redirect_link(tenant_id)
    sales_enabled = is_sales_enquiry_enabled_for_tenant(tenant_id)

    user_query = (query or "").strip()
    user_query_lower = user_query.lower()
    responses = []

    if user_query == "__welcome__":
        reset_session(session)
        persist_session(tenant_id, session_id, session)

        if sales_enabled:
            welcome_text = (
                "Hello 👋\n"
                "Please choose one option:\n\n"
                "1️⃣ Model Number\n"
                "2️⃣ Sales Enquiry"
            )
        else:
            custom_greeting = get_product_greeting_message(tenant_id)
            welcome_text = (
                custom_greeting
                or "Hello, do you have a model number? Please choose Yes or No."
            )

        return {
            "responses": [welcome_text],
            "step": session["step"],
            "lookup_type": session.get("lookup_type"),
            "selected_ticket_id": None,
            "selected_site_id": None,
        }

    if not user_query:
        return {
            "responses": ["Please type your message."],
            "step": session["step"],
            "lookup_type": session.get("lookup_type"),
            "selected_ticket_id": None,
            "selected_site_id": None,
        }

    if session["step"] == 1:
        if sales_enabled:
            if user_query_lower in ["1", "model", "model number", "model no", "model enquiry"]:
                session["intent"] = "model_number"
                session["lookup_type"] = "model_number"
                session["step"] = 2
                responses.append("Please enter your Model Number")

            elif user_query_lower in ["2", "sales", "sale", "sales enquiry", "sale enquiry", "last sales"]:
                session["intent"] = "sales_enquiry"
                session["lookup_type"] = "sales_model"
                session["step"] = 2
                responses.append("Please enter Model Number to check last 10 sales")

            else:
                responses.append(
                    "Please choose one option:\n\n"
                    "1️⃣ Model Number\n"
                    "2️⃣ Sales Enquiry"
                )

            persist_session(tenant_id, session_id, session)
            return {
                "responses": responses,
                "step": session["step"],
                "lookup_type": session.get("lookup_type"),
                "selected_ticket_id": None,
                "selected_site_id": None,
            }

        if user_query_lower in ["yes", "y"]:
            session["intent"] = "model_number"
            session["lookup_type"] = "model_number"
            session["step"] = 2
            responses.append("Please enter your Model Number")

        elif user_query_lower in ["no", "n"]:
            session["intent"] = "barcode"
            session["lookup_type"] = "barcode"
            session["step"] = 2
            responses.append(
                "Please enter Barcode. I will take first 4 numbers as Model Number and fetch the list."
            )

        else:
            results = search_items_by_model(tenant_id, user_query)
            session["intent"] = "model_number"
            session["last_model"] = user_query
            session["last_results"] = results

            if results:
                responses.append(format_item_list(results, user_query, redirect_link))
            else:
                responses.append("No item found for this model number.")
                responses.append(f"🔗 View Product List:\n{redirect_link}")

            session["step"] = 3

    elif session["step"] == 2:
        if session.get("intent") == "sales_enquiry":
            results = search_last_10_sales_by_model(tenant_id, user_query)
            session["last_model"] = user_query
            session["last_results"] = results

            if results:
                responses.append(format_sales_list(results, user_query))
            else:
                responses.append(f"No sales found for Model Number: {user_query}")

            session["step"] = 3

        else:
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
        if user_query_lower in ["yes", "new search", "search again", "another", "new", "menu", "start"]:
            reset_session(session)

            if sales_enabled:
                responses.append("New search started.")
                responses.append(
                    "Please choose one option:\n\n"
                    "1️⃣ Model Number\n"
                    "2️⃣ Sales Enquiry"
                )
            else:
                responses.append("New search started.")
                responses.append("Do you have model number? Choose: Yes / No")

        elif user_query_lower == "summary":
            if session["last_results"]:
                if session.get("intent") == "sales_enquiry":
                    responses.append(format_sales_list(session["last_results"], session.get("last_model")))
                else:
                    responses.append(format_item_list(session["last_results"], session.get("last_model"), redirect_link))
            else:
                responses.append("No result available.")

        else:
            if sales_enabled and user_query_lower in ["1", "model", "model number", "model no", "model enquiry"]:
                session["intent"] = "model_number"
                session["lookup_type"] = "model_number"
                session["step"] = 2
                responses.append("Please enter your Model Number")

            elif sales_enabled and user_query_lower in ["2", "sales", "sale", "sales enquiry", "sale enquiry", "last sales"]:
                session["intent"] = "sales_enquiry"
                session["lookup_type"] = "sales_model"
                session["step"] = 2
                responses.append("Please enter Model Number to check last 10 sales")

            else:
                results = search_items_by_model(tenant_id, user_query)
                session["intent"] = "model_number"
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
        if sales_enabled:
            responses.append(
                "Please choose one option:\n\n"
                "1️⃣ Model Number\n"
                "2️⃣ Sales Enquiry"
            )
        else:
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
