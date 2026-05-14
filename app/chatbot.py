# # import os
# # import json
# # from typing import Dict, List

# # import requests

# # from app.db import get_main_db_connection
# # from app.index_builder import search_faiss

# # CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


# # DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
# # - Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
# # - If trained context is missing or not enough, give a safe, generic, human reply.
# # - For unknown business-specific details, say: I will connect you with our team.
# # - Keep replies short, clear, and helpful."""


# # def get_text_from_result(item: Dict) -> str:
# #     if not isinstance(item, dict):
# #         return ""

# #     return (
# #         item.get("text")
# #         or item.get("chunk_text")
# #         or item.get("content")
# #         or item.get("page_content")
# #         or item.get("body")
# #         or item.get("description")
# #         or ""
# #     ).strip()

# # def _unique_keep_order(values):
# #     seen = set()
# #     output = []
# #     for value in values or []:
# #         key = str(value or "").strip()
# #         if not key or key in seen:
# #             continue
# #         seen.add(key)
# #         output.append(key)
# #     return output


# # def is_image_or_link_request(message: str) -> bool:
# #     """
# #     Return images/links only when the customer asks for visuals, photos, catalogue,
# #     product page/link, etc. This keeps normal chat responses unchanged.
# #     """
# #     value = (message or "").lower()
# #     keywords = [
# #         "image", "photo", "picture", "pic", "show", "see", "visual",
# #         "catalog", "catalogue", "brochure", "product page", "link", "url",
# #         "pipe image", "fitting image",
# #     ]
# #     return any(keyword in value for keyword in keywords)


# # def collect_assets_from_results(results: List[Dict], max_images: int = 6, max_links: int = 6) -> Dict:
# #     image_urls = []
# #     link_urls = []
# #     sources = []

# #     for item in results or []:
# #         image_urls.extend(item.get("images") or [])
# #         link_urls.extend(item.get("links") or [])

# #         source = item.get("url") or item.get("file_name") or item.get("title")
# #         if source:
# #             sources.append(source)

# #     images = _unique_keep_order(image_urls)[:max_images]
# #     links = _unique_keep_order(link_urls)[:max_links]
# #     sources = _unique_keep_order(sources)[:max_links]

# #     return {
# #         "images": images,
# #         "links": links,
# #         "sources": sources,
# #         "images_count": len(images),
# #         "links_count": len(links),
# #     }



# # def _json_load(value, default=None):
# #     if value is None:
# #         return default
# #     if isinstance(value, (dict, list)):
# #         return value
# #     try:
# #         return json.loads(value)
# #     except Exception:
# #         return default


# # def get_agent_settings_for_chat(tenant_id) -> Dict:
# #     try:
# #         conn = get_main_db_connection()
# #         try:
# #             with conn.cursor() as cur:
# #                 cur.execute(
# #                     """
# #                     SELECT
# #                         tas.business_name,
# #                         tas.greeting_message,
# #                         tas.system_prompt,
# #                         tas.restriction_rules,
# #                         tas.support_hours,
# #                         t.tenant_name
# #                     FROM tenants t
# #                     LEFT JOIN tenant_agent_settings tas ON tas.tenant_id = t.id
# #                     WHERE t.id=%s
# #                     LIMIT 1
# #                     """,
# #                     (tenant_id,),
# #                 )
# #                 row = cur.fetchone() or {}
# #         finally:
# #             conn.close()
# #     except Exception as exc:
# #         print("[CHAT SETTINGS ERROR]", repr(exc))
# #         row = {}

# #     tenant_name = row.get("tenant_name") or row.get("business_name") or "this business"
# #     business_name = row.get("business_name") or tenant_name
# #     system_prompt = (row.get("system_prompt") or "").strip()
# #     restriction_rules = (row.get("restriction_rules") or "").strip()

# #     if not system_prompt:
# #         system_prompt = f"""You are a helpful business assistant for {business_name}.
# # Reply naturally like a real human assistant.
# # Use trained knowledge when available.
# # If trained knowledge is not enough, do not invent details."""

# #     if not restriction_rules:
# #         restriction_rules = DEFAULT_RESTRICTION_RULES

# #     return {
# #         "tenant_name": tenant_name,
# #         "business_name": business_name,
# #         "system_prompt": system_prompt,
# #         "restriction_rules": restriction_rules,
# #         "support_hours": _json_load(row.get("support_hours"), default={}) or {},
# #     }


# # def build_context(results: List[Dict], max_chars: int = 1200) -> str:
# #     parts = []
# #     total = 0

# #     for i, item in enumerate(results, start=1):
# #         source = item.get("url") or item.get("file_name") or item.get("title") or "trained data"
# #         text = get_text_from_result(item)

# #         if not text:
# #             print("[CONTEXT SKIP] result has no text. keys:", list(item.keys()))
# #             continue

# #         block = f"[Source {i}: {source}]\n{text}"

