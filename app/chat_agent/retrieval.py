from app.index_builder import search_faiss

def retrieve_context(tenant_id, query, top_k=5):
    return search_faiss(
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
    )