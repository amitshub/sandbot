from typing import Any, Dict


def apply_support_strategy(intent: str, memory: Dict[str, Any]) -> Dict[str, Any]:
    """Small support guidance for prompt only. No facts are added here."""
    support_focus = memory.get("support_focus") or "general_support"

    base = {
        "should_support": intent in {"support", "general", "human_connect"},
        "safe_service_reply": intent == "support",
        "support_focus": support_focus,
        "terms": memory.get("terms", []),
        "avoid": [
            "repeating the full installation process for every support question",
            "saying installation videos are available unless a video link is present",
            "promising site visit/service unless confirmed in KB",
            "generic documentation-only answer when the customer asks a specific question",
        ],
    }

    focus_map = {
        "installation_steps": "Answer the installation/process question with short ordered steps from KB only.",
        "installation_guidance": "Confirm guidance/support only if KB supports it; offer to help with the specific project requirement.",
        "installation_tools": "Answer only the tools required; do not repeat all installation steps.",
        "installation_video": "Answer whether installation video/link is confirmed. If not confirmed, say it is not available here and offer installation steps or team support.",
        "project_technical_support": "Answer project technical support as consultation/specification/project assistance; collect one useful project detail.",
        "general_support": "Give concise support guidance and ask one practical next question.",
    }

    return {
        **base,
        "goal": focus_map.get(support_focus, focus_map["general_support"]),
        "max_reply_lines": 6,
    }