# #         if total + len(block) > max_chars:
# #             remaining = max_chars - total
# #             if remaining > 150:
# #                 parts.append(block[:remaining])
# #             break

# #         parts.append(block)
# #         total += len(block)

# #     context = "\n\n".join(parts)
# #     print("[CONTEXT BUILD] parts:", len(parts))
# #     print("[CONTEXT BUILD] length:", len(context))
# #     print("[CONTEXT BUILD] sample:", context[:300])
# #     return context


# # def clean_ai_reply(reply: str) -> str:
# #     if not reply:
# #         return "I will connect you with our team."

# #     cleaned = reply.strip()

# #     remove_phrases = [
# #         "According to the provided context,",
# #         "Based on the provided context,",
# #         "Based on the context,",
# #         "According to the context,",
# #         "From the context,",
# #         "According to the document,",
# #         "Based on the document,",
# #         "The context says",
# #         "The provided information says",
# #     ]

# #     for phrase in remove_phrases:
# #         cleaned = cleaned.replace(phrase, "").strip()

# #     return cleaned or "I will connect you with our team."


# # def fallback_answer() -> str:
# #     return "I will connect you with our team."


# # def build_first_welcome_message(settings: Dict, context: str) -> str:
# #     tenant_name = (
# #         settings.get("tenant_name")
# #         or settings.get("business_name")
# #         or "our company"
# #     )

# #     has_context = bool((context or "").strip())

# #     if has_context:
# #         return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# # I'm here to help you with any questions about our products, services, or support.

# # What brings you in today? Are you looking for a particular product, or do you have a question about something?"""

# #     return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# # I'm here to help you with any questions about our products or services.

# # What brings you in today?"""


# # def ask_groq(
# #     question: str,
# #     context: str,
# #     history: List[Dict[str, str]],
# #     settings: Dict = None,
# # ) -> str:
# #     api_key = os.getenv("GROQ_API_KEY", "").strip()
# #     model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

# #     print("[GROQ] key_exists:", bool(api_key))
# #     print("[GROQ] key_prefix:", api_key[:10] if api_key else "MISSING")
# #     print("[GROQ] model:", model)

# #     if not api_key:
# #         return ""

# #     settings = settings or {}
# #     business_name = settings.get("business_name") or "this business"
# #     system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
# #     restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES

# #     conversation = "\n".join(
# #         [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]
# #     )

# #     has_context = bool((context or "").strip())

# #     if has_context:
# #         context_instruction = """
# # You have trained knowledge context below.
# # Use it to answer the customer.
# # If the exact answer is not available in the context, do not invent.
# # Say naturally: "I will connect you with our team."
# # """.strip()
# #     else:
# #         context_instruction = """
# # No trained knowledge context was found for this question.
# # You may still reply like a human assistant, but ONLY with safe generic help.
# # Allowed:
# # - greet the customer
# # - ask what they need
# # - say you can connect them with the team
# # - ask for clarification
# # Not allowed:
# # - invent services, pricing, address, phone number, offers, guarantees, timings, or company facts
# # For any business-specific question, reply naturally:
# # "I will connect you with our team."
# # """.strip()

# #     prompt = f"""
# # You are a professional WhatsApp business assistant for {business_name}.
# # {system_prompt}

# # Your job is to reply like a real human on WhatsApp.

# # Language rules:
# # - Default reply language is English.
# # - If the user clearly writes in Hindi, reply in Hindi.
# # - If the user writes in Hinglish, reply in Hinglish.
# # - If the user writes in English, reply in English.
# # - If the user message is mixed, follow the user's dominant language.

# # Safety rules:
# # - Do not hallucinate.
# # - Do not invent business facts.
# # - Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
# # - If unsure, say you will connect the customer with the team.
# # - Keep reply short: 1 to 4 lines.
# # - Sound warm, natural, and helpful.
# # - Do not say "based on the context".
# # - Do not show sources, file names, URLs, or internal details.

# # DEFAULT_RESTRICTION_RULES
# # - Answer using trained knowledge base when available.
# # - Do not invent prices, offers, phone numbers, addresses, guarantees.
# # - If trained context is missing or not enough, give a safe, generic, human reply.
# # - For unknown business-specific details, say: I will connect you with our team.
# # - Keep replies short, clear, and helpful.

# # - Blog articles, educational content, comparisons, and guides
# #   do NOT mean the company sells those products.

# # - Only confirm products/services that are clearly present
# #   in product pages, catalog pages, or official company offerings.

# # - If unsure whether a product is sold by the company,
# #   say:
# #   "I could not confirm that this product is offered by the company."

# # Tenant restriction rules:
# # {restriction_rules}

# # Context handling:
# # {context_instruction}

# # Trained context:
# # {context if has_context else "[NO MATCHING TRAINED CONTEXT FOUND]"}

# # Conversation history:
# # {conversation if conversation else "[NO PREVIOUS HISTORY]"}

# # Customer message:
# # {question}

# # Write the best short WhatsApp reply.
# # """.strip()

