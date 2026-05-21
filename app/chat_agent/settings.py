import json
from typing import Any, Dict

try:
    from app.db import get_main_db_connection
except Exception:
    get_main_db_connection = None

CONTACT_COLUMNS = [
    "website_url", "website", "client_domain", "business_website", "allowed_hosts", "branding_api",
    "support_phone", "phone", "mobile", "whatsapp_number",
    "support_email", "email", "business_email", "address",
]


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


def get_agent_settings(tenant_id: int, agent_type: str = "chat") -> Dict[str, Any]:
    if get_main_db_connection is None:
        return {}
    row = {}
    try:
        conn = get_main_db_connection()
        try:
            with conn.cursor() as cur:
                tenant_cols = _get_table_columns(cur, "tenants")
                settings_cols = _get_table_columns(cur, "tenant_agent_settings")

                tenant_selects = ["t.tenant_name"]
                for col in CONTACT_COLUMNS:
                    if col in tenant_cols:
                        tenant_selects.append(f"t.{col}")

                setting_names = [
                    "business_name", "industry", "business_type", "business_description",
                    "website_url", "allowed_scope", "blocked_claims", "greeting_message",
                    "starter_questions", "system_prompt", "restriction_rules", "support_hours",
                ]
                settings_selects = [f"tas.{c}" if c in settings_cols else f"NULL AS {c}" for c in setting_names]

                sql = f"""
                    SELECT {', '.join(settings_selects)}, {', '.join(tenant_selects)}
                    FROM tenants t
                    LEFT JOIN tenant_agent_settings tas
                      ON tas.tenant_id = t.id
                     AND (tas.agent_type = %s OR tas.agent_type IS NULL)
                    WHERE t.id=%s
                    LIMIT 1
                """
                cur.execute(sql, (agent_type, tenant_id))
                row = cur.fetchone() or {}
        finally:
            conn.close()
    except Exception as exc:
        print("[CHAT_AGENT SETTINGS ERROR]", repr(exc))

    business_name = row.get("business_name") or row.get("tenant_name") or "our team"
    contact = {}
    for col in CONTACT_COLUMNS:
        value = (row.get(col) or "").strip() if isinstance(row.get(col), str) else row.get(col)
        if value:
            contact[col] = value

    return {
        "tenant_name": row.get("tenant_name") or business_name,
        "business_name": business_name,
        "industry": row.get("industry") or "",
        "business_type": row.get("business_type") or "",
        "business_description": row.get("business_description") or "",
        "allowed_scope": row.get("allowed_scope") or "",
        "blocked_claims": row.get("blocked_claims") or "",
        "greeting_message": row.get("greeting_message") or "",
        "starter_questions": _json_load(row.get("starter_questions"), default=[]) or [],
        "system_prompt": row.get("system_prompt") or "",
        "restriction_rules": row.get("restriction_rules") or "",
        "support_hours": _json_load(row.get("support_hours"), default={}) or {},
        "contact": contact,
    }
