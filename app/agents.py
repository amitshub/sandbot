import re
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import get_main_db_connection

router = APIRouter(prefix="/api/agents", tags=["Agents"])


class AgentCreateRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_type: Optional[str] = "chat"
    handler_key: Optional[str] = None
    public_slug: Optional[str] = None


class AgentUpdateRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    handler_key: Optional[str] = None
    public_slug: Optional[str] = None
    description: Optional[str] = None


class AgentStatusRequest(BaseModel):
    status: str


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "agent"


def _random_suffix(length: int = 5) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _normalize_agent_type(value: str) -> str:
    value = (value or "chat").strip().lower()
    if value not in {"chat", "product"}:
        raise HTTPException(status_code=400, detail="agent_type must be chat or product")
    return value


def _default_handler_key(agent_type: str) -> str:
    return "product_query_bot" if agent_type == "product" else "chat_rag_agent"


def _get_columns(cur, table_name: str) -> set:
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name}")
        return {row.get("Field") for row in cur.fetchall() or []}
    except Exception:
        return set()


def ensure_agents_schema() -> None:
    """Add-only schema helper. It does not remove old columns or indexes."""
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_agents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tenant_id INT NOT NULL,
                    agent_type ENUM('chat','product') NOT NULL DEFAULT 'chat',
                    agent_name VARCHAR(255) NOT NULL,
                    status ENUM('active','inactive') DEFAULT 'inactive',
                    public_slug VARCHAR(150) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_tenant_type (tenant_id, agent_type),
                    INDEX idx_tenant_status (tenant_id, agent_type, status)
                )
                """
            )
            cols = _get_columns(cur, "tenant_agents")
            alter_map = {
                "handler_key": "ADD COLUMN handler_key VARCHAR(100) DEFAULT NULL",
                "description": "ADD COLUMN description TEXT NULL",
                "created_by": "ADD COLUMN created_by INT NULL",
            }
            for col, ddl in alter_map.items():
                if col not in cols:
                    cur.execute(f"ALTER TABLE tenant_agents {ddl}")
    finally:
        conn.close()


def _get_tenant(cur, tenant_id: int) -> dict:
    cur.execute(
        "SELECT id, slug, tenant_name, active_agent_type FROM tenants WHERE id=%s LIMIT 1",
        (tenant_id,),
    )
    tenant = cur.fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _row_response(row: dict, tenant: dict = None) -> dict:
    row = row or {}
    tenant = tenant or {}
    agent_type = row.get("agent_type") or "chat"
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "tenant_slug": tenant.get("slug") or row.get("tenant_slug"),
        "tenant_name": tenant.get("tenant_name") or row.get("tenant_name"),
        "agent_type": agent_type,
        "agent_name": row.get("agent_name") or ("Product Bot" if agent_type == "product" else "Chat Agent"),
        "status": row.get("status") or "inactive",
        "handler_key": row.get("handler_key") or _default_handler_key(agent_type),
        "public_slug": row.get("public_slug") or "",
        "description": row.get("description") or "",
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _ensure_legacy_product_agent(cur, tenant: dict, user_id: int = None) -> None:
    """Create one product card for existing tenants without disturbing old product flow."""
    tenant_id = tenant["id"]
    cur.execute("SELECT COUNT(*) AS total FROM tenant_agents WHERE tenant_id=%s AND agent_type='product'", (tenant_id,))
    if int((cur.fetchone() or {}).get("total") or 0) > 0:
        return

    integration = None
    try:
        cur.execute(
            """
            SELECT company_name, website_url
            FROM t_integration
            WHERE tenant_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (tenant_id,),
        )
        integration = cur.fetchone() or None
    except Exception:
        integration = None

    if not integration and (tenant.get("active_agent_type") or "") != "product":
        return

    name = (integration or {}).get("company_name") or tenant.get("tenant_name") or "Product Bot"
    public_slug = f"{_slugify(tenant.get('slug') or name)}-product-{_random_suffix(4)}"
    status = "active" if (tenant.get("active_agent_type") or "") == "product" else "inactive"
    cur.execute(
        """
        INSERT INTO tenant_agents
            (tenant_id, agent_type, agent_name, status, public_slug, handler_key, description, created_by)
        VALUES (%s, 'product', %s, %s, %s, 'product_query_bot', %s, %s)
        """,
        (tenant_id, name, status, public_slug, "Migrated existing product bot", user_id),
    )


def _ensure_legacy_chat_agent(cur, tenant: dict, user_id: int = None) -> None:
    """Create one chat card for existing tenants without changing old chat pipeline."""
    tenant_id = tenant["id"]
    cur.execute("SELECT COUNT(*) AS total FROM tenant_agents WHERE tenant_id=%s AND agent_type='chat'", (tenant_id,))
    if int((cur.fetchone() or {}).get("total") or 0) > 0:
        return

    name = f"{tenant.get('tenant_name') or 'Main'} Chat Agent"
    public_slug = f"{_slugify(tenant.get('slug') or name)}-chat-{_random_suffix(4)}"
    status = "active" if (tenant.get("active_agent_type") or "chat") == "chat" else "inactive"
    cur.execute(
        """
        INSERT INTO tenant_agents
            (tenant_id, agent_type, agent_name, status, public_slug, handler_key, description, created_by)
        VALUES (%s, 'chat', %s, %s, %s, 'chat_rag_agent', %s, %s)
        """,
        (tenant_id, name, status, public_slug, "Migrated existing chat agent", user_id),
    )


