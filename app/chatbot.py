
# import os
# import json
# from typing import Dict, List
# import re
# import requests

# from app.db import get_main_db_connection
# from app.index_builder import search_faiss

# CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
# WELCOME_MESSAGE_KEY = "__welcome__"
# MIN_FAISS_SCORE = float(os.getenv("MIN_FAISS_SCORE", "0.35"))

# DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
# - Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
# - If trained context is missing or not enough, give a safe, generic, human reply.
# - For unknown business-specific details, politely say you will check with the team.
# - Keep replies short, clear, and helpful."""

# CONTACT_COLUMNS = [
#     "website_url", "website", "client_domain", "business_website",
#     "support_phone", "phone", "mobile", "whatsapp_number",
#     "support_email", "email", "business_email", "address",
# ]


# def get_text_from_result(item: Dict) -> str:
#     if not isinstance(item, dict):
#         return ""
#     return (
#         item.get("text")
#         or item.get("chunk_text")
#         or item.get("content")
#         or item.get("page_content")
#         or item.get("body")
#         or item.get("description")
#         or ""
#     ).strip()


# def _unique_keep_order(values):
#     seen = set()
#     output = []
#     for value in values or []:
#         key = str(value or "").strip()
#         if not key or key in seen:
#             continue
#         seen.add(key)
#         output.append(key)
#     return output


# def _json_load(value, default=None):
#     if value is None:
#         return default
#     if isinstance(value, (dict, list)):
#         return value
#     try:
#         return json.loads(value)
#     except Exception:
#         return default


# def is_greeting_only(message: str) -> bool:
#     value = (message or "").strip().lower()
#     greetings = {
#         "hi", "hii", "hello", "hey", "hey there", "good morning",
#         "good afternoon", "good evening", "namaste", "hola"
#     }
#     return value in greetings


# def should_reply_hindi(message: str) -> bool:
#     """English-first. Use Hindi only when the customer clearly writes Hindi/Hinglish."""
#     text = (message or "").strip()
#     if not text:
#         return False
#     # Devanagari is a strong signal.
#     if re.search(r"[\u0900-\u097F]", text):
#         return True

#     # Hinglish needs at least 2 strong words; names like Aniket/Aarvi must not trigger Hindi.
#     value = f" {text.lower()} "
#     hindi_words = [
#         " kya ", " kaise ", " mujhe ", " chahiye ", " batao ", " dikhao ",
#         " aap ", " apko ", " hai ", " hain ", " mera ", " meri ", " madad ",
#         " hindi ", " hinglish ", " karna ", " karo ", " krna ", " dikha ",
#     ]
#     return sum(1 for w in hindi_words if w in value) >= 2


# def is_likely_customer_name(message: str) -> bool:
#     value = (message or "").strip()
#     if not value or len(value) > 40:
#         return False
#     if is_greeting_only(value):
#         return False
#     if re.search(r"[?@:/\\0-9]", value):
#         return False
#     words = value.split()
#     if len(words) > 3:
#         return False
#     blocked = {
#         "pipe", "pipes", "fitting", "fittings", "image", "images", "photo",
#         "website", "contact", "number", "price", "service", "services", "english",
#     }
#     return all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", w) and w.lower() not in blocked for w in words)


# def user_requests_english(message: str) -> bool:
#     value = (message or "").lower()
#     return any(x in value for x in ["talk in english", "speak english", "english only", "reply in english", "in english"])


# def detect_intent(message: str) -> str:
#     """Simple safe router. No hardcoding of tenant data."""
#     value = (message or "").lower().strip()

#     contact_words = [
#         "phone", "mobile", "number", "call", "contact", "email", "mail",
#         "support", "customer care", "website", "site link", "web link", "address",
#         "location", "whatsapp", "specific contact",
#     ]
#     image_words = [
#         "image", "images", "photo", "photos", "picture", "pictures", "pic",
#         "visual", "catalog", "catalogue", "brochure", "show me", "show some",
#         "show more", "see some", "product page",
#     ]
#     recommendation_words = [
#         "best", "recommend", "suggest", "which one", "which pipe", "suitable",
#         "for my office", "office fitting", "home fitting", "commercial fitting",
#         "what should i use", "what should we use",
#     ]

#     if any(word in value for word in contact_words):
#         return "contact_request"
#     if any(word in value for word in image_words):
#         return "image_request"
#     if any(word in value for word in recommendation_words):
#         return "recommendation_request"
#     if is_greeting_only(value):
#         return "greeting"
#     return "normal_question"


# def is_image_request(message: str) -> bool:
#     return detect_intent(message) == "image_request"


# def is_random_image_request(message: str) -> bool:
#     value = (message or "").lower()
#     random_words = [
#         "random image", "random images", "any image", "any images",
#         "some images random", "show random", "show any", "any product image",
#         "any pipe image", "whatever image", "just show",
#     ]
#     return any(word in value for word in random_words)


# def normalize_url(url: str) -> str:
#     url = (url or "").strip()
#     if not url:
#         return ""
#     if url.startswith(("http://", "https://")):
#         return url
#     if "." in url and " " not in url:
#         return "https://" + url.lstrip("/")
#     return url



# def looks_like_internal_tenant_name(name: str) -> bool:
#     value = (name or "").strip().lower()
#     if not value:
#         return True
#     # Avoid customer-facing replies like "Tenant 3" or random tenant codes.
#     if re.fullmatch(r"tenant\s*\d+", value):
#         return True
#     if re.fullmatch(r"t[0-9a-z!@#$%^&*_-]{4,}", value):
#         return True
#     if value in {"tenant", "this business", "our company"}:
#         return True
#     return False


# def get_display_business_name(settings: Dict) -> str:
#     business_name = (settings.get("business_name") or "").strip()
#     tenant_name = (settings.get("tenant_name") or "").strip()

#     if business_name and not looks_like_internal_tenant_name(business_name):
#         return business_name
#     if tenant_name and not looks_like_internal_tenant_name(tenant_name):
#         return tenant_name
#     return "our team"


# def human_team_phrase(settings: Dict) -> str:
#     name = get_display_business_name(settings)
#     return f"{name} team" if name != "our team" else "our team"

# def is_valid_url(url: str) -> bool:
#     url = normalize_url(url)
#     if not url.startswith(("http://", "https://")):
#         return False
#     try:
#         response = requests.head(url, allow_redirects=True, timeout=4)
#         if response.status_code < 400:
#             return True
#         response = requests.get(url, allow_redirects=True, timeout=4, stream=True)
#         return response.status_code < 400
#     except Exception:
#         # Do not drop tenant data just because a server blocks HEAD/GET.
#         return True


