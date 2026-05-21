from typing import Any, Dict


def build_fallback_reply(intent: str = "general", memory: Dict[str, Any] = None, settings: Dict[str, Any] = None) -> str:
    memory = memory or {}
    settings = settings or {}
    terms = memory.get("terms") or []
    business_type = (settings.get("business_type") or "").strip().lower()

    if intent == "human_connect":
        return "Sure, I can connect you with our team. Our sales team will contact you shortly."

    if intent == "support":
        return (
            "We can help you with product guidance and related support. "
            "For service-related assistance, let me check the exact details with our team once and confirm it for you."
        )

    if intent == "product_overview" and terms:
        intro = "We manufacture and deal in" if business_type == "manufacturer" else "We can help you with products related to"
        return f"{intro} {', '.join(terms[:5])}. Please tell me what you are looking for, and I’ll guide you further."

    if intent in {"pricing", "availability"}:
        return "Let me check the exact details with our team once and confirm the right information for you."

    return "I can help you with your product details and requirements. Please tell me what you are looking for, and I’ll guide you further."