# #     messages = [
# #         {
# #             "role": "system",
# #             "content": (
# #                 "You are a safe WhatsApp business assistant. "
# #                 "Use trained context when available. "
# #                 "When context is missing, give only safe generic replies and never invent business facts."
# #             ),
# #         },
# #         {
# #             "role": "user",
# #             "content": prompt,
# #         },
# #     ]

# #     response = requests.post(
# #         "https://api.groq.com/openai/v1/chat/completions",
# #         headers={
# #             "Authorization": f"Bearer {api_key}",
# #             "Content-Type": "application/json",
# #         },
# #         json={
# #             "model": model,
# #             "messages": messages,
# #             "temperature": 0.2,
# #             "max_tokens": 140,
# #         },
# #         timeout=20,
# #     )

# #     if response.status_code >= 400:
# #         print("[GROQ HTTP ERROR]", response.status_code, response.text[:500])

# #     response.raise_for_status()
# #     data = response.json()

# #     usage = data.get("usage", {})
# #     print("\n========== GROQ TOKEN USAGE ==========")
# #     print("Prompt/Input Tokens :", usage.get("prompt_tokens", 0))
# #     print("Completion Tokens   :", usage.get("completion_tokens", 0))
# #     print("Total Tokens        :", usage.get("total_tokens", 0))
# #     print("======================================\n")

# #     reply = (
# #         data.get("choices", [{}])[0]
# #         .get("message", {})
# #         .get("content", "")
# #     )

# #     return clean_ai_reply(reply)


# # def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
# #     session_id = session_id or "default"
# #     message = (message or "").strip()

# #     history_key = f"{tenant_id}:{session_id}"
# #     history = CHAT_MEMORY.setdefault(history_key, [])

# #     results = []
# #     context = ""

# #     try:
# #         results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)

# #         print("==== FAISS RESULT TEXT CHECK ====")
# #         for i, r in enumerate(results):
# #             text = get_text_from_result(r)
# #             print("RESULT", i)
# #             print("KEYS:", list(r.keys()))
# #             print("TEXT LEN:", len(text))
# #             print("TEXT SAMPLE:", text[:300])
# #         print("=================================")

# #         context = build_context(results)

# #     except FileNotFoundError:
# #         print("[FAISS ERROR] Index missing for tenant:", tenant_id)
# #         raise
# #     except Exception as exc:
# #         print("[FAISS SEARCH ERROR]", repr(exc))
# #         results = []
# #         context = ""

# #     settings = get_agent_settings_for_chat(tenant_id)

# #     is_first_message = len(history) == 0

# #     if is_first_message:
# #         answer = build_first_welcome_message(settings, context)

# #         history.append({"role": "user", "content": message})
# #         history.append({"role": "assistant", "content": answer})
# #         CHAT_MEMORY[history_key] = history[-20:]

# #         assets = collect_assets_from_results(results) if is_image_or_link_request(message) else {"images": [], "links": [], "sources": [], "images_count": 0, "links_count": 0}

# #         return {
# #             "answer": answer,
# #             "session_id": session_id,
# #             "images": assets.get("images", []),
# #             "links": assets.get("links", []),
# #             "sources": assets.get("sources", []),
# #             "images_count": assets.get("images_count", 0),
# #             "links_count": assets.get("links_count", 0),
# #             "history_count": len(CHAT_MEMORY[history_key]),
# #             "debug": {
# #                 "tenant_id": tenant_id,
# #                 "faiss_results": len(results),
# #                 "context_found": bool(context),
# #                 "context_length": len(context),
# #                 "first_message": True,
# #                 "top_score": results[0].get("score") if results else None,
# #                 "top_text_len": len(get_text_from_result(results[0])) if results else 0,
# #             },
# #         }

# #     print("========== CHAT DEBUG ==========")
# #     print("TENANT ID:", tenant_id)
# #     print("SESSION ID:", session_id)
# #     print("MESSAGE:", message)
# #     print("FAISS RESULTS:", len(results))
# #     print("TOP SCORE:", results[0].get("score") if results else None)
# #     print("CONTEXT LENGTH:", len(context))
# #     print("GROQ KEY EXISTS:", bool(os.getenv("GROQ_API_KEY", "").strip()))
# #     print("================================")

# #     answer = ""

# #     try:
# #         answer = ask_groq(message, context, history, settings=settings)
# #     except Exception as exc:
# #         print("[GROQ ERROR]", repr(exc))
# #         answer = ""

# #     if not answer:
# #         answer = fallback_answer()

# #     history.append({"role": "user", "content": message})
# #     history.append({"role": "assistant", "content": answer})
# #     CHAT_MEMORY[history_key] = history[-20:]

# #     assets = collect_assets_from_results(results) if is_image_or_link_request(message) else {"images": [], "links": [], "sources": [], "images_count": 0, "links_count": 0}

