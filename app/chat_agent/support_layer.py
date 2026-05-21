from typing import Any, Dict


def apply_support_strategy(intent: str, memory: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "should_support": intent in {"support", "general", "human_connect"},
        "safe_service_reply": intent == "support",
        "terms": memory.get("terms", []),
    }
