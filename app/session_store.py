import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils import DATA_DIR, load_json, safe_filename, save_json


SESSION_DIR = Path(os.getenv("SESSION_DIR", str(DATA_DIR / "chat_sessions")))
SESSION_DIR.mkdir(parents=True, exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL", "").strip()
REDIS_PREFIX = os.getenv("REDIS_SESSION_PREFIX", "business_bot")
REDIS_TTL_SECONDS = int(os.getenv("REDIS_SESSION_TTL_SECONDS", str(60 * 60 * 24 * 30)))

_redis_client = None
_redis_checked = False


def _get_redis_client():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    if not REDIS_URL:
        return None

    try:
        import redis

        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        _redis_client = client
    except Exception as exc:
        print("[SESSION STORE] Redis unavailable, using /data files:", repr(exc))
        _redis_client = None

    return _redis_client


def _safe_key_part(value: Any) -> str:
    value = str(value or "default").strip()
    value = value.replace(":", "_")
    return safe_filename(value) or "default"


def _store_key(kind: str, tenant_id: Any, session_id: str) -> str:
    return f"{REDIS_PREFIX}:{kind}:{_safe_key_part(tenant_id)}:{_safe_key_part(session_id)}"


def _store_path(kind: str, tenant_id: Any, session_id: str) -> Path:
    return SESSION_DIR / kind / _safe_key_part(tenant_id) / f"{_safe_key_part(session_id)}.json"


def load_session_data(kind: str, tenant_id: Any, session_id: str, default: Optional[Any] = None):
    client = _get_redis_client()
    key = _store_key(kind, tenant_id, session_id)

    if client:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            print("[SESSION STORE] Redis read failed:", repr(exc))

    path = _store_path(kind, tenant_id, session_id)
    return load_json(path, default=default)


def save_session_data(kind: str, tenant_id: Any, session_id: str, data: Any) -> None:
    client = _get_redis_client()
    key = _store_key(kind, tenant_id, session_id)

    if client:
        try:
            client.setex(key, REDIS_TTL_SECONDS, json.dumps(data, ensure_ascii=False))
            return
        except Exception as exc:
            print("[SESSION STORE] Redis write failed, using /data files:", repr(exc))

    path = _store_path(kind, tenant_id, session_id)
    save_json(path, data)


def load_chat_history(tenant_id: Any, session_id: str) -> List[Dict[str, str]]:
    data = load_session_data("chat_history", tenant_id, session_id, default=[])
    return data if isinstance(data, list) else []


def save_chat_history(tenant_id: Any, session_id: str, history: List[Dict[str, str]]) -> None:
    save_session_data("chat_history", tenant_id, session_id, history[-20:])


def load_chat_state(tenant_id: Any, session_id: str) -> Dict[str, Any]:
    data = load_session_data("chat_state", tenant_id, session_id, default={})
    return data if isinstance(data, dict) else {}


def save_chat_state(tenant_id: Any, session_id: str, state: Dict[str, Any]) -> None:
    save_session_data("chat_state", tenant_id, session_id, state or {})


def load_product_session(tenant_id: Any, session_id: str, default: Dict[str, Any]) -> Dict[str, Any]:
    data = load_session_data("product_session", tenant_id, session_id, default=default)
    return data if isinstance(data, dict) else default.copy()


def save_product_session(tenant_id: Any, session_id: str, session: Dict[str, Any]) -> None:
    save_session_data("product_session", tenant_id, session_id, session or {})
