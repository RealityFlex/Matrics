"""Клиент GigaChat API: токен на 30 минут и chat/completions.

Документация: https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api
С 17.07.2026 рабочий хост генерации — https://api.giga.chat
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
# api.giga.chat с части сетей не отвечает (SSL handshake timeout).
DEFAULT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1"
FALLBACK_API_URL = "https://api.giga.chat/v1"
JSON_SYSTEM = "Ты — точный помощник. Всегда отвечай строго валидным JSON без комментариев и markdown."


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _credentials() -> str:
    key = (os.getenv("GIGACHAT_CREDENTIALS") or os.getenv("GIGACHAT_AUTHORIZATION_KEY") or "").strip()
    if key.lower().startswith("basic "):
        key = key[6:].strip()
    if key:
        return key
    client_id = (os.getenv("GIGACHAT_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GIGACHAT_CLIENT_SECRET") or "").strip()
    if client_id and client_secret:
        return base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return ""


def parse_llm_json(content: str) -> Any:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


class GigaChatClient:
    """Потокобезопасный клиент: один access_token на процесс."""

    def __init__(self) -> None:
        self.credentials = _credentials()
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS").strip() or "GIGACHAT_API_PERS"
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat").strip() or "GigaChat"
        self.auth_url = os.getenv("GIGACHAT_AUTH_URL", DEFAULT_AUTH_URL).rstrip("/")
        self.api_url = os.getenv("GIGACHAT_API_URL", DEFAULT_API_URL).rstrip("/")
        self.fallback_api_url = os.getenv("GIGACHAT_API_FALLBACK_URL", FALLBACK_API_URL).rstrip("/")
        self.verify_ssl = _env_flag("GIGACHAT_VERIFY_SSL", False)
        self.timeout = float(os.getenv("GIGACHAT_TIMEOUT", "20"))
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def available(self) -> bool:
        return bool(self.credentials)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl)

    async def _access_token(self, force: bool = False) -> str:
        wall = time.time()
        async with self._lock:
            if not force and self._token and wall < self._expires_at:
                return self._token
            if not self.credentials:
                raise RuntimeError("GigaChat: нет GIGACHAT_CREDENTIALS")
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {self.credentials}",
            }
            async with self._client() as client:
                response = await client.post(self.auth_url, headers=headers, data={"scope": self.scope})
                response.raise_for_status()
                data = response.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError(f"GigaChat: в ответе OAuth нет access_token: {data}")
            expires = float(data.get("expires_at") or 0)
            if expires > 10_000_000_000:
                expires /= 1000.0
            self._token = token
            self._expires_at = (expires - 60) if expires else wall + 25 * 60
            logger.info("GigaChat: получен access token")
            return token

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.1,
    ) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        token = await self._access_token()
        try:
            return await self._post_chat(token, payload, self.api_url)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code in {401, 403}:
                token = await self._access_token(force=True)
                return await self._post_chat(token, payload, self.api_url)
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            if self.fallback_api_url and self.fallback_api_url != self.api_url:
                logger.warning("GigaChat: %s недоступен (%s), пробуем %s", self.api_url, exc, self.fallback_api_url)
                return await self._post_chat(token, payload, self.fallback_api_url)
            raise

    async def _post_chat(self, token: str, payload: Dict[str, Any], api_url: str) -> str:
        url = f"{api_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        async with self._client() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and item.get("text"):
                        parts.append(str(item["text"]))
                content = "".join(parts)
            if content is None:
                raise RuntimeError(f"GigaChat: пустой content в ответе: {data}")
            return str(content).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"GigaChat: неожиданный ответ chat/completions: {data}") from exc


_client: Optional[GigaChatClient] = None


def gigachat_client() -> GigaChatClient:
    global _client
    if _client is None:
        _client = GigaChatClient()
    return _client
