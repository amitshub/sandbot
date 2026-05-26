
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

def _compact_repetitive_answer(answer: str, intent: str) -> str:
    """Keep customer replies short and remove repeated lines/points.

    This is a safety layer for cases where the LLM starts dumping the same
    product/certification flow again and again.
    """
    answer = (answer or "").strip()
    if not answer:
        return ""

    # Remove exact duplicate lines while preserving order.
    unique_lines = []
    seen = set()
    for line in answer.splitlines():
        clean = line.strip()
        key = re.sub(r"\s+", " ", clean.lower())
        if clean and key in seen:
            continue
        if clean:
            seen.add(key)
        unique_lines.append(line)

    answer = "\n".join(unique_lines).strip()
    answer = re.sub(r"\n{3,}", "\n\n", answer)

    # For sales-style intents, prevent very long robotic replies.
    short_reply_intents = {
        "project_discussion",
        "pricing",
        "availability",
        "buying_guidance",
        "product_options",
        "contact",
        "location",
        "human_connect",
        "support",
    }
    if intent in short_reply_intents:
        lines = [line for line in answer.splitlines() if line.strip()]
        if len(lines) > 8:
            answer = "\n".join(lines[:8]).strip()

    return answer.strip()



def _normalize_user_message(message: str) -> str:
    text = (message or "").strip()

    replacements = {
        "136l": "316l",
        "136L": "316L",
        "moy hosue": "my house",
        "moy house": "my house",
        "my hosue": "my house",
        "hosue": "house",
        "providde": "provided",
        "servcie": "service",
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


def _detect_support_focus(message: str) -> str:
    """Detect the exact support sub-question so the bot does not repeat one generic installation reply."""
    value = (message or "").lower()

    if any(word in value for word in ["video", "videos", "tutorial", "youtube"]):
        return "installation_video"

    if any(phrase in value for phrase in [
        "tools required", "tool required", "required tools", "installation tools",
        "what tools", "which tools", "press tool", "crimping tool", "tool for installation",
    ]):
        return "installation_tools"

    if any(phrase in value for phrase in [
        "technical support", "project technical support", "project support",
        "site support", "project assistance", "technical consultation",
    ]):
        return "project_technical_support"

    if any(phrase in value for phrase in [
        "provide installation guidance", "installation guidance", "guide me",
        "installation guide", "do you provide installation",
    ]):
        return "installation_guidance"

    if any(phrase in value for phrase in [
        "how are", "how to install", "installed", "installation process",
        "press fitting process", "fitting process", "how to fit", "how to use", "crimping",
    ]):
        return "installation_steps"

    return "general_support"


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
        "project_discussion": "project consultation plumbing requirement BOQ quotation pipe size grade quantity location 304 316L sales support",
        "pricing": "price cost quote rate grade size quantity location",
        "availability": "availability stock supply delivery grade size",
        "trust_proof": "certification certified standards projects clients customers supplied provided to whom used by quality BIS ISO project references",
        "support": "installation support process press fitting crimping guidance required tools press tool crimping tool installation video technical support project assistance",
        "contact": "contact phone email address website",
        "image_request": "product images catalogue photos pipe types grades 304 316L fittings",
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
        "project_discussion",
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
    support_focus = _detect_support_focus(message) if intent == "support" else "none"

    query = _expanded_query_for_intent(intent, message, history_text, settings)
    if intent == "support" and support_focus != "none":
        query = f"{query} {support_focus.replace('_', ' ')}"

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
            top_k=max(top_k or 5, 10 if intent in {"buying_guidance", "project_discussion", "trust_proof", "support", "pricing", "availability"} else (top_k or 5)),
            min_score=0.12 if intent in {
                "product_overview",
                "product_options",
                "buying_guidance",
                "project_discussion",
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
    memory["support_focus"] = support_focus

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
            "response_style": {
                "max_lines": 6 if intent in {"project_discussion", "pricing", "availability", "buying_guidance", "support"} else 8,
                "rule": "Do not repeat the same KB points. Do not dump certifications unless user asks for proof/certificate. Ask only one practical next question.",
            },
        },
        history=history,
    )

    answer = generate_response(
        prompt,
        business_name=settings.get("business_name")
        or settings.get("tenant_name")
        or "our team",
    )

    answer = _compact_repetitive_answer(_strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer)), intent)

    if not answer:
        answer = build_fallback_reply(
            intent=intent,
            memory=memory,
            settings=settings,
        )
        answer = _compact_repetitive_answer(_strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer)), intent)

    # Add images only for explicit image requests.
    if intent == "image_request" and assets.get("images") and not any(
        img in answer for img in assets["images"][:2]
    ):
        answer = f"{answer}\n\nRelevant image(s):\n" + "\n".join(assets["images"][:3])

    # Add links only when customer explicitly asks for link/catalogue/website.
    if _customer_asked_for_link(message) and assets.get("links"):
        if not any(link in answer for link in assets["links"][:2]):
            answer = f"{answer}\n\nRelevant link(s):\n" + "\n".join(assets["links"][:3])

    answer = _compact_repetitive_answer(_strip_raw_kb_metadata(_clean_trailing_url_punctuation(answer)), intent)

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
            "support_focus": support_focus,
            "history_count": len(history or []),
        },
    }


# Backward-compatible alias. Keep this because chatbot.py may call either name.
def run_sales_support_agent_safe(*args, **kwargs):
    return run_sales_support_agent(*args, **kwargs)
