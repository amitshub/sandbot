import os
import re
import requests


def clean_ai_reply(reply: str) -> str:
    text = (reply or "").strip()
    for phrase in [
        "According to the provided context,", "Based on the provided context,",
        "Based on the context,", "According to the context,", "From the context,",
        "According to the knowledge base,", "Based on the knowledge base,",
    ]:
        text = text.replace(phrase, "").strip()
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def generate_response(prompt: str, business_name: str = "our team") -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

    if not api_key:
        return ""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a safe WhatsApp-style sales/support employee for {business_name}. Give KB-grounded intelligent sales answers, never expose internal implementation, and never invent facts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 320,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            print("[CHAT_AGENT GROQ HTTP ERROR]", response.status_code, response.text[:500])
        response.raise_for_status()
        data = response.json()
        return clean_ai_reply(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    except Exception as exc:
        print("[CHAT_AGENT GROQ ERROR]", repr(exc))
        return ""
