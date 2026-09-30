import time
from unittest.mock import patch

import httpx
import pytest

from services.shared import gigachat as gigachat_mod
from services.shared.gigachat import GigaChatClient, parse_llm_json
from services.task_service.ai_evaluator import TaskComplexityEvaluator


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "https://example.test")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=self.request, response=httpx.Response(self.status_code))


class FakeAsyncClient:
    def __init__(self, handler, *args, **kwargs):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        return self._handler(url, **kwargs)


def test_parse_llm_json_from_markdown():
    payload = parse_llm_json('```json\n{"is_spam": false, "reward_coins": 5}\n```')
    assert payload["reward_coins"] == 5


@pytest.mark.asyncio
async def test_gigachat_chat_and_assess_task(monkeypatch):
    monkeypatch.setenv("GIGACHAT_CREDENTIALS", "dGVzdA==")
    monkeypatch.setenv("LLM_PROVIDER", "gigachat")
    gigachat_mod._client = None

    calls = {"oauth": 0, "chat": 0}

    def handler(url, **kwargs):
        if "oauth" in url:
            calls["oauth"] += 1
            return FakeResponse({"access_token": "tok", "expires_at": int((time.time() + 1800) * 1000)})
        calls["chat"] += 1
        return FakeResponse({
            "choices": [{
                "message": {
                    "content": '{"is_spam": false, "reward_coins": 7, "reward_intelligence": 9, "reward_satisfaction": 11}'
                }
            }]
        })

    with patch("services.shared.gigachat.httpx.AsyncClient", lambda *a, **k: FakeAsyncClient(handler, *a, **k)):
        client = GigaChatClient()
        text = await client.chat([{"role": "user", "content": "hi"}], max_tokens=40)
        assert "reward_coins" in text
        evaluator = TaskComplexityEvaluator()
        evaluator._gigachat = client
        evaluator.llm_available = True
        result = await evaluator.assess_task("Решить 5 задач по матану", "Производные и пределы")
        assert result["is_spam"] is False
        assert result["reward_coins"] == 7
        assert result["reward_intelligence"] == 9
        assert calls["oauth"] == 1
        assert calls["chat"] == 2
