# Enhanced Chat Agent

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

## What is included

- Tenant-aware settings from `tenant_agent_settings`
- Tenant-scoped FAISS retrieval
- Product overview retrieval with broad query expansion
- Product-page ranking boost for `/product`, `/catalog`, `/shop`, `/item`, category pages
- Low-priority filtering for privacy/terms/blog/cart pages
- Groq response generation
- KB-derived fallback from repeated product-like terms
- Contact/website reply support
- Image/link asset extraction
- Sales/support strategy separation
- Optional editable KB rules through `knowledge_admin.py`

## Editable KB rules

Rules are stored tenant-wise at:

```txt
/data/knowledge_admin/tenant_<tenant_id>_rules.json
```

Example:

```json
{
  "hidden_urls": ["https://example.com/privacy-policy"],
  "boosted_urls": ["https://example.com/product.html"],
  "page_labels": {
    "https://example.com/product.html": "product_page"
  }
}
```

This does not break your existing training flow. It only improves retrieval ranking after FAISS returns results.
