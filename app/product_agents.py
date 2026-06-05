import re
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import get_main_db_connection

router = APIRouter(prefix="/api/product-agents", tags=["Product Agents"])


class ProductAgentCreateRequest(BaseModel):
    agent_name: Optional[str] = None
    handler_key: Optional[str] = "product_query_bot"
    public_slug: Optional[str] = None


class ProductAgentUpdateRequest(BaseModel):
    agent_name: Optional[str] = None
    handler_key: Optional[str] = None
    public_slug: Optional[str] = None


class ProductAgentStatusRequest(BaseModel):
    status: str


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "product-bot"


def _random_suffix(length: int = 5) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _get_columns(cur, table_name: str) -> set:
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name}")
        return {row.get("Field") for row in cur.fetchall() or []}
    except Exception:
        return set()


def ensure_product_agents_schema() -> None:
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_agents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tenant_id INT NOT NULL,
                    agent_type ENUM('chat','product') NOT NULL DEFAULT 'product',
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
            if "handler_key" not in cols:
                cur.execute("ALTER TABLE tenant_agents ADD COLUMN handler_key VARCHAR(100) DEFAULT 'product_query_bot'")
            if "description" not in cols:
                cur.execute("ALTER TABLE tenant_agents ADD COLUMN description TEXT NULL")
            if "created_by" not in cols:
                cur.execute("ALTER TABLE tenant_agents ADD COLUMN created_by INT NULL")
    finally:
        conn.close()


def _row_response(row: dict, tenant: dict = None) -> dict:
    row = row or {}
    tenant = tenant or {}
    return {
        "id": row.get("id"),
        "tenant_id": row.get("tenant_id"),
        "tenant_slug": tenant.get("slug") or row.get("tenant_slug"),
        "tenant_name": tenant.get("tenant_name") or row.get("tenant_name"),
        "agent_type": row.get("agent_type") or "product",
        "agent_name": row.get("agent_name") or "Product Bot",
        "status": row.get("status") or "inactive",
        "handler_key": row.get("handler_key") or "product_query_bot",
        "public_slug": row.get("public_slug") or "",
        "description": row.get("description") or "",
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


def _get_tenant(cur, tenant_id: int) -> dict:
    cur.execute("SELECT id, slug, tenant_name FROM tenants WHERE id=%s LIMIT 1", (tenant_id,))
    tenant = cur.fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _ensure_legacy_product_agent(cur, tenant: dict, user_id: int = None) -> None:
    """Create one product-agent card for old tenants that already have product integration/settings."""
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

    if not integration:
        return

    name = (integration or {}).get("company_name") or tenant.get("tenant_name") or "Product Bot"
    public_slug = f"{_slugify(tenant.get('slug') or name)}-product-{_random_suffix(4)}"
    status = "active" if integration else "inactive"
    cur.execute(
        """
        INSERT INTO tenant_agents
            (tenant_id, agent_type, agent_name, status, public_slug, handler_key, description, created_by)
        VALUES (%s, 'product', %s, %s, %s, 'product_query_bot', %s, %s)
        """,
        (tenant_id, name, status, public_slug, "Migrated existing product bot", user_id),
    )


@router.get("")
def list_product_agents(current_user: dict = Depends(get_current_user)):
    ensure_product_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    user_id = current_user.get("user_id")
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            _ensure_legacy_product_agent(cur, tenant, user_id=user_id)
            cur.execute(
                """
                SELECT *
                FROM tenant_agents
                WHERE tenant_id=%s AND agent_type='product'
                ORDER BY id DESC
                """,
                (tenant_id,),
            )
            agents = [_row_response(row, tenant) for row in cur.fetchall() or []]
    finally:
        conn.close()
    return {"success": True, "count": len(agents), "agents": agents}


@router.post("")
def create_product_agent(req: ProductAgentCreateRequest, current_user: dict = Depends(get_current_user)):
    ensure_product_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    user_id = current_user.get("user_id")
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            tenant = _get_tenant(cur, tenant_id)
            name = (req.agent_name or "").strip() or f"{tenant.get('tenant_name') or 'Product'} Bot"
            handler_key = (req.handler_key or "product_query_bot").strip() or "product_query_bot"
            public_slug = (req.public_slug or "").strip() or f"{_slugify(tenant.get('slug') or name)}-{_slugify(name)}-{_random_suffix(5)}"
            cur.execute(
                """
                INSERT INTO tenant_agents
                    (tenant_id, agent_type, agent_name, status, public_slug, handler_key, created_by)
                VALUES (%s, 'product', %s, 'inactive', %s, %s, %s)
                """,
                (tenant_id, name, public_slug, handler_key, user_id),
            )
            agent_id = cur.lastrowid
            cur.execute("SELECT * FROM tenant_agents WHERE id=%s AND tenant_id=%s LIMIT 1", (agent_id, tenant_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": "Product agent created.", "agent": agent}


@router.put("/{agent_id}")
def update_product_agent(agent_id: int, req: ProductAgentUpdateRequest, current_user: dict = Depends(get_current_user)):
    ensure_product_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    fields = []
    values = []
    if req.agent_name is not None:
        name = req.agent_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Agent name cannot be empty")
        fields.append("agent_name=%s")
        values.append(name)
    if req.handler_key is not None:
        fields.append("handler_key=%s")
        values.append((req.handler_key or "product_query_bot").strip() or "product_query_bot")
    if req.public_slug is not None:
        fields.append("public_slug=%s")
        values.append(_slugify(req.public_slug))
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
                WHERE tenant_id=%s AND id=%s AND agent_type='product'
                """,
                tuple(values),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Product agent not found")
            cur.execute("SELECT * FROM tenant_agents WHERE tenant_id=%s AND id=%s LIMIT 1", (tenant_id, agent_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": "Product agent updated.", "agent": agent}


@router.patch("/{agent_id}/status")
def update_product_agent_status(agent_id: int, req: ProductAgentStatusRequest, current_user: dict = Depends(get_current_user)):
    ensure_product_agents_schema()
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
                WHERE tenant_id=%s AND id=%s AND agent_type='product'
                """,
                (status, tenant_id, agent_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Product agent not found")
            cur.execute("SELECT * FROM tenant_agents WHERE tenant_id=%s AND id=%s LIMIT 1", (tenant_id, agent_id))
            agent = _row_response(cur.fetchone() or {}, tenant)
    finally:
        conn.close()
    return {"success": True, "message": f"Product agent marked {status}.", "agent": agent}


@router.delete("/{agent_id}")
def delete_product_agent(agent_id: int, current_user: dict = Depends(get_current_user)):
    ensure_product_agents_schema()
    tenant_id = int(current_user["tenant_id"])
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tenant_agents WHERE tenant_id=%s AND id=%s AND agent_type='product'",
                (tenant_id, agent_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Product agent not found")
    finally:
        conn.close()
    return {"success": True, "message": "Product agent deleted.", "deleted_agent_id": agent_id}
