import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import get_main_db_connection

router = APIRouter(tags=["Agent Config"])

DEFAULT_SCOPE_BY_TYPE = {
    "manufacturer": {
        "allowed_scope": "product information, specifications, images, catalog details, product support",
        "blocked_claims": "installation services, repair services, maintenance services, on-site services, contractor services, unconfirmed pricing, unconfirmed warranty",
    },
    "product_seller": {
        "allowed_scope": "product information, availability guidance, specifications, images, product support",
        "blocked_claims": "manufacturing claims, installation services, repair services, maintenance services, unconfirmed pricing, unconfirmed warranty",
    },
    "service_provider": {
        "allowed_scope": "service information, booking guidance, support process, contact sharing, service details confirmed in KB",
        "blocked_claims": "product manufacturing claims, unconfirmed product availability, unconfirmed pricing, unconfirmed guarantees",
    },
    "ecommerce": {
        "allowed_scope": "product information, order guidance, catalogue details, shipping/return details only if present in KB",
        "blocked_claims": "offline service claims, manufacturing claims, repair services, unconfirmed shipping policy, unconfirmed returns, unconfirmed discounts",
    },
    "software_company": {
        "allowed_scope": "software features, demos, support, integrations, implementation details confirmed in KB",
        "blocked_claims": "hardware product claims, medical/legal/financial advice, unconfirmed pricing, unconfirmed guarantees",
    },
    "educational": {
        "allowed_scope": "courses, admissions guidance, schedules, fees only if present in KB, contact sharing",
        "blocked_claims": "guaranteed results, unconfirmed fees, unconfirmed admission promises, medical/legal/financial advice",
    },
    "healthcare": {
        "allowed_scope": "general clinic/service information, appointment guidance, contact sharing, non-emergency support",
        "blocked_claims": "diagnosis, prescription, emergency instructions, guaranteed outcomes, unconfirmed medical claims",
    },
    "real_estate": {
        "allowed_scope": "property information, location guidance, amenities, contact sharing, site visit guidance if confirmed in KB",
        "blocked_claims": "legal guarantees, unconfirmed pricing, unconfirmed availability, investment guarantees",
    },
    "restaurant": {
        "allowed_scope": "menu information, opening hours if confirmed, booking/order guidance, contact sharing",
        "blocked_claims": "medical nutrition advice, unconfirmed offers, unconfirmed availability, guaranteed delivery time",
    },
    "mixed": {
        "allowed_scope": "products and services explicitly confirmed in the knowledge base",
        "blocked_claims": "anything not present in trained KB, unconfirmed pricing, unconfirmed guarantees, unconfirmed policies",
    },
}


class AgentConfigRequest(BaseModel):
    agent_type: str = "chat"
    agent_id: Optional[int] = None
    business_name: Optional[str] = None
    industry: Optional[str] = None
    business_type: Optional[str] = None
    business_description: Optional[str] = None
    website_url: Optional[str] = None
    allowed_scope: Optional[str] = None
    blocked_claims: Optional[str] = None
    greeting_message: Optional[str] = None
    starter_questions: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    restriction_rules: Optional[str] = None
    support_hours: Optional[Dict[str, Any]] = None


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


