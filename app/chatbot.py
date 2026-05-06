import os
import json
from typing import Dict, List

import requests

from app.db import get_main_db_connection
from app.index_builder import search_faiss

CHAT_MEMORY: Dict[str, List[Dict[str, str]]] = {}


DEFAULT_RESTRICTION_RULES = """- Answer only using trained knowledge base.
- Do not invent prices, offers, phone numbers, addresses, or guarantees.
- If answer is not available, say: I will connect you with our team.
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
    """Read tenant chatbot settings. Falls back safely if table/row does not exist."""
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
    except Exception:
        row = {}

    tenant_name = row.get("tenant_name") or row.get("business_name") or "this business"
    business_name = row.get("business_name") or tenant_name
    system_prompt = (row.get("system_prompt") or "").strip()
    restriction_rules = (row.get("restriction_rules") or "").strip()

    if not system_prompt:
        system_prompt = f"""You are a helpful business assistant for {business_name}.
Your job is to answer customer questions using only the trained knowledge base.
Reply naturally like a real human assistant. Keep answers short, clear, and helpful."""

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


def fallback_answer(results: List[Dict]) -> str:
    if not results:
        return "I will connect you with our team."

    best = results[0]
    text = (best.get("text") or "").strip()

    if not text:
        return "I will connect you with our team."

    if len(text) > 700:
        text = text[:700].rsplit(" ", 1)[0] + "..."

    return text


def ask_groq(question: str, context: str, history: List[Dict[str, str]], settings: Dict = None) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    if not api_key:
        return ""

    settings = settings or {}
    system_prompt = settings.get("system_prompt") or "You are a helpful business assistant."
    restriction_rules = settings.get("restriction_rules") or DEFAULT_RESTRICTION_RULES

    conversation = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in history[-6:]]
    )

    prompt = f"""
{system_prompt}

Your job is to reply like a real human on WhatsApp.

Language rules:
- Default reply language is English.
- If the user clearly writes in Hindi, reply in Hindi.
- If the user writes in Hinglish, reply in Hinglish.
- If the user writes in English, reply in English.
- If the user message is mixed, follow the user's dominant language.
- Do not switch to Hindi unless the user uses Hindi or Hinglish.

Rules:
- Answer ONLY using the provided context.
- Use conversation history only to understand follow-up questions.
- If the answer is not found in the context, reply naturally:
  "I will connect you with our team."
- Keep replies short, clear, warm, and natural.
- Do not sound robotic.
- Do not say "based on the context" or "according to the data".
- Do not show sources, file names, URLs, or internal details.

Tenant restriction rules:
{restriction_rules}

Context:
{context}

Conversation history:
{conversation}

User:
{question}
""".strip()

    messages = [
        {
            "role": "system",
            "content": system_prompt,
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
            "temperature": 0.3,
            "max_tokens": 120,
        },
        timeout=10,
    )

    response.raise_for_status()
    data = response.json()

    return clean_ai_reply(data["choices"][0]["message"]["content"])


def chat_with_agent(session_id: str, message: str, tenant_id, top_k: int = 5) -> Dict:
    session_id = session_id or "default"
    message = (message or "").strip()

    history_key = f"{tenant_id}:{session_id}"
    history = CHAT_MEMORY.setdefault(history_key, [])

    results = search_faiss(message, tenant_id=tenant_id, top_k=top_k)
    context = build_context(results)
    settings = get_agent_settings_for_chat(tenant_id)

    answer = ""

    try:
        if context:
            answer = ask_groq(message, context, history, settings=settings)
    except Exception:
        answer = ""

    if not answer:
        answer = fallback_answer(results)

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    CHAT_MEMORY[history_key] = history[-20:]

    return {
        "answer": answer,
        "session_id": session_id,
        "history_count": len(CHAT_MEMORY[history_key]),
    } 

