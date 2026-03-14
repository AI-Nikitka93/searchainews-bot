import json
import html
from typing import List, Any, Dict


MAX_ACTION_ITEMS = 5


def parse_json_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        try:
            data = json.loads(value)
            if isinstance(data, list):
                return [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            return [value.strip()] if value.strip() else []
    return [str(value).strip()]


def format_news_item(item: Dict[str, Any]) -> str:
    title = html.escape(item.get("title") or "Untitled")
    url = html.escape(item.get("url") or "")
    score = item.get("impact_score")
    rationale = html.escape(item.get("impact_rationale") or "")

    action_items = parse_json_list(item.get("action_items_json"))[:MAX_ACTION_ITEMS]
    if action_items:
        actions = "\n".join(f"- {html.escape(a)}" for a in action_items)
    else:
        actions = "- No action items provided"

    parts = [
        f"<b>{title}</b>",
        f"<a href=\"{url}\">Source</a>" if url else "",
        f"Impact score: {score}" if score is not None else "Impact score: n/a",
        f"Rationale: {rationale}" if rationale else "Rationale: n/a",
        "Action items:\n" + actions,
    ]
    return "\n".join(p for p in parts if p)
