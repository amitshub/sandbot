from typing import Any, Dict


def _first_contact_value(contact: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = contact.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value:
            return str(value)
    return ""


def _sales_coordinator_contact_reply(settings: Dict[str, Any]) -> str:
    contact = settings.get("contact") or {}
    phone = _first_contact_value(contact, "support_phone", "phone", "mobile", "whatsapp_number")
    email = _first_contact_value(contact, "support_email", "email", "business_email")

    lines = [
        "I’ll be happy to help you with this.",
        "Our sales team can confirm the exact quotation and product details for you.",
    ]
    if phone:
        lines.append(f"Phone/WhatsApp: {phone}")
    if email:
        lines.append(f"Email: {email}")

    if not phone and not email:
        lines.append("Please share your contact details, and our team will connect with you.")

    return "\n".join(lines)


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
    if intent == "contact":
        return _sales_coordinator_contact_reply(settings)
    if intent in {"pricing", "availability"}:
        return _sales_coordinator_contact_reply(settings)

    return "I can help you with your product details and requirements. Please tell me what you are looking for, and I’ll guide you further."
