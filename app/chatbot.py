# import os
# import json
# from typing import Dict, List

# import requests

# from app.db import get_main_db_connection
# from app.index_builder import search_faiss

# CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


# DEFAULT_RESTRICTION_RULES = """- Answer only using trained knowledge base.
# - Do not invent prices, offers, phone numbers, addresses, or guarantees.
# - If answer is not available, say: I will connect you with our team.
# - Keep replies short, clear, and helpful."""


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
#     """Read tenant chatbot settings. Falls back safely if table/row does not exist."""
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
#     except Exception:
#         row = {}

#     tenant_name = row.get("tenant_name") or row.get("business_name") or "this business"
#     business_name = row.get("business_name") or tenant_name
#     system_prompt = (row.get("system_prompt") or "").strip()
#     restriction_rules = (row.get("restriction_rules") or "").strip()

#     if not system_prompt:
#         system_prompt = f"""You are a helpful business assistant for {business_name}.
# Your job is to answer customer questions using only the trained knowledge base.
# Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""

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
#         text = (item.get("text") or "").strip()

#         if not text:
#             continue

#         block = f"[Source {i}: {source}]\n{text}"

#         if total + len(block) > max_chars:
#             break

#         parts.append(block)
#         total += len(block)

#     return "\n\n".join(parts)


# def clean_ai_reply(reply: str) -> str:
#     if not reply:
#         return "I will connect you with our team."

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

#     return cleaned or "I will connect you with our team."


# def fallback_answer(results: List[Dict]) -> str:
#     return "I will connect you with our team."


# def ask_groq(question: str, context: str, history: List[Dict[str, str]], settings: Dict = None) -> str:

#     api_key = os.getenv("GROQ_API_KEY", "").strip()
#     print("GROQ KEY EXISTS:", bool(api_key))
#     print("GROQ KEY PREFIX:", api_key[:10] if api_key else "MISSING")
#     model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

#     if not api_key:
#         return ""

#     settings = settings or {}
#     system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
#     restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES

#     conversation = "\n".join(
#         [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]
#     )

#     prompt = f"""
# You are a professional WhatsApp business assistant for {settings.get("business_name", "this business")}.
# {system_prompt}

# Your job is to reply like a real human on WhatsApp.

# Language rules:
# - Default reply language is English.
# - If the user clearly writes in Hindi, reply in Hindi.
# - If the user writes in Hinglish, reply in Hinglish.
# - If the user writes in English, reply in English.
# - If the user message is mixed, follow the user's dominant language.
# - Do not switch to Hindi unless the user uses Hindi or Hinglish.

# Rules:
# - Answer ONLY using the provided context.
# - Use conversation history only to understand follow-up questions.
# - If the answer is not found in the context, reply naturally:
#   "I will connect you with our team."
# - Keep replies short, clear, warm, and natural.
# - Keep reply short: 2 to 4 lines only.
# - Sound human, polite, and helpful.
# - Do not sound robotic.
# - Do not say "based on the context" or "according to the data".
# - Do not show sources, file names, URLs, or internal details.

# Tenant restriction rules:
# {restriction_rules}

# Context:
# {context}

# Conversation history:
# {conversation}
# Write the best short WhatsApp reply.
# User:
# {question}
# """.strip()

#     messages = [
#         {
#             "role": "system",
#             "content": system_prompt,
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
#             "temperature": 0.3,
#             "max_tokens": 120,
#         },
#         timeout=20,
#     )

#     response.raise_for_status()
#     data = response.json()

#     return clean_ai_reply(data["choices"][0]["message"]["content"])


# def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
#     session_id = session_id or "default"
#     message = (message or "").strip()

#     history_key = f"{tenant_id}:{session_id}"
#     history = CHAT_MEMORY.setdefault(history_key, [])

#     results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)
#     context = build_context(results)
#     settings = get_agent_settings_for_chat(tenant_id)

#     answer = ""

#     try:
#         if context:
#             answer = ask_groq(message, context, history, settings=settings)
#     except Exception:
#         answer = ""

#     if not answer:
#         answer = fallback_answer(results)

#     history.append({"role": "user", "content": message})
#     history.append({"role": "assistant", "content": answer})
#     CHAT_MEMORY[history_key] = history[-20:]

#     return {
#         "answer": answer,
#         "session_id": session_id,
#         "history_count": len(CHAT_MEMORY[history_key]),
#     } 

import os
import json
from typing import Dict, List

import requests

from app.db import get_main_db_connection
from app.index_builder import search_faiss

CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


DEFAULT_RESTRICTION_RULES = """- Answer using trained knowledge base when available.
- Do not invent prices, offers, phone numbers, addresses, guarantees, services, or company details.
- If trained context is missing or not enough, give a safe, generic, human reply.
- For unknown business-specific details, say: I will connect you with our team.
- Keep replies short, clear, and helpful."""


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
        text = (item.get("text") or "").strip()

        if not text:
            continue

        block = f"[Source {i}: {source}]\n{text}"

        if total + len(block) > max_chars:
            break

        parts.append(block)
        total += len(block)

    return "\n\n".join(parts)


def clean_ai_reply(reply: str) -> str:
    if not reply:
        return "I will connect you with our team."

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

    return cleaned or "I will connect you with our team."


def fallback_answer() -> str:
    return "I will connect you with our team."


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
Say naturally: "I will connect you with our team."
""".strip()
    else:
        context_instruction = """
No trained knowledge context was found for this question.
You may still reply like a human assistant, but ONLY with safe generic help.
Allowed:
- greet the customer
- ask what they need
- say you can connect them with the team
- ask for clarification
Not allowed:
- invent services, pricing, address, phone number, offers, guarantees, timings, or company facts
For any business-specific question, reply naturally:
"I will connect you with our team."
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
- If unsure, say you will connect the customer with the team.
- Keep reply short: 1 to 4 lines.
- Sound warm, natural, and helpful.
- Do not say "based on the context".
- Do not show sources, file names, URLs, or internal details.

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

    return clean_ai_reply(data["choices"][0]["message"]["content"])


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
    session_id = session_id or "default"
    message = (message or "").strip()

    history_key = f"{tenant_id}:{session_id}"
    history = CHAT_MEMORY.setdefault(history_key, [])

    results = []
    context = ""

    try:
        results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)
        context = build_context(results)
    except FileNotFoundError:
        print("[FAISS ERROR] Index missing for tenant:", tenant_id)
        raise
    except Exception as exc:
        print("[FAISS SEARCH ERROR]", repr(exc))
        results = []
        context = ""

    settings = get_agent_settings_for_chat(tenant_id)

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
        answer = fallback_answer()

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    CHAT_MEMORY[history_key] = history[-20:]

    return {
        "answer": answer,
        "session_id": session_id,
        "history_count": len(CHAT_MEMORY[history_key]),
        "debug": {
            "tenant_id": tenant_id,
            "faiss_results": len(results),
            "context_found": bool(context),
            "top_score": results[0].get("score") if results else None,
        },
    }