def ensure_tenant_agent_settings_schema() -> None:
    """Safe schema helper. Run once before reading/writing agent config."""
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_agent_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tenant_id INT NOT NULL,
                    agent_type VARCHAR(50) NOT NULL DEFAULT 'chat',
                    agent_id INT NULL,
                    UNIQUE KEY uniq_tenant_agent_type (tenant_id, agent_type),
                    business_name VARCHAR(255) NULL,
                    industry VARCHAR(120) NULL,
                    business_type VARCHAR(120) NULL,
                    business_description TEXT NULL,
                    allowed_scope TEXT NULL,
                    blocked_claims TEXT NULL,
                    greeting_message TEXT NULL,
                    starter_questions JSON NULL,
                    system_prompt TEXT NULL,
                    restriction_rules TEXT NULL,
                    support_hours JSON NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
            )
            cols = _get_table_columns(cur, "tenant_agent_settings")
            alter_map = {
                "agent_type": "ADD COLUMN agent_type VARCHAR(50) NOT NULL DEFAULT 'chat'",
                "agent_id": "ADD COLUMN agent_id INT NULL",
                "industry": "ADD COLUMN industry VARCHAR(120) NULL",
                "business_type": "ADD COLUMN business_type VARCHAR(120) NULL",
                "business_description": "ADD COLUMN business_description TEXT NULL",
                "allowed_scope": "ADD COLUMN allowed_scope TEXT NULL",
                "blocked_claims": "ADD COLUMN blocked_claims TEXT NULL",
                "starter_questions": "ADD COLUMN starter_questions JSON NULL",
                "website_url": "ADD COLUMN website_url VARCHAR(500) NULL",
            }
            for col, ddl in alter_map.items():
                if col not in cols:
                    cur.execute(f"ALTER TABLE tenant_agent_settings {ddl}")

            # New multi-agent support: each product bot can have its own settings by agent_id.
            try:
                cur.execute("SHOW INDEX FROM tenant_agent_settings")
                all_indexes = cur.fetchall() or []
                has_agent_unique = any(row.get("Key_name") == "uniq_tenant_settings_agent_id" for row in all_indexes)
                if not has_agent_unique:
                    cur.execute("ALTER TABLE tenant_agent_settings ADD UNIQUE KEY uniq_tenant_settings_agent_id (tenant_id, agent_id)")
            except Exception:
                pass

            # Legacy fix: older table had UNIQUE(tenant_id), which blocks
            # separate chat/product settings. Keep tenants.active_agent_type as-is;
            # this only changes customization uniqueness.
            cur.execute("SHOW INDEX FROM tenant_agent_settings")
            indexes = cur.fetchall() or []

            unique_tenant_only_indexes = []
            grouped = {}
            for row in indexes:
                key_name = row.get("Key_name")
                if not key_name or key_name == "PRIMARY" or int(row.get("Non_unique", 1)) != 0:
                    continue
                grouped.setdefault(key_name, []).append(row.get("Column_name"))

            for key_name, cols_for_key in grouped.items():
                if cols_for_key == ["tenant_id"]:
                    unique_tenant_only_indexes.append(key_name)

            for key_name in unique_tenant_only_indexes:
                try:
                    cur.execute(f"ALTER TABLE tenant_agent_settings DROP INDEX {key_name}")
                except Exception as exc:
                    print("[AGENT CONFIG SCHEMA] could not drop old unique index:", key_name, repr(exc))

            try:
                cur.execute("ALTER TABLE tenant_agent_settings DROP INDEX uniq_tenant_agent_type")
            except Exception:
                pass
    finally:
        conn.close()


def make_scope_for_business_type(business_type: str) -> Dict[str, str]:
    key = (business_type or "mixed").strip().lower()
    return DEFAULT_SCOPE_BY_TYPE.get(key, DEFAULT_SCOPE_BY_TYPE["mixed"])