# #     # If customer clearly asks for an image/link and matching metadata exists, keep the text short.
# #     if is_image_or_link_request(message) and assets.get("images") and answer == fallback_answer():
# #         answer = "Sure, here are the matching images I found."

# #     return {
# #         "answer": answer,
# #         "session_id": session_id,
# #         "images": assets.get("images", []),
# #         "links": assets.get("links", []),
# #         "sources": assets.get("sources", []),
# #         "images_count": assets.get("images_count", 0),
# #         "links_count": assets.get("links_count", 0),
# #         "history_count": len(CHAT_MEMORY[history_key]),
# #         "debug": {
# #             "tenant_id": tenant_id,
# #             "faiss_results": len(results),
# #             "context_found": bool(context),
# #             "context_length": len(context),
# #             "top_score": results[0].get("score") if results else None,
# #             "top_text_len": len(get_text_from_result(results[0])) if results else 0,
# #         },
# #     }

# import os
# import json
# from typing import Dict, List

# import requests

# from app.db import get_main_db_connection
# from app.index_builder import search_faiss

# CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


# DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
# - Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
# - If trained context is missing or not enough, give a safe, generic, human reply.
# - For unknown business-specific details, politely say you will check with the team.
# - Keep replies short, clear, and helpful."""


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


# def is_image_or_link_request(message: str) -> bool:
#     value = (message or "").lower()
#     keywords = [
#         "image", "images", "photo", "photos", "picture", "pictures", "pic",
#         "show", "see", "visual", "catalog", "catalogue", "brochure",
#         "product page", "link", "url", "pipe image", "fitting image",
#     ]
#     return any(keyword in value for keyword in keywords)


# def is_greeting_only(message: str) -> bool:
#     value = (message or "").strip().lower()
#     greetings = {
#         "hi", "hii", "hello", "hey", "hey there", "good morning",
#         "good afternoon", "good evening", "namaste", "hola"
#     }
#     return value in greetings


# def is_valid_url(url: str) -> bool:
#     url = (url or "").strip()

#     if not url.startswith(("http://", "https://")):
#         return False

#     try:
#         response = requests.head(url, allow_redirects=True, timeout=5)
#         if response.status_code < 400:
#             return True

#         # Some servers block HEAD, so try GET lightly
#         response = requests.get(url, allow_redirects=True, timeout=5, stream=True)
#         return response.status_code < 400

#     except Exception:
#         return False


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

#     # Remove broken / 404 URLs
#     valid_images = []
#     for url in images:
#         if is_valid_url(url):
#             valid_images.append(url)
#         if len(valid_images) >= max_images:
#             break

#     valid_links = []
#     for url in links:
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


# def _json_load(value, default=None):
#     if value is None:
#         return default
#     if isinstance(value, (dict, list)):
#         return value
#     try:
#         return json.loads(value)
#     except Exception:
#         return default


# def get_agent_settings_for_chat(tenant_id) -> Dict:
#     try:
#         conn = get_main_db_connection()
#         try:
#             with conn.cursor() as cur:
#                 cur.execute(
#                     """
#                     SELECT
#                         tas.business_name,
#                         tas.greeting_message,
#                         tas.system_prompt,
#                         tas.restriction_rules,
#                         tas.support_hours,
#                         t.tenant_name
#                     FROM tenants t
#                     LEFT JOIN tenant_agent_settings tas ON tas.tenant_id = t.id
#                     WHERE t.id=%s
#                     LIMIT 1
#                     """,
#                     (tenant_id,),
#                 )
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

#     return {
#         "tenant_name": tenant_name,
#         "business_name": business_name,
#         "system_prompt": system_prompt,
#         "restriction_rules": restriction_rules,
#         "support_hours": _json_load(row.get("support_hours"), default={}) or {},
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
#         "According to the provided context,",
#         "Based on the provided context,",
#         "Based on the context,",
#         "According to the context,",
#         "From the context,",
#         "According to the document,",
#         "Based on the document,",
#         "The context says",
#         "The provided information says",
#     ]

#     for phrase in remove_phrases:
#         cleaned = cleaned.replace(phrase, "").strip()

#     return cleaned


# def fallback_answer(message: str = "") -> str:
#     if is_image_or_link_request(message):
#         return "Sure, I found these matching product images."
#     return "I’ll check this with our team and get back to you."


# def build_first_welcome_message(settings: Dict, context: str) -> str:
#     tenant_name = (
#         settings.get("tenant_name")
#         or settings.get("business_name")
#         or "our company"
#     )

#     has_context = bool((context or "").strip())

#     if has_context:
#         return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# I'm here to help you with any questions about our products, services, or support.

# What brings you in today? Are you looking for a particular product, or do you have a question about something?"""

#     return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# I'm here to help you with any questions about our products or services.

# What brings you in today?"""


# def ask_groq(
#     question: str,
#     context: str,
#     history: List[Dict[str, str]],
#     settings: Dict = None,
# ) -> str:
#     api_key = os.getenv("GROQ_API_KEY", "").strip()
#     model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

