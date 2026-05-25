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
    titles = ", ".join(memory.get("titles") or [])
    available_links = ", ".join(memory.get("links") or [])
    available_images = ", ".join(memory.get("images") or [])
    conversation = "\n".join([f"{x.get('role')}: {x.get('content')}" for x in history[-6:]])

    if intent == "product_options":
        task = (
            "The customer is asking what options are available. "
            "Do not repeat the previous recommendation. "
            "List available product options/categories from the trained reference only. "
            "Mention SS 304 and SS 316L separately if present in the reference. "
            "Include fittings/accessories only if present in the reference."
        )
        reply_format = (
            "Reply format:\n"
            "You have these options:\n\n"
            "• Option 1\n"
            "• Option 2\n"
            "• Option 3\n\n"
            "End with one short follow-up question about usage area, size, or requirement."
        )

    elif intent == "product_overview":
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
        task = (
            "Answer safely like a sales representative. Do not invent prices, stock, discounts, or delivery timelines. "
            "Do not say 'I will check with the team' too early. "
            "Explain that quotation/availability depends on the exact requirement. "
            "Ask for grade, size/specification, quantity, and delivery location when missing."
        )
        reply_format = (
            "Keep it short and sales-helpful. "
            "Ask for missing requirement details first. "
            "Only say you will confirm with the team after collecting the key requirement details."
        )
    # elif intent in {"pricing", "availability"}:
    #     task = "Answer safely. Do not invent prices or stock. If not confirmed in the trained reference, say you will check with the team."
    #     reply_format = "Keep it short, human, and sales-helpful."
    # elif intent == "support":
    #     task = "Give product guidance and related support only. Do not promise installation/repair/site visit unless reference confirms it."
    #     reply_format = "Keep it short and offer to check exact service details with the team when needed."
    # elif intent in {"recommendation", "buying_guidance"}:
    #     task = (
    #         "Guide the customer like a sales representative using only the trained reference. "
    #         "Do not repeat company/product intro. Suggest suitable confirmed product category if clear, "
    #         "otherwise ask one practical follow-up such as usage area, size/specification, quantity, or requirement."
    #     )
    #     reply_format = "Keep it helpful, natural, and sales-oriented. Do not invent product examples."
    elif intent == "support":
        task = (
            "Give product guidance and related support using only the trained reference. "
            "If the trained reference contains installation or process steps, explain the steps first in simple order. "
            "Do not promise installation, repair, warranty, or site visit unless the reference confirms it. "
            "If a relevant trained link is available, offer it after the steps."
        )
        reply_format = (
            "Reply with clear support steps first. "
            "Then offer the relevant trained link only if available. "
            "Keep it practical and concise."
        )
    elif intent in {"recommendation", "buying_guidance"}:
        task = (
            "Guide the customer like a sales representative using only the trained reference. "
            "First give a clear recommendation based on the customer's need and conversation history. "
            "Then briefly explain the difference between 304 and 316L only if relevant to the question. "
            "For general home plumbing, explain that 304 is commonly suitable where confirmed by reference; "
            "for higher corrosion resistance, coastal, chemical, or premium applications, 316L may be preferred if confirmed by reference. "
            "Then ask exactly one practical follow-up question such as usage area, size/specification, quantity, or project requirement. "
            "Do not repeat company/product intro. Do not invent product examples."
        )
        reply_format = (
            "Reply format:\n"
            "1. Recommendation in 1-2 lines.\n"
            "2. Brief 304 vs 316L explanation if relevant.\n"
            "3. Ask one follow-up question.\n"
            "Do not send website/product link unless the customer specifically asks for link, website, catalogue, or product page."
        )
    else:
        task = "Answer the customer using the trained reference when available. If exact details are missing, ask one useful follow-up question."
        reply_format = "Keep it short: 1 to 4 lines."

    return f"""
You are replying as a real sales/support employee from {business_name}.
Do not say AI, bot, FAISS, trained data, context, tenant, or knowledge base.
Use only the tenant's trained reference and tenant settings. Do not invent facts.
When the customer asks for product links/images, mention only the relevant trained link/image if present. Never create a generic or guessed URL.

Tenant settings:
- Business type: {business_type}
- Industry: {industry}
- Business description: {business_description}
- Custom instructions: {system_prompt}
- Restriction rules: {restriction_rules}

Intent: {intent}
Task: {task}
Detected product-like terms from reference: {terms or '[none]'}
Relevant KB titles: {titles or '[none]'}
Relevant trained links: {available_links or '[none]'}
Relevant trained images: {available_images or '[none]'}

Private trained reference:
{context if context else '[NO MATCHING TRAINED REFERENCE FOUND]'}

Conversation history:
{conversation if conversation else '[NO PREVIOUS HISTORY]'}

Customer message:
{message}

{reply_format}
""".strip()
