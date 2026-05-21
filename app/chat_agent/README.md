# Chat Agent Full

Copy this folder to:

```txt
backend/app/chat_agent/
```

Minimal integration in your existing `chatbot.py`:

```python
from app.chat_agent.engine import run_sales_support_agent

def chat_with_agent(session_id, message, tenant_id, top_k=5):
    return run_sales_support_agent(
        tenant_id=tenant_id,
        session_id=session_id,
        message=message,
        top_k=top_k,
        agent_type="chat",
    )
```

The returned dict includes both `answer` and `reply`, so it works with most existing frontend response handling.

## What it includes

- Tenant-aware settings from `tenant_agent_settings`
- Tenant-scoped FAISS retrieval
- Product overview retrieval with broad query expansion
- Groq response generation
- KB-derived fallback from repeated product-like terms
- Contact/website reply support
- Image/link asset extraction
- Sales/support strategy separation
- Safe fallback for service-related questions