#     print("[GROQ] key_exists:", bool(api_key))
#     print("[GROQ] key_prefix:", api_key[:10] if api_key else "MISSING")
#     print("[GROQ] model:", model)

#     if not api_key:
#         return ""

#     settings = settings or {}
#     business_name = settings.get("business_name") or "this business"
#     system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
#     restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES

#     conversation = "\n".join(
#         [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]
#     )

#     has_context = bool((context or "").strip())

#     if has_context:
#         context_instruction = """
# You have trained knowledge context below.
# Use it to answer the customer.
# If the exact answer is not available in the context, do not invent.
# If useful images or links are already available from metadata, do not say "I will connect you with our team" unnecessarily.
# """.strip()
#     else:
#         context_instruction = """
# No trained knowledge context was found for this question.
# You may still reply like a human assistant, but ONLY with safe generic help.
# Allowed:
# - greet the customer
# - ask what they need
# - say you can check with the team
# - ask for clarification
# Not allowed:
# - invent services, pricing, address, phone number, offers, guarantees, timings, or company facts.
# """.strip()

#     prompt = f"""
# You are a professional WhatsApp business assistant for {business_name}.
# {system_prompt}

# Your job is to reply like a real human on WhatsApp.

# Language rules:
# - Default reply language is English.
# - If the user clearly writes in Hindi, reply in Hindi.
# - If the user writes in Hinglish, reply in Hinglish.
# - If the user writes in English, reply in English.
# - If the user message is mixed, follow the user's dominant language.

# Safety rules:
# - Do not hallucinate.
# - Do not invent business facts.
# - Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
# - For unknown business-specific details, politely say you will check with the team.
# - Do not repeat "I will connect you with our team" when useful images, links, or context are already available.
# - Keep reply short: 1 to 4 lines.
# - Sound warm, natural, and helpful.
# - Do not say "based on the context".
# - Do not show sources, file names, URLs, or internal details.

# Important product rule:
# - Blog articles, educational content, comparisons, and guides do NOT mean the company sells those products.
# - Only confirm products/services that are clearly present in product pages, catalog pages, or official company offerings.
# - If unsure whether a product is sold by the company, say:
#   "I could not confirm that this product is offered by the company."

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

#     messages = [
#         {
#             "role": "system",
#             "content": (
#                 "You are a safe WhatsApp business assistant. "
#                 "Use trained context when available. "
#                 "When context is missing, give only safe generic replies and never invent business facts."
#             ),
#         },
#         {
#             "role": "user",
#             "content": prompt,
#         },
#     ]

#     response = requests.post(
#         "https://api.groq.com/openai/v1/chat/completions",
#         headers={
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json",
#         },
#         json={
#             "model": model,
#             "messages": messages,
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

#     reply = (
#         data.get("choices", [{}])[0]
#         .get("message", {})
#         .get("content", "")
#     )

#     return clean_ai_reply(reply)


# def empty_assets() -> Dict:
#     return {
#         "images": [],
#         "links": [],
#         "sources": [],
#         "images_count": 0,
#         "links_count": 0,
#     }


# def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
#     session_id = session_id or "default"
#     message = (message or "").strip()

#     history_key = f"{tenant_id}:{session_id}"
#     history = CHAT_MEMORY.setdefault(history_key, [])

#     results = []
#     context = ""

#     try:
#         results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)

#         print("==== FAISS RESULT TEXT CHECK ====")
#         for i, r in enumerate(results):
#             text = get_text_from_result(r)
#             print("RESULT", i)
#             print("KEYS:", list(r.keys()))
#             print("TEXT LEN:", len(text))
#             print("TEXT SAMPLE:", text[:300])
#         print("=================================")

#         context = build_context(results)

#     except FileNotFoundError:
#         print("[FAISS ERROR] Index missing for tenant:", tenant_id)
#         raise
#     except Exception as exc:
#         print("[FAISS SEARCH ERROR]", repr(exc))
#         results = []
#         context = ""

#     settings = get_agent_settings_for_chat(tenant_id)

#     is_first_message = len(history) == 0
#     wants_assets = is_image_or_link_request(message)

#     assets = collect_assets_from_results(results) if wants_assets else empty_assets()

#     if is_first_message:
#         if is_greeting_only(message):
#             answer = build_first_welcome_message(settings, context)
#         else:
#             answer = ""

#             try:
#                 answer = ask_groq(message, context, history, settings=settings)
#             except Exception as exc:
#                 print("[GROQ ERROR FIRST MESSAGE]", repr(exc))
#                 answer = ""

#             if not answer:
#                 answer = fallback_answer(message)

#             if wants_assets and assets.get("images"):
#                 if "connect" in answer.lower() or "team" in answer.lower():
#                     answer = "Sure, here are the matching product images I found."

#         history.append({"role": "user", "content": message})
#         history.append({"role": "assistant", "content": answer})
#         CHAT_MEMORY[history_key] = history[-20:]