def upsert_tenant_business_rules(
    tenant_id: int,
    business_type: str,
    allowed_scope: str = "",
    blocked_claims: str = "",
    agent_id: Optional[int] = None,
    agent_type: str = "chat",
) -> None:
    """Use this inside /train-agent/start after reading Form fields."""
    ensure_tenant_agent_settings_schema()
    defaults = make_scope_for_business_type(business_type)
    allowed_scope = (allowed_scope or defaults["allowed_scope"]).strip()
    blocked_claims = (blocked_claims or defaults["blocked_claims"]).strip()

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_agent_settings
                    (tenant_id, agent_type, agent_id, business_type, allowed_scope, blocked_claims)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    agent_type = VALUES(agent_type),
                    business_type = VALUES(business_type),
                    allowed_scope = VALUES(allowed_scope),
                    blocked_claims = VALUES(blocked_claims),
                    updated_at = NOW()
                """,
                (tenant_id, agent_type, agent_id, business_type, allowed_scope, blocked_claims),
            )
    finally:
        conn.close()


def _get_training_summary(tenant_id: int) -> Dict[str, Any]:
    try:
        from app.index_builder import load_metadata
        metadata = load_metadata(tenant_id)
        website_docs = len({m.get("url") for m in metadata if m.get("url")})
        uploaded_docs = len({m.get("file_name") for m in metadata if m.get("file_name")})
        return {
            "entries": len(metadata),
            "website_documents": website_docs,
            "uploaded_documents": uploaded_docs,
            "total_vectors": len(metadata),
            "processed_sources": [],
            "skipped_sources": [],
            "failed_sources": [],
        }
    except Exception:
        return {
            "entries": 0,
            "website_documents": 0,
            "uploaded_documents": 0,
            "total_vectors": 0,
            "processed_sources": [],
            "skipped_sources": [],
            "failed_sources": [],
        }


def _build_config(tenant: Dict[str, Any], settings: Dict[str, Any], tenant_id: int) -> Dict[str, Any]:
    business_type = settings.get("business_type") or "mixed"
    defaults = make_scope_for_business_type(business_type)
    support_hours = _json_load(settings.get("support_hours"), default={}) or {}
    starter_questions = _json_load(settings.get("starter_questions"), default=None) or [
        "Tell me about your services",
        "What products do you offer?",
        "How can I contact your team?",
        "Do you provide pricing details?",
    ]
    kb = _get_training_summary(tenant_id)
    return {
        "tenant": tenant,
        "business": {
            "name": settings.get("business_name") or tenant.get("tenant_name") or "",
            "industry": settings.get("industry") or "General Business",
            "type": business_type,
            "description": settings.get("business_description") or "",
            "website_url": settings.get("website_url") or "",
            "allowed_scope": settings.get("allowed_scope") or defaults["allowed_scope"],
            "blocked_claims": settings.get("blocked_claims") or defaults["blocked_claims"],
        },
        "chat_experience": {
            "greeting_message": settings.get("greeting_message") or "Welcome! How can I help you today?",
            "starter_questions": starter_questions,
        },
        "behavior": {
            "system_prompt": settings.get("system_prompt") or "",
            "restriction_rules": settings.get("restriction_rules") or "",
            "allowed_scope": settings.get("allowed_scope") or defaults["allowed_scope"],
            "blocked_claims": settings.get("blocked_claims") or defaults["blocked_claims"],
        },
        "support_hours": {
            "opening_time": support_hours.get("opening_time", "09:00 AM"),
            "closing_time": support_hours.get("closing_time", "06:00 PM"),
            "working_days": support_hours.get("working_days", "Monday - Saturday"),
        },
        "knowledge_base": kb,
        "training_summary": kb,
    }



def _has_product_integration(cur, tenant_id: int, agent_id: Optional[int] = None) -> bool:
    try:
        if agent_id:
            cur.execute(
                """
                SELECT id FROM t_integration
                WHERE tenant_id=%s AND agent_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id, agent_id),
            )
        else:
            cur.execute(
                """
                SELECT id FROM t_integration
                WHERE tenant_id=%s
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id,),
            )
        return bool(cur.fetchone())
    except Exception:
        return False

@router.get("/agent-config")
def get_agent_config(
    agent_type: Optional[str] = None,
    agent_id: Optional[int] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    ensure_tenant_agent_settings_schema()
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant not found in token")

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, tenant_name
                FROM tenants
                WHERE id=%s
                LIMIT 1
                """,
                (tenant_id,),
            )
            tenant = cur.fetchone() or {}

            selected_agent_type = (agent_type or "").strip().lower()
            if agent_id:
                cur.execute("""
                    SELECT agent_type
                    FROM tenant_agents
                    WHERE tenant_id=%s AND id=%s
                    LIMIT 1
                """, (tenant_id, agent_id))
                agent_row = cur.fetchone() or {}
                selected_agent_type = (agent_row.get("agent_type") or selected_agent_type or "").strip().lower()
            if selected_agent_type not in {"chat", "product"}:
                selected_agent_type = "product" if _has_product_integration(cur, tenant_id, agent_id) else "chat"
            selected_agent_type = "product" if selected_agent_type == "product" else "chat"

            settings = {}
            if agent_id:
                cur.execute(
                    """
                    SELECT *
                    FROM tenant_agent_settings
                    WHERE tenant_id=%s AND agent_id=%s
                    LIMIT 1
                    """,
                    (tenant_id, agent_id),
                )
                settings = cur.fetchone() or {}

            if not settings:
                cur.execute(
                    """
                    SELECT *
                    FROM tenant_agent_settings
                    WHERE tenant_id=%s AND agent_type=%s AND agent_id IS NULL
                    LIMIT 1
                    """,
                    (tenant_id, selected_agent_type),
                )
                settings = cur.fetchone() or {}
    finally:
        conn.close()

    return {
        "success": True,
        "agent_type": selected_agent_type,
        "active_agent_type": selected_agent_type,
        "agent_id": agent_id or settings.get("agent_id"),
        "config": _build_config(tenant, settings, tenant_id),
    }


