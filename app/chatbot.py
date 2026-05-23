import os
import json
from typing import Dict, List
import re
import requests

from app.db import get_main_db_connection
from app.index_builder import load_metadata, search_faiss
from app.session_store import (
    load_chat_history,
    load_chat_state,
    save_chat_history,
    save_chat_state,
)

try:
    from app.chat_agent.engine import run_sales_support_agent
except Exception as exc:
    print("[SALES SUPPORT AGENT IMPORT ERROR]", repr(exc))
    run_sales_support_agent = None

WELCOME_MESSAGE_KEY = "__welcome__"
MIN_FAISS_SCORE = float(os.getenv("MIN_FAISS_SCORE", "0.35"))
IMAGE_EXACT_MIN_SCORE = float(os.getenv("IMAGE_EXACT_MIN_SCORE", "0.30"))
IMAGE_RELATED_MIN_SCORE = float(os.getenv("IMAGE_RELATED_MIN_SCORE", "0.25"))

DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
- Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
- If trained context is missing or not enough, give a safe, generic, human reply.
- For unknown business-specific details, politely say you will check with the team.
- Keep replies short, clear, and helpful."""

CONTACT_COLUMNS = [
    "website_url", "website", "client_domain", "business_website", "allowed_hosts", "branding_api",
    "support_phone", "phone", "mobile", "whatsapp_number",
    "support_email", "email", "business_email", "address",
]


def get_text_from_result(item: Dict) -> str:
    if not isinstance(item, dict):
        return ""
    return (
        item.get("text")
        or item.get("chunk_text")
        or item.get("content")
        or item.get("page_content")
        or item.get("body")
        or item.get("description")
        or ""
    ).strip()


def _unique_keep_order(values):
    seen = set()
    output = []
    for value in values or []:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(key)
    return output


def _json_load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def is_greeting_only(message: str) -> bool:
    value = (message or "").strip().lower()
    greetings = {
        "hi", "hii", "hello", "hey", "hey there", "good morning",
        "good afternoon", "good evening", "namaste", "hola"
    }
    return value in greetings


def should_reply_hindi(message: str) -> bool:
    """English-first. Use Hindi only when the customer clearly writes Hindi/Hinglish."""
    text = (message or "").strip()
    if not text:
        return False
    # Devanagari is a strong signal.
    if re.search(r"[\u0900-\u097F]", text):
        return True

    # Hinglish needs at least 2 strong words; names like Aniket/Aarvi must not trigger Hindi.
    value = f" {text.lower()} "
    hindi_words = [
        " kya ", " kaise ", " mujhe ", " chahiye ", " batao ", " dikhao ",
        " aap ", " apko ", " hai ", " hain ", " mera ", " meri ", " madad ",
        " hindi ", " hinglish ", " karna ", " karo ", " krna ", " dikha ",
    ]
    return sum(1 for w in hindi_words if w in value) >= 2


def is_likely_customer_name(message: str) -> bool:
    value = (message or "").strip()
    if not value or len(value) > 40:
        return False
    if is_greeting_only(value):
        return False
    if re.search(r"[?@:/\\0-9]", value):
        return False
    words = value.split()
    if len(words) > 3:
        return False
    blocked = {
        "pipe", "pipes", "fitting", "fittings", "image", "images", "photo",
        "website", "contact", "number", "price", "service", "services", "english",
    }
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", w) and w.lower() not in blocked for w in words)


def user_requests_english(message: str) -> bool:
    value = (message or "").lower()
    return any(x in value for x in ["talk in english", "speak english", "english only", "reply in english", "in english"])


def _has_phrase(value: str, phrases: List[str]) -> bool:
    text = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', (value or '').lower()).strip()} "
    for phrase in phrases:
        p = f" {re.sub(r'[^a-zA-Z0-9]+', ' ', phrase.lower()).strip()} "
        if p.strip() and p in text:
            return True
    return False


def contact_request_type(message: str) -> str:
    """Return exact contact field requested. Avoid substring bugs like 'call them'."""
    value = (message or "").lower()
    if _has_phrase(value, ["website", "web site", "site", "site link", "web link", "url", "website address"]):
        return "website"
    if _has_phrase(value, ["email", "mail id", "email id"]):
        return "email"
    if _has_phrase(value, ["address", "location", "where are you", "office address"]):
        return "address"
    if _has_phrase(value, ["phone", "mobile", "number", "customer care", "support number", "whatsapp", "contact number", "call number"]):
        return "phone"
    if _has_phrase(value, ["contact", "contact details", "specific contact"]):
        return "all"
    return ""
def wants_human_connect(message: str) -> bool:
    value = (message or "").strip().lower()

    return _has_phrase(value, [
        "connect with you",
        "connect with team",
        "connect me",
        "i want to connect",
        "talk to sales",
        "sales team",
        "contact sales",
        "speak to someone",
        "talk to someone",
        "call me",
    ])

def is_service_question(message: str) -> bool:
    value = (message or "").lower()
    return _has_phrase(value, [
        "service", "services", "installation", "install", "maintenance", "repair",
        "fix", "broken", "door", "store timing", "store timings", "open the store",
        "opening time", "closing time", "area", "areas", "agra", "service area",
    ])


def is_product_terminology_question(message: str) -> bool:
    value = (message or "").lower()
    return _has_phrase(value, [
        "what we call", "what do we call", "what is it called", "name of this",
        "do not know the name", "don't know the name", "i dont know the name", "i don't know the name",
        "what are these called", "which part", "what part",
    ])


def is_followup_when_question(message: str) -> bool:
    return (message or "").strip().lower() in {"when", "kab", "when?", "how soon", "when can", "timing", "time"}


def is_out_of_scope_service(message: str) -> bool:
    value = (message or "").lower()
    out_scope = ["door", "window", "electric", "fan", "ac", "paint", "carpenter", "furniture"]
    return any(re.search(rf"\b{re.escape(w)}\b", value) for w in out_scope)


def is_pipe_problem_request(message: str) -> bool:
    value = (message or "").lower()
    return any(x in value for x in ["pipe took out", "pipe came out", "pipe is out", "pipe broken", "pipe loose", "pipe disconnected"])


def wants_single_or_clear_image(message: str) -> bool:
    value = (message or "").lower()
    return _has_phrase(value, ["single pipe", "single image", "one image", "clear image", "clear images", "understand well"])


def is_image_analysis_or_recommendation(message: str) -> bool:
    value = (message or "").lower()
    has_image_ref = _has_phrase(value, ["given images", "these images", "out of images", "from images", "which one"])
    has_reco = _has_phrase(value, ["best", "which one", "suitable", "buy", "bathroom sink", "for my bathroom", "for my house"])
    return has_image_ref and has_reco



def is_broad_product_overview_question(message: str) -> bool:
    value = (message or "").lower()
    return _has_phrase(value, [
        "what products",
        "products do you offer",
        "what products do you offer",
        "what products do you provide",
        "what are you providing",
        "what are your products",
        "your products",
        "give me types",
        "types of products",
        "product types",
        "what do you sell",
        "what do you manufacture",
        "what are your services",
        "services do you offer",
        "tell me about your services",
        "share more details",
    ])

def detect_intent(message: str) -> str:
    """Safe router with priority for human conversation.
    Important: recommendation/terminology must beat image/contact when customer refers to previous images.
    """
    value = (message or "").lower().strip()

    if is_greeting_only(value):
        return "greeting"
    if user_requests_english(value):
        return "language_preference"
    if is_product_terminology_question(value):
        return "terminology_request"
    if is_followup_when_question(value):
        return "service_request"
    if is_image_analysis_or_recommendation(value):
        return "recommendation_request"

    recommendation_words = [
        "best", "recommend", "suggest", "which one", "which pipe", "suitable",
        "for my office", "office fitting", "home fitting", "house fitting", "bathroom sink",
        "commercial fitting", "what should i use", "what should we use", "i want to buy",
    ]
    if _has_phrase(value, recommendation_words):
        return "recommendation_request"

    if is_broad_product_overview_question(value):
        return "product_overview_request"

    ctype = contact_request_type(value)
    if ctype:
        return "contact_request"

    image_words = [
        "image", "images", "photo", "photos", "picture", "pictures", "pic",
        "visual", "catalog", "catalogue", "brochure", "show me", "show some",
        "show more", "see some", "product page",
    ]
    if _has_phrase(value, image_words):
        return "image_request"

    if is_service_question(value):
        return "service_request"

    return "normal_question"


def is_image_request(message: str) -> bool:
    return detect_intent(message) == "image_request"


def is_random_image_request(message: str) -> bool:
    value = (message or "").lower()
    random_words = [
        "random image", "random images", "any image", "any images",
        "some images random", "show random", "show any", "any product image",
        "whatever image", "just show", "show me images", "show images",
        "product images", "catalog images", "catalogue images",
    ]
    return any(word in value for word in random_words)


def is_more_image_followup(message: str) -> bool:
    value = (message or "").strip().lower()
    return bool(re.fullmatch(r"(i want )?()?(\d+ )?(more|more images|more photos|another|another one|some more|show more|show more images|i want 3 more|i want more|more pipes|more pipe images)", value)) or value in {"where?", "where"}


def requested_image_limit(message: str, default: int = 4) -> int:
    match = re.search(r"\b(\d+)\b", message or "")
    if match:
        try:
            return max(1, min(12, int(match.group(1))))
        except Exception:
            return default
    if wants_single_or_clear_image(message):
        return 2
    return default


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if "." in url and " " not in url:
        return "https://" + url.lstrip("/")
    return url



def looks_like_internal_tenant_name(name: str) -> bool:
    value = (name or "").strip().lower()
    if not value:
        return True
    # Avoid customer-facing replies like "Tenant 3" or random tenant codes.
    if re.fullmatch(r"tenant\s*\d+", value):
        return True
    if re.fullmatch(r"t[0-9a-z!@#$%^&*_-]{4,}", value):
        return True
    if value in {"tenant", "this business", "our company"}:
        return True
    return False


def get_display_business_name(settings: Dict) -> str:
    business_name = (settings.get("business_name") or "").strip()
    tenant_name = (settings.get("tenant_name") or "").strip()

    if business_name and not looks_like_internal_tenant_name(business_name):
        return business_name
    if tenant_name and not looks_like_internal_tenant_name(tenant_name):
        return tenant_name
    return "our team"


def human_team_phrase(settings: Dict) -> str:
    name = get_display_business_name(settings)
    return f"{name} team" if name != "our team" else "our team"

def is_valid_url(url: str) -> bool:
    url = normalize_url(url)
    if not url.startswith(("http://", "https://")):
        return False
    try:
        response = requests.head(url, allow_redirects=True, timeout=4)
        if response.status_code < 400:
            return True
        response = requests.get(url, allow_redirects=True, timeout=4, stream=True)
        return response.status_code < 400
    except Exception:
        # Do not drop tenant data just because a server blocks HEAD/GET.
        return True


def extract_product_terms(message: str) -> List[str]:
    value = (message or "").lower()
    phrases = [
        "stainless steel", "cast iron", "single pipe", "bathroom sink", "sink connector",
        "kitchen tap", "bathroom tap", "tap", "taps", "faucet", "faucets",
        "sink", "wash basin", "basin", "water tap",
        "ss", "abs", "pvc", "pipe", "pipes", "fitting", "fittings", "pressfit",
        "elbow", "tee", "coupler", "valve", "flange", "bend", "socket", "adapter",
        "drain", "connector", "reducer", "nipple", "union",
    ]
    found = []
    for phrase in phrases:
        if phrase in value:
            found.append(phrase)
    noise = {
        "show", "me", "some", "more", "image", "images", "photo", "photos",
        "picture", "pictures", "please", "can", "you", "provide", "give", "the",
        "a", "an", "of", "for", "my", "your", "and", "or", "other", "than", "these",
        "single", "clear", "actually", "not", "much", "there", "are", "various",
        "page", "product", "right", "first", "get", "want", "need", "available",
        "okay", "great", "understand", "well", "buy", "house", "bathroom", "given",
        "best", "out", "called", "name", "call", "them", "what", "which",
    }
    for word in re.findall(r"[a-zA-Z0-9]+", value):
        if len(word) >= 3 and word not in noise:
            found.append(word)
    return _unique_keep_order(found)


def clean_image_label(message: str, history: List[Dict[str, str]] = None) -> str:
    """Create a clean customer-facing label for image responses, never raw query fragments."""
    terms = extract_product_terms(message)
    generic_terms = {"pipe", "pipes", "image", "images", "photo", "photos", "single", "clear", "more", "product", "page"}
    meaningful = [t for t in terms if t not in generic_terms]
    if not meaningful and history:
        previous = last_image_terms_from_history(history)
        if previous:
            terms = extract_product_terms(previous)

    # If customer asks for a single/clear image, keep previous material but avoid fitting names unless asked.
    if wants_single_or_clear_image(message):
        terms = [t for t in terms if t not in {"tee", "elbow", "coupler", "fitting", "fittings"}]
        if "pipe" not in terms and "pipes" not in terms:
            terms.append("pipe")

    label_parts = []
    priority = [
        "stainless steel", "cast iron", "abs", "pvc", "ss", "bathroom sink",
        "kitchen tap", "bathroom tap", "tap", "taps", "faucet", "faucets",
        "sink", "basin", "elbow", "tee", "coupler", "connector",
        "fitting", "fittings", "pipe", "pipes",
    ]
    for item in priority:
        if item in terms:
            normalized = "stainless steel" if item == "ss" else item
            if normalized not in label_parts:
                label_parts.append(normalized)

    # Avoid awkward labels like "stainless steel tee pipes" unless tee/elbow was explicitly requested now.
    now = (message or "").lower()
    if "tee" not in now:
        label_parts = [x for x in label_parts if x != "tee"]
    if "elbow" not in now:
        label_parts = [x for x in label_parts if x != "elbow"]

    if not label_parts and terms:
        label_parts = terms[:2]

    label = " ".join(label_parts).strip()
    label = re.sub(r"\b(stainless steel) \1\b", r"\1", label)
    label = re.sub(r"\bpipe pipes\b|\bpipes pipe\b", "pipes", label)
    label = re.sub(r"\bfitting fittings\b|\bfittings fitting\b", "fittings", label)
    return label or "product"


def is_selling_confirmation_question(message: str) -> bool:
    value = (message or "").lower()
    return any(x in value for x in [
        "do you sell", "are you selling", "you selling", "do you provide",
        "do you have", "available at you", "available with you", "what pipes do you sell",
        "which pipes do you sell", "what do you sell",
    ])


def contains_product_page_intent(message: str) -> bool:
    value = (message or "").lower()
    return "product page" in value or "product images" in value or "various pipe images" in value


def looks_like_blog_or_comparison(item: Dict) -> bool:
    haystack = " ".join([
        str(item.get("url") or ""),
        str(item.get("title") or ""),
        get_text_from_result(item),
    ]).lower()
    blog_words = ["blog", "article", "compare", "comparison", "alternative", "traditional", "guide", "advantages", "disadvantages"]
    return any(w in haystack for w in blog_words)


def build_product_boundary_reply(message: str, context: str, settings: Dict) -> str:
    """Prevent blog/comparison content from becoming fake inventory."""
    value = (message or "").lower()
    business_name = get_display_business_name(settings)

    # We do not hardcode tenant inventory. This sentence uses context if available, but refuses unsupported products.
    if any(x in value for x in ["copper", "abs", "pvc", "cast iron"]):
        if "stainless steel" in (context or "").lower() or "ss" in (context or "").lower():
            return f"We mainly deal in stainless steel pipes and fittings. I may have educational/blog information about other pipe materials, but I shouldn’t say we sell them unless it’s listed in our product data."
        return f"I can see some reference information, but I don’t have confirmed product data showing that {business_name} sells that item. I can check this with the team."

    return "I’ll check the confirmed product list and help you with the right option."


def rank_results_for_images(results: List[Dict], message: str, history: List[Dict[str, str]] = None) -> List[Dict]:
    terms = _image_query_terms(message)
    if history and not terms:
        previous = last_image_terms_from_history(history)
        terms = _image_query_terms(previous) or terms

    def score(item: Dict) -> float:
        haystack = " ".join([
            get_text_from_result(item),
            str(item.get("title") or ""),
            str(item.get("url") or ""),
            str(item.get("file_name") or ""),
            " ".join(item.get("images") or []),
            " ".join(item.get("links") or []),
        ]).lower()
        s = _score_float(item) * 10
        for t in terms:
            if t and t in haystack:
                s += 3
        if item.get("images"):
            s += 5 + min(5, len(item.get("images") or []))
        if looks_like_blog_or_comparison(item):
            s -= 2
        return s

    return sorted(results or [], key=score, reverse=True)


def result_matches_terms(item: Dict, terms: List[str]) -> bool:
    if not terms:
        return True
    haystack = " ".join([
        get_text_from_result(item),
        str(item.get("title") or ""),
        str(item.get("url") or ""),
        str(item.get("file_name") or ""),
        " ".join(item.get("images") or []),
        " ".join(item.get("links") or []),
    ]).lower()

    return any(t in haystack for t in terms)


def filter_results_by_message(results: List[Dict], message: str) -> List[Dict]:
    terms = extract_product_terms(message)
    filtered = [item for item in (results or []) if result_matches_terms(item, terms)]
    return filtered



def _score_float(item: Dict, default: float = 0.0) -> float:
    try:
        score = item.get("score")
        return float(score) if score is not None else default
    except Exception:
        return default


def _has_images(item: Dict) -> bool:
    return bool((item or {}).get("images"))


def _image_query_terms(message: str) -> List[str]:
    """Important requested words. Generic image/chat words are ignored."""
    generic = {
        "image", "images", "photo", "photos", "picture", "pictures", "pic",
        "show", "some", "more", "product", "products", "catalog", "catalogue",
        "clear", "single", "one", "available", "page", "random", "any", "give",
        "send", "share", "want", "need", "please", "me", "the", "a", "an", "of",
        "for", "to", "and", "or", "with", "from", "records", "data",
    }
    value = (message or "").lower()
    words = [
        word for word in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value)
        if len(word) >= 3 and word not in generic
    ]

    # Keep short meaningful model/SKU-like tokens only when they contain digits.
    words.extend([
        word for word in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", value)
        if len(word) < 3 and any(ch.isdigit() for ch in word)
    ])
    return _unique_keep_order(words)


def image_request_has_specific_terms(message: str) -> bool:
    return bool(_image_query_terms(message))


def image_results_from_tenant_metadata(tenant_id, message: str = "") -> List[Dict]:
    try:
        metadata = load_metadata(tenant_id)
    except Exception as exc:
        print("[IMAGE METADATA FALLBACK ERROR]", repr(exc))
        return []
    return rank_results_for_images([item for item in metadata if _has_images(item)], message)


def filter_exact_image_results(results: List[Dict], message: str) -> List[Dict]:
    """
    Exact image match:
    - must have images
    - must pass cosine/FAISS score threshold
    - must match requested product/material terms when the user gave them
    """
    terms = _image_query_terms(message)
    output = []
    for item in results or []:
        if not _has_images(item):
            continue
        if _score_float(item) < IMAGE_EXACT_MIN_SCORE:
            continue
        if terms and not result_matches_terms(item, terms):
            continue
        output.append(item)
    return output


def filter_related_image_results(results: List[Dict], message: str) -> List[Dict]:
    """
    Related image fallback from the same tenant FAISS results only.
    No fixed product words and no broad catalogue search.
    This is used when exact requested image is unavailable, but nearby high-score
    tenant product images exist. The reply must clearly say the exact item is not in records.
    """
    output = []
    for item in results or []:
        if not _has_images(item):
            continue
        if looks_like_blog_or_comparison(item):
            continue
        if _score_float(item) < IMAGE_RELATED_MIN_SCORE:
            continue
        output.append(item)
    return output

def filter_by_score(results: List[Dict], min_score: float = MIN_FAISS_SCORE) -> List[Dict]:
    output = []
    for item in results or []:
        score = item.get("score")
        try:
            if score is None or float(score) >= min_score:
                output.append(item)
        except Exception:
            output.append(item)
    return output


def collect_assets_from_results(
    results: List[Dict],
    max_images: int = 6,
    max_links: int = 6,
    exclude_images: List[str] = None,
) -> Dict:
    image_urls = []
    link_urls = []
    sources = []
    excluded = {normalize_url(x) for x in (exclude_images or []) if x}

    for item in results or []:
        image_urls.extend(item.get("images") or [])
        link_urls.extend(item.get("links") or [])
        source = item.get("url") or item.get("file_name") or item.get("title")
        if source:
            sources.append(source)

    images = _unique_keep_order(image_urls)
    links = _unique_keep_order(link_urls)
    sources = _unique_keep_order(sources)[:max_links]

    valid_images = []
    for url in images:
        url = normalize_url(url)
        if not url or url in excluded:
            continue
        if is_valid_url(url):
            valid_images.append(url)
        if len(valid_images) >= max_images:
            break

    valid_links = []
    for url in links:
        url = normalize_url(url)
        if is_valid_url(url):
            valid_links.append(url)
        if len(valid_links) >= max_links:
            break

    return {
        "images": valid_images,
        "links": valid_links,
        "sources": sources,
        "images_count": len(valid_images),
        "links_count": len(valid_links),
    }


def empty_assets() -> Dict:
    return {"images": [], "links": [], "sources": [], "images_count": 0, "links_count": 0}


def _get_table_columns(cur, table_name: str) -> set:
    try:
        cur.execute(f"SHOW COLUMNS FROM {table_name}")
        return {row.get("Field") for row in cur.fetchall() or []}
    except Exception:
        return set()

def get_agent_settings_for_chat(tenant_id, agent_type="chat"):
# def get_agent_settings_for_chat(tenant_id) -> Dict:
    row = {}
    try:
        conn = get_main_db_connection()
        try:
            with conn.cursor() as cur:
                tenant_cols = _get_table_columns(cur, "tenants")
                settings_cols = _get_table_columns(cur, "tenant_agent_settings")

                tenant_selects = ["t.tenant_name"]
                for col in CONTACT_COLUMNS:
                    if col in tenant_cols:
                        tenant_selects.append(f"t.{col}")

                settings_selects = []
            

                for col in [
                    "business_name",
                    "industry",
                    "business_type",
                    "business_description",
                    "website_url",
                    "allowed_scope",
                    "blocked_claims",
                    "greeting_message",
                    "starter_questions",
                    "system_prompt",
                    "restriction_rules",
                    "support_hours"
                ]:
                    if col in settings_cols:
                        settings_selects.append(f"tas.{col}")
                    else:
                        settings_selects.append(f"NULL AS {col}")

                sql = f"""
                    SELECT
                        {", ".join(settings_selects)},
                        {", ".join(tenant_selects)}
                    FROM tenants t
                    LEFT JOIN tenant_agent_settings tas
                        ON tas.tenant_id = t.id
                       AND (tas.agent_type = %s OR tas.agent_type IS NULL)
                    WHERE t.id=%s
                    LIMIT 1
                """
                cur.execute(sql, (agent_type, tenant_id))
                row = cur.fetchone() or {}
        finally:
            conn.close()
    except Exception as exc:
        print("[CHAT SETTINGS ERROR]", repr(exc))
        row = {}

    tenant_name = row.get("tenant_name") or row.get("business_name") or "this business"
    business_name = row.get("business_name") or tenant_name
    system_prompt = (row.get("system_prompt") or "").strip()
    restriction_rules = (row.get("restriction_rules") or "").strip()
    business_type = (row.get("business_type") or "").strip()
    industry = (row.get("industry") or "").strip()
    business_description = (row.get("business_description") or "").strip()
    allowed_scope = (row.get("allowed_scope") or "").strip()
    blocked_claims = (row.get("blocked_claims") or "").strip()

    if not system_prompt:
        system_prompt = f"""You are a helpful business assistant for {business_name}.