# def extract_product_terms(message: str) -> List[str]:
#     value = (message or "").lower()
#     phrases = [
#         "cast iron", "stainless steel", "ss", "abs", "pvc", "pipe", "pipes",
#         "fitting", "fittings", "pressfit", "elbow", "tee", "coupler", "valve",
#         "flange", "bend", "socket", "adapter",
#     ]
#     found = []
#     for phrase in phrases:
#         if phrase in value:
#             found.append(phrase)
#     # Also keep important free words from user's query.
#     noise = {
#         "show", "me", "some", "more", "image", "images", "photo", "photos",
#         "picture", "pictures", "please", "can", "you", "provide", "give", "the",
#         "a", "an", "of", "for", "my", "your", "and", "or", "other", "than", "these",
#         "more", "single", "clear", "actually", "not", "much", "there", "are", "various",
#         "page", "product", "right", "first", "get", "want", "need", "available",
#     }
#     for word in re.findall(r"[a-zA-Z0-9]+", value):
#         if len(word) >= 3 and word not in noise:
#             found.append(word)
#     return _unique_keep_order(found)


# def clean_image_label(message: str, history: List[Dict[str, str]] = None) -> str:
#     """Create a clean customer-facing label for image responses."""
#     terms = extract_product_terms(message)

#     # If user says "more images", "single image", "clear image" etc, continue previous image topic.
#     generic_terms = {"pipe", "pipes", "image", "images", "photo", "photos", "single", "clear", "more", "product", "page"}
#     meaningful = [t for t in terms if t not in generic_terms]
#     if not meaningful and history:
#         previous = last_image_terms_from_history(history)
#         if previous:
#             terms = extract_product_terms(previous)

#     label_parts = []
#     priority = [
#         "stainless steel", "cast iron", "abs", "pvc", "ss", "elbow", "tee",
#         "coupler", "fitting", "fittings", "pipe", "pipes",
#     ]
#     for item in priority:
#         if item in terms and item not in label_parts:
#             label_parts.append("stainless steel" if item == "ss" else item)

#     if not label_parts and terms:
#         label_parts = terms[:3]

#     label = " ".join(label_parts).strip()
#     label = re.sub(r"\b(pipe) pipes\b", "pipes", label)
#     label = re.sub(r"\bpipes pipe\b", "pipes", label)
#     return label or "product"


# def is_selling_confirmation_question(message: str) -> bool:
#     value = (message or "").lower()
#     return any(x in value for x in [
#         "do you sell", "are you selling", "you selling", "do you provide",
#         "do you have", "available at you", "available with you", "what pipes do you sell",
#         "which pipes do you sell", "what do you sell",
#     ])


# def contains_product_page_intent(message: str) -> bool:
#     value = (message or "").lower()
#     return "product page" in value or "product images" in value or "various pipe images" in value


# def looks_like_blog_or_comparison(item: Dict) -> bool:
#     haystack = " ".join([
#         str(item.get("url") or ""),
#         str(item.get("title") or ""),
#         get_text_from_result(item),
#     ]).lower()
#     blog_words = ["blog", "article", "compare", "comparison", "alternative", "traditional", "guide", "advantages", "disadvantages"]
#     return any(w in haystack for w in blog_words)


# def build_product_boundary_reply(message: str, context: str, settings: Dict) -> str:
#     """Prevent blog/comparison content from becoming fake inventory."""
#     value = (message or "").lower()
#     business_name = get_display_business_name(settings)

#     # We do not hardcode tenant inventory. This sentence uses context if available, but refuses unsupported products.
#     if any(x in value for x in ["copper", "abs", "pvc", "cast iron"]):
#         if "stainless steel" in (context or "").lower() or "ss" in (context or "").lower():
#             return f"We mainly deal in stainless steel pipes and fittings. I may have educational/blog information about other pipe materials, but I shouldn’t say we sell them unless it’s listed in our product data."
#         return f"I can see some reference information, but I don’t have confirmed product data showing that {business_name} sells that item. I can check this with the team."

#     return "I’ll check the confirmed product list and help you with the right option."


# def rank_results_for_images(results: List[Dict], message: str, history: List[Dict[str, str]] = None) -> List[Dict]:
#     terms = extract_product_terms(message)
#     if history and len([t for t in terms if t not in {"pipe", "pipes", "image", "images", "photo", "photos", "more", "single", "clear"}]) == 0:
#         previous = last_image_terms_from_history(history)
#         terms = extract_product_terms(previous) or terms

#     def score(item: Dict) -> int:
#         haystack = " ".join([
#             get_text_from_result(item),
#             str(item.get("title") or ""),
#             str(item.get("url") or ""),
#             str(item.get("file_name") or ""),
#             " ".join(item.get("images") or []),
#             " ".join(item.get("links") or []),
#         ]).lower()
#         s = 0
#         for t in terms:
#             if t and t in haystack:
#                 s += 3 if t in {"stainless steel", "cast iron", "abs", "pvc", "elbow", "tee", "coupler"} else 1
#         if item.get("images"):
#             s += 5
#         if "product" in haystack or "pipe" in haystack or "fitting" in haystack:
#             s += 2
#         if looks_like_blog_or_comparison(item):
#             s -= 2
#         return s

#     return sorted(results or [], key=score, reverse=True)


# def result_matches_terms(item: Dict, terms: List[str]) -> bool:
#     if not terms:
#         return True
#     haystack = " ".join([
#         get_text_from_result(item),
#         str(item.get("title") or ""),
#         str(item.get("url") or ""),
#         str(item.get("file_name") or ""),
#         " ".join(item.get("images") or []),
#         " ".join(item.get("links") or []),
#     ]).lower()

#     # Require important material/product terms when user asked for them.
#     important = [t for t in terms if t in {"cast iron", "stainless steel", "abs", "pvc", "ss"}]
#     if important and not any(t in haystack for t in important):
#         return False

#     # Generic pipe/fitting terms are enough when no specific material is present.
#     return any(t in haystack for t in terms)


# def filter_results_by_message(results: List[Dict], message: str) -> List[Dict]:
#     terms = extract_product_terms(message)
#     filtered = [item for item in (results or []) if result_matches_terms(item, terms)]
#     return filtered


