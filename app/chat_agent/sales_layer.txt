from typing import Any, Dict


def apply_sales_strategy(intent: str, memory: Dict[str, Any]) -> Dict[str, Any]:
    """Return small, intent-specific guidance for the prompt.

    This does not add facts. Facts must still come from retrieved KB/context.
    It only controls the sales conversation style.
    """
    base = {
        "terms": memory.get("terms", []),
        "avoid_claims": [
            "unconfirmed price",
            "unconfirmed stock",
            "unconfirmed warranty",
            "unconfirmed client names",
            "unconfirmed installation/service promise",
        ],
    }

    if intent == "product_overview":
        return {
            **base,
            "goal": "Explain confirmed product range from KB in simple customer language.",
            "reply_pattern": "category_summary_then_next_choice",
            "followup_rule": "Ask whether customer wants images, specifications, or recommendation.",
        }

    if intent == "product_options":
        return {
            **base,
            "goal": "Show confirmed options/types only; connect them to the customer’s previous use-case.",
            "reply_pattern": "confirmed_options_then_one_next_step",
            "followup_rule": "Ask one practical next question only if needed.",
        }

    if intent == "buying_guidance":
        return {
            **base,
            "goal": "Act like a plumbing sales engineer: recommend first, then qualify.",
            "reply_pattern": "recommendation_first_reason_second_question_last",
            "followup_fields": ["application area", "water pressure", "pipe size", "quantity", "project location"],
            "avoid": ["generic company intro", "asking office size first", "asking many questions", "website link first"],
        }

    if intent == "pricing":
        return {
            **base,
            "goal": "Collect quote details without inventing price.",
            "reply_pattern": "explain_price_depends_then_ask_missing_detail",
            "followup_fields": ["grade", "size", "quantity", "location"],
        }

    if intent == "trust_proof":
        return {
            **base,
            "goal": "Answer client/project/certification trust questions only from KB.",
            "reply_pattern": "confirmed_proof_summary_not_installation",
            "avoid": ["installation steps", "service explanation", "invented client names"],
        }

    return {
        **base,
        "goal": "Give a helpful KB-grounded sales/support reply.",
        "reply_pattern": "answer_first_then_one_relevant_followup",
    }
