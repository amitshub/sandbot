"""Optional editable knowledge-base helpers.

These helpers do not change your existing training flow. They are safe utilities you can
connect later to a Knowledge Base dashboard to hide, boost, or label retrieved pages.
"""
import json
import os
from typing import Any, Dict, List


def _rules_path(tenant_id: int, base_dir: str = "/data/knowledge_admin") -> str:
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, f"tenant_{tenant_id}_rules.json")


def load_kb_rules(tenant_id: int) -> Dict[str, Any]:
    path = _rules_path(tenant_id)
    if not os.path.exists(path):
        return {"hidden_urls": [], "boosted_urls": [], "page_labels": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("hidden_urls", [])
        data.setdefault("boosted_urls", [])
        data.setdefault("page_labels", {})
        return data
    except Exception:
        return {"hidden_urls": [], "boosted_urls": [], "page_labels": {}}


def save_kb_rules(tenant_id: int, rules: Dict[str, Any]) -> Dict[str, Any]:
    clean = {
        "hidden_urls": list(dict.fromkeys([str(x).strip() for x in rules.get("hidden_urls", []) if str(x).strip()])),
        "boosted_urls": list(dict.fromkeys([str(x).strip() for x in rules.get("boosted_urls", []) if str(x).strip()])),
        "page_labels": rules.get("page_labels") or {},
    }
    with open(_rules_path(tenant_id), "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2)
    return clean


def apply_kb_rules(results: List[Dict[str, Any]], tenant_id: int) -> List[Dict[str, Any]]:
    rules = load_kb_rules(tenant_id)
    hidden = set(rules.get("hidden_urls") or [])
    boosted = set(rules.get("boosted_urls") or [])
    labels = rules.get("page_labels") or {}

    output = []
    for item in results or []:
        url = str(item.get("url") or item.get("source") or "").strip()
        if url in hidden:
            continue
        item = dict(item)
        if url in labels:
            item["page_type"] = labels[url]
        if url in boosted:
            item["score"] = float(item.get("score") or 0) + 0.25
        output.append(item)
    return output
