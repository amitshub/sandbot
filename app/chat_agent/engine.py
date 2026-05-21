def run_sales_support_agent(tenant_id, session_id, message, top_k=5):
    return {
        "reply": "Sales support agent initialized.",
        "tenant_id": tenant_id,
        "session_id": session_id,
    }