Reply naturally like a real human assistant.
Use trained knowledge when available.
If trained knowledge is not enough, do not invent details."""

    if not restriction_rules:
        restriction_rules = DEFAULT_RESTRICTION_RULES

    contact = {}
    for col in CONTACT_COLUMNS:
        value = (row.get(col) or "").strip() if isinstance(row.get(col), str) else row.get(col)
        if value:
            contact[col] = value

    return {
    "tenant_name": tenant_name,
    "business_name": business_name,
    "industry": industry,
    "business_type": business_type,
    "business_description": business_description,
    "allowed_scope": allowed_scope,
    "blocked_claims": blocked_claims,
    "greeting_message": row.get("greeting_message") or "",
    "starter_questions": _json_load(
        row.get("starter_questions"),
        default=[]
    ) or [],
    "system_prompt": system_prompt,
    "restriction_rules": restriction_rules,
    "support_hours": _json_load(row.get("support_hours"), default={}) or {},
    "contact": contact,
   }

    # return {
    #     "tenant_name": tenant_name,
    #     "business_name": business_name,
    #     "industry": industry,
    #     "business_type": business_type,
    #     "business_description": business_description,
    #     "allowed_scope": allowed_scope,
    #     "blocked_claims": blocked_claims,
    #     "system_prompt": system_prompt,
    #     "restriction_rules": restriction_rules,
    #     "support_hours": _json_load(row.get("support_hours"), default={}) or {},
    #     "contact": contact,
    # }


def build_context(results: List[Dict], max_chars: int = 1200) -> str:
    parts = []
    total = 0
    for i, item in enumerate(results, start=1):
        source = item.get("url") or item.get("file_name") or item.get("title") or "trained data"
        text = get_text_from_result(item)
        if not text:
            print("[CONTEXT SKIP] result has no text. keys:", list(item.keys()))
            continue
        block = f"[Source {i}: {source}]\n{text}"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 150:
                parts.append(block[:remaining])
            break
        parts.append(block)
        total += len(block)
    context = "\n\n".join(parts)
    print("[CONTEXT BUILD] parts:", len(parts))
    print("[CONTEXT BUILD] length:", len(context))
    print("[CONTEXT BUILD] sample:", context[:300])
    return context


def clean_ai_reply(reply: str) -> str:
    if not reply:
        return ""
    cleaned = reply.strip()
    remove_phrases = [
        "According to the provided context,", "Based on the provided context,",
        "Based on the context,", "According to the context,", "From the context,",
        "According to the document,", "Based on the document,", "The context says",
        "The provided information says",
    ]
    for phrase in remove_phrases:
        cleaned = cleaned.replace(phrase, "").strip()
    return cleaned


def fallback_answer(message: str = "", settings: Dict = None) -> str:
    """Customer-friendly fallback. Never exposes KB/FAISS/internal tenant language."""
    settings = settings or {}
    intent = detect_intent(message)

    if intent == "image_request":
        return "I couldn’t find a clearly matching image for that item right now. Share the product name or type once, and I’ll check the closest available images for you."

    if intent == "contact_request":
        return "I don’t have those contact details saved here right now. Let me check with our team and confirm the right details for you."

    return "Let me check this with our team once and confirm the right details for you."



def trim_to_complete_sentence(text: str, max_chars: int = 260) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars and re.search(r"[.!?]$", text):
        return text
    cut = text[:max_chars].strip()
    last_end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if last_end >= 80:
        return cut[: last_end + 1].strip()
    return cut.rstrip(",;:- ") + "."


def build_contact_reply(settings: Dict, request_type: str = "all", extra_website: str = "") -> str:
    contact = settings.get("contact") or {}
    business_name = get_display_business_name(settings)

    website = get_website_from_settings(settings, extra_website=extra_website)
    phone = contact.get("support_phone") or contact.get("phone") or contact.get("mobile") or contact.get("whatsapp_number")
    email = contact.get("support_email") or contact.get("email") or contact.get("business_email")
    address = contact.get("address")

    def missing(field: str) -> str:
        return f"I don’t have a confirmed {field} saved here yet. I can connect you with the {human_team_phrase(settings)}."

    if request_type == "website":
        return f"You can visit our website here: {normalize_url(str(website))}" if website else missing("website")
    if request_type == "phone":
        return f"You can contact us on this number: {phone}" if phone else missing("phone number")
    if request_type == "email":
        return f"You can email us at: {email}" if email else missing("email")
    if request_type == "address":
        return f"Sure, the address for {business_name} is: {address}" if address else missing("address")

    lines = ["You can contact us using the details below:"]
    if website:
        lines.append(f"Website: {normalize_url(str(website))}")
    if phone:
        lines.append(f"Phone/WhatsApp: {phone}")
    if email:
        lines.append(f"Email: {email}")
    if address:
        lines.append(f"Address: {address}")

    if len(lines) == 1:
        return f"I don’t have confirmed contact details saved here yet. I can connect you with the {human_team_phrase(settings)}."
    return "\n".join(lines)



def _normalize_phone_candidate(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) < 8 or len(digits) > 15:
        return ""
    # Avoid product grades/specifications becoming phone numbers.
    if digits in {"304", "316", "3161", "316l"}:
        return ""
    if len(set(digits)) <= 2:
        return ""
    return raw.strip(" .,:;|/")


def _extract_contact_details_from_kb(results: List[Dict]) -> Dict:
    """Extract only tenant-trained contact details from FAISS/KB results.
    This intentionally does not read tenant/default WhatsApp settings, because those can
    contain platform/test numbers and create false customer-facing contact replies.
    """
    text_blocks = []
    urls = []

    for item in results or []:
        text = get_text_from_result(item)
        if text:
            text_blocks.append(text)
        if item.get("url"):
            urls.append(str(item.get("url")))
        urls.extend([str(x) for x in (item.get("links") or []) if x])

    combined = "\n".join(text_blocks)

    emails = _unique_keep_order(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", combined))

    phone_matches = re.findall(
        r"(?:(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{3,5})",
        combined,
    )
    phones = []
    for match in phone_matches:
        phone = _normalize_phone_candidate(match)
        if phone:
            phones.append(phone)
    phones = _unique_keep_order(phones)

    # Prefer homepage/contact/about URLs from trained source URLs and page links.
    clean_urls = []
    for url in urls:
        clean = normalize_url(url)
        if clean.startswith(("http://", "https://")):
            clean_urls.append(clean.rstrip("/"))
    clean_urls = _unique_keep_order(clean_urls)

    website = ""
    for url in clean_urls:
        value = url.lower()
        if any(x in value for x in ["contact", "about"]):
            website = url
            break
    if not website:
        # For general contact, homepage-like URL is better than product/spec page.
        homepage_candidates = [u for u in clean_urls if len(urlparse(u).path.strip("/")) == 0]
        website = homepage_candidates[0] if homepage_candidates else (clean_urls[0] if clean_urls else "")

    # Lightweight address extraction from lines that look like address/location rows.
    address = ""
    for line in combined.splitlines():
        line_clean = re.sub(r"\s+", " ", line).strip(" -:|\t")
        lower = line_clean.lower()
        if not line_clean or len(line_clean) < 8:
            continue
        if any(k in lower for k in ["address", "location", "factory", "office", "showroom"]):
            if not any(k in lower for k in ["email", "phone", "mobile", "whatsapp"]):
                address = line_clean
                break

    return {
        "website": website,
        "phone": phones[0] if phones else "",
        "email": emails[0] if emails else "",
        "address": address,
    }


def build_kb_first_contact_reply(
    settings: Dict,
    request_type: str = "all",
    kb_results: List[Dict] = None,
) -> str:
    details = _extract_contact_details_from_kb(kb_results or [])
    team = human_team_phrase(settings)

    def missing(field: str) -> str:
        return f"I don’t have a confirmed {field} in our trained knowledge base right now. I can connect you with the {team}."

    if request_type == "website":
        return f"You can visit our website here: {details['website']}" if details.get("website") else missing("website")
    if request_type == "phone":
        return f"You can reach our team at: {details['phone']}" if details.get("phone") else missing("phone number")
    if request_type == "email":
        return f"You can email our team at: {details['email']}" if details.get("email") else missing("email")
    if request_type == "address":
        return f"Sure, here is the address I found in our knowledge base:\n{details['address']}" if details.get("address") else missing("address")

    lines = ["Sure — you can reach our team using the confirmed details below:"]
    if details.get("website"):
        lines.append(f"Website: {details['website']}")
    if details.get("phone"):
        lines.append(f"Phone/WhatsApp: {details['phone']}")
    if details.get("email"):
        lines.append(f"Email: {details['email']}")
    if details.get("address"):
        lines.append(f"Address: {details['address']}")

    if len(lines) == 1:
        return f"I can connect you with the {team}."
    return "\n".join(lines)


def extract_website_from_results(results: List[Dict]) -> str:
    for item in results or []:
        candidates = []
        if item.get("url"):
            candidates.append(item.get("url"))
        candidates.extend(item.get("links") or [])
        for url in candidates:
            url = normalize_url(str(url))
            if url.startswith(("http://", "https://")):
                return url.rstrip("/")
    return ""


def _parse_allowed_hosts(value) -> List[str]:
    data = _json_load(value, default=value)
    if isinstance(data, list):
        hosts = data
    elif isinstance(data, str):
        hosts = re.split(r"[,\s]+", data)
    else:
        hosts = []
    output = []
    for host in hosts:
        host = str(host or "").strip().strip("/")
        if not host or "localhost" in host or "127.0.0.1" in host:
            continue
        # Avoid Railway/internal app hosts as customer website when a client domain exists.
        if "railway.app" in host or "up.railway" in host:
            continue
        output.append(host)
    return _unique_keep_order(output)


def get_website_from_settings(settings: Dict, extra_website: str = "") -> str:
    contact = settings.get("contact") or {}
    candidates = [
        contact.get("website_url"),
        contact.get("website"),
        contact.get("business_website"),
        contact.get("client_domain"),
        extra_website,
    ]
    # branding_api is often like https://domain/api/get-branding; convert to domain.
    branding_api = contact.get("branding_api")
    if branding_api:
        candidates.append(str(branding_api).split("/api/")[0])
    candidates.extend(_parse_allowed_hosts(contact.get("allowed_hosts")))

    for candidate in candidates:
        url = normalize_url(str(candidate or "").strip())
        if url and url.startswith(("http://", "https://")) and "." in url:
            return url.rstrip("/")
    return ""


def build_recommendation_question(settings: Dict, message: str, history: List[Dict[str, str]] = None, context: str = "") -> str:
    return ""


def build_terminology_reply(settings: Dict, message: str, history: List[Dict[str, str]] = None) -> str:
    return ""

def _clean_scope_for_customer(scope: str) -> str:
    """Turn saved allowed_scope into natural customer-facing text."""
    value = re.sub(r"\s+", " ", scope or "").strip().strip(".")
    value = re.sub(r"knowledge base", "", value, flags=re.IGNORECASE)
    value = re.sub(r"confirmed in KB", "", value, flags=re.IGNORECASE)
    value = re.sub(r"explicitly confirmed", "", value, flags=re.IGNORECASE)
    value = re.sub(r"confirmed with us", "", value, flags=re.IGNORECASE)
    if not value:
        return "product details, fittings, images, specifications, catalogue details, and support"

    replacements = {
        "product information": "product details",
        "catalog details": "catalogue details",
        "catalogue details": "catalogue details",
        "service information": "service details",
        "confirmed in KB": "confirmed with us",
        "confirmed in knowledge base": "confirmed with us",
        "KB": "our details",
    }
    for old, new in replacements.items():
        value = re.sub(re.escape(old), new, value, flags=re.IGNORECASE)
    value = re.sub(r"\bonly if present in our details\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+,", ",", value).strip(" ,.")
    return value or "product details, fittings, images, specifications, catalogue details, and support"


def _mentions_any(text: str, words: List[str]) -> bool:
    value = (text or "").lower()
    return any(re.search(rf"\b{re.escape(word.lower())}\b", value) for word in words if word)


def _requested_service_label(message: str) -> str:
    value = (message or "").lower()

    if _mentions_any(value, ["installation", "install", "installment"]):
        return "installation"

    if _mentions_any(value, ["maintenance", "maintain"]):
        return "maintenance"

    if _mentions_any(value, ["repair", "fix", "broken", "loose", "disconnected"]):
        return "repair"

    if _mentions_any(value, ["site visit", "on-site", "onsite"]):
        return "site visit"

    if _mentions_any(value, ["service area", "area", "location"]):
        return "service-area details"

    if _mentions_any(value, ["timing", "open", "opening", "closing", "store"]):
        return "timing details"

    return "service"


def _context_explicitly_confirms_service(context: str, message: str) -> bool:
    text = (context or "").lower()
    if not text:
        return False

    service_label = _requested_service_label(message)

    if service_label == "installation":
        return _mentions_any(text, ["installation", "install", "setup"])

    if service_label == "maintenance":
        return _mentions_any(text, ["maintenance", "maintain", "support"])

    if service_label == "repair":
        return _mentions_any(text, ["repair", "fix", "service support"])

    if service_label == "site visit":
        return _mentions_any(text, ["site visit", "on-site", "onsite"])

    if service_label == "timing details":
        return _mentions_any(text, ["opening hours", "timing", "store timing", "working hours", "open from"])

    if service_label == "service-area details":
        return _mentions_any(text, ["service area", "available in", "location", "areas covered", "we serve"])

    return _mentions_any(text, ["service", "services", "support"])

# def build_safe_service_reply(settings: Dict, message: str, context: str = "") -> str:
#     """
#     Human employee-style service guard.
#     Uses tenant_agent_settings.allowed_scope + blocked_claims as the boundary,
#     and FAISS context only as private reference, never as raw customer-facing text.
#     """
#     value = (message or "").lower()
#     business_type = (settings.get("business_type") or "").strip().lower()
#     allowed_scope_raw = (settings.get("allowed_scope") or "").strip()
#     blocked_claims = (settings.get("blocked_claims") or "").strip().lower()
#     scope_text = _clean_scope_for_customer(allowed_scope_raw)
#     requested_service = _requested_service_label(message)

