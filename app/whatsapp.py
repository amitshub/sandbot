# import os
# import re
# from typing import Optional, Dict, Any

# import requests
# from fastapi import HTTPException
# from twilio.rest import Client

# from app.db import get_main_db_connection
# from app.chatbot import chat_with_agent


# def normalize_phone(phone: str, default_country_code: str = "+91") -> str:
#     """Return E.164-ish phone number. If user enters 10 digit Indian number, prefix +91."""
#     phone = (phone or "").strip()
#     if not phone:
#         return ""

#     phone = phone.replace("whatsapp:", "").strip()
#     phone = re.sub(r"[\s().-]+", "", phone)

#     if phone.startswith("+"):
#         return phone

#     digits = re.sub(r"\D", "", phone)
#     if len(digits) == 10:
#         return f"{default_country_code}{digits}"
#     if digits.startswith("91") and len(digits) == 12:
#         return f"+{digits}"
#     if digits:
#         return f"+{digits}"
#     return phone


# def get_tenant_whatsapp_config(tenant_id: Optional[int] = None, tenant_slug: Optional[str] = None) -> Dict[str, Any]:
#     if not tenant_id and not tenant_slug:
#         raise HTTPException(status_code=400, detail="tenant_id or tenant_slug is required")

#     conn = get_main_db_connection()
#     try:
#         with conn.cursor() as cur:
#             if tenant_id:
#                 cur.execute(
#                     """
#                     SELECT id, slug, tenant_name, whatsapp_provider,
#                            twilio_account_sid, twilio_auth_token, twilio_phone_number,
#                            meta_access_token, meta_phone_number_id, meta_business_account_id,
#                            whatsapp_number, whatsapp_verify_token
#                     FROM tenants
#                     WHERE id=%s AND status='active'
#                     LIMIT 1
#                     """,
#                     (tenant_id,),
#                 )
#             else:
#                 cur.execute(
#                     """
#                     SELECT id, slug, tenant_name, whatsapp_provider,
#                            twilio_account_sid, twilio_auth_token, twilio_phone_number,
#                            meta_access_token, meta_phone_number_id, meta_business_account_id,
#                            whatsapp_number, whatsapp_verify_token
#                     FROM tenants
#                     WHERE slug=%s AND status='active'
#                     LIMIT 1
#                     """,
#                     (tenant_slug,),
#                 )
#             tenant = cur.fetchone()
#     finally:
#         conn.close()

#     if not tenant:
#         raise HTTPException(status_code=404, detail="Tenant not found or inactive")

#     provider = (tenant.get("whatsapp_provider") or "").strip().lower()
#     if provider not in {"twilio", "meta"}:
#         raise HTTPException(status_code=400, detail="WhatsApp is not connected for this tenant")

#     return tenant


# def send_whatsapp_text(tenant_id: int, to_phone: str, message: str) -> Dict[str, Any]:
#     tenant = get_tenant_whatsapp_config(tenant_id=tenant_id)
#     provider = tenant.get("whatsapp_provider")

#     if provider == "twilio":
#         return send_twilio_text(tenant, to_phone, message)
#     if provider == "meta":
#         return send_meta_text(tenant, to_phone, message)

#     raise HTTPException(status_code=400, detail="Unsupported WhatsApp provider")


# def send_whatsapp_media(tenant_id: int, to_phone: str, media_url: str, caption: str = "") -> Dict[str, Any]:
#     tenant = get_tenant_whatsapp_config(tenant_id=tenant_id)
#     provider = tenant.get("whatsapp_provider")

#     if provider == "twilio":
#         return send_twilio_media(tenant, to_phone, media_url, caption)
#     if provider == "meta":
#         return send_meta_media(tenant, to_phone, media_url, caption)

#     raise HTTPException(status_code=400, detail="Unsupported WhatsApp provider")


# def send_twilio_text(tenant: Dict[str, Any], to_phone: str, message: str) -> Dict[str, Any]:
#     sid = tenant.get("twilio_account_sid")
#     token = tenant.get("twilio_auth_token")
#     from_number = normalize_phone(tenant.get("twilio_phone_number"))
#     to_number = normalize_phone(to_phone)