# def filter_by_score(results: List[Dict], min_score: float = MIN_FAISS_SCORE) -> List[Dict]:
#     output = []
#     for item in results or []:
#         score = item.get("score")
#         try:
#             if score is None or float(score) >= min_score:
#                 output.append(item)
#         except Exception:
#             output.append(item)
#     return output


# def collect_assets_from_results(results: List[Dict], max_images: int = 6, max_links: int = 6) -> Dict:
#     image_urls = []
#     link_urls = []
#     sources = []

#     for item in results or []:
#         image_urls.extend(item.get("images") or [])
#         link_urls.extend(item.get("links") or [])
#         source = item.get("url") or item.get("file_name") or item.get("title")
#         if source:
#             sources.append(source)

#     images = _unique_keep_order(image_urls)
#     links = _unique_keep_order(link_urls)
#     sources = _unique_keep_order(sources)[:max_links]

#     valid_images = []
#     for url in images:
#         url = normalize_url(url)
#         if is_valid_url(url):
#             valid_images.append(url)
#         if len(valid_images) >= max_images:
#             break

#     valid_links = []
#     for url in links:
#         url = normalize_url(url)
#         if is_valid_url(url):
#             valid_links.append(url)
#         if len(valid_links) >= max_links:
#             break

#     return {
#         "images": valid_images,
#         "links": valid_links,
#         "sources": sources,
#         "images_count": len(valid_images),
#         "links_count": len(valid_links),
#     }


# def empty_assets() -> Dict:
#     return {"images": [], "links": [], "sources": [], "images_count": 0, "links_count": 0}


# def _get_table_columns(cur, table_name: str) -> set:
#     try:
#         cur.execute(f"SHOW COLUMNS FROM {table_name}")
#         return {row.get("Field") for row in cur.fetchall() or []}
#     except Exception:
#         return set()


# def get_agent_settings_for_chat(tenant_id) -> Dict:
#     row = {}
#     try:
#         conn = get_main_db_connection()
#         try:
#             with conn.cursor() as cur:
#                 tenant_cols = _get_table_columns(cur, "tenants")
#                 settings_cols = _get_table_columns(cur, "tenant_agent_settings")

#                 tenant_selects = ["t.tenant_name"]
#                 for col in CONTACT_COLUMNS:
#                     if col in tenant_cols:
#                         tenant_selects.append(f"t.{col}")

#                 settings_selects = []
#                 for col in ["business_name", "greeting_message", "system_prompt", "restriction_rules", "support_hours"]:
#                     if col in settings_cols:
#                         settings_selects.append(f"tas.{col}")
#                     else:
#                         settings_selects.append(f"NULL AS {col}")

#                 sql = f"""
#                     SELECT
#                         {", ".join(settings_selects)},
#                         {", ".join(tenant_selects)}
#                     FROM tenants t
#                     LEFT JOIN tenant_agent_settings tas ON tas.tenant_id = t.id
#                     WHERE t.id=%s
#                     LIMIT 1
#                 """
#                 cur.execute(sql, (tenant_id,))
#                 row = cur.fetchone() or {}
#         finally:
#             conn.close()
#     except Exception as exc:
#         print("[CHAT SETTINGS ERROR]", repr(exc))
#         row = {}

#     tenant_name = row.get("tenant_name") or row.get("business_name") or "this business"
#     business_name = row.get("business_name") or tenant_name
#     system_prompt = (row.get("system_prompt") or "").strip()
#     restriction_rules = (row.get("restriction_rules") or "").strip()

#     if not system_prompt:
#         system_prompt = f"""You are a helpful business assistant for {business_name}.
# Reply naturally like a real human assistant.
# Use trained knowledge when available.
# If trained knowledge is not enough, do not invent details."""

#     if not restriction_rules:
#         restriction_rules = DEFAULT_RESTRICTION_RULES

#     contact = {}
#     for col in CONTACT_COLUMNS:
#         value = (row.get(col) or "").strip() if isinstance(row.get(col), str) else row.get(col)
#         if value:
#             contact[col] = value

#     return {
#         "tenant_name": tenant_name,
#         "business_name": business_name,
#         "system_prompt": system_prompt,
#         "restriction_rules": restriction_rules,
#         "support_hours": _json_load(row.get("support_hours"), default={}) or {},
#         "contact": contact,
#     }


# def build_context(results: List[Dict], max_chars: int = 1200) -> str:
#     parts = []
#     total = 0
#     for i, item in enumerate(results, start=1):
#         source = item.get("url") or item.get("file_name") or item.get("title") or "trained data"
#         text = get_text_from_result(item)
#         if not text:
#             print("[CONTEXT SKIP] result has no text. keys:", list(item.keys()))
#             continue
#         block = f"[Source {i}: {source}]\n{text}"
#         if total + len(block) > max_chars:
#             remaining = max_chars - total
#             if remaining > 150:
#                 parts.append(block[:remaining])
#             break
#         parts.append(block)
#         total += len(block)
#     context = "\n\n".join(parts)
#     print("[CONTEXT BUILD] parts:", len(parts))
#     print("[CONTEXT BUILD] length:", len(context))
#     print("[CONTEXT BUILD] sample:", context[:300])
#     return context


# def clean_ai_reply(reply: str) -> str:
#     if not reply:
#         return ""
#     cleaned = reply.strip()
#     remove_phrases = [
#         "According to the provided context,", "Based on the provided context,",
#         "Based on the context,", "According to the context,", "From the context,",
#         "According to the document,", "Based on the document,", "The context says",
#         "The provided information says",
#     ]
#     for phrase in remove_phrases:
#         cleaned = cleaned.replace(phrase, "").strip()
#     return cleaned


# def fallback_answer(message: str = "", settings: Dict = None) -> str:
#     settings = settings or {}
#     team = human_team_phrase(settings)
#     if detect_intent(message) == "image_request":
#         return f"I could not find clearly matching images for that in the trained data. I can check this with the {team}."
#     if detect_intent(message) == "contact_request":
#         return f"I do not have confirmed contact details saved here. I can connect you with the {team}."
#     return f"I’ll check this with the {team} and get back to you."


# def trim_to_complete_sentence(text: str, max_chars: int = 260) -> str:
#     text = re.sub(r"\s+", " ", text or "").strip()
#     if not text:
#         return ""
#     if len(text) <= max_chars and re.search(r"[.!?]$", text):
#         return text
#     cut = text[:max_chars].strip()
#     last_end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
#     if last_end >= 80:
#         return cut[: last_end + 1].strip()
#     return cut.rstrip(",;:- ") + "."