@router.post("/agent-config")
def save_agent_config(req: AgentConfigRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    ensure_tenant_agent_settings_schema()
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant not found in token")

    defaults = make_scope_for_business_type(req.business_type or "mixed")
    allowed_scope = (req.allowed_scope or defaults["allowed_scope"]).strip()
    blocked_claims = (req.blocked_claims or defaults["blocked_claims"]).strip()
    agent_type = (req.agent_type or "chat").strip().lower()
    final_agent_id = req.agent_id
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            if final_agent_id:
                cur.execute(
                    """
                    INSERT INTO tenant_agent_settings
                        (tenant_id, agent_type, agent_id, business_name, industry, business_type, business_description,
                        website_url, allowed_scope, blocked_claims, greeting_message, starter_questions,
                        system_prompt, restriction_rules, support_hours)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        agent_type=VALUES(agent_type),
                        business_name=VALUES(business_name),
                        industry=VALUES(industry),
                        business_type=VALUES(business_type),
                        business_description=VALUES(business_description),
                        website_url=VALUES(website_url),
                        allowed_scope=VALUES(allowed_scope),
                        blocked_claims=VALUES(blocked_claims),
                        greeting_message=VALUES(greeting_message),
                        starter_questions=VALUES(starter_questions),
                        system_prompt=VALUES(system_prompt),
                        restriction_rules=VALUES(restriction_rules),
                        support_hours=VALUES(support_hours),
                        updated_at=NOW()
                    """,
                    (
                        tenant_id, agent_type, final_agent_id, req.business_name, req.industry, req.business_type,
                        req.business_description, req.website_url, allowed_scope, blocked_claims, req.greeting_message,
                        json.dumps(req.starter_questions or [], ensure_ascii=False), req.system_prompt,
                        req.restriction_rules, json.dumps(req.support_hours or {}, ensure_ascii=False),
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO tenant_agent_settings
                        (tenant_id, agent_type, agent_id, business_name, industry, business_type, business_description,
                        website_url, allowed_scope, blocked_claims, greeting_message, starter_questions,
                        system_prompt, restriction_rules, support_hours)
                    VALUES (%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE
                        business_name=VALUES(business_name),
                        industry=VALUES(industry),
                        business_type=VALUES(business_type),
                        business_description=VALUES(business_description),
                        website_url=VALUES(website_url),
                        allowed_scope=VALUES(allowed_scope),
                        blocked_claims=VALUES(blocked_claims),
                        greeting_message=VALUES(greeting_message),
                        starter_questions=VALUES(starter_questions),
                        system_prompt=VALUES(system_prompt),
                        restriction_rules=VALUES(restriction_rules),
                        support_hours=VALUES(support_hours),
                        updated_at=NOW()
                    """,
                    (
                        tenant_id, agent_type, req.business_name, req.industry, req.business_type, req.business_description,
                        req.website_url, allowed_scope, blocked_claims, req.greeting_message,
                        json.dumps(req.starter_questions or [], ensure_ascii=False), req.system_prompt, req.restriction_rules,
                        json.dumps(req.support_hours or {}, ensure_ascii=False),
                    ),
                )
            cur.execute("SELECT id, slug, tenant_name FROM tenants WHERE id=%s LIMIT 1", (tenant_id,))
            tenant = cur.fetchone() or {}
            if final_agent_id:
                cur.execute(
                    "SELECT * FROM tenant_agent_settings WHERE tenant_id=%s AND agent_id=%s LIMIT 1",
                    (tenant_id, final_agent_id),
                )
            else:
                cur.execute(
                    "SELECT * FROM tenant_agent_settings WHERE tenant_id=%s AND agent_type=%s AND agent_id IS NULL LIMIT 1",
                    (tenant_id, agent_type),
                )
            settings = cur.fetchone() or {}
    finally:
        conn.close()

    return {
        "success": True,
        "message": "Agent settings saved successfully.",
        "agent_type": agent_type,
        "agent_id": final_agent_id,
        "config": _build_config(tenant, settings, tenant_id),
    }
