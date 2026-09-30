"""Дорожная карта цели: зависимости между подзадачами (ориентированный граф)."""
from __future__ import annotations

import json
from typing import Any, Dict, List


def parse_depends_on(value: Any) -> List[int]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return []
    else:
        return []
    result: List[int] = []
    for item in raw:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def dump_depends_on(value: Any) -> str:
    return json.dumps(parse_depends_on(value), separators=(",", ":"))


def sanitize_breakdown(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Нумерация 0..n-1, только рёбра назад, без циклов. Пустые зависимости — цепочка."""
    cleaned: List[Dict[str, Any]] = []
    for index, item in enumerate(tasks):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        order = len(cleaned)
        deps = [dep for dep in parse_depends_on(item.get("depends_on")) if 0 <= dep < order]
        if order > 0 and not deps:
            deps = [order - 1]
        cleaned.append({
            "title": title[:120],
            "description": str(item.get("description") or "").strip()[:500],
            "order_index": order,
            "depends_on": deps,
            "reward_coins": item.get("reward_coins"),
            "reward_intelligence": item.get("reward_intelligence"),
            "reward_satisfaction": item.get("reward_satisfaction"),
        })
    return cleaned
