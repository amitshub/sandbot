
from typing import Any, Dict, List
import re

from app.session_store import load_chat_history

from .asset_layer import build_assets
from .fallback_layer import build_fallback_reply
from .intent_router import detect_chat_intent
from .product_memory import build_product_memory
from .prompt_builder import build_prompt
from .response_generator import generate_response
from .retrieval import (
    build_context,
    classify_match_quality,
    retrieve_context,
    retrieve_overview_context,
)
from .sales_layer import apply_sales_strategy
from .settings import get_agent_settings
from .support_layer import apply_support_strategy


LINK_REQUEST_WORDS = {
    "link",
    "url",
    "website",
    "catalog",
    "catalogue",
    "product page",
    "detailed page",
    "brochure",
}


def _clean_trailing_url_punctuation(answer: str) -> str:
    return re.sub(
        r"(https?://[^\s]+?)([.,!?;:])(\s|$)",
        r"\1\3",
        answer or "",
    )


def _strip_raw_kb_metadata(answer: str) -> str:
    """Never expose raw KB labels/tags/source metadata in customer replies."""
    if not answer:
        return ""

    lines = []
    blocked_prefixes = (
        "knowledge label:",
        "source url:",
        "source:",
        "tags:",
        "priority:",
        "chunk:",
        "title:",
        "metadata:",
    )

    for line in str(answer).splitlines():
        clean = line.strip()
        if not clean:
            lines.append(line)
            continue
        if clean.lower().startswith(blocked_prefixes):
            continue
        lines.append(line)

    text = "\n".join(lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\bProduct\s+\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOption\s+\d+\b", "", text, flags=re.IGNORECASE)
    return text.strip()


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


def _history_suggests_sales_context(history_text: str) -> bool:
    value = (history_text or "").lower()
    return any(word in value for word in [
        "plumbing", "pipe", "pipes", "fitting", "fittings", "304", "316l",
        "commercial", "residential", "industrial", "house", "home", "bathroom", "kitchen",
    ])


def _customer_asked_for_link(message: str) -> bool:
    value = (message or "").lower()
    return any(word in value for word in LINK_REQUEST_WORDS)


def _expanded_query_for_intent(
    intent: str,
    message: str,
    history_text: str,
    settings: Dict[str, Any],
) -> str:
    business_type = settings.get("business_type") or ""
    industry = settings.get("industry") or ""
    business_name = settings.get("business_name") or settings.get("tenant_name") or ""

    intent_terms = {
        "product_overview": "products product range 304 316L stainless steel pipes fittings plumbing",
        "product_options": "product options types 304 316L stainless steel pipes fittings plumbing",
        "buying_guidance": "recommend suitable grade application residential commercial industrial 304 316L",
        "pricing": "price cost quote rate grade size quantity location",
        "availability": "availability stock supply delivery grade size",
        "trust_proof": "certification certified standards projects clients quality BIS ISO",
        "support": "installation support process contact guidance",
        "contact": "contact phone email address website",
        "image_request": "product images catalogue photos",
    }.get(intent, "")

    return " ".join(
        part.strip()
        for part in [history_text, message, business_name, business_type, industry, intent_terms]
        if part and str(part).strip()
    )


def _filter_sales_noise(results: List[Dict[str, Any]], intent: str) -> List[Dict[str, Any]]:
    """Reduce blog/comparison noise for sales/product questions without blocking KB completely."""
    if not results:
        return []

    sales_intents = {
        "product_overview",
        "product_options",
        "buying_guidance",
        "pricing",
        "availability",
        "trust_proof",
        "support",
    }
    if intent not in sales_intents:
        return results

    filtered = []
    for item in results:
        haystack = " ".join([
            str(item.get("url") or ""),
            str(item.get("title") or ""),
            str(item.get("page_type") or ""),
            str(item.get("source_type") or ""),
        ]).lower()

        # Keep certification/contact/product pages. Only push obvious blog/comparison pages down.
        if any(word in haystack for word in ["blog", "comparison", "article"]):
            continue
        filtered.append(item)

    return filtered or results


def _normalize_intent_with_history(intent: str, history_text: str) -> str:
    # Short replies like "commercial" or "316L" often arrive as general.
    # Use prior chat to keep it inside sales guidance.
    if intent in {"general", "normal_question"} and _history_suggests_sales_context(history_text):
        return "buying_guidance"
    return intent


def run_sales_support_agent(
    tenant_id,
    session_id: str,
    message: str,
    top_k: int = 5,
    agent_type: str = "chat",
) -> Dict[str, Any]:
    """
    KB-grounded sales/support agent.

    Safe for multi-tenant flow:
    - Uses tenant_id for settings, history, and FAISS retrieval.
    - Does not touch public link/customization settings.
    - Does not change product-agent DB routing in main.py/chatbot.py.
    """
    message = _normalize_user_message(message)
    history = load_chat_history(tenant_id, session_id) or []
    history_text = _history_to_text(history)

    settings = get_agent_settings(tenant_id, agent_type=agent_type) or {}

    intent = detect_chat_intent(message)
    intent = _normalize_intent_with_history(intent, history_text)

    query = _expanded_query_for_intent(intent, message, history_text, settings)

    if intent in {"product_overview", "product_options"}:
        results = retrieve_overview_context(
            tenant_id=tenant_id,
            message=query,
            business_type=settings.get("business_type") or "",
            top_k=max(top_k or 5, 10),
        )
    else:
        results = retrieve_context(
            tenant_id=tenant_id,
            query=query,
            top_k=max(top_k or 5, 10 if intent in {"buying_guidance", "trust_proof", "support", "pricing", "availability"} else (top_k or 5)),
            min_score=0.12 if intent in {
                "product_overview",
                "product_options",
                "buying_guidance",
                "trust_proof",
                "support",
                "pricing",
                "availability",
            } else 0.20,
        )

    results = _filter_sales_noise(results, intent)

    context = build_context(results, max_chars=3200)
    match_quality = classify_match_quality(results, message)
    assets = build_assets(results)
    memory = build_product_memory(results, context=context)
    memory["match_quality"] = match_quality

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

    answer = _strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer))

    if not answer:
        answer = build_fallback_reply(
            intent=intent,
            memory=memory,
            settings=settings,
        )
        answer = _strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer))

    # Add images only for explicit image requests.
    if intent == "image_request" and assets.get("images") and not any(
        img in answer for img in assets["images"][:2]
    ):
        answer = f"{answer}\n\nRelevant image(s):\n" + "\n".join(assets["images"][:3])

    # Add links only when customer explicitly asks for link/catalogue/website.
    if _customer_asked_for_link(message) and assets.get("links"):
        if not any(link in answer for link in assets["links"][:2]):
            answer = f"{answer}\n\nRelevant link(s):\n" + "\n".join(assets["links"][:3])

    answer = _strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer))

    return {
        "answer": answer,
        "reply": answer,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "intent": intent,
        "assets": assets,
        "images": assets.get("images", []),
        "links": assets.get("links", []),
        "sources": assets.get("sources", []),
        "images_count": len(assets.get("images", [])),
        "links_count": len(assets.get("links", [])),
        "debug": {
            "context_found": bool(context),
            "match_quality": match_quality,
            "faiss_results": len(results or []),
            "memory_terms": memory.get("terms", []),
            "agent_type": agent_type,
            "history_count": len(history or []),
        },
    }


# Backward-compatible alias. Keep this because chatbot.py may call either name.
def run_sales_support_agent_safe(*args, **kwargs):
    return run_sales_support_agent(*args, **kwargs)
