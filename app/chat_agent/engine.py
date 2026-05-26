from typing import Any, Dict, List

from app.session_store import load_chat_history

from .asset_layer import build_assets, normalize_url
from .fallback_layer import build_fallback_reply
from .intent_router import detect_chat_intent
from .product_memory import build_product_memory
from .prompt_builder import build_prompt
from .response_generator import generate_response
from .retrieval import build_context, classify_match_quality, retrieve_context, retrieve_overview_context
from .sales_layer import apply_sales_strategy
from .settings import get_agent_settings
from .support_layer import apply_support_strategy

import re


import re

def _clean_trailing_url_punctuation(answer: str) -> str:
    return re.sub(
        r"(https?://[^\s]+?)([.,!?;:])(\s|$)",
        r"\1\3",
        answer or "",
    )


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


def _expanded_query_for_intent(intent: str, message: str, history_text: str, settings: Dict[str, Any]) -> str:
    business_type = settings.get("business_type") or ""
    base = f"{history_text} {message} {business_type}".strip()

    # If the user gives a short follow-up like "commercial", use the previous chat
    # to keep the sales context instead of treating it as an isolated generic message.
    if intent == "general" and _history_suggests_sales_context(history_text):
        intent = "buying_guidance"

    if intent in {"product_overview", "product_options"}:
        results = retrieve_overview_context(
            tenant_id=tenant_id,
            message=_expanded_query_for_intent(intent, message, history_text, settings),
            business_type=settings.get("business_type") or "",
            top_k=max(top_k, 10),
        )
    else:
        results = retrieve_context(
            tenant_id=tenant_id,
            query=_expanded_query_for_intent(intent, message, history_text, settings),
            top_k=max(top_k, 10 if intent in {"buying_guidance", "trust_proof", "support"} else top_k),
            min_score=0.12 if intent in {"product_overview", "product_options", "buying_guidance", "trust_proof", "support", "pricing", "availability"} else 0.20,
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
    answer = _clean_trailing_url_punctuation(answer)


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
        for word in ["link", "url", "website", "catalog", "catalogue", "product page", "detailed page"]
    ) and assets.get("links"):
        if not any(link in answer for link in assets["links"][:2]):
            answer = f"{answer}\n\nRelevant link(s):\n" + "\n".join(assets["links"][:3])
    answer = _clean_trailing_url_punctuation(answer)

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