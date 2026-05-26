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
        "talk to someone", "call me", "human", "representative"
    ]):
        return "human_connect"

    
    if _has_phrase(value, ["website", "web site", "site link", "web link", "url", "email", "phone", "mobile", "contact", "address", "location"]):
        return "contact"

    if _has_phrase(value, [
        "options do i have",
        "available options",
        "product options",
        "types available",
        "what range",
        "pipe options",
        "fitting options",
    ]):
        return "product_options"

    if _has_phrase(value, [
        "i want to buy",
        "need to buy",
        "want to purchase",
        "need to purchase",
        "for my bathroom",
        "for my home",
        "for my house",
        "for my office",
        "for office",
        "which one is best",
        "which product is best",
        "recommend",
        "suggest",
        "suitable",
        "what should i use",
        "help me choose",
        "need plumbing pipes",
        "for house",
        "for home plumbing",
        "which pipe",
        "which ss pipe",
        "304 or 316",
        "316l",
        "136l",
        "best pipe",
        "best ss pipe",
        "best for plumbing",
        "which fitting",
        "pipe recommendation",
    ]):
        return "buying_guidance"

    if _has_phrase(value, [
        "clients",
        "client",
        "projects",
        "project",
        "supplied to",
        "supplied your products",
        "supplied products",
        "provided your products",
        "provided products",
        "provided to anyone",
        "provided to anybody",
        "provided to any body",
        "provided anyone",
        "provided anybody",
        "where used",
        "where are your products used",
        "who uses your products",
        "used by",
        "case study",
        "any client",
        "any clients",
        "client list",
        "customer list",
        "certified",
        "certification",
        "certificate",
        "isi",
        "iso",
        "bis",
        "approved",
        "standard",
    ]):
        return "trust_proof"

    if _has_phrase(value, [
        "what products", "products do you offer", "what products do you provide",
            "your products", "tell me about your products", "product range",
            "what do you sell", "what do you manufacture", "catalog", "catalogue"

   
    ]):
        return "product_overview"

    if _has_phrase(value, ["image", "images", "photo", "photos", "picture", "show me", "catalogue image"]):
        return "image_request"

    if _has_phrase(value, ["price", "pricing", "rate", "cost", "quotation", "quote"]):
        return "pricing"

    if _has_phrase(value, ["stock", "available", "availability", "in stock"]):
        return "availability"

    if _has_phrase(value, [
        
        "install",
        "installation",
        "installation process",
        "how to install",
        "press fitting process",
        "crimping",
        "repair",
        "maintenance",
        "service",
        "site visit",
    ]):
        return "support"
    


    return "general"