#         return {
#             "answer": answer,
#             "session_id": session_id,
#             "images": assets.get("images", []),
#             "links": assets.get("links", []),
#             "sources": assets.get("sources", []),
#             "images_count": assets.get("images_count", 0),
#             "links_count": assets.get("links_count", 0),
#             "history_count": len(CHAT_MEMORY[history_key]),
#             "debug": {
#                 "tenant_id": tenant_id,
#                 "faiss_results": len(results),
#                 "context_found": bool(context),
#                 "context_length": len(context),
#                 "first_message": True,
#                 "top_score": results[0].get("score") if results else None,
#                 "top_text_len": len(get_text_from_result(results[0])) if results else 0,
#             },
#         }

#     print("========== CHAT DEBUG ==========")
#     print("TENANT ID:", tenant_id)
#     print("SESSION ID:", session_id)
#     print("MESSAGE:", message)
#     print("FAISS RESULTS:", len(results))
#     print("TOP SCORE:", results[0].get("score") if results else None)
#     print("CONTEXT LENGTH:", len(context))
#     print("GROQ KEY EXISTS:", bool(os.getenv("GROQ_API_KEY", "").strip()))
#     print("================================")

#     answer = ""

#     try:
#         answer = ask_groq(message, context, history, settings=settings)
#     except Exception as exc:
#         print("[GROQ ERROR]", repr(exc))
#         answer = ""

#     if not answer:
#         answer = fallback_answer(message)

#     if wants_assets and assets.get("images"):
#         if "connect" in answer.lower() or "team" in answer.lower():
#             answer = "Sure, here are the matching product images I found."

#     history.append({"role": "user", "content": message})
#     history.append({"role": "assistant", "content": answer})
#     CHAT_MEMORY[history_key] = history[-20:]

#     return {
#         "answer": answer,
#         "session_id": session_id,
#         "images": assets.get("images", []),
#         "links": assets.get("links", []),
#         "sources": assets.get("sources", []),
#         "images_count": assets.get("images_count", 0),
#         "links_count": assets.get("links_count", 0),
#         "history_count": len(CHAT_MEMORY[history_key]),
#         "debug": {
#             "tenant_id": tenant_id,
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

import requests

from app.db import get_main_db_connection
from app.index_builder import search_faiss

CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}
WELCOME_MESSAGE_KEY = "__welcome__"


DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
- Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
- If trained context is missing or not enough, give a safe, generic, human reply.
- For unknown business-specific details, politely say you will check with the team.
- Keep replies short, clear, and helpful."""


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


def is_image_or_link_request(message: str) -> bool:
    value = (message or "").lower()
    keywords = [
        "image", "images", "photo", "photos", "picture", "pictures", "pic",
        "show", "see", "visual", "catalog", "catalogue", "brochure",
        "product page", "link", "url", "pipe image", "fitting image",
    ]
    return any(keyword in value for keyword in keywords)


def is_greeting_only(message: str) -> bool:
    value = (message or "").strip().lower()
    greetings = {
        "hi", "hii", "hello", "hey", "hey there", "good morning",
        "good afternoon", "good evening", "namaste", "hola"
    }
    return value in greetings


def is_valid_url(url: str) -> bool:
    url = (url or "").strip()

    if not url.startswith(("http://", "https://")):
        return False

    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        if response.status_code < 400:
            return True

        # Some servers block HEAD, so try GET lightly
        response = requests.get(url, allow_redirects=True, timeout=5, stream=True)
        return response.status_code < 400

    except Exception:
        return False


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

    # Remove broken / 404 URLs
    valid_images = []
    for url in images:
        if is_valid_url(url):
            valid_images.append(url)
        if len(valid_images) >= max_images:
            break

    valid_links = []
    for url in links:
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


def _json_load(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def get_agent_settings_for_chat(tenant_id) -> Dict:
    try:
        conn = get_main_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        tas.business_name,
                        tas.greeting_message,
                        tas.system_prompt,
                        tas.restriction_rules,
                        tas.support_hours,
                        t.tenant_name
                    FROM tenants t
                    LEFT JOIN tenant_agent_settings tas ON tas.tenant_id = t.id
                    WHERE t.id=%s
                    LIMIT 1
                    """,
                    (tenant_id,),
                )
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

    return {
        "tenant_name": tenant_name,
        "business_name": business_name,
        "system_prompt": system_prompt,
        "restriction_rules": restriction_rules,
        "support_hours": _json_load(row.get("support_hours"), default={}) or {},
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
        "According to the provided context,",
        "Based on the provided context,",
        "Based on the context,",
        "According to the context,",
        "From the context,",
        "According to the document,",
        "Based on the document,",
        "The context says",
        "The provided information says",
    ]

    for phrase in remove_phrases:
        cleaned = cleaned.replace(phrase, "").strip()

    return cleaned
