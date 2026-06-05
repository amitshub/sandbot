"""Clean generic chatbot bridge for the KB-grounded chat_agent flow.

Purpose:
- Keep chatbot.py as a thin shell: session, welcome, history, and response shape.
- Route sales/support/company-section questions to app.chat_agent.engine.run_sales_support_agent.
- Avoid company-specific/product-specific hardcoding in this file.

Company-specific facts must come from:
- tenant settings
- tenant knowledge base / FAISS
- app.chat_agent retrieval + prompt pipeline
"""

import re
from typing import Any, Dict, List, Tuple

from app.session_store import load_chat_history, save_chat_history

try:
    from app.chat_agent.engine import run_sales_support_agent
except Exception as exc:  # keeps deployment safe if chat_agent import fails
    print("[SALES SUPPORT AGENT IMPORT ERROR]", repr(exc))
    run_sales_support_agent = None

try:
    from app.chat_agent.settings import get_agent_settings
except Exception as exc:  # keeps deployment safe during local tests
    print("[CHAT AGENT SETTINGS IMPORT ERROR]", repr(exc))
    get_agent_settings = None


WELCOME_MESSAGE_KEY = "__welcome__"

DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
- Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
- If trained context is missing or not enough, give a safe, generic, human reply.
- Keep replies short, clear, and helpful."""


# -----------------------------------------------------------------------------
# Small generic helpers
# -----------------------------------------------------------------------------


def empty_assets() -> Dict[str, Any]:
    return {
        "images": [],
        "links": [],
        "sources": [],
        "images_count": 0,
        "links_count": 0,
    }


def clean_ai_reply(reply: str) -> str:
    text = (reply or "").strip()
    for phrase in [
        "According to the provided context,",
        "Based on the provided context,",
        "Based on the context,",
        "According to the context,",
        "From the context,",
        "According to the knowledge base,",
        "Based on the knowledge base,",
        "Based on our conversation,",
        "Based on our previous conversation,",
        "As per our conversation,",
        "As discussed,",
    ]:
        text = text.replace(phrase, "").strip()
    text = re.sub(
        r"^(based on our conversation|based on our previous conversation|as per our conversation|as discussed)[:,\s-]+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def safe_customer_answer(answer: str) -> str:
    """Final customer-facing cleanup only. No business facts are added here."""
    text = clean_ai_reply(answer or "")
    text = re.sub(r"\b(Product|Option|Category)\s+\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _has_phrase(value: str, phrases: List[str]) -> bool:
    text = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', (value or '').lower()).strip()} "
    for phrase in phrases:
        p = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', phrase.lower()).strip()} "
        if p.strip() and p in text:
            return True
    return False


def is_greeting_only(message: str) -> bool:
    value = (message or "").strip().lower()
    return value in {
        "hi",
        "hii",
        "hello",
        "hey",
        "hey there",
        "good morning",
        "good afternoon",
        "good evening",
        "namaste",
    }


def user_requests_english(message: str) -> bool:
    value = (message or "").lower()
    return any(
        x in value
        for x in ["talk in english", "speak english", "english only", "reply in english", "in english"]
    )


def wants_assets(message: str) -> bool:
    """Only expose retrieved assets when the customer asks for them."""
    return _has_phrase(
        message or "",
        [
            "image",
            "images",
            "photo",
            "photos",
            "picture",
            "pictures",
            "catalog",
            "catalogue",
            "brochure",
            "show me",
            "i want to see",
            "want to see",
            "product images",
            "show me product images",
            "get me product images",
            "see images",
            "show images",
            "share link",
            "send link",
        ],
    )


def _normalize_assets(assets: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(assets, dict):
        return empty_assets()

    images = assets.get("images") or []
    links = assets.get("links") or []
    sources = assets.get("sources") or []

    if isinstance(images, str):
        images = [images]
    if isinstance(links, str):
        links = [links]
    if isinstance(sources, str):
        sources = [sources]

    return {
        "images": [str(x).strip() for x in images if str(x).strip()],
        "links": [str(x).strip() for x in links if str(x).strip()],
        "sources": [str(x).strip() for x in sources if str(x).strip()],
        "images_count": len([x for x in images if str(x).strip()]),
        "links_count": len([x for x in links if str(x).strip()]),
    }


def _settings_for_chat(tenant_id, agent_type: str = "chat", agent_id=None) -> Dict[str, Any]:
    if callable(get_agent_settings):
        try:
            settings = get_agent_settings(tenant_id, agent_type=agent_type, agent_id=agent_id) or {}
            if isinstance(settings, dict):
                return settings
        except Exception as exc:
            print("[CHAT SETTINGS ERROR]", repr(exc))
    return {
        "tenant_name": "",
        "business_name": "our team",
        "greeting_message": "",
        "starter_questions": [],
        "restriction_rules": DEFAULT_RESTRICTION_RULES,
    }


def _display_business_name(settings: Dict[str, Any]) -> str:
    name = (
        settings.get("business_name")
        or settings.get("tenant_name")
        or "our team"
    )
    return str(name).strip() or "our team"


def build_first_welcome_message(settings: Dict[str, Any]) -> str:
    """Generic welcome. Do not mention any fixed industry/product."""
    custom = (settings.get("greeting_message") or "").strip()
    if custom:
        return custom

    business_name = _display_business_name(settings)
    if business_name == "our team":
        return "Hi, welcome. How can I help you today?"
    return f"Hi, welcome to {business_name}. How can I help you today?"


def fallback_answer(settings: Dict[str, Any] = None) -> str:
    business_name = _display_business_name(settings or {})
    team = f"{business_name} team" if business_name != "our team" else "our team"
    return (
        "I don’t have this exact detail in the current information. "
        f"Please share a little more, and {team} can guide you better."
    )


# -----------------------------------------------------------------------------
# chat_agent bridge
# -----------------------------------------------------------------------------


def run_sales_support_agent_safe(
    tenant_id,
    session_id: str,
    message: str,
    top_k: int = 5,
    agent_id=None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Call the KB-grounded chat_agent and normalize its output."""
    if not callable(run_sales_support_agent):
        return "", empty_assets(), {"sales_agent_available": False}

    try:
        result = run_sales_support_agent(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            top_k=top_k,
            agent_id=agent_id,
        )

        if isinstance(result, str):
            answer = result.strip()
            assets = empty_assets()
            debug = {"sales_agent_result_type": "str"}
        elif isinstance(result, dict):
            answer = str(
                result.get("answer")
                or result.get("reply")
                or result.get("response")
                or result.get("message")
                or ""
            ).strip()
            assets = _normalize_assets(result.get("assets") or {})
            debug = {
                "sales_agent_result_type": "dict",
                "sales_agent_intent": result.get("intent"),
                "sales_agent_match_quality": result.get("match_quality"),
            }
        else:
            return "", empty_assets(), {"sales_agent_result_type": type(result).__name__}

        weak_outputs = {
            "Sales support agent initialized.",
            "Generated response from Sales Support Agent.",
            "Sales support agent response generated successfully.",
        }
        if answer in weak_outputs:
            return "", empty_assets(), {
                **debug,
                "sales_agent_skipped_reason": "placeholder_response",
            }

        return safe_customer_answer(answer), assets, debug

    except Exception as exc:
        print("[SALES SUPPORT AGENT ERROR]", repr(exc))
        return "", empty_assets(), {"sales_agent_error": repr(exc)}


