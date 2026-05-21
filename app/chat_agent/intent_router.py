def detect_chat_intent(message):
    value = (message or "").lower()

    if "price" in value:
        return "pricing"

    if "stock" in value:
        return "availability"

    return "general"