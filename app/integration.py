from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import pymysql
import os

router = APIRouter(prefix="/integration", tags=["Integration"])


def get_main_db():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
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


@router.post("/save")
def save_integration(data: IntegrationRequest):
    allowed_platforms = ["wordpress", "shopify", "wix", "react", "html", "nextjs"]

    if data.platform not in allowed_platforms:
        raise HTTPException(status_code=400, detail="Invalid platform selected")

    try:
        conn = get_main_db()
        with conn.cursor() as cursor:
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
                    website_url
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                data.website_url
            ))

        return {
            "success": True,
            "message": "Integration details saved successfully"
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
                    created_at
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