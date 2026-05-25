from typing import Any, Dict, List

from app.session_store import load_chat_history

from .asset_layer import build_assets, normalize_url
from .fallback_layer import build_fallback_reply
from .intent_router import detect_chat_intent
from .product_memory import build_product_memory
from .prompt_builder import build_prompt
from .response_generator import generate_response
from .retrieval import build_context, retrieve_context, retrieve_overview_context
from .sales_layer import apply_sales_strategy
from .settings import get_agent_settings
from .support_layer import apply_support_strategy


def _normalize_user_message(message: str) -> str:
    text = (message or "").strip()

    replacements = {
        "136l": "316l",
        "136L": "316L",
        "moy hosue": "my house",
        "moy house": "my house",
        "my hosue": "my house",
        "hosue": "house",
    }

    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)

    return text


def _history_to_text(history: List[Dict[str, str]], limit: int = 6) -> str:
    lines = []
    for item in (history or [])[-limit:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or "user"
        content = item.get("content") or ""
        if content:
            lines.append(f"{role}: {content}")
    return " ".join(lines)


def _contact_reply(settings: Dict[str, Any], message: str) -> str:
    value = (message or "").lower()
    contact = settings.get("contact") or {}

    website = (
        contact.get("website_url")
        or contact.get("website")
        or contact.get("business_website")
        or contact.get("client_domain")
    )
    phone = (
        contact.get("support_phone")
        or contact.get("phone")
        or contact.get("mobile")
        or contact.get("whatsapp_number")
    )
    email = contact.get("support_email") or contact.get("email") or contact.get("business_email")
    address = contact.get("address")

    if "website" in value or "site" in value or "url" in value:
        return (
            f"You can visit our website here: {normalize_url(str(website))}"
            if website
            else "I can connect you with our team for the correct website details."
        )

    if "email" in value or "mail" in value:
        return (
            f"You can email us at: {email}"
            if email
            else "I can connect you with our team for the correct email details."
        )

    if "address" in value or "location" in value:
        return (
            f"Our address is: {address}"
            if address
            else "I can connect you with our team for the correct address details."
        )

    if phone:
        return f"You can contact us on this number: {phone}"

    return "Sure, I can connect you with our team. Our sales team will contact you shortly."


def run_sales_support_agent(
    tenant_id: int,
    session_id: str,
    message: str,
    top_k: int = 5,
    agent_type: str = "chat",
) -> Dict[str, Any]:

    session_id = session_id or "default"
    message = _normalize_user_message(message)

    settings = get_agent_settings(tenant_id, agent_type=agent_type)
    intent = detect_chat_intent(message)

    if intent == "empty":
        answer = "Please type your message."
        return {
            "answer": answer,
            "reply": answer,
            "session_id": session_id,
            "intent": intent,
            "images": [],
            "links": [],
            "sources": [],
        }

    if intent == "human_connect":
        answer = build_fallback_reply(intent, settings=settings)
        return {
            "answer": answer,
            "reply": answer,
            "session_id": session_id,
            "intent": intent,
            "images": [],
            "links": [],
            "sources": [],
        }

    if intent == "contact":
        answer = _contact_reply(settings, message)
        return {
            "answer": answer,
            "reply": answer,
            "session_id": session_id,
            "intent": intent,
            "images": [],
            "links": [],
            "sources": [],
        }

    history = load_chat_history(tenant_id, session_id)
    history_text = _history_to_text(history, limit=6)

    if intent in {"product_overview", "product_options"}:
        results = retrieve_overview_context(
            tenant_id=tenant_id,
            message=message,
            business_type=settings.get("business_type") or "",
            top_k=max(top_k, 8),
        )

    elif intent == "buying_guidance":
        results = retrieve_context(
            tenant_id=tenant_id,
            query=(
                f"{history_text} {message} "
                "recommended product suitable requirement use case "
                "specification material application product guidance"
            ),
            top_k=max(top_k, 8),
        )

        results = [
            r for r in results
            if r.get("page_type") not in ["blog_page", "article_page", "policy_page"]
        ] or results

    elif intent == "trust_proof":
        results = retrieve_context(
            tenant_id=tenant_id,
            query=(
                f"{message} "
                "clients projects supplied case study installations "
                "trusted by certification certified certificate "
                "ISO BIS ISI approved quality standard industries served experience"
                
            ),
            top_k=max(top_k, 10),
        )

        results = [
            r for r in results
            if r.get("page_type") not in ["blog_page", "article_page", "policy_page"]
        ] or results

    else:
        results = retrieve_context(
            tenant_id=tenant_id,
            query=message,
            top_k=top_k,
        )

    context = build_context(results, max_chars=2600)
    assets = build_assets(results)
    memory = build_product_memory(results, context=context)

    sales_strategy = apply_sales_strategy(intent, memory)
    support_strategy = apply_support_strategy(intent, memory)

    prompt = build_prompt(
        message=message,
        context=context,
        settings=settings,
        intent=intent,
        memory={
            **memory,
            "sales_strategy": sales_strategy,
            "support_strategy": support_strategy,
        },
        history=history,
    )

    answer = generate_response(
        prompt,
        business_name=settings.get("business_name")
        or settings.get("tenant_name")
        or "our team",
    )

    if not answer:
        answer = build_fallback_reply(
            intent=intent,
            memory=memory,
            settings=settings,
        )

    if intent == "image_request" and assets.get("images") and not any(
        img in answer for img in assets["images"][:2]
    ):
        answer = f"{answer}\n\nRelevant image(s):\n" + "\n".join(assets["images"][:3])

    if any(
        word in message.lower()
        for word in ["link", "url", "website", "buy", "catalog", "catalogue"]
    ) and assets.get("links"):
        if not any(link in answer for link in assets["links"][:2]):
            answer = f"{answer}\n\nRelevant link(s):\n" + "\n".join(assets["links"][:3])

    return {
        "answer": answer,
        "reply": answer,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "intent": intent,
        "images": assets.get("images", []),
        "links": assets.get("links", []),
        "sources": assets.get("sources", []),
        "images_count": len(assets.get("images", [])),
        "links_count": len(assets.get("links", [])),
        "debug": {
            "context_found": bool(context),
            "faiss_results": len(results or []),
            "memory_terms": memory.get("terms", []),
            "agent_type": agent_type,
            "history_count": len(history or []),
        },
    }