def build_first_welcome_message(settings: Dict, context: str) -> str:
    tenant_name = (
        settings.get("tenant_name")
        or settings.get("business_name")
        or "our company"
    )

    def make_smart_business_intro(context_text: str) -> str:
        text = (context_text or "").replace("\n", " ").strip()

        if not text:
            return "We are here to help you with products, services, and support."

        # Remove noisy words
        bad_phrases = [
            "privacy policy",
            "terms and conditions",
            "cookie policy",
            "all rights reserved",
            "blog",
            "comparison",
            "read more",
            "contact us",
        ]

        lower_text = text.lower()
        for phrase in bad_phrases:
            lower_text = lower_text.replace(phrase, "")

        # Prefer useful company/product lines
        sentences = re.split(r"(?<=[.!?])\s+", text)

        useful_sentences = []
        for sentence in sentences:
            s = sentence.strip()
            low = s.lower()

            if len(s) < 30:
                continue

            if any(bad in low for bad in bad_phrases):
                continue

            if any(word in low for word in [
                "manufactures",
                "manufacturer",
                "supplier",
                "provides",
                "offers",
                "specializes",
                "products",
                "services",
                "pipes",
                "fittings",
                "pressfit",
                "plumbing",
            ]):
                useful_sentences.append(s)

        if useful_sentences:
            intro = " ".join(useful_sentences[:2])
        else:
            intro = text[:220]

        intro = re.sub(r"\s+", " ", intro).strip()

        if len(intro) > 220:
            intro = intro[:220].rsplit(" ", 1)[0] + "."

        return intro

    business_intro = make_smart_business_intro(context)

    return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

{business_intro}

I'm here to help you with any questions about our products, services, or support.

What brings you in today? Are you looking for a particular product, or do you have a question about something?"""
# def build_first_welcome_message(settings: Dict, context: str) -> str:
#     tenant_name = (
#         settings.get("tenant_name")
#         or settings.get("business_name")
#         or "our company"
#     )

#     business_intro = ""

#     # Try to create a short company intro from system prompt
#     system_prompt = (settings.get("system_prompt") or "").strip()

#     if system_prompt:
#         cleaned = (
#             system_prompt
#             .replace("\n", " ")
#             .replace("You are a helpful business assistant for", "")
#             .strip()
#         )

#         business_intro = cleaned[:180].strip()

#     if not business_intro:
#         business_intro = (
#             "We are here to help you with products, services, and support."
#         )

#     return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# {business_intro}

# I'm here to help you with any questions about our products, services, or support.


# I'm here to help you with any questions about our products, services, or support.

# What brings you in today? Are you looking for a particular product, or do you have a question about something?"""

#     return f"""Hey, I'm the AI sales and support agent for {tenant_name}.

# I'm here to help you with any questions about our products or services.

# What brings you in today?"""


