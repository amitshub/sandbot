import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.db import get_main_db_connection

router = APIRouter(tags=["Agent Widget Settings"])

DEFAULT_THEME_CONFIG = {
    "primary_color": "#7c3aed",
    "secondary_color": "#ede9fe",
    "background_color": "#ffffff",
    "text_color": "#0f172a",
}

DEFAULT_WIDGET_CONFIG = {
    "font_family": "System Default",
    "widget_position": "bottom_right",
    "offset_horizontal": 20,
    "offset_vertical": 20,
    "button_effect": "none",
}

DEFAULT_BEHAVIOR_CONFIG = {
    "show_handoff_cta": True,
    "show_online_badge": True,
}


class WidgetSettingsRequest(BaseModel):
    agent_type: str = "chat"
    theme_name: Optional[str] = "custom"
    theme_config: Optional[Dict[str, Any]] = None
    widget_config: Optional[Dict[str, Any]] = None
    behavior_config: Optional[Dict[str, Any]] = None


def normalize_agent_type(value: str) -> str:
    value = (value or "chat").strip().lower()
    return value or "chat"


def _json_load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def ensure_widget_settings_schema() -> None:
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tenant_agent_widget_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    tenant_id INT NOT NULL,
                    agent_type VARCHAR(50) NOT NULL,
                    theme_name VARCHAR(100) DEFAULT 'custom',
                    theme_config JSON NULL,
                    widget_config JSON NULL,
                    behavior_config JSON NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_tenant_agent_widget (tenant_id, agent_type)
                )
                """
            )
    finally:
        conn.close()


def _build_response(row: Optional[Dict[str, Any]], tenant_id: int, agent_type: str) -> Dict[str, Any]:
    row = row or {}
    theme_config = _json_load(row.get("theme_config"), default={}) or {}
    widget_config = _json_load(row.get("widget_config"), default={}) or {}
    behavior_config = _json_load(row.get("behavior_config"), default={}) or {}

    return {
        "success": True,
        "tenant_id": tenant_id,
        "agent_type": agent_type,
        "settings": {
            "theme_name": row.get("theme_name") or "custom",
            "theme_config": {**DEFAULT_THEME_CONFIG, **theme_config},
            "widget_config": {**DEFAULT_WIDGET_CONFIG, **widget_config},
            "behavior_config": {**DEFAULT_BEHAVIOR_CONFIG, **behavior_config},
        },
    }


def _get_tenant_by_slug(tenant_slug: str) -> Optional[Dict[str, Any]]:
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, slug, tenant_name, status
                FROM tenants
                WHERE slug=%s AND status='active'
                LIMIT 1
                """,
                ((tenant_slug or "").strip(),),
            )
            return cur.fetchone()
    finally:
        conn.close()


def _get_settings_row(tenant_id: int, agent_type: str) -> Optional[Dict[str, Any]]:
    ensure_widget_settings_schema()
    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tenant_id, agent_type, theme_name, theme_config, widget_config, behavior_config
                FROM tenant_agent_widget_settings
                WHERE tenant_id=%s AND agent_type=%s
                LIMIT 1
                """,
                (tenant_id, agent_type),
            )
            return cur.fetchone()
    finally:
        conn.close()


@router.get("/agent-widget-settings")
def get_agent_widget_settings(
    agent_type: str = Query("chat"),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = int(current_user["tenant_id"])
    agent_type = normalize_agent_type(agent_type)
    row = _get_settings_row(tenant_id, agent_type)
    return _build_response(row, tenant_id, agent_type)


@router.post("/agent-widget-settings")
def save_agent_widget_settings(
    request: WidgetSettingsRequest,
    agent_type: str = Query(None),
    current_user: dict = Depends(get_current_user),
):
    ensure_widget_settings_schema()
    tenant_id = int(current_user["tenant_id"])
    final_agent_type = normalize_agent_type(agent_type or request.agent_type)

    theme_config = {**DEFAULT_THEME_CONFIG, **(request.theme_config or {})}
    widget_config = {**DEFAULT_WIDGET_CONFIG, **(request.widget_config or {})}
    behavior_config = {**DEFAULT_BEHAVIOR_CONFIG, **(request.behavior_config or {})}

    conn = get_main_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_agent_widget_settings
                    (tenant_id, agent_type, theme_name, theme_config, widget_config, behavior_config)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    theme_name=VALUES(theme_name),
                    theme_config=VALUES(theme_config),
                    widget_config=VALUES(widget_config),
                    behavior_config=VALUES(behavior_config),
                    updated_at=NOW()
                """,
                (
                    tenant_id,
                    final_agent_type,
                    request.theme_name or "custom",
                    json.dumps(theme_config),
                    json.dumps(widget_config),
                    json.dumps(behavior_config),
                ),
            )
    finally:
        conn.close()

    row = _get_settings_row(tenant_id, final_agent_type)
    response = _build_response(row, tenant_id, final_agent_type)
    response["message"] = "Widget appearance saved successfully."
    return response


@router.get("/public-agent-widget-settings/{tenant_slug}")
def get_public_agent_widget_settings(tenant_slug: str, agent_type: str = Query("chat")):
    tenant = _get_tenant_by_slug(tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive.")

    tenant_id = int(tenant["id"])
    agent_type = normalize_agent_type(agent_type)
    row = _get_settings_row(tenant_id, agent_type)
    response = _build_response(row, tenant_id, agent_type)
    response["tenant_slug"] = tenant.get("slug")
    return response
