import re
from typing import List


def _has_phrase(value: str, phrases: List[str]) -> bool:
    text = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', (value or '').lower()).strip()} "
    for phrase in phrases:
        p = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', phrase.lower()).strip()} "
        if p.strip() and p in text:
            return True
    return False


def detect_chat_intent(message: str) -> str:
    value = (message or "").strip().lower()

    if not value:
        return "empty"

    if value in {"hi", "hii", "hello", "hey", "namaste", "good morning", "good evening"}:
        return "greeting"

    if _has_phrase(value, [
        "connect with you", "connect with team", "connect me", "i want to connect",
        "talk to sales", "sales team", "contact sales", "speak to someone",
        "talk to someone", "call me", "human", "representative", "person",
        "real person", "sales person", "support person",
    ]):
        return "human_connect"

    if _has_phrase(value, [
        "website", "web site", "site link", "web link", "url", "email", "phone",
        "mobile", "contact", "address", "location", "office", "factory", "plant",
    ]):
        return "contact"

    if _has_phrase(value, [
        "options do i have", "option do i have", "what option", "what options",
        "available options", "product options", "types available", "available types",
        "what range", "pipe options", "fitting options", "range available",
        "which options", "show options",
    ]):
        return "product_options"

    if _has_phrase(value, [
        "price", "pricing", "rate", "cost", "quotation", "quote", "estimate",
        "budget", "how much", "charges", "commercial quote",
    ]):
        return "pricing"

    if _has_phrase(value, ["stock", "available", "availability", "in stock", "ready stock"]):
        return "availability"

    if _has_phrase(value, [
        "clients", "client", "projects", "project", "supplied to", "supplied your products",
        "supplied products", "provided your products", "provided products", "provided to anyone",
        "provided to anybody", "provided to any body", "provided anyone", "provided anybody",
        "where used", "where are your products used", "who uses your products", "used by",
        "case study", "any client", "any clients", "client list", "customer list",
        "certified", "certification", "certificate", "isi", "iso", "bis", "approved",
        "standard", "quality standard", "approval",
    ]):
        return "trust_proof"

    if _has_phrase(value, [
        "install", "installation", "installation process", "how to install",
        "press fitting process", "crimping", "repair", "maintenance", "service", "site visit",
        "how to fit", "how to use", "fitting process",
    ]):
        return "support"

    if _has_phrase(value, [
        "i want to buy", "need to buy", "want to purchase", "need to purchase",
        "need plumbing pipe", "need plumbing pipes", "plumbing pipe", "plumbing pipes",
        "for my bathroom", "for my kitchen", "for my home", "for my house",
        "for residential", "residential", "commercial", "industrial", "for my office",
        "for office", "which one is best", "which product is best", "recommend", "suggest",
        "suitable", "what should i use", "help me choose", "for house", "for home plumbing",
        "which pipe", "which ss pipe", "what kind ss pipe", "what kind ss pipes",
        "304 or 316", "304", "316l", "136l", "best pipe", "best ss pipe",
        "best for plumbing", "which fitting", "pipe recommendation", "opt", "should opt",
    ]):
        return "buying_guidance"

    if _has_phrase(value, [
        "what products", "products do you offer", "what products do you provide",
        "your products", "tell me about your products", "product range",
        "what do you sell", "what do you manufacture", "catalog", "catalogue",
        "product list", "all products",
    ]):
        return "product_overview"

    if _has_phrase(value, ["image", "images", "photo", "photos", "picture", "show me", "catalogue image"]):
        return "image_request"

    return "general"
