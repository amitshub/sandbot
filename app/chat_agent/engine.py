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
    "details page",
    "service page",
    "more details",
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
    text = re.sub(
        r"^\s*(Product|Option|Category)\s+\d+\s*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
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
       
    "commercial",
    "industrial",
    "business",
    "project",
    "office",
    "facility",
    "residential",
])



def _customer_asked_for_link(message: str) -> bool:
    value = (message or "").lower()
    return any(word in value for word in LINK_REQUEST_WORDS)



def _is_product_related_result(item: Dict[str, Any]) -> bool:
    text = " ".join([
        str(item.get("url") or item.get("source_url") or item.get("source") or ""),
        str(item.get("title") or ""),
        str(item.get("page_type") or ""),
        " ".join(str(x) for x in (item.get("tags") or [])),
    ]).lower()
    page_type = str(item.get("page_type") or "").lower().strip()
    if page_type in {"product_page", "products_page", "catalog_page", "catalogue_page"}:
        return True
    blocked = ["career", "job", "hiring", "team", "board", "about", "blog", "article", "csr", "testimonial", "contact"]
    if any(x in text for x in blocked):
        return False
    return any(x in text for x in [
        "product", "catalog", "catalogue", "pipe", "fitting", "elbow", "tee", "adaptor", "adapter",
        "socket", "coupler", "coupling", "reducer", "end cap", "pipe bridge",
    ])


def _prioritize_product_results(results: List[Dict[str, Any]], intent: str) -> List[Dict[str, Any]]:
    if not results:
        return []
    if intent not in {"image_request", "product_overview", "product_options", "buying_guidance"}:
        return results

    def rank(item: Dict[str, Any]):
        text = " ".join([
            str(item.get("url") or item.get("source_url") or ""),
            str(item.get("title") or ""),
            str(item.get("page_type") or ""),
        ]).lower()
        page_type = str(item.get("page_type") or "").lower().strip()
        if page_type in {"product_page", "products_page"} or "product.html" in text or "/product" in text:
            return 0
        if _is_product_related_result(item):
            return 1
        if any(x in text for x in ["career", "job", "team", "board", "about", "blog", "article", "csr", "testimonial"]):
            return 3
        return 2

    ordered = sorted(results, key=rank)
    # For image requests, keep only product-related results when possible.
    if intent == "image_request":
        product_only = [item for item in ordered if _is_product_related_result(item)]
        return product_only or ordered
    return ordered