#     product_first_types = {"manufacturer", "product_seller", "ecommerce", "supplier", "industrial_supplier"}
#     service_words = ["service", "services", "installation", "install", "installment", "maintenance", "repair", "on-site", "onsite", "site visit"]
#     asks_general_services = _has_phrase(value, ["which service", "which services", "what service", "what services", "services you provide", "service you provide"])

#     # Non-plumbing or unrelated maintenance should be redirected without sounding like a third party.
#     if is_out_of_scope_service(message):
#         return (
#             "We mainly help with our pipe and fitting related product guidance here. "
#             "For that type of repair or maintenance, it would be better to check with the right service professional."
#         )

#     # General service question: explain what we can safely help with from DB scope.
#     if asks_general_services:
#         if business_type in product_first_types or any(word in blocked_claims for word in service_words):
#             return (
#                 f"We mainly help with {scope_text}. "
#                 "For installation, repair, maintenance, or site visits, let me check with our team once and confirm the right details for you."
#             )
#         return (
#             f"We can help with {scope_text}. "
#             "Tell me what you need help with, and I’ll guide you with the right details."
#         )

#     # Timings/location/area should stay human, but not invented.
#     if requested_service == "timing details":
#         return "I don’t have the exact timings with me right now. Let me check with our team once and confirm the correct timing for you."