def ask_groq(
    question: str,
    context: str,
    history: List[Dict[str, str]],
    settings: Dict = None,
) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    print("[GROQ] key_exists:", bool(api_key))
    print("[GROQ] key_prefix:", api_key[:10] if api_key else "MISSING")
    print("[GROQ] model:", model)

    if not api_key:
        return ""

    settings = settings or {}
    business_name = settings.get("business_name") or "this business"
    system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
    restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES

    conversation = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]
    )

    has_context = bool((context or "").strip())

    if has_context:
        context_instruction = """
You have trained knowledge context below.
Use it to answer the customer.
If the exact answer is not available in the context, do not invent.
If useful images or links are already available from metadata, do not say "I will connect you with our team" unnecessarily.
""".strip()
    else:
        context_instruction = """
No trained knowledge context was found for this question.
You may still reply like a human assistant, but ONLY with safe generic help.
Allowed:
- greet the customer
- ask what they need
- say you can check with the team
- ask for clarification
Not allowed:
- invent services, pricing, address, phone number, offers, guarantees, timings, or company facts.
""".strip()

    prompt = f"""
You are a professional WhatsApp business assistant for {business_name}.
{system_prompt}

Your job is to reply like a real human on WhatsApp.

Language rules:
- Default reply language is English.
- If the user clearly writes in Hindi, reply in Hindi.
- If the user writes in Hinglish, reply in Hinglish.
- If the user writes in English, reply in English.
- If the user message is mixed, follow the user's dominant language.

Safety rules:
- Do not hallucinate.
- Do not invent business facts.
- Do not invent prices, phone numbers, addresses, products, services, offers, policies, guarantees, or availability.
- For unknown business-specific details, politely say you will check with the team.
- Do not repeat "I will connect you with our team" when useful images, links, or context are already available.
- Keep reply short: 1 to 4 lines.
- Sound warm, natural, and helpful.
- Do not say "based on the context".
- Do not show sources, file names, URLs, or internal details.

Important product rule:
- Blog articles, educational content, comparisons, and guides do NOT mean the company sells those products.
- Only confirm products/services that are clearly present in product pages, catalog pages, or official company offerings.
- If unsure whether a product is sold by the company, say:
  "I could not confirm that this product is offered by the company."

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

    messages = [
        {
            "role": "system",
            "content": (
                "You are a safe WhatsApp business assistant. "
                "Use trained context when available. "
                "When context is missing, give only safe generic replies and never invent business facts."
            ),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
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

    reply = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    return clean_ai_reply(reply)


def empty_assets() -> Dict:
    return {
        "images": [],
        "links": [],
        "sources": [],
        "images_count": 0,
        "links_count": 0,
    }


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
    session_id = session_id or "default"
    message = (message or "").strip()

    history_key = f"{tenant_id}:{session_id}"
    history = CHAT_MEMORY.setdefault(history_key, [])

    # Frontend calls this once when chatbot page opens.
    # It returns real tenant_name from DB and does NOT save anything in chat history.
    if message == WELCOME_MESSAGE_KEY:
        settings = get_agent_settings_for_chat(tenant_id)
        answer = build_first_welcome_message(settings, "")
        answer = f"{answer}\n\nPlease share your name to start the chat."

        return {
            "answer": answer,
            "session_id": session_id,
            "tenant_name": settings.get("tenant_name"),
            "business_name": settings.get("business_name"),
            "images": [],
            "links": [],
            "sources": [],
            "images_count": 0,
            "links_count": 0,
            "history_count": len(history),
            "debug": {
                "tenant_id": tenant_id,
                "welcome_only": True,
            },
        }

    results = []
    context = ""

    try:
        results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)

        print("==== FAISS RESULT TEXT CHECK ====")
        for i, r in enumerate(results):
            text = get_text_from_result(r)
            print("RESULT", i)
            print("KEYS:", list(r.keys()))
            print("TEXT LEN:", len(text))
            print("TEXT SAMPLE:", text[:300])
        print("=================================")

        context = build_context(results)

    except FileNotFoundError:
        print("[FAISS ERROR] Index missing for tenant:", tenant_id)
        raise
    except Exception as exc:
        print("[FAISS SEARCH ERROR]", repr(exc))
        results = []
        context = ""

    settings = get_agent_settings_for_chat(tenant_id)

    is_first_message = len(history) == 0
    wants_assets = is_image_or_link_request(message)

    assets = collect_assets_from_results(results) if wants_assets else empty_assets()

    if is_first_message:
        if is_greeting_only(message):
            answer = build_first_welcome_message(settings, context)
        else:
            answer = ""

            try:
                answer = ask_groq(message, context, history, settings=settings)
            except Exception as exc:
                print("[GROQ ERROR FIRST MESSAGE]", repr(exc))
                answer = ""

            if not answer:
                answer = fallback_answer(message)

            if wants_assets and assets.get("images"):
                if "connect" in answer.lower() or "team" in answer.lower():
                    answer = "Sure, here are the matching product images I found."

        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": answer})
        CHAT_MEMORY[history_key] = history[-20:]

        return {
            "answer": answer,
            "session_id": session_id,
            "images": assets.get("images", []),
            "links": assets.get("links", []),
            "sources": assets.get("sources", []),
            "images_count": assets.get("images_count", 0),
            "links_count": assets.get("links_count", 0),
            "history_count": len(CHAT_MEMORY[history_key]),
            "debug": {
                "tenant_id": tenant_id,
                "faiss_results": len(results),
                "context_found": bool(context),
                "context_length": len(context),
                "first_message": True,
                "top_score": results[0].get("score") if results else None,
                "top_text_len": len(get_text_from_result(results[0])) if results else 0,
            },
        }

    print("========== CHAT DEBUG ==========")
    print("TENANT ID:", tenant_id)
    print("SESSION ID:", session_id)
    print("MESSAGE:", message)
    print("FAISS RESULTS:", len(results))
    print("TOP SCORE:", results[0].get("score") if results else None)
    print("CONTEXT LENGTH:", len(context))
    print("GROQ KEY EXISTS:", bool(os.getenv("GROQ_API_KEY", "").strip()))
    print("================================")

    answer = ""

    try:
        answer = ask_groq(message, context, history, settings=settings)
    except Exception as exc:
        print("[GROQ ERROR]", repr(exc))
        answer = ""

    if not answer:
        answer = fallback_answer(message)

    if wants_assets and assets.get("images"):
        if "connect" in answer.lower() or "team" in answer.lower():
            answer = "Sure, here are the matching product images I found."

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    CHAT_MEMORY[history_key] = history[-20:]

    return {
        "answer": answer,
        "session_id": session_id,
        "images": assets.get("images", []),
        "links": assets.get("links", []),
        "sources": assets.get("sources", []),
        "images_count": assets.get("images_count", 0),
        "links_count": assets.get("links_count", 0),
        "history_count": len(CHAT_MEMORY[history_key]),
        "debug": {
            "tenant_id": tenant_id,
            "faiss_results": len(results),
            "context_found": bool(context),
            "context_length": len(context),
            "top_score": results[0].get("score") if results else None,
            "top_text_len": len(get_text_from_result(results[0])) if results else 0,
        },
    }