# def build_contact_reply(settings: Dict) -> str:
#     contact = settings.get("contact") or {}
#     business_name = get_display_business_name(settings)

#     website = contact.get("website_url") or contact.get("website") or contact.get("client_domain") or contact.get("business_website")
#     phone = contact.get("support_phone") or contact.get("phone") or contact.get("mobile") or contact.get("whatsapp_number")
#     email = contact.get("support_email") or contact.get("email") or contact.get("business_email")
#     address = contact.get("address")

#     lines = [f"Sure, here are the available contact details for {business_name}:"]
#     if website:
#         lines.append(f"Website: {normalize_url(str(website))}")
#     if phone:
#         lines.append(f"Phone/WhatsApp: {phone}")
#     if email:
#         lines.append(f"Email: {email}")
#     if address:
#         lines.append(f"Address: {address}")

#     if len(lines) == 1:
#         return "I don’t have confirmed contact details saved for this business yet. I can connect you with the team."
#     return "\n".join(lines)


# def build_recommendation_question(settings: Dict, message: str) -> str:
#     return (
#         "Sure — I can guide you. Just tell me 2 things first:\n"
#         "1. Is it for water supply, drainage, gas, or another use?\n"
#         "2. Is the fitting indoor or outdoor?\n\n"
#         "Then I’ll suggest the most suitable option from what we have."
#     )


# def build_first_welcome_message(settings: Dict, context: str) -> str:
#     tenant_name = get_display_business_name(settings)

#     def make_smart_business_intro(context_text: str) -> str:
#         text = (context_text or "").replace("\n", " ").strip()
#         if not text:
#             return "We can help you with product details, fittings, images, specifications, and support."
#         api_key = os.getenv("GROQ_API_KEY", "").strip()
#         model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
#         if not api_key:
#             return "We can help you with product details, fittings, images, specifications, and support."
#         prompt = f"""
# Create a short and professional company introduction.

# Your task:
# - Explain clearly what the company does.
# - Keep it simple and human.
# - Maximum 2 short lines.
# - Do NOT list product names one by one.
# - Do NOT copy raw catalogue text.
# - Do NOT mention charity/social work unless the user asks about it.
# - Do NOT mention random features unless they are central to the business.
# - Return a complete sentence only.

# Business context:
# {text}

# Return ONLY the company introduction.
# """.strip()
#         try:
#             response = requests.post(
#                 "https://api.groq.com/openai/v1/chat/completions",
#                 headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
#                 json={
#                     "model": model,
#                     "messages": [
#                         {"role": "system", "content": "You create clean business introductions from raw website content."},
#                         {"role": "user", "content": prompt},
#                     ],
#                     "temperature": 0.1,
#                     "max_tokens": 80,
#                 },
#                 timeout=15,
#             )
#             response.raise_for_status()
#             data = response.json()
#             intro = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
#             intro = re.sub(r"\s+", " ", intro).strip()
#             return trim_to_complete_sentence(intro, max_chars=260) or "We can help you with product details, fittings, images, specifications, and support."
#         except Exception as exc:
#             print("[SMART INTRO ERROR]", repr(exc))
#             return "We can help you with product details, fittings, images, specifications, and support."

#     business_intro = make_smart_business_intro(context)
#     return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# {business_intro}"""


# def ask_groq(question: str, context: str, history: List[Dict[str, str]], settings: Dict = None) -> str:
#     api_key = os.getenv("GROQ_API_KEY", "").strip()
#     model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
#     print("[GROQ] key_exists:", bool(api_key))
#     print("[GROQ] model:", model)
#     if not api_key:
#         return ""

#     settings = settings or {}
#     business_name = get_display_business_name(settings)
#     system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
#     restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES
#     conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history[-6:]])
#     has_context = bool((context or "").strip())

#     context_instruction = (
#         "Use the trained context below to answer. If the exact answer is not available, do not invent."
#         if has_context else
#         "No trained knowledge context was found. Give only safe generic help and do not invent business facts."
#     )

#     prompt = f"""
# You are a professional WhatsApp business assistant for {business_name}.
# {system_prompt}

# Language rules:
# - Primary/default reply language is English only.
# - Reply in Hindi/Hinglish only when the customer clearly writes Hindi/Hinglish using multiple Hindi words or Devanagari script.
# - Customer names like Aarvi, Aniket, Raj, Priya, etc. are NOT Hindi-language signals.
# - If the customer asks "talk in English" or similar, continue in English for the conversation.

# Safety rules:
# - Do not hallucinate.
# - Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
# - For unknown business-specific details, politely say you will check with the team.
# - Keep reply short: 1 to 4 lines.
# - Do not say "based on the context".
# - Blog articles/guides/comparison pages do not prove the company sells those products.
# - Only say the company sells/provides a product when the trained context clearly says it is a product, catalogue item, service, or company specialization.
# - If a material appears only in a comparison/blog article, say it may be educational information and redirect to confirmed products.
# - Never introduce yourself as "Tenant 1", "Tenant 2", "Tenant 3", or any internal tenant code.
# - If the business name is unclear, say "our team" instead of exposing internal tenant names.
# - Sound like a helpful human sales/support person, not a robotic AI.

# Tenant restriction rules:
# {restriction_rules}

# Context handling:
# {context_instruction}

# Trained context:
# {context if has_context else "[NO MATCHING TRAINED CONTEXT FOUND]"}

# Conversation history:
# {conversation if conversation else "[NO PREVIOUS HISTORY]"}

# Customer message:
# {question}

# Write the best short WhatsApp reply.
# """.strip()

#     response = requests.post(
#         "https://api.groq.com/openai/v1/chat/completions",
#         headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
#         json={
#             "model": model,
#             "messages": [
#                 {"role": "system", "content": f"You are a safe WhatsApp business assistant for {business_name}. Never expose internal tenant names or IDs. Use trained context and never invent business facts."},
#                 {"role": "user", "content": prompt},
#             ],
#             "temperature": 0.2,
#             "max_tokens": 140,
#         },
#         timeout=20,
#     )
#     if response.status_code >= 400:
#         print("[GROQ HTTP ERROR]", response.status_code, response.text[:500])
#     response.raise_for_status()
#     data = response.json()
#     usage = data.get("usage", {})
#     print("\n========== GROQ TOKEN USAGE ==========")
#     print("Prompt/Input Tokens :", usage.get("prompt_tokens", 0))
#     print("Completion Tokens   :", usage.get("completion_tokens", 0))
#     print("Total Tokens        :", usage.get("total_tokens", 0))
#     print("======================================\n")
#     reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
#     return clean_ai_reply(reply)