#     if requested_service == "service-area details":
#         return "Let me check the exact service-area coverage with our team once and confirm it for you."

#     # Product/manufacturer style tenants must not become fake service providers.
#     if any(word in value for word in service_words):
#         if business_type in product_first_types or any(word in blocked_claims for word in service_words):
#             followup = ""
#             if requested_service == "pipe installation":
#                 followup = " Meanwhile, please share whether it is for home, commercial, or industrial use, so I can guide you on the right product side."
#             return (
#                 f"We mainly help with {scope_text}. "
#                 f"For {requested_service}, let me check with our team once and confirm the right details for you."
#                 f"{followup}"
#             )

#         # If DB says service provider and trained content explicitly confirms the service, answer positively but still avoid overclaiming.
#         if _context_explicitly_confirms_service(context, message):
#             return (
#                 "For service-related assistance, let me check the exact details with our team once and confirm it for you."
#             )

#         return (
#             "We can help you with product guidance and related support. "
#             f"For {requested_service}, let me check the exact details with our team once and confirm it for you."
#         )

#     return (
#     "We can help you with product guidance and related support. "
#     "Tell me what you’re looking for, and I’ll guide you with the right details."
# )

def build_safe_service_reply(settings: Dict, message: str, context: str = "") -> str:
    return ""
    
