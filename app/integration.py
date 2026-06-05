from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from app.auth import get_current_user
import pymysql
import os

router = APIRouter(prefix="/integration", tags=["Integration"])


def get_main_db():
    return pymysql.connect(
        host=os.getenv("MAIN_DB_HOST"),
        user=os.getenv("MAIN_DB_USER"),
        password=os.getenv("MAIN_DB_PASSWORD"),
        database=os.getenv("MAIN_DB_NAME"),
        port=int(os.getenv("MAIN_DB_PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


class IntegrationRequest(BaseModel):
    tenant_id: int | None = None
    tenant_slug: str | None = None
    company_name: str | None = None
    platform: str
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str
    website_url: str | None = None
    agent_id: int | None = None


@router.post("/save")
def save_integration(data: IntegrationRequest):
    allowed_platforms = ["wordpress", "shopify", "wix", "react", "html", "nextjs"]

    if data.platform not in allowed_platforms:
        raise HTTPException(status_code=400, detail="Invalid platform selected")

    try:
        conn = get_main_db()
        with conn.cursor() as cursor:
            try:
                cursor.execute("SHOW COLUMNS FROM t_integration LIKE 'agent_id'")
                if not cursor.fetchone():
                    cursor.execute("ALTER TABLE t_integration ADD COLUMN agent_id INT NULL")
            except Exception:
                pass

            if data.agent_id:
                cursor.execute(
                    """
                    UPDATE t_integration
                    SET tenant_slug=%s, company_name=%s, platform=%s, db_host=%s, db_port=%s,
                        db_user=%s, db_password=%s, db_name=%s, website_url=%s, status=COALESCE(status,'active')
                    WHERE tenant_id=%s AND agent_id=%s
                    """,
                    (data.tenant_slug, data.company_name, data.platform, data.db_host, data.db_port,
                     data.db_user, data.db_password, data.db_name, data.website_url, data.tenant_id, data.agent_id),
                )
                if cursor.rowcount:
                    return {"success": True, "message": "Integration details updated successfully", "agent_type": "product", "agent_id": data.agent_id}

            sql = """
                INSERT INTO t_integration
                (
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
                    agent_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """

            cursor.execute(sql, (
                data.tenant_id,
                data.tenant_slug,
                data.company_name,
                data.platform,
                data.db_host,
                data.db_port,
                data.db_user,
                data.db_password,
                data.db_name,
                data.website_url,
                data.agent_id
            ))

            # Do not mark the whole tenant as product here.
            # Product bot active/inactive is now controlled by tenant_agents.status.

        return {
            "success": True,
            "message": "Integration details saved successfully",
            "agent_type": "product"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
def list_integrations():
    try:
        conn = get_main_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    tenant_id,
                    tenant_slug,
                    company_name,
                    platform,
                    db_host,
                    db_port,
                    db_user,
                    db_name,
                    website_url,
                    status,
                    created_at,
                    agent_id
                FROM t_integration
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()

        return {
            "success": True,
            "data": rows
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/current")
def get_current_integration(
    agent_id: int | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user.get("tenant_id")
    try:
        conn = get_main_db()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, tenant_id, tenant_slug, company_name, platform, db_host, db_port,
                       db_user, db_password, db_name, website_url, status, agent_id, created_at
                FROM t_integration
                WHERE tenant_id=%s
                  AND (%s IS NULL OR agent_id=%s)
                  AND (status IS NULL OR status='active')
                ORDER BY id DESC
                LIMIT 1
                """,
                (tenant_id, agent_id, agent_id),
            )
            row = cursor.fetchone()
        return {"success": True, "data": row, "agent_id": agent_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
