"""
Сборка единой спецификации OpenAPI 3.1 (docs/openapi.json) из сервисов,
как они видны снаружи через API Gateway (Caddy).

Запуск при поднятом стеке:
    python scripts/export_openapi.py [--base http://localhost] [--out docs/openapi.json]

Внутренние маршруты, закрытые на gateway (межсервисные вызовы), в спецификацию не попадают.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request

# сервис в /docs/<name>/openapi.json → функция «путь сервиса → публичный путь»
SERVICES = {
    "users": lambda p: "/api" + p,
    "characters": lambda p: "/api" + p,
    "tasks": lambda p: "/api" + p,
    "habits": lambda p: "/api" + p,
    "achievements": lambda p: "/api" + p,
    "inventory": lambda p: ("/api" + p) if p.startswith("/inventory") else "/api/inventory" + p,
    "social": lambda p: "/api/social" + p,
    "events": lambda p: "/api/events" + p,
    "economy": lambda p: "/api/economy" + p,
    "competitions": lambda p: "/api/competitions" + p,
    "statistics": lambda p: "/api/statistics" + p,
}

# Совпадают с блокировками в gateway/Caddyfile
BLOCKED = [
    r"^/api/users/\{[^}]+\}/coins/(add|subtract)$",
    r"^/api/users/internal/.*$",
    r"^/api/characters/\{[^}]+\}/(satisfaction/adjust|intelligence/add|bonus/add)$",
    r"^/api/characters/user/\{[^}]+\}/appearance/check-unlocks$",
    r"^/api/events/internal/.*$",
    r"^/api/rewards.*$",
]
SKIP = {"/", "/health"}


def fetch(base: str, name: str) -> dict:
    with urllib.request.urlopen(f"{base}/docs/{name}/openapi.json", timeout=15) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost")
    parser.add_argument("--out", default="docs/openapi.json")
    args = parser.parse_args()

    merged = {
        "openapi": "3.1.0",
        "info": {
            "title": "Матрикс — публичный API (через API Gateway)",
            "version": "1.1.0",
            "description": (
                "Сводная спецификация микросервисов «Матрикс». Базовый адрес — адрес gateway. "
                "Административные операции требуют заголовок X-Admin-Token; действия студента в MAX — "
                "X-Max-Init-Data (подписанный initData). Основной сценарий: "
                "GET /api/events/schedule/users/{user_id} → POST /api/events/lessons/{lesson_id}/check-in."
            ),
        },
        "servers": [{"url": args.base}],
        "paths": {},
        "components": {"schemas": {}},
    }

    for name, to_public in SERVICES.items():
        spec = fetch(args.base, name)
        for path, item in spec.get("paths", {}).items():
            if path in SKIP:
                continue
            public = to_public(path)
            if any(re.match(pattern, public) for pattern in BLOCKED):
                continue
            for operation in item.values():
                if isinstance(operation, dict):
                    operation.setdefault("tags", [name])
            merged["paths"].setdefault(public, {}).update(item)
        for schema_name, schema in spec.get("components", {}).get("schemas", {}).items():
            merged["components"]["schemas"].setdefault(schema_name, schema)

    merged["paths"] = dict(sorted(merged["paths"].items()))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    print(f"{args.out}: {len(merged['paths'])} путей, {len(merged['components']['schemas'])} схем")


if __name__ == "__main__":
    main()