def build_first_welcome_message(settings: Dict, context: str) -> str:
    custom_greeting = (settings.get("greeting_message") or "").strip()
    if custom_greeting:
        return custom_greeting

    tenant_name = get_display_business_name(settings)
    allowed_scope = _clean_scope_for_customer(settings.get("allowed_scope") or "")
    business_type = (settings.get("business_type") or "").strip().lower()

    if business_type == "manufacturer":
        allowed_scope = (
            "We manufacture and deal in pipe fittings, and we can help you with "
            "product details, specifications, catalogue guidance, images, and support."
        )
    def make_smart_business_intro(context_text: str) -> str:
        text = (context_text or "").replace("\n", " ").strip()
        if not text:
            return f"We can help you with {allowed_scope}."
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        if not api_key:
            product_terms = extract_product_like_terms_from_context(context)

            if product_terms:
                return (
                    "We can help you with products related to "
                    + ", ".join(product_terms[:5])
                    + ". Please tell me what you are looking for, and I’ll guide you further."
                )

            return build_knowledge_summary_from_context(context, settings)
        prompt = f"""
Create a short company-side welcome line from raw trained business text.

Rules:
- Speak as the company using "we" and "our".
- Do NOT say AI, bot, knowledge base, trained data, context, or third-party assistant.
- Keep it human and complete, maximum 2 short lines.
- Mention only core business help, not charity/social work unless central.
- Do NOT copy raw catalogue text.
- Do NOT promise services unless clearly confirmed.

Saved allowed scope:
{allowed_scope}

Business reference text:
{text}

Return ONLY the welcome line.
""".strip()
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You write short customer-facing company welcome lines. Never mention AI, bot, context, or knowledge base."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 80,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            intro = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            intro = clean_ai_reply(re.sub(r"\s+", " ", intro).strip())
            return trim_to_complete_sentence(intro, max_chars=260) or f"We can help you with {allowed_scope}."
        except Exception as exc:
            print("[SMART INTRO ERROR]", repr(exc))
            return f"We can help you with {allowed_scope}."

    business_intro = make_smart_business_intro(context)
    return f"""Hi, welcome to {tenant_name}.

{business_intro}

How can I help you today?"""