#     if not sid or not token or not from_number:
#         raise HTTPException(status_code=400, detail="Twilio credentials are incomplete")

#     client = Client(sid, token)
#     msg = client.messages.create(
#         from_=f"whatsapp:{from_number}",
#         to=f"whatsapp:{to_number}",
#         body=message,
#     )
#     return {"success": True, "provider": "twilio", "message_sid": msg.sid, "status": msg.status}


# def send_twilio_media(tenant: Dict[str, Any], to_phone: str, media_url: str, caption: str = "") -> Dict[str, Any]:
#     sid = tenant.get("twilio_account_sid")
#     token = tenant.get("twilio_auth_token")
#     from_number = normalize_phone(tenant.get("twilio_phone_number"))
#     to_number = normalize_phone(to_phone)

#     if not sid or not token or not from_number:
#         raise HTTPException(status_code=400, detail="Twilio credentials are incomplete")

#     client = Client(sid, token)
#     payload = {
#         "from_": f"whatsapp:{from_number}",
#         "to": f"whatsapp:{to_number}",
#         "media_url": [media_url],
#     }
#     if caption:
#         payload["body"] = caption

#     msg = client.messages.create(**payload)
#     return {"success": True, "provider": "twilio", "message_sid": msg.sid, "status": msg.status}


# def send_meta_text(tenant: Dict[str, Any], to_phone: str, message: str) -> Dict[str, Any]:
#     access_token = tenant.get("meta_access_token")
#     phone_number_id = tenant.get("meta_phone_number_id")
#     to_number = normalize_phone(to_phone).replace("+", "")

#     if not access_token or not phone_number_id:
#         raise HTTPException(status_code=400, detail="Meta credentials are incomplete")

#     url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
#     response = requests.post(
#         url,
#         headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
#         json={
#             "messaging_product": "whatsapp",
#             "to": to_number,
#             "type": "text",
#             "text": {"body": message},
#         },
#         timeout=20,
#     )
#     if response.status_code >= 400:
#         raise HTTPException(status_code=400, detail=response.text)
#     return {"success": True, "provider": "meta", "response": response.json()}


# def send_meta_media(tenant: Dict[str, Any], to_phone: str, media_url: str, caption: str = "") -> Dict[str, Any]:
#     access_token = tenant.get("meta_access_token")
#     phone_number_id = tenant.get("meta_phone_number_id")
#     to_number = normalize_phone(to_phone).replace("+", "")

#     if not access_token or not phone_number_id:
#         raise HTTPException(status_code=400, detail="Meta credentials are incomplete")

#     url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
#     image_payload = {"link": media_url}
#     if caption:
#         image_payload["caption"] = caption

#     response = requests.post(
#         url,
#         headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
#         json={
#             "messaging_product": "whatsapp",
#             "to": to_number,
#             "type": "image",
#             "image": image_payload,
#         },
#         timeout=20,
#     )
#     if response.status_code >= 400:
#         raise HTTPException(status_code=400, detail=response.text)
#     return {"success": True, "provider": "meta", "response": response.json()}


# def handle_incoming_text_and_reply(tenant_slug: str, customer_phone: str, incoming_message: str) -> Dict[str, Any]:
#     tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)
#     session_id = f"whatsapp:{normalize_phone(customer_phone)}"

#     chat_result = chat_with_agent(
#         session_id=session_id,
#         message=incoming_message,
#         tenant_id=tenant["id"],
#         top_k=2,
#     )
#     answer = chat_result.get("answer") or "I will connect you with our team."
#     send_result = send_whatsapp_text(tenant["id"], customer_phone, answer)

#     return {
#         "success": True,
#         "tenant_id": tenant["id"],
#         "customer_phone": customer_phone,
#         "answer": answer,
#         "send_result": send_result,
#     }

import os
import re
from typing import Optional, Dict, Any

import requests
from fastapi import HTTPException
from twilio.rest import Client