# def run_faiss_search(message: str, tenant_id, top_k: int) -> List[Dict]:
#     results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)
#     results = filter_by_score(results)
#     return results


# def last_image_terms_from_history(history: List[Dict[str, str]]) -> str:
#     for item in reversed(history or []):
#         if item.get("role") == "user" and detect_intent(item.get("content", "")) == "image_request":
#             terms = extract_product_terms(item.get("content", ""))
#             if terms:
#                 return " ".join(terms[:4])
#     return ""


# def build_knowledge_summary_from_context(context: str, settings: Dict) -> str:
#     text = re.sub(r"\s+", " ", context or "").strip()
#     if not text:
#         return fallback_answer("", settings)
#     snippet = trim_to_complete_sentence(text, max_chars=500)
#     business_name = get_display_business_name(settings)
#     return f"Here’s what I currently have for {business_name}: {snippet}"


# def save_history(history_key: str, history: List[Dict[str, str]], message: str, answer: str):
#     history.append({"role": "user", "content": message})
#     history.append({"role": "assistant", "content": answer})
#     CHAT_MEMORY[history_key] = history[-20:]


# def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
#     session_id = session_id or "default"
#     message = (message or "").strip()
#     history_key = f"{tenant_id}:{session_id}"
#     history = CHAT_MEMORY.setdefault(history_key, [])
#     settings = get_agent_settings_for_chat(tenant_id)
#     intent = detect_intent(message)

#     if message == WELCOME_MESSAGE_KEY:
#         welcome_query = "company overview business introduction services products what company does about company"
#         try:
#             welcome_results = search_faiss(welcome_query, tenant_id=tenant_id, top_k=5)
#             welcome_context = build_context(filter_by_score(welcome_results, min_score=0.20), max_chars=1800)
#         except Exception as exc:
#             print("[WELCOME FAISS ERROR]", repr(exc))
#             welcome_context = ""
#         answer = build_first_welcome_message(settings, welcome_context)
#         answer = f"{answer}\n\nPlease share your name to start the chat."
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             "tenant_name": settings.get("tenant_name"),
#             "business_name": settings.get("business_name"),
#             **empty_assets(),
#             "history_count": len(history),
#             "debug": {"tenant_id": tenant_id, "welcome_only": True, "intent": "welcome", "welcome_context_found": bool(welcome_context)},
#         }

#     # English-first + name capture: do not send Hindi just because the customer name is Indian.
#     if user_requests_english(message):
#         answer = "Sure, I’ll continue in English. How can I help you today?"
#         save_history(history_key, history, message, answer)
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             **empty_assets(),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {"tenant_id": tenant_id, "intent": "language_preference", "english_first": True},
#         }

#     if is_likely_customer_name(message) and len(history) <= 2:
#         customer_name = message.strip().split()[0].strip(".,!")
#         answer = f"Hello {customer_name}, how can I help you today?"
#         save_history(history_key, history, message, answer)
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             **empty_assets(),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {"tenant_id": tenant_id, "intent": "customer_name", "english_first": True},
#         }

#     # Contact requests should never trigger product images or hallucinated LLM answers.
#     if intent == "contact_request":
#         answer = build_contact_reply(settings)
#         save_history(history_key, history, message, answer)
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             **empty_assets(),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {"tenant_id": tenant_id, "intent": intent, "routed_without_faiss": True},
#         }

#     # Recommendation requests should avoid guessing and first collect required use-case details.
#     if intent == "recommendation_request":
#         answer = build_recommendation_question(settings, message)
#         save_history(history_key, history, message, answer)
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             **empty_assets(),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {"tenant_id": tenant_id, "intent": intent, "routed_without_guessing": True},
#         }

#     results = []
#     context = ""
#     assets = empty_assets()

#     try:
#         search_message = message

#         # Human behavior: "show more images" should continue previous product image request.
#         if intent == "image_request" and not is_random_image_request(message):
#             terms_now = extract_product_terms(message)
#             generic_terms = {"pipe", "pipes", "image", "images", "photo", "photos", "more", "single", "clear", "product", "page"}
#             meaningful_terms = [t for t in terms_now if t not in generic_terms]
#             if len(meaningful_terms) == 0:
#                 previous_terms = last_image_terms_from_history(history)
#                 if previous_terms:
#                     search_message = f"{message} {previous_terms}"

#         # When customer asks what information we have, search broad business/product overview.
#         if re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
#             search_message = "company overview products services business information contact service areas"

#         results = run_faiss_search(search_message, tenant_id=tenant_id, top_k=max(top_k, 6))

#         if intent == "image_request" and not is_random_image_request(message):
#             results = filter_results_by_message(results, search_message)

#         context = build_context(results)
#     except FileNotFoundError:
#         print("[FAISS ERROR] Index missing for tenant:", tenant_id)
#         raise
#     except Exception as exc:
#         print("[FAISS SEARCH ERROR]", repr(exc))
#         results = []
#         context = ""

#     if intent == "image_request":
#         # First collect strict/ranked assets. If too few, expand to product-page/catalogue chunks.
#         ranked_results = rank_results_for_images(results, search_message, history)
#         assets = collect_assets_from_results(ranked_results, max_images=8, max_links=10)

#         if len(assets.get("images") or []) < 3:
#             try:
#                 label = clean_image_label(search_message, history)
#                 expanded_queries = [
#                     f"{label} product page images catalogue",
#                     f"{label} pipe fitting product images",
#                     "product page pipe fitting images catalogue",
#                 ]
#                 expanded = []
#                 for q in expanded_queries:
#                     expanded.extend(run_faiss_search(q, tenant_id=tenant_id, top_k=10))
#                 expanded = rank_results_for_images(_unique_keep_order(expanded), search_message, history)
#                 expanded_assets = collect_assets_from_results(expanded, max_images=8, max_links=10)
#                 if len(expanded_assets.get("images") or []) > len(assets.get("images") or []):
#                     assets = expanded_assets
#                     results = expanded
#             except Exception as exc:
#                 print("[EXPANDED IMAGE SEARCH ERROR]", repr(exc))