def ask_groq(question: str, context: str, history: List[Dict[str, str]], settings: Dict = None) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
    print("[GROQ] key_exists:", bool(api_key))
    print("[GROQ] model:", model)
    if not api_key:
        return ""

    settings = settings or {}
    business_name = get_display_business_name(settings)
    system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
    restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES
    business_type = settings.get("business_type") or "General Business"
    industry = settings.get("industry") or "General"
    business_description = settings.get("business_description") or ""
    allowed_scope = _clean_scope_for_customer(settings.get("allowed_scope") or "")
    blocked_claims = settings.get("blocked_claims") or "Do not claim anything not confirmed in trained data."
    conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-6:]])
    has_context = bool((context or "").strip())

    context_instruction = (
        "Use the trained reference only to understand and verify. Rewrite naturally; do not copy raw chunks. If exact details are missing, say you will check with our team."
        if has_context else
        "No matching trained reference was found. Give only safe generic help and do not invent business facts."
    )

    prompt = f"""
You are replying as a real sales/support employee from {business_name}, not as a third-party bot.
{system_prompt}

Language rules:
- Primary/default reply language is English only.
- Reply in Hindi/Hinglish only when the customer clearly writes Hindi/Hinglish using multiple Hindi words or Devanagari script.
- Customer names like Aarvi, Aniket, Raj, Priya, etc. are NOT Hindi-language signals.
- If the customer asks "talk in English" or similar, continue in English for the conversation.

Tenant business controls from DB:
- Business type: {business_type}
- Industry: {industry}
- Business description: {business_description}
- Allowed scope: {allowed_scope}
- Blocked claims: {blocked_claims}

Human answer style:
- Use "we", "our", "I’ll check", "let me confirm".
- Do NOT say AI, bot, trained context, FAISS, knowledge base, saved data, tenant, or third-party assistant.
- Do NOT start with the company name repeatedly; speak naturally like an employee.
- Keep reply short: 1 to 4 lines.
- Ask only one useful follow-up question when needed.

Safety rules:
- Do not hallucinate.
- Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
- Use the trained reference as private reference only; never directly dump raw text.
- Blog/articles/comparison pages do not prove we sell or provide something.
- Do not claim installation, repair, maintenance, door repair, or on-site service unless clearly confirmed and not blocked by DB rules.
- If the customer asks outside Allowed scope or about Blocked claims, say: "Let me check with our team once and confirm the right details for you."

Tenant restriction rules:
{restriction_rules}

Reference handling:
{context_instruction}

Private trained reference:
{context if has_context else "[NO MATCHING TRAINED REFERENCE FOUND]"}

Conversation history:
{conversation if conversation else "[NO PREVIOUS HISTORY]"}

Customer message:
{question}

Write the best short WhatsApp reply as a company employee.
""".strip()

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are a safe employee-style WhatsApp sales/support assistant for {business_name}. Never expose internal tenant names or IDs. Never mention AI, FAISS, context, or knowledge base. Use DB business controls strictly and do not invent facts."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        print("[GROQ HTTP ERROR]", response.status_code, response.text[:500])
    response.raise_for_status()
    data = response.json()
    usage = data.get("usage", {})
    print("\n========== GROQ TOKEN USAGE ==========")
    print("Prompt/Input Tokens :", usage.get("prompt_tokens", 0))
    print("Completion Tokens   :", usage.get("completion_tokens", 0))
    print("Total Tokens        :", usage.get("total_tokens", 0))
    print("======================================\n")
    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return clean_ai_reply(reply)


    settings = settings or {}
    business_name = get_display_business_name(settings)
    system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
    restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES
    business_type = settings.get("business_type") or "General Business"
    industry = settings.get("industry") or "General"
    business_description = settings.get("business_description") or ""
    allowed_scope = settings.get("allowed_scope") or "Use only the trained knowledge base and confirmed tenant settings."
    blocked_claims = settings.get("blocked_claims") or "Do not claim anything not confirmed in trained data."
    conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-6:]])
    has_context = bool((context or "").strip())

    context_instruction = (
        "Use the trained context below to answer. If the exact answer is not available, do not invent."
        if has_context else
        "No trained knowledge context was found. Give only safe generic help and do not invent business facts."
    )

    prompt = f"""
You are a professional WhatsApp business assistant for {business_name}.
{system_prompt}

Language rules:
- Primary/default reply language is English only.
- Reply in Hindi/Hinglish only when the customer clearly writes Hindi/Hinglish using multiple Hindi words or Devanagari script.
- Customer names like Aarvi, Aniket, Raj, Priya, etc. are NOT Hindi-language signals.
- If the customer asks "talk in English" or similar, continue in English for the conversation.

Tenant business controls:
- Business type: {business_type}
- Industry: {industry}
- Business description: {business_description}
- Allowed scope: {allowed_scope}
- Blocked claims: {blocked_claims}
- If the customer asks outside Allowed scope or about Blocked claims, politely say it is not confirmed and offer to connect with the team.

Safety rules:
- Do not hallucinate.
- Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
- For unknown business-specific details, politely say you will check with the team.
- Keep reply short: 1 to 4 lines.
- Do not say "based on the context".
- Blog articles/guides/comparison pages do not prove the company sells those products.
- Do not claim installation, repair, maintenance, door repair, or on-site service unless the trained context explicitly confirms it.
- Only say the company sells/provides a product when the trained context clearly says it is a product, catalogue item, service, or company specialization.
- If a material appears only in a comparison/blog article, say it may be educational information and redirect to confirmed products.
- Never introduce yourself as "Tenant 1", "Tenant 2", "Tenant 3", or any internal tenant code.
- If the business name is unclear, say "our team" instead of exposing internal tenant names.
- Sound like a helpful human sales/support person, not a robotic AI.

Tenant restriction rules:
{restriction_rules}

Context handling:
{context_instruction}

Trained context:
{context if has_context else "[NO MATCHING TRAINED CONTEXT FOUND]"}

Conversation history:
{conversation if conversation else "[NO PREVIOUS HISTORY]"}

Customer message:
{question}

Write the best short WhatsApp reply.
""".strip()

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are a safe WhatsApp business assistant for {business_name}. Never expose internal tenant names or IDs. Use trained context and never invent business facts. Follow tenant business controls strictly."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 140,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        print("[GROQ HTTP ERROR]", response.status_code, response.text[:500])
    response.raise_for_status()
    data = response.json()
    usage = data.get("usage", {})
    print("\n========== GROQ TOKEN USAGE ==========")
    print("Prompt/Input Tokens :", usage.get("prompt_tokens", 0))
    print("Completion Tokens   :", usage.get("completion_tokens", 0))
    print("Total Tokens        :", usage.get("total_tokens", 0))
    print("======================================\n")
    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return clean_ai_reply(reply)


def run_faiss_search(message: str, tenant_id, top_k: int) -> List[Dict]:
    results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)
    results = filter_by_score(results)
    return results


def last_image_terms_from_history(history: List[Dict[str, str]]) -> str:
    for item in reversed(history or []):
        if item.get("role") == "user" and detect_intent(item.get("content", "")) == "image_request":
            terms = extract_product_terms(item.get("content", ""))
            if terms:
                return " ".join(terms[:4])
    return ""


def build_knowledge_summary_from_context(context: str, settings: Dict) -> str:
    text = re.sub(r"\s+", " ", context or "").strip()
    if not text:
        return fallback_answer("", settings)
    snippet = trim_to_complete_sentence(text, max_chars=500)
    business_name = get_display_business_name(settings)
    return f"Here’s what I currently have for {business_name}: {snippet}"

def extract_product_like_terms_from_context(context: str, max_terms: int = 6) -> List[str]:
    text = re.sub(r"[^a-zA-Z0-9\s&/-]", " ", context or "").lower()

    stopwords = {
        "the", "and", "for", "with", "from", "this", "that", "your", "our",
        "you", "are", "can", "will", "have", "has", "about", "company",
        "business", "products", "product", "services", "service", "details",
        "information", "page", "website", "contact", "home", "read", "more",
        "quality", "best", "provide", "offer", "offers", "available"
    }

    words = [
        w for w in text.split()
        if len(w) >= 4 and w not in stopwords and not w.isdigit()
    ]

    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, count in ranked[:max_terms] if count >= 2]


def build_product_overview_reply(context: str, settings: Dict) -> str:
    """Create a short sales-assistant product/service overview from tenant FAISS context only."""
    text = re.sub(r"\s+", " ", context or "").strip()
    business_name = get_display_business_name(settings)

    # if not text:
    #     return (
    #         f"{business_name} can help with products and services based on your requirement. "
    #         "Please tell me what you are looking for, and I’ll guide you with the right details."
    #     )
   
    if not text:
        return fallback_answer("", settings)

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    if not api_key:
        return build_knowledge_summary_from_context(context, settings)

    prompt = f"""
You are a trained business sales assistant for {business_name}.

Use ONLY the trained business reference below.
Do not invent product names, services, prices, or availability.
Do not say generic lines like "we offer a range of products".
Do not ask "what type are you looking for" before giving available categories.
Extract clear product/service categories from the tenant’s trained reference. If exact categories are present, name them directly. If only descriptive product text is present, infer simple customer-friendly categories from that reference only.
Keep it short, helpful, and customer-facing.

Trained business reference:
{text}

Reply format:
We provide:

• Category 1
• Category 2

End naturally with:
"Please tell me what you are looking for, and I’ll guide you further."

Do not mention projects.
Do not ask technical sales questions.
Speak like a simple helpful company representative.
""".strip()

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You write short business product overview replies from provided reference only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 180,
            },
            timeout=15,
        )
        if response.status_code >= 400:
            print("[PRODUCT OVERVIEW HTTP ERROR]", response.status_code, response.text[:500])
        response.raise_for_status()
        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return clean_ai_reply(reply) or build_knowledge_summary_from_context(context, settings)
    except Exception as exc:
        print("[PRODUCT OVERVIEW ERROR]", repr(exc))
        return build_knowledge_summary_from_context(context, settings)