def _ensure_legacy_agents(cur, tenant: dict, user_id: int = None) -> None:
    _ensure_legacy_chat_agent(cur, tenant, user_id=user_id)
    _ensure_legacy_product_agent(cur, tenant, user_id=user_id)


@router.get("")
def list_agents(current_user: dict = Depends(get_current_user)):
    ensure_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    user_id = current_user.get("user_id")
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            _ensure_legacy_agents(cur, tenant, user_id=user_id)
            cur.execute(
                """
                SELECT *
                FROM tenant_agents
                WHERE tenant_id=%s
                ORDER BY FIELD(agent_type, 'chat', 'product'), id DESC
                """,
                (tenant_id,),
            )
            agents = [_row_response(row, tenant) for row in cur.fetchall() or []]
    finally:
        conn.close()
    return {"success": True, "count": len(agents), "agents": agents}


@router.post("")
def create_agent(req: AgentCreateRequest, current_user: dict = Depends(get_current_user)):
    ensure_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    user_id = current_user.get("user_id")
    agent_type = _normalize_agent_type(req.agent_type or "chat")
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            default_name = f"{tenant.get('tenant_name') or 'New'} {'Product Bot' if agent_type == 'product' else 'Chat Agent'}"
            name = (req.agent_name or "").strip() or default_name
            handler_key = (req.handler_key or _default_handler_key(agent_type)).strip() or _default_handler_key(agent_type)
            public_slug = (req.public_slug or "").strip() or f"{_slugify(tenant.get('slug') or name)}-{_slugify(name)}-{_random_suffix(5)}"
            cur.execute(
                """
                INSERT INTO tenant_agents
                    (tenant_id, agent_type, agent_name, status, public_slug, handler_key, created_by)
                VALUES (%s, %s, %s, 'inactive', %s, %s, %s)
                """,
                (tenant_id, agent_type, name, public_slug, handler_key, user_id),
            )
            agent_id = cur.lastrowid
            cur.execute("SELECT * FROM tenant_agents WHERE tenant_id=%s AND id=%s LIMIT 1", (tenant_id, agent_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": "Agent created.", "agent": agent}


@router.put("/{agent_id}")
def update_agent(agent_id: int, req: AgentUpdateRequest, current_user: dict = Depends(get_current_user)):
    ensure_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    fields = []
    values = []

    if req.agent_name is not None:
        name = req.agent_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Agent name cannot be empty")
        fields.append("agent_name=%s")
        values.append(name)
    if req.agent_type is not None:
        agent_type = _normalize_agent_type(req.agent_type)
        fields.append("agent_type=%s")
        values.append(agent_type)
        if req.handler_key is None:
            fields.append("handler_key=%s")
            values.append(_default_handler_key(agent_type))
    if req.handler_key is not None:
        fields.append("handler_key=%s")
        values.append((req.handler_key or "").strip())
    if req.public_slug is not None:
        fields.append("public_slug=%s")
        values.append(_slugify(req.public_slug))
    if req.description is not None:
        fields.append("description=%s")
        values.append(req.description)

    if not fields:
        raise HTTPException(status_code=400, detail="No changes provided")

    values.extend([tenant_id, agent_id])
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            cur.execute(
                f"""
                UPDATE tenant_agents
                SET {', '.join(fields)}, updated_at=NOW()
                WHERE tenant_id=%s AND id=%s
                """,
                tuple(values),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Agent not found")
            cur.execute("SELECT * FROM tenant_agents WHERE tenant_id=%s AND id=%s LIMIT 1", (tenant_id, agent_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": "Agent updated.", "agent": agent}


@router.patch("/{agent_id}/status")
def update_agent_status(agent_id: int, req: AgentStatusRequest, current_user: dict = Depends(get_current_user)):
    ensure_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    status = (req.status or "").strip().lower()
    if status not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail="status must be active or inactive")

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            cur.execute(
                """
                UPDATE tenant_agents
                SET status=%s, updated_at=NOW()
                WHERE tenant_id=%s AND id=%s
                """,
                (status, tenant_id, agent_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Agent not found")
            cur.execute("SELECT * FROM tenant_agents WHERE tenant_id=%s AND id=%s LIMIT 1", (tenant_id, agent_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": f"Agent marked {status}.", "agent": agent}


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, current_user: dict = Depends(get_current_user)):
    ensure_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tenant_agents WHERE tenant_id=%s AND id=%s",
                (tenant_id, agent_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Agent not found")
    finally:
        conn.close()
    return {"success": True, "message": "Agent deleted.", "deleted_agent_id": agent_id}