# -----------------------------------------------------------------------------
# History + response shape
# -----------------------------------------------------------------------------


def save_history(tenant_id, session_id: str, history: List[Dict[str, str]], message: str, answer: str, agent_id=None):
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    del history[:-20]
    save_chat_history(tenant_id, session_id, history, agent_id=agent_id)


def build_response(
    tenant_id,
    session_id: str,
    history: List[Dict[str, str]],
    answer: str,
    assets: Dict[str, Any] = None,
    debug: Dict[str, Any] = None,
    agent_id=None,
) -> Dict[str, Any]:
    clean_answer = safe_customer_answer(answer)
    clean_assets = _normalize_assets(assets or {})
    return {
        "answer": clean_answer,
        "session_id": session_id,
        "images": clean_assets.get("images", []),
        "links": clean_assets.get("links", []),
        "sources": clean_assets.get("sources", []),
        "images_count": len(clean_assets.get("images", []) or []),
        "links_count": len(clean_assets.get("links", []) or []),
        "history_count": len(history),
        "debug": {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            **(debug or {}),
        },
    }


# -----------------------------------------------------------------------------
# Main entrypoint used by your app
# -----------------------------------------------------------------------------


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5, agent_id=None) -> Dict[str, Any]:
    """Main clean chatbot entrypoint.

    This file intentionally does not contain industry-specific product logic.
    All real answering goes through app.chat_agent, which retrieves from tenant KB.
    """
    session_id = session_id or "default"
    message = (message or "").strip()
    history = load_chat_history(tenant_id, session_id, agent_id=agent_id) or []
    settings = _settings_for_chat(tenant_id, agent_id=agent_id)

    # Welcome route only. No FAISS/product hardcoding here.
    if message == WELCOME_MESSAGE_KEY:
        answer = build_first_welcome_message(settings)
        return {
            "answer": answer,
            "session_id": session_id,
            "tenant_name": settings.get("tenant_name"),
            "business_name": settings.get("business_name"),
            "starter_questions": settings.get("starter_questions", []) or [],
            **empty_assets(),
            "history_count": len(history),
            "debug": {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "welcome_only": True,
                "flow": "clean_chatbot_bridge",
            },
        }

    # Empty message guard.
    if not message:
        answer = "Please type your question, and I’ll help you."
        return build_response(
            tenant_id,
            session_id,
            history,
            answer,
            empty_assets(),
            {"flow": "empty_message"},
            agent_id=agent_id,
        )

    # Simple greeting stays outside agent to keep chat fast and natural.
    if is_greeting_only(message):
        answer = build_first_welcome_message(settings)
        save_history(tenant_id, session_id, history, message, answer, agent_id=agent_id)
        return build_response(
            tenant_id,
            session_id,
            history,
            answer,
            empty_assets(),
            {"flow": "greeting"},
            agent_id=agent_id,
        )

    if user_requests_english(message):
        answer = "Sure, I’ll continue in English. How can I help you today?"
        save_history(tenant_id, session_id, history, message, answer, agent_id=agent_id)
        return build_response(
            tenant_id,
            session_id,
            history,
            answer,
            empty_assets(),
            {"flow": "language_preference"},
            agent_id=agent_id,
        )

    # Main KB-grounded sales/support/company-section flow.
    answer, assets, agent_debug = run_sales_support_agent_safe(
        tenant_id=tenant_id,
        session_id=session_id,
        message=message,
        top_k=max(top_k or 5, 8),
        agent_id=agent_id,
    )

    if not answer:
        answer = fallback_answer(settings)
        assets = empty_assets()

    # Do not push links/images unless customer asked for them.
    # agent_intent = (agent_debug or {}).get("sales_agent_intent")
    # if not wants_assets(message) and agent_intent not in {
    #     "career", "dealership", "contact", "article_post",
    #     "certification", "specification", "installation"
    # }:
    #     assets = empty_assets()

    # Never show images/products unless user explicitly asks for images/catalogue.
    agent_intent = (agent_debug or {}).get("sales_agent_intent")

    if agent_intent != "image_request":
        assets = {
            **_normalize_assets(assets),
            "images": [],
            "images_count": 0,
        }

    # Never show extra links/images for simple contact questions.
    if agent_intent == "contact":
        assets = empty_assets()

    # Only allow assets for explicit asset/page requests.
    elif not wants_assets(message) and agent_intent not in {
        "career",
        "dealership",
        "article_post",
        "certification",
        "specification",
        "installation",
        "image_request",
    }:
        assets = empty_assets()

    save_history(tenant_id, session_id, history, message, answer, agent_id=agent_id)

    return build_response(
        tenant_id,
        session_id,
        history,
        answer,
        assets,
        {
            "flow": "chat_agent_first",
            "sales_support_agent_used": bool(answer),
            "sales_support_agent_debug": agent_debug,
            "assets_allowed": wants_assets(message),
        },
        agent_id=agent_id,
    )