def run_sales_support_agent_safe(
    tenant_id,
    session_id: str,
    message: str,
    top_k: int = 5,
):
    """
    Optional bridge to the new app/chat_agent engine.

    Important:
    - Does not break old chatbot.py if chat_agent folder is missing.
    - Accepts both {"reply": "..."} and {"answer": "..."} formats.
    - Falls back to old ask_groq() flow if the new agent returns empty/stub output.
    """
    if not callable(run_sales_support_agent):
        return "", {}, {}

    try:
        result = run_sales_support_agent(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            top_k=top_k,
        )

        if isinstance(result, str):
            answer = result.strip()
            assets = {}
            debug = {"sales_agent_result_type": "str"}
        elif isinstance(result, dict):
            answer = (
                result.get("answer")
                or result.get("reply")
                or result.get("response")
                or result.get("message")
                or ""
            )
            answer = str(answer or "").strip()
            assets = result.get("assets") if isinstance(result.get("assets"), dict) else {}
            debug = {
                "sales_agent_result_type": "dict",
                "sales_agent_intent": result.get("intent"),
            }
        else:
            return "", {}, {"sales_agent_result_type": type(result).__name__}

        # Protect production from placeholder/stub answers.
        weak_outputs = {
            "Sales support agent initialized.",
            "Generated response from Sales Support Agent.",
            "Sales support agent response generated successfully.",
        }
        if answer in weak_outputs:
            return "", {}, {
                **debug,
                "sales_agent_skipped_reason": "placeholder_response",
            }

        return answer, assets, debug

    except Exception as exc:
        print("[SALES SUPPORT AGENT ERROR]", repr(exc))
        return "", {}, {
            "sales_agent_error": repr(exc),
        }