from app.db import get_main_db_connection
from app.chatbot import chat_with_agent


def normalize_phone(phone: str, default_country_code: str = "+91") -> str:
    phone = (phone or "").strip()
    if not phone:
        return ""

    phone = phone.replace("whatsapp:", "").strip()
    phone = re.sub(r"[\s().-]+", "", phone)

    if phone.startswith("+"):
        return phone

    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if digits:
        return f"+{digits}"

    return phone


def is_valid_email(value: str) -> bool:
    value = (value or "").strip()
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value))


def clean_name(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value[:255]


def get_tenant_whatsapp_config(
    tenant_id: Optional[int] = None,
    tenant_slug: Optional[str] = None,
) -> Dict[str, Any]:
    if not tenant_id and not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_id or tenant_slug is required")

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            if tenant_id:
                cur.execute(
                    """
                    SELECT id, slug, tenant_name, whatsapp_provider,
                           twilio_account_sid, twilio_auth_token, twilio_phone_number,
                           meta_access_token, meta_phone_number_id, meta_business_account_id,
                           whatsapp_number, whatsapp_verify_token
                    FROM tenants
                    WHERE id=%s AND status='active'
                    LIMIT 1
                    """,
                    (tenant_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, slug, tenant_name, whatsapp_provider,
                           twilio_account_sid, twilio_auth_token, twilio_phone_number,
                           meta_access_token, meta_phone_number_id, meta_business_account_id,
                           whatsapp_number, whatsapp_verify_token
                    FROM tenants
                    WHERE slug=%s AND status='active'
                    LIMIT 1
                    """,
                    (tenant_slug,),
                )

            tenant = cur.fetchone()
    finally:
        conn.close()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")

    provider = (tenant.get("whatsapp_provider") or "").strip().lower()
    if provider not in {"twilio", "meta"}:
        raise HTTPException(status_code=400, detail="WhatsApp is not connected for this tenant")

    return tenant


def get_or_create_whatsapp_customer(
    tenant_id: int,
    session_id: str,
    phone: str,
    message: str = "",
) -> Dict[str, Any]:
    phone = normalize_phone(phone)
    message = (message or "").strip()

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_customers
                    (tenant_id, session_id, phone, first_message, last_message,
                     source, status, last_seen_at)
                VALUES
                    (%s, %s, %s, %s, %s, 'whatsapp', 'new', NOW())
                ON DUPLICATE KEY UPDATE
                    phone = COALESCE(VALUES(phone), phone),
                    first_message = COALESCE(first_message, VALUES(first_message)),
                    last_message = VALUES(last_message),
                    source = 'whatsapp',
                    last_seen_at = NOW(),
                    updated_at = NOW()
                """,
                (tenant_id, session_id, phone, message, message),
            )

            cur.execute(
                """
                SELECT id, tenant_id, session_id, name, email, phone, first_message,
                       last_message, source, status, last_seen_at
                FROM tenant_customers
                WHERE tenant_id=%s AND session_id=%s
                LIMIT 1
                """,
                (tenant_id, session_id),
            )
            return cur.fetchone() or {}
    finally:
        conn.close()


def update_whatsapp_customer(
    tenant_id: int,
    session_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    message: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    fields = []
    values = []

    if name is not None:
        fields.append("name=%s")
        values.append(clean_name(name))

    if email is not None:
        fields.append("email=%s")
        values.append(email.strip().lower())

    if phone is not None:
        fields.append("phone=%s")
        values.append(normalize_phone(phone))

    if message is not None:
        fields.append("last_message=%s")
        values.append((message or "").strip())

    if status is not None:
        fields.append("status=%s")
        values.append(status)

    fields.append("last_seen_at=NOW()")
    fields.append("updated_at=NOW()")

    values.extend([tenant_id, session_id])

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE tenant_customers
                SET {", ".join(fields)}
                WHERE tenant_id=%s AND session_id=%s
                """,
                tuple(values),
            )

            cur.execute(
                """
                SELECT id, tenant_id, session_id, name, email, phone, first_message,
                       last_message, source, status, last_seen_at
                FROM tenant_customers
                WHERE tenant_id=%s AND session_id=%s
                LIMIT 1
                """,
                (tenant_id, session_id),
            )
            return cur.fetchone() or {}
    finally:
        conn.close()


def send_whatsapp_text(tenant_id: int, to_phone: str, message: str) -> Dict[str, Any]:
    tenant = get_tenant_whatsapp_config(tenant_id=tenant_id)
    provider = tenant.get("whatsapp_provider")

    if provider == "twilio":
        return send_twilio_text(tenant, to_phone, message)

    if provider == "meta":
        return send_meta_text(tenant, to_phone, message)

    raise HTTPException(status_code=400, detail="Unsupported WhatsApp provider")


def send_whatsapp_media(
    tenant_id: int,
    to_phone: str,
    media_url: str,
    caption: str = "",
) -> Dict[str, Any]:
    tenant = get_tenant_whatsapp_config(tenant_id=tenant_id)
    provider = tenant.get("whatsapp_provider")

    if provider == "twilio":
        return send_twilio_media(tenant, to_phone, media_url, caption)

    if provider == "meta":
        return send_meta_media(tenant, to_phone, media_url, caption)

    raise HTTPException(status_code=400, detail="Unsupported WhatsApp provider")


def send_twilio_text(tenant: Dict[str, Any], to_phone: str, message: str) -> Dict[str, Any]:
    sid = tenant.get("twilio_account_sid")
    token = tenant.get("twilio_auth_token")
    from_number = normalize_phone(tenant.get("twilio_phone_number"))
    to_number = normalize_phone(to_phone)

    if not sid or not token or not from_number:
        raise HTTPException(status_code=400, detail="Twilio credentials are incomplete")

    client = Client(sid, token)
    msg = client.messages.create(
        from_=f"whatsapp:{from_number}",
        to=f"whatsapp:{to_number}",
        body=message,
    )

    return {
        "success": True,
        "provider": "twilio",
        "message_sid": msg.sid,
        "status": msg.status,
    }


def send_twilio_media(
    tenant: Dict[str, Any],
    to_phone: str,
    media_url: str,
    caption: str = "",
) -> Dict[str, Any]:
    sid = tenant.get("twilio_account_sid")
    token = tenant.get("twilio_auth_token")
    from_number = normalize_phone(tenant.get("twilio_phone_number"))
    to_number = normalize_phone(to_phone)

    if not sid or not token or not from_number:
        raise HTTPException(status_code=400, detail="Twilio credentials are incomplete")

    payload = {
        "from_": f"whatsapp:{from_number}",
        "to": f"whatsapp:{to_number}",
        "media_url": [media_url],
    }

    if caption:
        payload["body"] = caption

    client = Client(sid, token)
    msg = client.messages.create(**payload)

    return {
        "success": True,
        "provider": "twilio",
        "message_sid": msg.sid,
        "status": msg.status,
    }


def send_meta_text(tenant: Dict[str, Any], to_phone: str, message: str) -> Dict[str, Any]:
    access_token = tenant.get("meta_access_token")
    phone_number_id = tenant.get("meta_phone_number_id")
    to_number = normalize_phone(to_phone).replace("+", "")

    if not access_token or not phone_number_id:
        raise HTTPException(status_code=400, detail="Meta credentials are incomplete")

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message},
        },
        timeout=20,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=response.text)

    return {
        "success": True,
        "provider": "meta",
        "response": response.json(),
    }


def send_meta_media(
    tenant: Dict[str, Any],
    to_phone: str,
    media_url: str,
    caption: str = "",
) -> Dict[str, Any]:
    access_token = tenant.get("meta_access_token")
    phone_number_id = tenant.get("meta_phone_number_id")
    to_number = normalize_phone(to_phone).replace("+", "")

    if not access_token or not phone_number_id:
        raise HTTPException(status_code=400, detail="Meta credentials are incomplete")

    image_payload = {"link": media_url}
    if caption:
        image_payload["caption"] = caption

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "image",
            "image": image_payload,
        },
        timeout=20,
    )

    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail=response.text)

    return {
        "success": True,
        "provider": "meta",
        "response": response.json(),
    }


def handle_incoming_text_and_reply(
    tenant_slug: str,
    customer_phone: str,
    incoming_message: str,
) -> Dict[str, Any]:
    tenant = get_tenant_whatsapp_config(tenant_slug=tenant_slug)

    normalized_phone = normalize_phone(customer_phone)
    session_id = f"whatsapp:{normalized_phone}"
    incoming_message = (incoming_message or "").strip()

    print("========== WHATSAPP INCOMING ==========")
    print("TENANT:", tenant_slug)
    print("TENANT ID:", tenant["id"])
    print("FROM:", normalized_phone)
    print("MESSAGE:", incoming_message)
    print("=======================================")

    customer = get_or_create_whatsapp_customer(
        tenant_id=tenant["id"],
        session_id=session_id,
        phone=normalized_phone,
        message=incoming_message,
    )

    name = (customer.get("name") or "").strip()
    email = (customer.get("email") or "").strip()

    if not name:
        if customer.get("status") == "new":
            update_whatsapp_customer(
                tenant_id=tenant["id"],
                session_id=session_id,
                phone=normalized_phone,
                message=incoming_message,
                status="awaiting_name",
            )

            answer = "Hi 👋 Please share your name to start the chat."

            send_result = send_whatsapp_text(
                tenant["id"],
                normalized_phone,
                answer,
            )

            return {
                "success": True,
                "tenant_id": tenant["id"],
                "customer": customer,
                "customer_phone": normalized_phone,
                "answer": answer,
                "send_result": send_result,
                "step": "ask_name",
            }

        updated_customer = update_whatsapp_customer(
            tenant_id=tenant["id"],
            session_id=session_id,
            name=incoming_message,
            phone=normalized_phone,
            message=incoming_message,
            status="active",
        )

        answer = f"Thanks {updated_customer.get('name')}. Please share your email address."

        send_result = send_whatsapp_text(
            tenant["id"],
            normalized_phone,
            answer,
        )

        return {
            "success": True,
            "tenant_id": tenant["id"],
            "customer": updated_customer,
            "customer_phone": normalized_phone,
            "answer": answer,
            "send_result": send_result,
            "step": "ask_email",
        }

    if not email:
        if is_valid_email(incoming_message):
            updated_customer = update_whatsapp_customer(
                tenant_id=tenant["id"],
                session_id=session_id,
                email=incoming_message,
                phone=normalized_phone,
                message=incoming_message,
                status="active",
            )

            answer = "Thank you. How can I help you today?"
            send_result = send_whatsapp_text(tenant["id"], normalized_phone, answer)

            return {
                "success": True,
                "tenant_id": tenant["id"],
                "customer": updated_customer,
                "customer_phone": normalized_phone,
                "answer": answer,
                "send_result": send_result,
                "step": "ready_for_chat",
            }

        answer = "Please share a valid email address."
        send_result = send_whatsapp_text(tenant["id"], normalized_phone, answer)

        return {
            "success": True,
            "tenant_id": tenant["id"],
            "customer": customer,
            "customer_phone": normalized_phone,
            "answer": answer,
            "send_result": send_result,
            "step": "ask_email",
        }

    customer = update_whatsapp_customer(
        tenant_id=tenant["id"],
        session_id=session_id,
        phone=normalized_phone,
        message=incoming_message,
        status="active",
    )

    chat_result = chat_with_agent(
        session_id=session_id,
        message=incoming_message,
        tenant_id=tenant["id"],
        top_k=2,
    )

    answer = chat_result.get("answer") or "I will connect you with our team."
    send_result = send_whatsapp_text(tenant["id"], normalized_phone, answer)

    return {
        "success": True,
        "tenant_id": tenant["id"],
        "customer": customer,
        "customer_phone": normalized_phone,
        "answer": answer,
        "send_result": send_result,
        "step": "chat",
    }