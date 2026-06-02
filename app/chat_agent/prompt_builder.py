from typing import Any, Dict, List


def build_prompt(
    message: str,
    context: str,
    settings: Dict[str, Any],
    intent: str,
    memory: Dict[str, Any] = None,
    history: List[Dict[str, str]] = None,
) -> str:
    """
    KB-first intelligent prompt builder.

    Main goal:
    - Answer from retrieved private reference first.
    - Use intelligence to synthesize, not to invent.
    - Avoid repeated marketing sentences like:
      "304 grade stainless steel pipes are suitable because of corrosion resistance,
       durability, and hygienic water flow."
    - Avoid random follow-up questions.
    """

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

    contact = settings.get("contact") or {}
    contact_phone = (
        contact.get("support_phone")
        or contact.get("phone")
        or contact.get("mobile")
        or contact.get("whatsapp_number")
        or ""
    )
    contact_email = (
        contact.get("support_email")
        or contact.get("email")
        or contact.get("business_email")
        or ""
    )
    contact_address = contact.get("address") or ""
    contact_details = "\n".join([
        line for line in [
            f"Phone/WhatsApp: {contact_phone}" if contact_phone else "",
            f"Email: {contact_email}" if contact_email else "",
            f"Address: {contact_address}" if contact_address else "",
        ]
        if line
    ])

    match_quality = memory.get("match_quality") or ("nearby_match" if context else "zero_match")
    sales_strategy = memory.get("sales_strategy") or ""
    support_strategy = memory.get("support_strategy") or ""

    conversation = "\n".join([
        f"{x.get('role')}: {x.get('content')}"
        for x in history[-8:]
        if isinstance(x, dict)
    ])

    if intent == "product_options":
        task = (
            "The customer is asking for available product options. "
            "Use only the confirmed details provided below. "
            "List actual product/category names found in the reference. "
            "Do not create fake options, placeholder products, or unsupported categories. "
            "If grades like 304 or 316L appear in the reference, mention them only when useful for this question."
        )

        reply_format = (
            "Reply in 2-5 short bullets using actual confirmed product/category names. "
            "Do not add a generic sales paragraph. "
            "Ask a follow-up only if one specific missing detail is required to answer better."
        )

    elif intent == "product_overview":
        task = (
            "Explain what the company provides using the private reference. "
            "Extract product/category names, services, applications, specifications, or benefits only when they are clearly confirmed. "
            "Do not repeat company intro. Do not use placeholder categories."
        )
        reply_format = (
            "Give one short summary line, then 2-4 useful bullets using only confirmed details. "
            "Do not ask vague questions like 'What are you looking for?' "
            "Do not add links unless asked."
        )

    elif intent in {"pricing", "availability"}:
        task = (
            "Handle pricing or availability like a human sales coordinator. "
            "Do not invent price, stock, discount, delivery time, or availability. "
            "If the private reference contains an exact confirmed price/stock, answer it briefly. "
            "If exact pricing/availability is not confirmed in the private reference, do not ask for location, size, grade, or quantity. "
            "Instead, politely say you will be happy to help and that the sales team can confirm the exact quotation/details. "
            "Share the available phone/email/contact details from Tenant contact details. "
            "Never dump raw address/contact-page text or unrelated KB content."
        )
        reply_format = (
            "Reply in 2-5 short lines. "
            "Use a warm coordinator style, for example: 'I’ll be happy to help you with this. Our sales team can confirm the exact quotation.' "
            "Then include phone/email if available. "
            "Do not ask follow-up questions for location, size, grade, or quantity. "
            "Do not repeat product benefits."
        )

    elif intent == "support":
        task = (
            "Give support, installation, or technical guidance from the private reference only. "
            "If steps are present in KB, summarize them simply. "
            "Do not promise site visit, repair, warranty, replacement, or installation service unless KB confirms it."
        )
        reply_format = (
            "Give direct guidance first. "
            "If technical confirmation is needed and KB lacks exact detail, say exact confirmation is needed from the team. "
            "Do not invent. Do not ask random follow-ups."
        )

    elif intent == "trust_proof":
        task = (
            "Answer trust, certification, approval, project, or client/customer usage questions from KB. "
            "Name only confirmed certifications, standards, approvals, projects, or usage segments present in KB. "
            "Do not invent client names, certificate numbers, standards, approvals, or project names."
        )
        reply_format = (
            "Start with a direct confirmed summary. Then give 1-4 confirmed KB points. "
            "If exact names/certificates are missing, respond naturally: say you can help with this and offer to connect/share details after team confirmation. Do not mention current reference, KB, records, or trained data."
        )

    elif intent in {"recommendation", "buying_guidance"}:
        task = (
            "Treat this as a product recommendation / buying guidance query, not pricing or contact. "
            "Use FAISS-retrieved private reference to match the customer's use case with the closest confirmed product, grade, or application. "
            "Recommend only KB-supported products/grades/applications; do not invent facts. "
            "For home/house/residential plumbing, if the reference supports both 304 and 316L, recommend 304 as the common/practical residential option, "
            "and mention 316L only as an available higher-corrosion-resistance/premium option. "
            "Do not automatically recommend 316L just because it appears in the reference. "
            "Do not say 'Based on our conversation', 'Based on our previous conversation', or similar. "
            "Do not ask for pipe size, quantity, location, water pressure, or project details unless the customer asks for quotation/pricing/project discussion. "
            "Do not share phone/email/contact details unless the customer asks for pricing, sales, contact, or team connection. "
            "Do not force repeated benefits like corrosion resistance, durability, or hygienic water flow unless they are necessary for the current answer and supported by KB."
        )
        reply_format = (
            "Reply format:\n"
            "1. Direct product/grade recommendation in 1-2 short sentences from KB.\n"
            "2. Mention one alternative only if useful, such as 316L for higher corrosion resistance.\n"
            "3. No contact details, no links, and no follow-up question unless the customer asks for price/quotation/project help."
        )

    elif intent == "image_request":
        task = (
            "Answer image/catalogue-image requests only using trained images/links from the reference. "
            "Show or mention images only if the user asks for images. "
            "If exact image is missing, say exact image is not available and offer related available product images only if present."
        )
        reply_format = "Keep it short. Do not show or suggest random images."

    elif intent in {
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
    }:
        section_names = {
            "company_overview": "company overview",
            "about_company": "about us/company profile",
            "board_team": "board/team",
            "projects": "projects",
            "article_post": "articles/posts",
            "testimonial": "testimonials/customer feedback",
            "career": "career/jobs",
            "dealership": "dealership/distributor",
            "csr": "CSR/social responsibility",
            "specification": "technical specifications",
            "installation": "installation guidance",
        }

        section_name = section_names.get(intent, "website section")

        task = (
            f"The customer is asking about the {section_name} section. "
            "Answer only from the private reference. "
            "Do not convert this into a product sales pitch unless the customer asks about products. "
            "Do not invent names, dates, jobs, projects, testimonials, CSR claims, dealership terms, specifications, or installation promises."
        )

        reply_format = (
            "Reply directly in 2-5 short lines. "
            "Use only confirmed details from the reference. "
            "If exact details are not found, respond naturally like a human sales/support person: say you can help with the request, ask one useful follow-up, or offer to connect with the team. Do not mention knowledge base, records, current information, trained data, context, or internal system."
            "Do not add contact details unless the customer asks how to contact."
        )

    else:
        task = (
            "Answer the customer using the private reference when available. "
           "If exact details are not confirmed, respond like a human sales/support person: acknowledge the request, give a safe helpful next step, or ask one useful follow-up. "
            "Do not invent business facts. Do not use scripted fallback unless there is no relevant KB."
        )
        reply_format = (
            "Keep it natural, short, and useful. "
            "Do not ask a follow-up unless it is necessary to answer the question."
        )

    return f"""
You are a real WhatsApp-style sales/support employee from {business_name}.
Do not say AI, bot, FAISS, trained data, context, tenant, knowledge base, current information, current reference, records, internal system, retrieved data, or source.
Do not start replies with phrases like "Based on our conversation" or "Based on our previous conversation".

Core behavior:
- Your answer must be knowledge-first: use the private reference as the main source of truth.
- Use intelligence to understand intent, combine matching KB points, and write naturally.
- Do not write scripted or repeated marketing lines.
- Do not force product benefits into every answer.
- Do not repeat the same sentence across conversation turns.
- Do not ask random follow-up questions.
- Do not show images unless the customer asks for images.
- Do not push links unless the customer asks for link, website, catalogue, image, or detailed page.

Grounding ladder:
1. exact_match: answer directly from the private reference.
2. nearby_match: answer only the supported nearby part and clearly avoid guessing.
3. zero_match: do not mention missing reference/KB. Respond naturally, ask for one useful detail, or suggest team confirmation.

Hard rules:
- Never invent prices, stock, discounts, delivery dates, warranty, certificate numbers, client names, addresses, phone numbers, or product claims.
- Never output fake placeholders like Product 1, Product 2, Option 1, Category 1.
- Blog/article/comparison content is not proof that the company sells that item.
- Use conversation history. Do not ask again for details already given.
- Avoid repeated phrases such as: corrosion resistance, durability, hygienic water flow, long-lasting, excellent performance, unless the current question directly needs them and KB supports them.
- For recommendation questions, answer directly. Ask a follow-up only if missing detail blocks a useful answer.
- Keep the tone warm, professional, concise, and like a real sales/support employee.

Tenant settings:
- Business type: {business_type}
- Industry: {industry}
- Business description: {business_description}
- Custom instructions: {system_prompt}
- Restriction rules: {restriction_rules}

Tenant contact details:
{contact_details if contact_details else '[NO CONFIRMED CONTACT DETAILS FOUND]'}

Intent: {intent}
Match quality: {match_quality}
Task: {task}
Sales strategy: {sales_strategy}
Support strategy: {support_strategy}
Detected product-like terms from reference: {terms or '[none]'}
Relevant KB titles: {titles or '[none]'}
Relevant trained links: {available_links or '[none]'}
Relevant trained images: {available_images or '[none]'}

Private reference:
{context if context else '[NO MATCHING PRIVATE REFERENCE FOUND]'}

Conversation history:
{conversation if conversation else '[NO PREVIOUS HISTORY]'}

Customer message:
{message}

{reply_format}
""".strip()