def save_history(tenant_id, session_id: str, history: List[Dict[str, str]], message: str, answer: str):
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    del history[:-20]
    save_chat_history(tenant_id, session_id, history)


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
    session_id = session_id or "default"
    message = (message or "").strip()
    history = load_chat_history(tenant_id, session_id)
    settings = get_agent_settings_for_chat(tenant_id)
    state = load_chat_state(tenant_id, session_id)
    state.setdefault("last_image_query", "")
    state.setdefault("shown_images", [])
    intent = detect_intent(message)
    if intent == "normal_question" and is_more_image_followup(message) and state.get("last_image_query"):
        intent = "image_request"
    if message == WELCOME_MESSAGE_KEY:
            welcome_query = "company overview business introduction services products what company does about company"

            try:
                welcome_results = search_faiss(
                    welcome_query,
                    tenant_id=tenant_id,
                    top_k=5
                )

                welcome_context = build_context(
                    filter_by_score(welcome_results, min_score=0.20),
                    max_chars=1800
                )

            except Exception as exc:
                print("[WELCOME FAISS ERROR]", repr(exc))
                welcome_context = ""

            answer = build_first_welcome_message(settings, welcome_context)

            

            return {
                "answer": answer,
                "session_id": session_id,
                "tenant_name": settings.get("tenant_name"),
                "business_name": settings.get("business_name"),

                "starter_questions": settings.get(
                    "starter_questions",
                    []
                ),

                **empty_assets(),

                "history_count": len(history),

                "debug": {
                    "tenant_id": tenant_id,
                    "welcome_only": True,
                    "intent": "welcome",
                    "welcome_context_found": bool(welcome_context),
                },
            }
    # if message == WELCOME_MESSAGE_KEY:
    #     welcome_query = "company overview business introduction services products what company does about company"
    #     try:
    #         welcome_results = search_faiss(welcome_query, tenant_id=tenant_id, top_k=5)
    #         welcome_context = build_context(filter_by_score(welcome_results, min_score=0.20), max_chars=1800)
    #     except Exception as exc:
    #         print("[WELCOME FAISS ERROR]", repr(exc))
    #         welcome_context = ""
    #     answer = build_first_welcome_message(settings, welcome_context)
    #     answer = f"{answer}\n\nPlease share your name to start the chat."
    #     return {
    #         "answer": answer,
    #         "session_id": session_id,
    #         "tenant_name": settings.get("tenant_name"),
    #         "business_name": settings.get("business_name"),
    #         **empty_assets(),
    #         "history_count": len(history),
    #         "debug": {"tenant_id": tenant_id, "welcome_only": True, "intent": "welcome", "welcome_context_found": bool(welcome_context)},
    #     }

    # # English-first + name capture: do not send Hindi just because the customer name is Indian.
    # if user_requests_english(message):
    #     answer = "Sure, I’ll continue in English. How can I help you today?"
    #     save_history(tenant_id, session_id, history, message, answer)
    #     return {
    #         "answer": answer,
    #         "session_id": session_id,
    #         **empty_assets(),
    #         "history_count": len(history),
    #         "debug": {"tenant_id": tenant_id, "intent": "language_preference", "english_first": True},
    #     }

    # if is_likely_customer_name(message) and len(history) <= 2:
    #     customer_name = message.strip().split()[0].strip(".,!")
    #     answer = f"Hello {customer_name}, how can I help you today?"
    #     save_history(tenant_id, session_id, history, message, answer)
    #     return {
    #         "answer": answer,
    #         "session_id": session_id,
    #         **empty_assets(),
    #         "history_count": len(history),
    #         "debug": {"tenant_id": tenant_id, "intent": "customer_name", "english_first": True},
    #     }

    # Contact requests should never trigger product images or hallucinated LLM answers.
    
    if wants_human_connect(message):
        try:
            # KB/FAISS first for sales-team/contact handoff.
            # Do not return generic handoff or tenant/default WhatsApp numbers here.
            contact_query = (
                "official contact details phone mobile whatsapp email address website "
                "contact us about company homepage office address sales team"
            )
            kb_contact_results = search_faiss(contact_query, tenant_id=tenant_id, top_k=15)
        except Exception as exc:
            print("[HUMAN CONNECT KB SEARCH ERROR]", repr(exc))
            kb_contact_results = []

        answer = build_kb_first_contact_reply(
            settings,
            request_type="all",
            kb_results=kb_contact_results,
        )

        if "confirmed contact details" not in answer.lower():
            answer = (
                f"{answer}\n\n"
            )

        save_history(tenant_id, session_id, history, message, answer)

        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(history),
            "debug": {
                "tenant_id": tenant_id,
                "intent": "human_connect_request",
                "kb_first_contact": True,
                "routed_without_groq": True,
            },
        }

    if intent == "contact_request":
        req_type = contact_request_type(message) or "all"
        try:
            # KB/FAISS is the first priority for all customer-facing contact details.
            # Do not use tenant/default WhatsApp numbers here because they may be platform/test numbers.
            contact_query = (
                "official contact details phone mobile whatsapp email address website "
                "contact us about company homepage"
            )
            kb_contact_results = search_faiss(contact_query, tenant_id=tenant_id, top_k=15)
        except Exception as exc:
            print("[CONTACT KB SEARCH ERROR]", repr(exc))
            kb_contact_results = []

        answer = build_kb_first_contact_reply(
            settings,
            request_type=req_type,
            kb_results=kb_contact_results,
        )
        save_history(tenant_id, session_id, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(history),
            "debug": {
                "tenant_id": tenant_id,
                "intent": intent,
                "contact_type": req_type,
                "kb_first_contact": True,
                "contact_results_count": len(kb_contact_results),
            },
        }

    if intent in ["recommendation_request", "terminology_request", "service_request"]:
        intent = "normal_question"

    

    # Broad product/service overview should answer from tenant knowledge like a sales assistant.
    if intent == "product_overview_request":
        try:
            business_type = (
                settings.get("business_type") or ""
            ).strip().lower()

            overview_query = (
                f"{message} "
                f"{business_type} "
                "product products product list product range "
                "product category product categories "
                "catalogue catalog items offerings "
                "what we sell what we provide "
                "company overview business overview about company"
            )

            raw_overview_results = search_faiss(
                overview_query,
                tenant_id=tenant_id,
                top_k=15,
            )

            overview_results = filter_by_score(
                raw_overview_results,
                min_score=0.15,
            )

            overview_context = build_context(
                overview_results,
                max_chars=2500,
            )

            assets = collect_assets_from_results(
                overview_results,
                max_images=3,
                max_links=5,
            )

        except Exception as exc:
            print("[PRODUCT OVERVIEW FAISS ERROR]", repr(exc))
            overview_results = []
            overview_context = ""
            assets = empty_assets()

        answer = build_product_overview_reply(overview_context, settings)
        save_history(tenant_id, session_id, history, message, answer)

        return {
            "answer": answer,
            "session_id": session_id,
            "images": assets.get("images", []),
            "links": assets.get("links", []),
            "sources": assets.get("sources", []),
            "images_count": assets.get("images_count", 0),
            "links_count": assets.get("links_count", 0),
            "history_count": len(history),
            "debug": {
                "tenant_id": tenant_id,
                "intent": intent,
                "overview_mode": True,
                "faiss_results": len(overview_results),
                "context_found": bool(overview_context),
            },
        }
        
    # Recommendation requests should avoid guessing and first collect required use-case details.
    if intent in ["recommendation_request", "terminology_request", "service_request"]:
      intent = "normal_question"

    results = []
    context = ""
    assets = empty_assets()

    try:
        search_message = message

        # Human behavior: "show more images" should continue previous product image request.
        if intent == "image_request" and not is_random_image_request(message):
            meaningful_terms = _image_query_terms(message)
            if not meaningful_terms:
                previous_terms = state.get("last_image_query") or last_image_terms_from_history(history)
                if previous_terms:
                    search_message = previous_terms
                else:
                    # Generic request like "show me some images": use tenant's saved business scope,
                    # not fixed product names. This keeps the logic universal for every tenant.
                    scope_for_images = _clean_scope_for_customer(settings.get("allowed_scope") or "")
                    description_for_images = (settings.get("business_description") or "").strip()
                    search_message = f"{description_for_images} {scope_for_images} product images catalogue".strip()
            else:
                search_message = " ".join(meaningful_terms[:5])

        # When customer asks what information we have, search broad business/product overview.
        if re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
            search_message = "company overview products services business information contact service areas"

        raw_results = run_faiss_search(search_message, tenant_id=tenant_id, top_k=max(top_k, 8))

        if intent == "image_request" and not is_random_image_request(message):
            results = filter_results_by_message(raw_results, search_message)
        else:
            results = raw_results

        # Contact queries should only use contact-related chunks.
        if intent == "contact_request":
            contact_results = [
                r for r in results
                if r.get("page_type") == "contact_page"
                or "contact" in (r.get("url") or "").lower()
                or "contact" in (r.get("title") or "").lower()
            ]

            if contact_results:
                results = contact_results[:2]

        context = build_context(results)
    except FileNotFoundError:
        print("[FAISS ERROR] Index missing for tenant:", tenant_id)
        raise
    except Exception as exc:
        print("[FAISS SEARCH ERROR]", repr(exc))
        results = []
        context = ""

    if intent == "image_request":
        label = clean_image_label(search_message, history)
        limit = requested_image_limit(message, default=4)
        exclude = state.get("shown_images") or []
        has_specific_image_terms = image_request_has_specific_terms(message)
        raw_image_results = raw_results if 'raw_results' in locals() else results

        # First collect exact product images from tenant FAISS results.
        # FAISS is tenant-specific because every search call uses tenant_id.
        exact_results = filter_exact_image_results(
            rank_results_for_images(results, search_message, history),
            search_message,
        )
        assets = collect_assets_from_results(
            exact_results,
            max_images=limit,
            max_links=10,
            exclude_images=exclude if is_more_image_followup(message) else [],
        )

        used_related_fallback = False
        used_random_fallback = False

        # If exact image is not available, show high-score related images
        # from the same tenant knowledge.
        if not assets.get("images"):
            related_candidates = filter_related_image_results(
                rank_results_for_images(raw_image_results, search_message, history),
                search_message,
            )
            related_assets = collect_assets_from_results(
                related_candidates,
                max_images=limit,
                max_links=10,
                exclude_images=exclude if is_more_image_followup(message) else [],
            )
            if related_assets.get("images"):
                assets = related_assets
                used_related_fallback = True

        # Generic/random image requests should still show tenant images when the
        # FAISS query has no exact product term to match.
        if not assets.get("images") and (is_random_image_request(message) or not has_specific_image_terms):
            metadata_candidates = image_results_from_tenant_metadata(tenant_id, search_message)
            metadata_assets = collect_assets_from_results(
                metadata_candidates,
                max_images=limit,
                max_links=10,
                exclude_images=exclude if is_more_image_followup(message) else [],
            )
            if metadata_assets.get("images"):
                assets = metadata_assets
                used_random_fallback = True

        if not assets.get("images") and is_more_image_followup(message) and state.get("last_image_query"):
            answer = f"I don’t have more new {clean_image_label(state.get('last_image_query') or label, history)} i I can check with the {human_team_phrase(settings)}."
        elif assets.get("images"):
            # Persist image conversation state for natural follow-ups like "3 more".
            state["last_image_query"] = search_message or label
            state["shown_images"] = _unique_keep_order((state.get("shown_images") or []) + assets.get("images", []))[-80:]

            if used_related_fallback:
                if is_more_image_followup(message):
                    answer = "Here are your few more related product images."
                else:
                    answer = f"I couldn’t get the exact {label} image , but I can share some related product images that may help."
            elif is_more_image_followup(message):
                answer = f"Sure, here are more {clean_image_label(state.get('last_image_query') or label, history)} images I found."
            elif is_random_image_request(message):
                answer = "Sure, I’m sharing a few product images for you."
            elif contains_product_page_intent(message):
                answer = "Yes, I have more product-page images. Here are the available ones I can show you."
            elif wants_single_or_clear_image(message):
                answer = f"Sure, I’m sharing clearer {label} image options for you"
            else:
                answer = f"Sure, here are some {label} images I found."
        else:
            metadata_candidates = image_results_from_tenant_metadata(
                tenant_id,
                search_message,
            )

            metadata_assets = collect_assets_from_results(
                metadata_candidates,
                max_images=max(3, limit),
                max_links=10,
            )

            if metadata_assets.get("images"):
                assets = metadata_assets

                state["last_image_query"] = search_message or label
                state["shown_images"] = _unique_keep_order(
                    (state.get("shown_images") or []) + assets.get("images", [])
                )[-80:]

                answer = (
                    f"I couldn’t get the exact {label} image, "
                    "but I am sharing some related product images with you."
                )

            else:
                team = human_team_phrase(settings)

                if is_random_image_request(message):
                    answer = (
                        f"I don’t have any usable product images right now. "
                        f"I can check this with the {team}."
                    )
                else:
                    answer = (
                        f"I couldn’t find product images right now. "
                        f"I can check this with the {team}."
                    )

        save_history(tenant_id, session_id, history, message, answer)
        save_chat_state(tenant_id, session_id, state)
        return {
            "answer": answer,
            "session_id": session_id,
            "images": assets.get("images", []),
            "links": assets.get("links", []),
            "sources": assets.get("sources", []),
            "images_count": assets.get("images_count", 0),
            "links_count": assets.get("links_count", 0),
            "history_count": len(history),
            "debug": {"tenant_id": tenant_id, "intent": intent, "image_query": state.get("last_image_query"), "shown_images": len(state.get("shown_images") or []), "faiss_results": len(results), "context_found": bool(context), "top_score": results[0].get("score") if results else None},
        }


    if is_selling_confirmation_question(message) and any(x in message.lower() for x in ["copper", "abs", "pvc", "cast iron"]):
        answer = build_product_boundary_reply(message, context, settings)
    elif re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
        answer = build_knowledge_summary_from_context(context, settings)
    elif len(history) == 0 and is_greeting_only(message):
        answer = build_first_welcome_message(settings, context)
    else:
        agent_assets = {}
        agent_debug = {}

        # New Sales/Support Agent layer:
        # Only used for final normal questions, after all existing special routes
        # like welcome, contact, service, images, terminology, and recommendations.
        answer, agent_assets, agent_debug = run_sales_support_agent_safe(
            tenant_id=tenant_id,
            session_id=session_id,
            message=message,
            top_k=max(top_k, 8),
        )

        # Production-safe fallback:
        # If the new chat_agent folder is missing, errors, or returns a placeholder,
        # your existing Groq + FAISS answer flow continues unchanged.
        if not answer:
            try:
                answer = ask_groq(message, context, history, settings=settings)
            except Exception as exc:
                print("[GROQ ERROR]", repr(exc))
                answer = ""

        if not answer:
            answer = fallback_answer(message, settings)

    save_history(tenant_id, session_id, history, message, answer)

    response_assets = agent_assets if isinstance(locals().get("agent_assets"), dict) and agent_assets else empty_assets()

    return {
        "answer": answer,
        "session_id": session_id,
        "images": response_assets.get("images", []),
        "links": response_assets.get("links", []),
        "sources": response_assets.get("sources", []),
        "images_count": len(response_assets.get("images", []) or []),
        "links_count": len(response_assets.get("links", []) or []),
        "history_count": len(history),
        "debug": {
            "tenant_id": tenant_id,
            "intent": intent,
            "sales_support_agent_used": bool(locals().get("agent_debug")) and bool(answer),
            "sales_support_agent_debug": locals().get("agent_debug", {}),
            "faiss_results": len(results),
            "context_found": bool(context),
            "context_length": len(context),
            "top_score": results[0].get("score") if results else None,
            "top_text_len": len(get_text_from_result(results[0])) if results else 0,
        },
    }