def _detect_support_focus(message: str) -> str:
    """Detect the exact support sub-question so the bot does not repeat one generic installation reply."""
    value = (message or "").lower()

    if any(word in value for word in ["video", "videos", "tutorial", "youtube"]):
        return "installation_video"

    if any(phrase in value for phrase in [
      "tools required",
    "tool required",
    "required tools",
    "installation tools",
    "what tools",
    "which tools",
    "setup tools",
    "tool for installation",
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
        "setup process",
        "installation process", "how to fit", "how to use"
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
                "company_overview": "company overview business overview introduction what company does",
        "about_company": "about us company background company profile mission vision values history",
        "board_team": "board directors founder chairman management leadership our team team members",
        "projects": "our projects completed projects project references customer implementations case studies clients",
        "article_post": "articles posts blog guides educational content resources",
        "testimonial": "testimonials reviews customer feedback client feedback customer experience",
        "career": "career jobs hiring vacancy apply fresher work with us",
        "dealership": "dealership dealer distributor channel partner become dealer become distributor",
        "csr": "csr charity social responsibility social causes community sustainability",
        "specification": "technical specifications dimensions features compatibility requirements",
        "installation": "installation setup implementation deployment configuration guide",
        "product_overview": "products services offerings product range service range categories",
        "product_options": "product options service options types categories available offerings",
        "buying_guidance": "recommend suitable option use case requirement application",
        "support": "support help guidance installation setup troubleshooting technical assistance",
        "image_request": "product images service images catalogue photos brochure",
        "pricing": "price cost quote pricing quantity requirement delivery location",
        "availability": "availability stock supply delivery grade size",
        "trust_proof": "certification certified standards approvals compliance customer usage projects clients quality references",
        "contact": "contact phone email address website",
        
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
        "image_request",
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
        if intent != "article_post":
            if any(word in haystack for word in ["blog", "comparison", "article"]):
                continue
        filtered.append(item)

    return filtered or results

# def _resolve_short_followup_intent(message: str, history_text: str, current_intent: str) -> str:
#     value = (message or "").strip().lower()
#     history = (history_text or "").lower()

#     yes_words = {"yes", "yes please", "yeah", "ok", "okay", "sure", "please share", "send it", "share it"}

#     if value not in yes_words:
#         return current_intent

#     if any(x in history for x in ["career", "careers", "job", "jobs", "hiring", "vacancy"]):
#         return "career"

#     if any(x in history for x in ["dealership", "dealer", "distributor"]):
#         return "dealership"

#     if any(x in history for x in ["catalog", "catalogue", "brochure", "link", "page"]):
#         return "link_request"

#     return current_intent

def _last_assistant_message(history: List[Dict[str, str]]) -> str:
    for item in reversed(history or []):
        if isinstance(item, dict) and item.get("role") == "assistant":
            return str(item.get("content") or "")
    return ""


def _resolve_short_followup_intent(
    message: str,
    last_assistant_text: str,
    current_intent: str,
) -> str:

    value = (message or "").strip().lower()
    history = (last_assistant_text or "").lower()

    short_yes = {
        "yes",
        "yeah",
        "yep",
        "sure",
        "okay",
        "ok",
        "please",
        "please share",
        "send it",
        "share it",
        "show me",
        "i want to see",
        "want to see",
        "show me product images",
        "get me product images",
        "show product images",
        "do that",
        "continue",
    }

    if value not in short_yes:
        return current_intent

    followup_map = {
        "career": ["career", "careers", "job", "jobs", "hiring", "vacancy"],
        "dealership": ["dealership", "dealer", "distributor"],
        "testimonial": ["testimonial", "review", "feedback"],
        "projects": ["project", "projects", "case study"],
        "article_post": ["article", "blog", "post", "guide"],
        "certification": ["certificate", "certification", "approved", "ISO", "BIS"],
        "installation": ["installation", "setup", "guide"],
        "specification": ["specification", "technical", "datasheet"],
        "contact": ["contact", "phone", "email", "address"],

        # KEEP IMAGE/LINK BEFORE PRODUCT
        "image_request": ["image", "images", "photo", "photos", "picture", "pictures", "product images", "available product images", "catalogue image", "catalog images"],
        "link_request": ["link", "website", "page", "catalogue", "brochure"],

        "product_overview": [
            "product range",
            "available products",
            "what products",
            "what services",
        ],
    }

    for intent_name, keywords in followup_map.items():
        if any(k in history for k in keywords):
            return intent_name

    return current_intent
def _normalize_intent_with_history(intent: str, history_text: str) -> str:
    history = (history_text or "").lower()

    protected_intents = {
        "career",
        "dealership",
        "testimonial",
        "projects",
        "article_post",
        "certification",
        "installation",
        "specification",
        "contact",
        "image_request",
        "link_request",
        "company_overview",
        "about_company",
        "board_team",
        "csr",
    }

    # If intent is already a clear section/action intent, never override it.
    if intent in protected_intents:
        return intent

    # If previous conversation was about a protected section,
    # do not convert short follow-ups into product buying guidance.
    if any(x in history for x in [
        "career", "careers", "job", "jobs", "hiring", "vacancy",
        "dealership", "dealer", "distributor",
        "testimonial", "review", "feedback",
        "article", "blog", "post",
        "certificate", "certification",
        "installation", "setup",
        "specification", "technical",
        "contact", "phone", "email",
        "csr", "charity",
        "board", "team", "director",
    ]):
        return intent

    if intent in {"general", "normal_question"} and _history_suggests_sales_context(history_text):
        return "buying_guidance"

    return intent
def _is_short_yes(message: str) -> bool:
    return (message or "").strip().lower() in {
        "yes", "yes please", "yeah", "yep", "ok", "okay", "sure",
        "please", "please share", "send it", "share it", "show me",
        "i want to see", "want to see", "show me product images", "get me product images"
    }
def _last_customer_product_focus(history: List[Dict[str, str]], memory: Dict[str, Any]) -> str:
    terms = [str(x).lower().strip() for x in (memory.get("terms") or []) if str(x).strip()]
    if not terms:
        return ""

    # Check latest user/assistant messages first
    recent_text = " ".join(
        str(item.get("content") or "").lower()
        for item in (history or [])[-6:]
        if isinstance(item, dict)
    )

    # Prefer the latest term mentioned in recent conversation
    matched = [term for term in terms if term and term in recent_text]
    return matched[-1] if matched else ""
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
    last_assistant_text = _last_assistant_message(history)
    intent = _resolve_short_followup_intent(message, last_assistant_text, intent)
    followup_confirmed = _is_short_yes(message)
    intent = _normalize_intent_with_history(intent, history_text)
    support_focus = _detect_support_focus(message) if intent == "support" else "none"

    query = _expanded_query_for_intent(intent, message, history_text, settings)
    if intent == "image_request":
        # Pull product/catalogue page chunks first so image assets come from product KB, not career/about pages.
        query = f"{query} product page product images product catalogue product catalog pipe fittings elbows tees adaptors reducers sockets"
    if intent == "support" and support_focus != "none":
        query = f"{query} {support_focus.replace('_', ' ')}"

    section_intents = {
        "company_overview",
        "about_company",
        "board_team",
        "projects",
        "article_post",
        "testimonial",
        "career",
        "dealership",
        "csr",
        "specification",
        "installation",
    }

    wide_intents = {
        "buying_guidance",
        "project_discussion",
        "trust_proof",
        "support",
        "pricing",
        "availability",
        *section_intents,
    }


    if intent in {"product_overview", "product_options", "image_request"}:
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
    top_k=max(top_k or 5, 10 if intent in wide_intents else (top_k or 5)),
    min_score=0.12 if intent in {
        "product_overview",
        "product_options",
        *wide_intents,
    } else 0.20,
)
        
    results = _filter_sales_noise(results, intent)
    results = _prioritize_product_results(results, intent)

    context = build_context(results, max_chars=3200)
    match_quality = classify_match_quality(results, message)
    
    
    memory = build_product_memory(results, context=context)
    memory["followup_confirmed"] = followup_confirmed
    memory["match_quality"] = match_quality
    memory["support_focus"] = support_focus
    memory["last_product_focus"] = _last_customer_product_focus(history, memory)
    assets = build_assets(
        results,
        intent=intent,
        focus=memory.get("last_product_focus") or "",
        max_images=5 if intent == "image_request" else 12,
    )
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
    # Do not print raw image URLs inside answer text; frontend will render images from assets.
    if intent == "image_request":
        if assets.get("images"):
            answer = "Sure, here are some product images."
        else:
            answer = "I couldn’t find product images in the current product details. You can ask for a specific product name, and I’ll check again."

    # Add links only when customer explicitly asks for link/catalogue/website.
    if _customer_asked_for_link(message) and assets.get("links"):
        value = (message or "").lower()

        if any(x in value for x in ["website", "site link", "web link", "homepage", "home page"]):
            # Website request should share only main website, not internal pages
            pass
        else:
            filtered_links = assets["links"][:2]
            if filtered_links and not any(link in answer for link in filtered_links):
                answer = f"{answer}\n\n" + "\n".join(filtered_links)

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
