from typing import Any, Dict


def apply_sales_strategy(intent: str, memory: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "should_sell": intent in {"product_overview", "general", "pricing", "availability"},
        "avoid_claims": ["unconfirmed price", "unconfirmed stock", "unconfirmed warranty"],
        "terms": memory.get("terms", []),
    }
