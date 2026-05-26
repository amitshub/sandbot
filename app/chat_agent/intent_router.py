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

    # Contact intent must be specific. Do NOT treat plain "office", "factory",
    # or "plant" as contact words because customers also say
    # "pipes for my office" or "industrial plant plumbing".
    if _has_phrase(value, [
        "website", "web site", "site link", "web link", "url", "email", "phone",
        "mobile", "contact", "contact details", "address", "office address",
        "factory address", "plant address", "location details", "where are you located",
    ]):
        return "contact"

    if _has_phrase(value, [
        "options do i have", "option do i have", "what option", "what options",
        "available options", "product options", "types available", "available types",
        "what range", "pipe options", "fitting options", "range available",
        "which options", "show options", "what all type", "what type of pipes",
        "types of pipes", "pipe types", "which types",
    ]):
        return "product_options"

    if _has_phrase(value, [
        "price", "pricing", "rate", "cost", "quotation", "quote", "estimate",
        "budget", "how much", "charges", "commercial quote",
    ]):
        return "pricing"

    if _has_phrase(value, ["stock", "available", "availability", "in stock", "ready stock"]):
        return "availability"

    # Project discussion / consultation intent must come before trust_proof.
    if _has_phrase(value, [
        "discuss project", "plumbing project", "new project", "project requirement",
        "project discussion", "commercial project", "residential project",
        "industrial project", "need consultation", "technical consultation",
        "boq", "site requirement", "site discussion", "project consultation",
        "want to discuss project", "discuss plumbing", "discuss a plumbing project",
    ]):
        return "project_discussion"

    # Installation/support questions must come before trust_proof and buying guidance.
    # These are customer-support questions, not generic product/company questions.
    if _has_phrase(value, [
        "install", "installation", "installation process", "how to install",
        "press fitting process", "crimping", "crimping tool", "press tool",
        "tools required", "tool required", "required tools", "installation tools",
        "what tools", "which tools", "repair", "maintenance", "site visit",
        "how to fit", "how to use", "fitting process", "installation guide",
        "installation guidance", "installation video", "installation videos",
        "video guide", "technical support", "project technical support",
    ]):
        return "support"

    if _has_phrase(value, [
        "clients", "client", "projects", "project", "project list", "supplied to", "supplied your products",
        "supplied products", "provided your products", "provided products", "provided to anyone",
        "provided to anybody", "provided to any body", "provided anyone", "provided anybody",
        "providde your service", "providde your products", "provide your service to anybody",
        "provided your service", "provided your service to anybody", "service to anybody",
        "service to anyone", "to whom you provide", "to whom you supply", "who do you supply",
        "where used", "where are your products used", "who uses your products", "used by",
        "case study", "any client", "any clients", "client list", "customer list",
        "certified", "certification", "certificate", "isi", "iso", "bis", "approved",
        "standard", "quality standard", "approval",
    ]):
        return "trust_proof"

    if _has_phrase(value, [
        "i want to buy", "need to buy", "want to purchase", "need to purchase",
        "need plumbing pipe", "need plumbing pipes", "plumbing pipe", "plumbing pipes",
        "for my bathroom", "for my kitchen", "for my home", "for my house",
        "for residential", "residential", "commercial", "industrial", "for my office",
        "for office", "office plumbing", "office pipes", "commercial plumbing",
        "which one is best", "which product is best", "recommend", "suggest",
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

    if _has_phrase(value, [
        "team", "management", "director", "founder", "owner",
        "leadership", "board", "company head", "key people",
        "promoter", "who runs the company", "management team",
        "about chairman", "about director",
    ]):
        return "team_detail"

    if _has_phrase(value, [
        "location", "located", "where are you",
        "factory location", "plant location",
        "branch", "dealer", "dealer near me",
        "office location", "company location",
        "visit office", "nearest dealer",
    ]):
        return "location"

    return "general"
