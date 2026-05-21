from typing import Any, Dict, List


def build_prompt(message: str, context: str, settings: Dict[str, Any], intent: str, memory: Dict[str, Any] = None, history: List[Dict[str, str]] = None) -> str:
    memory = memory or {}
    history = history or []
    business_name = settings.get("business_name") or settings.get("tenant_name") or "our team"
    business_type = settings.get("business_type") or "business"
    industry = settings.get("industry") or ""
    business_description = settings.get("business_description") or ""
    system_prompt = settings.get("system_prompt") or ""
    restriction_rules = settings.get("restriction_rules") or ""
    terms = ", ".join(memory.get("terms") or [])
    conversation = "\n".join([f"{x.get('role')}: {x.get('content')}" for x in history[-6:]])

    if intent == "product_overview":
        task = "Extract clear product or category names from the trained reference. If exact categories are present, name them directly. If only descriptive product text is present, infer simple customer-friendly categories from the reference only."
        reply_format = (
            "Reply format:\n"
            "We provide:\n\n"
            "• Category 1\n"
            "• Category 2\n"
            "• Category 3\n\n"
            "End naturally with: Please tell me what you are looking for, and I’ll guide you further.\n"
            "Do not mention projects. Do not say you do not have enough information if reference exists."
        )
    elif intent in {"pricing", "availability"}:
        task = "Answer safely. Do not invent prices or stock. If not confirmed in the trained reference, say you will check with the team."
        reply_format = "Keep it short, human, and sales-helpful."
    elif intent == "support":
        task = "Give product guidance and related support only. Do not promise installation/repair/site visit unless reference confirms it."
        reply_format = "Keep it short and offer to check exact service details with the team when needed."
    else:
        task = "Answer the customer using the trained reference when available. If exact details are missing, ask one useful follow-up question."
        reply_format = "Keep it short: 1 to 4 lines."

    return f"""
You are replying as a real sales/support employee from {business_name}.
Do not say AI, bot, FAISS, trained data, context, tenant, or knowledge base.
Use only the tenant's trained reference and tenant settings. Do not invent facts.

Tenant settings:
- Business type: {business_type}
- Industry: {industry}
- Business description: {business_description}
- Custom instructions: {system_prompt}
- Restriction rules: {restriction_rules}

Intent: {intent}
Task: {task}
Detected repeated product-like terms from reference: {terms or '[none]'}

Private trained reference:
{context if context else '[NO MATCHING TRAINED REFERENCE FOUND]'}

Conversation history:
{conversation if conversation else '[NO PREVIOUS HISTORY]'}

Customer message:
{message}

{reply_format}
""".strip()