#         if assets.get("images"):
#             if is_random_image_request(message):
#                 answer = "Sure, I’m sharing a few available product images from our trained data."
#             elif contains_product_page_intent(message):
#                 answer = "Yes, I found more product-page images. Here are the available ones I can show you."
#             else:
#                 label = clean_image_label(search_message, history)
#                 answer = f"Sure, here are the matching {label} images I found."
#         else:
#             team = human_team_phrase(settings)
#             if is_random_image_request(message):
#                 answer = f"I don’t have any usable product images saved in the trained data right now. I can check this with the {team}."
#             else:
#                 answer = f"I couldn’t find a clear matching image for that exact item. I can still check this with the {team}."
#         save_history(history_key, history, message, answer)
#         return {
#             "answer": answer,
#             "session_id": session_id,
#             "images": assets.get("images", []),
#             "links": assets.get("links", []),
#             "sources": assets.get("sources", []),
#             "images_count": assets.get("images_count", 0),
#             "links_count": assets.get("links_count", 0),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {"tenant_id": tenant_id, "intent": intent, "faiss_results": len(results), "context_found": bool(context), "top_score": results[0].get("score") if results else None},
#         }

#     if is_selling_confirmation_question(message) and any(x in message.lower() for x in ["copper", "abs", "pvc", "cast iron"]):
#         answer = build_product_boundary_reply(message, context, settings)
#     elif re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
#         answer = build_knowledge_summary_from_context(context, settings)
#     elif len(history) == 0 and is_greeting_only(message):
#         answer = build_first_welcome_message(settings, context)
#     else:
#         try:
#             answer = ask_groq(message, context, history, settings=settings)
#         except Exception as exc:
#             print("[GROQ ERROR]", repr(exc))
#             answer = ""
#         if not answer:
#             answer = fallback_answer(message, settings)

#     save_history(history_key, history, message, answer)
#     return {
#         "answer": answer,
#         "session_id": session_id,
#         **empty_assets(),
#         "history_count": len(CHAT_MEMORY[history_key]),
#         "debug": {
#             "tenant_id": tenant_id,
#             "intent": intent,
#             "faiss_results": len(results),
#             "context_found": bool(context),
#             "context_length": len(context),
#             "top_score": results[0].get("score") if results else None,
#             "top_text_len": len(get_text_from_result(results[0])) if results else 0,
#         },
#     }

import os
import json
from typing import Dict, List
import re
import requests

from app.db import get_main_db_connection
from app.index_builder import search_faiss

CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
WELCOME_MESSAGE_KEY = "__welcome__"
MIN_FAISS_SCORE = float(os.getenv("MIN_FAISS_SCORE", "0.35"))

DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
- Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
- If trained context is missing or not enough, give a safe, generic, human reply.
- For unknown business-specific details, politely say you will check with the team.
- Keep replies short, clear, and helpful."""

CONTACT_COLUMNS = [
    "website_url", "website", "client_domain", "business_website",
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
        "any pipe image", "whatever image", "just show",
    ]
    return any(word in value for word in random_words)


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
        "elbow", "tee", "coupler", "connector", "fitting", "fittings", "pipe", "pipes",
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
    terms = extract_product_terms(message)
    if history and len([t for t in terms if t not in {"pipe", "pipes", "image", "images", "photo", "photos", "more", "single", "clear"}]) == 0:
        previous = last_image_terms_from_history(history)
        terms = extract_product_terms(previous) or terms

    def score(item: Dict) -> int:
        haystack = " ".join([
            get_text_from_result(item),
            str(item.get("title") or ""),
            str(item.get("url") or ""),
            str(item.get("file_name") or ""),
            " ".join(item.get("images") or []),
            " ".join(item.get("links") or []),
        ]).lower()
        s = 0
        for t in terms:
            if t and t in haystack:
                s += 3 if t in {"stainless steel", "cast iron", "abs", "pvc", "elbow", "tee", "coupler"} else 1
        if item.get("images"):
            s += 5
        if "product" in haystack or "pipe" in haystack or "fitting" in haystack:
            s += 2
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

    # Require important material/product terms when user asked for them.
    important = [t for t in terms if t in {"cast iron", "stainless steel", "abs", "pvc", "ss"}]
    if important and not any(t in haystack for t in important):
        return False

    # Generic pipe/fitting terms are enough when no specific material is present.
    return any(t in haystack for t in terms)


def filter_results_by_message(results: List[Dict], message: str) -> List[Dict]:
    terms = extract_product_terms(message)
    filtered = [item for item in (results or []) if result_matches_terms(item, terms)]
    return filtered


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


def collect_assets_from_results(results: List[Dict], max_images: int = 6, max_links: int = 6) -> Dict:
    image_urls = []
    link_urls = []
    sources = []

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


def get_agent_settings_for_chat(tenant_id) -> Dict:
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
                for col in ["business_name", "greeting_message", "system_prompt", "restriction_rules", "support_hours"]:
                    if col in settings_cols:
                        settings_selects.append(f"tas.{col}")
                    else:
                        settings_selects.append(f"NULL AS {col}")

                sql = f"""
                    SELECT
                        {", ".join(settings_selects)},
                        {", ".join(tenant_selects)}
                    FROM tenants t
                    LEFT JOIN tenant_agent_settings tas ON tas.tenant_id = t.id
                    WHERE t.id=%s
                    LIMIT 1
                """
                cur.execute(sql, (tenant_id,))
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
        "system_prompt": system_prompt,
        "restriction_rules": restriction_rules,
        "support_hours": _json_load(row.get("support_hours"), default={}) or {},
        "contact": contact,
    }


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
    settings = settings or {}
    team = human_team_phrase(settings)
    if detect_intent(message) == "image_request":
        return f"I could not find clearly matching images for that in the trained data. I can check this with the {team}."
    if detect_intent(message) == "contact_request":
        return f"I do not have confirmed contact details saved here. I can connect you with the {team}."
    return f"I’ll check this with the {team} and get back to you."


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

    website = contact.get("website_url") or contact.get("website") or contact.get("client_domain") or contact.get("business_website") or extra_website
    phone = contact.get("support_phone") or contact.get("phone") or contact.get("mobile") or contact.get("whatsapp_number")
    email = contact.get("support_email") or contact.get("email") or contact.get("business_email")
    address = contact.get("address")

    def missing(field: str) -> str:
        return f"I don’t have a confirmed {field} saved here yet. I can connect you with the {human_team_phrase(settings)}."

    if request_type == "website":
        return f"Sure, the website for {business_name} is: {normalize_url(str(website))}" if website else missing("website")
    if request_type == "phone":
        return f"Sure, the customer care number for {business_name} is: {phone}" if phone else missing("phone number")
    if request_type == "email":
        return f"Sure, the email for {business_name} is: {email}" if email else missing("email")
    if request_type == "address":
        return f"Sure, the address for {business_name} is: {address}" if address else missing("address")

    lines = [f"Sure, here are the available contact details for {business_name}:"]
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


def build_recommendation_question(settings: Dict, message: str, history: List[Dict[str, str]] = None, context: str = "") -> str:
    value = (message or "").lower()
    team = human_team_phrase(settings)

    if is_out_of_scope_service(message):
        return f"I’m sorry about that. We mainly help with our pipe and fitting product information here. For door or non-plumbing maintenance, I’d suggest checking with the right repair professional."

    if is_pipe_problem_request(message):
        return f"Sorry to hear that. It sounds like there may be an issue with the bathroom pipe connection. I can help connect you with the {team} for the right guidance."

    if "bathroom sink" in value or "sink" in value:
        return (
            "For a bathroom sink, you’ll usually be looking at compact stainless steel pipe/fitting parts such as connector pipes, elbows, couplers, or drain-related fittings.\n\n"
            "To suggest the best one, please tell me: is it for water supply connection or drainage under the sink?"
        )

    if "given image" in value or "given images" in value or "these images" in value:
        return (
            "From the images, I can guide you by use-case rather than guessing the exact part name.\n"
            "For bathroom or wet-area fitting, stainless steel pipe/fitting parts are usually preferred because they resist corrosion.\n\n"
            "Please tell me whether it is for sink water inlet, outlet/drainage, or a bend/turn connection."
        )

    return (
        "Sure — I can guide you. Just tell me 2 things first:\n"
        "1. Is it for water supply, drainage, gas, or another use?\n"
        "2. Is the fitting indoor or outdoor?\n\n"
        "Then I’ll suggest the most suitable option from what we have."
    )


def build_terminology_reply(settings: Dict, message: str, history: List[Dict[str, str]] = None) -> str:
    value = (message or "").lower()
    if "sink" in value or any("sink" in (h.get("content", "").lower()) for h in (history or [])[-8:]):
        return (
            "No problem — for a bathroom sink, people usually ask for parts like:\n"
            "• sink connector pipe\n"
            "• elbow fitting\n"
            "• coupler/connector\n"
            "• drain or outlet fitting\n\n"
            "If you can share which side it connects to — water inlet or drainage — I can guide you better."
        )
    return (
        "No problem — those parts are generally called pipe fittings. Common names include elbow, tee, coupler, connector, reducer, and pipe socket.\n\n"
        "Tell me where it will be used and I’ll help identify the closest name."
    )


def build_safe_service_reply(settings: Dict, message: str, context: str = "") -> str:
    value = (message or "").lower()
    team = human_team_phrase(settings)
    if is_out_of_scope_service(message):
        return "I’m sorry about that. We mainly help with pipe and fitting product information here, so I can’t confirm door or non-plumbing maintenance from the saved business details."
    if "timing" in value or "open" in value or "store" in value:
        return f"I don’t have confirmed store timings saved here yet. I can connect you with the {team} for the exact timing."
    if "area" in value or "agra" in value or "location" in value:
        return f"I don’t have confirmed service-area details saved here yet. I can connect you with the {team} for the exact location coverage."
    if "service" in value or "installation" in value or "maintenance" in value or "repair" in value:
        return f"We mainly have confirmed information about our pipes and fittings. For installation, repair, or on-site service, I can connect you with the {team} to confirm availability."
    return f"I can check this with the {team} and guide you."


def build_first_welcome_message(settings: Dict, context: str) -> str:
    tenant_name = get_display_business_name(settings)

    def make_smart_business_intro(context_text: str) -> str:
        text = (context_text or "").replace("\n", " ").strip()
        if not text:
            return "We can help you with product details, fittings, images, specifications, and support."
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        if not api_key:
            return "We can help you with product details, fittings, images, specifications, and support."
        prompt = f"""
Create a short and professional company introduction.

Your task:
- Explain clearly what the company does.
- Keep it simple and human.
- Maximum 2 short lines.
- Do NOT list product names one by one.
- Do NOT copy raw catalogue text.
- Do NOT mention charity/social work unless the user asks about it.
- Do NOT mention random features unless they are central to the business.
- Return a complete sentence only.

Business context:
{text}

Return ONLY the company introduction.
""".strip()
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You create clean business introductions from raw website content."},
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
            intro = re.sub(r"\s+", " ", intro).strip()
            return trim_to_complete_sentence(intro, max_chars=260) or "We can help you with product details, fittings, images, specifications, and support."
        except Exception as exc:
            print("[SMART INTRO ERROR]", repr(exc))
            return "We can help you with product details, fittings, images, specifications, and support."

    business_intro = make_smart_business_intro(context)
    return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

{business_intro}"""


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
                {"role": "system", "content": f"You are a safe WhatsApp business assistant for {business_name}. Never expose internal tenant names or IDs. Use trained context and never invent business facts."},
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


def save_history(history_key: str, history: List[Dict[str, str]], message: str, answer: str):
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    CHAT_MEMORY[history_key] = history[-20:]


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
    session_id = session_id or "default"
    message = (message or "").strip()
    history_key = f"{tenant_id}:{session_id}"
    history = CHAT_MEMORY.setdefault(history_key, [])
    settings = get_agent_settings_for_chat(tenant_id)
    intent = detect_intent(message)

    if message == WELCOME_MESSAGE_KEY:
        welcome_query = "company overview business introduction services products what company does about company"
        try:
            welcome_results = search_faiss(welcome_query, tenant_id=tenant_id, top_k=5)
            welcome_context = build_context(filter_by_score(welcome_results, min_score=0.20), max_chars=1800)
        except Exception as exc:
            print("[WELCOME FAISS ERROR]", repr(exc))
            welcome_context = ""
        answer = build_first_welcome_message(settings, welcome_context)
        answer = f"{answer}\n\nPlease share your name to start the chat."
        return {
            "answer": answer,
            "session_id": session_id,
            "tenant_name": settings.get("tenant_name"),
            "business_name": settings.get("business_name"),
            **empty_assets(),
            "history_count": len(history),
            "debug": {"tenant_id": tenant_id, "welcome_only": True, "intent": "welcome", "welcome_context_found": bool(welcome_context)},
        }

    # English-first + name capture: do not send Hindi just because the customer name is Indian.
    if user_requests_english(message):
        answer = "Sure, I’ll continue in English. How can I help you today?"
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": "language_preference", "english_first": True},
        }

    if is_likely_customer_name(message) and len(history) <= 2:
        customer_name = message.strip().split()[0].strip(".,!")
        answer = f"Hello {customer_name}, how can I help you today?"
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": "customer_name", "english_first": True},
        }

    # Contact requests should never trigger product images or hallucinated LLM answers.
    if intent == "contact_request":
        req_type = contact_request_type(message) or "all"
        extra_website = ""
        if req_type == "website":
            try:
                web_results = run_faiss_search("official website homepage contact about company", tenant_id=tenant_id, top_k=8)
                extra_website = extract_website_from_results(web_results)
            except Exception as exc:
                print("[CONTACT WEBSITE FALLBACK ERROR]", repr(exc))
        answer = build_contact_reply(settings, request_type=req_type, extra_website=extra_website)
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": intent, "contact_type": req_type, "routed_without_faiss": True},
        }

    if intent == "terminology_request":
        answer = build_terminology_reply(settings, message, history)
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": intent, "routed_without_guessing": True},
        }

    if intent == "service_request":
        answer = build_safe_service_reply(settings, message)
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": intent, "service_safe": True},
        }

    # Recommendation requests should avoid guessing and first collect required use-case details.
    if intent == "recommendation_request":
        answer = build_recommendation_question(settings, message, history)
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            **empty_assets(),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": intent, "routed_without_guessing": True},
        }

    results = []
    context = ""
    assets = empty_assets()

    try:
        search_message = message

        # Human behavior: "show more images" should continue previous product image request.
        if intent == "image_request" and not is_random_image_request(message):
            terms_now = extract_product_terms(message)
            generic_terms = {"pipe", "pipes", "image", "images", "photo", "photos", "more", "single", "clear", "product", "page"}
            meaningful_terms = [t for t in terms_now if t not in generic_terms]
            if len(meaningful_terms) == 0:
                previous_terms = last_image_terms_from_history(history)
                if previous_terms:
                    search_message = f"{message} {previous_terms}"

        # When customer asks what information we have, search broad business/product overview.
        if re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
            search_message = "company overview products services business information contact service areas"

        results = run_faiss_search(search_message, tenant_id=tenant_id, top_k=max(top_k, 6))

        if intent == "image_request" and not is_random_image_request(message):
            results = filter_results_by_message(results, search_message)

        context = build_context(results)
    except FileNotFoundError:
        print("[FAISS ERROR] Index missing for tenant:", tenant_id)
        raise
    except Exception as exc:
        print("[FAISS SEARCH ERROR]", repr(exc))
        results = []
        context = ""

    if intent == "image_request":
        # First collect strict/ranked assets. If too few, expand to product-page/catalogue chunks.
        ranked_results = rank_results_for_images(results, search_message, history)
        assets = collect_assets_from_results(ranked_results, max_images=8, max_links=10)

        if len(assets.get("images") or []) < 3:
            try:
                label = clean_image_label(search_message, history)
                expanded_queries = [
                    f"{label} product page images catalogue",
                    f"{label} pipe fitting product images",
                    "product page pipe fitting images catalogue",
                ]
                expanded = []
                for q in expanded_queries:
                    expanded.extend(run_faiss_search(q, tenant_id=tenant_id, top_k=10))
                expanded = rank_results_for_images(_unique_keep_order(expanded), search_message, history)
                expanded_assets = collect_assets_from_results(expanded, max_images=8, max_links=10)
                if len(expanded_assets.get("images") or []) > len(assets.get("images") or []):
                    assets = expanded_assets
                    results = expanded
            except Exception as exc:
                print("[EXPANDED IMAGE SEARCH ERROR]", repr(exc))

        if assets.get("images"):
            if is_random_image_request(message):
                answer = "Sure, I’m sharing a few available product images from our trained data."
            elif contains_product_page_intent(message):
                answer = "Yes, I found more product-page images. Here are the available ones I can show you."
            else:
                label = clean_image_label(search_message, history)
                if wants_single_or_clear_image(message):
                    answer = f"Sure, I’m sharing clearer {label} image options from the product data."
                else:
                    answer = f"Sure, here are the matching {label} images I found."
        else:
            team = human_team_phrase(settings)
            if is_random_image_request(message):
                answer = f"I don’t have any usable product images saved in the trained data right now. I can check this with the {team}."
            else:
                answer = f"I couldn’t find a clear matching image for that exact item. I can still check this with the {team}."
        save_history(history_key, history, message, answer)
        return {
            "answer": answer,
            "session_id": session_id,
            "images": assets.get("images", []),
            "links": assets.get("links", []),
            "sources": assets.get("sources", []),
            "images_count": assets.get("images_count", 0),
            "links_count": assets.get("links_count", 0),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {"tenant_id": tenant_id, "intent": intent, "faiss_results": len(results), "context_found": bool(context), "top_score": results[0].get("score") if results else None},
        }

    if is_selling_confirmation_question(message) and any(x in message.lower() for x in ["copper", "abs", "pvc", "cast iron"]):
        answer = build_product_boundary_reply(message, context, settings)
    elif re.search(r"\b(what information|what do you know|what you know|what details)\b", message.lower()):
        answer = build_knowledge_summary_from_context(context, settings)
    elif len(history) == 0 and is_greeting_only(message):
        answer = build_first_welcome_message(settings, context)
    else:
        try:
            answer = ask_groq(message, context, history, settings=settings)
        except Exception as exc:
            print("[GROQ ERROR]", repr(exc))
            answer = ""
        if not answer:
            answer = fallback_answer(message, settings)

    save_history(history_key, history, message, answer)
    return {
        "answer": answer,
        "session_id": session_id,
        **empty_assets(),
        "history_count": len(CHAT_MEMORY[history_key]),
        "debug": {
            "tenant_id": tenant_id,
            "intent": intent,
            "faiss_results": len(results),
            "context_found": bool(context),
            "context_length": len(context),
            "top_score": results[0].get("score") if results else None,
            "top_text_len": len(get_text_from_result(results[0])) if results else 0,
        },
    }
