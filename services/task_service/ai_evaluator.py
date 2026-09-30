"""
Модуль для оценки сложности задачи через нейронную сеть
Поддерживает OpenRouter (для демонстрации) и Ollama (для продакшена)
"""
import os
import re
import json
import httpx
import asyncio
import logging
from typing import Optional, List, Dict, Any
from enum import Enum
from dotenv import load_dotenv

from services.task_service.goal_graph import sanitize_breakdown

load_dotenv()
logger = logging.getLogger(__name__)

STUB_REWARD_COINS = 4
STUB_REWARD_INTELLIGENCE = 2
STUB_REWARD_SATISFACTION = 3

class LLMProvider(str, Enum):
    """Провайдеры LLM"""
    OPENROUTER = "openrouter"  # Для демонстрации (быстро)
    OLLAMA = "ollama"  # Для продакшена (локально)

class TaskComplexityEvaluator:
    """Оценщик сложности задачи через LLM"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", LLMProvider.OPENROUTER.value)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout = 12.0
        self.llm_available = True
        self._llm_disabled_reason: Optional[str] = None
        self._stub_rewards = (
            STUB_REWARD_COINS,
            STUB_REWARD_INTELLIGENCE,
            STUB_REWARD_SATISFACTION,
        )

        if self.provider == LLMProvider.OPENROUTER.value and not self.openrouter_api_key:
            self._disable_llm("OPENROUTER_API_KEY отсутствует")

    def _disable_llm(self, reason: str) -> None:
        if not self.llm_available:
            return
        self.llm_available = False
        self._llm_disabled_reason = reason
        logger.warning("LLM отключен: %s. Будут использованы заглушки наград.", reason)

    def is_llm_available(self) -> bool:
        return self.llm_available

    def get_llm_disabled_reason(self) -> Optional[str]:
        return self._llm_disabled_reason

    def get_stub_rewards(self) -> tuple[int, int, int]:
        return self._stub_rewards

    # ==============================
    # 🔑 Главный JSON-парсер
    # ==============================
    async def _parse_json_response(
        self,
        prompt: str,
        field_name: str,
        expected_type: type = int,
        fallback: Any = 0,
        max_tokens: int = 80,
        temperature: float = 0.0
    ) -> Any:
        """
        Универсальный парсер для извлечения одного поля из JSON-ответа LLM.
        """
        if not self.llm_available:
            raise RuntimeError("LLM недоступен")

        if self.provider == LLMProvider.OPENROUTER.value:
            content = await self._call_openrouter_json(prompt, max_tokens, temperature)
        elif self.provider == LLMProvider.OLLAMA.value:
            content = await self._call_ollama_json(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Неизвестный провайдер LLM: {self.provider}")

        try:
            # Очистка от markdown-блоков
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content).strip()

            parsed = json.loads(content)
            value = parsed.get(field_name)
            if value is None:
                raise ValueError(f"Поле '{field_name}' отсутствует в JSON: {content}")

            if expected_type is bool:
                if isinstance(value, str):
                    value = value.strip().lower() in ("true", "1", "yes", "spam")
                return bool(value)
            elif expected_type is int:
                return int(value)
            else:
                return value

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(
                f"[JSON Parse Error] field={field_name}, expected={expected_type}, fallback={fallback}, error={e}, raw='{content}'"
            )
            return fallback

    # ==============================
    # 📡 Вызовы API
    # ==============================
    async def _call_openrouter_json(
        self,
        prompt: str,
        max_tokens: int = 80,
        temperature: float = 0.0
    ) -> str:
        if not self.openrouter_api_key:
            self._disable_llm("OPENROUTER_API_KEY не установлен")
            raise RuntimeError("LLM недоступен из-за отсутствующего ключа OpenRouter")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "qwen/qwen3-30b-a3b:free",
            "messages": [
                {
                    "role": "system",
                    "content": "Ты — точный помощник. Всегда отвечай строго валидным JSON без комментариев и markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                self._disable_llm(f"OpenRouter вернул статус {e.response.status_code}")
                logger.error(f"[OpenRouter Error] {e}")
                raise
            except Exception as e:
                logger.error(f"[OpenRouter Error] {e}")
                raise

    async def _call_ollama_json(
        self,
        prompt: str,
        max_tokens: int = 80,
        temperature: float = 0.0
    ) -> str:
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            },
            "format": "json"  # ← Ollama поддерживает принудительный JSON формат (начиная с 0.1.43+)
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
            except httpx.HTTPStatusError as e:
                self._disable_llm(f"Ollama вернула статус {e.response.status_code}")
                logger.error(f"[Ollama Error] {e}")
                raise
            except Exception as e:
                logger.error(f"[Ollama Error] {e}")
                raise

    # ==============================
    # 🧠 Оценка наград
    # ==============================
    async def evaluate_task_complexity(
        self,
        title: str,
        description: Optional[str] = None,
        priority: Optional[str] = None
    ) -> int:
        if not self.llm_available:
            return STUB_REWARD_COINS

        task_text = f"Название: {title}"
        if description:
            task_text += f"\nОписание: {description}"
        if priority:
            task_text += f"\nПриоритет: {priority}"

        prompt = f"""Ты — эксперт по оценке учебных задач в приложении-тамагочи.
Оцени сложность задачи в монетах по шкале 0–10:
- 0: спам/бессмысленно/нет образовательной ценности;
- 1–2: очень простая полезная задача (повторение, короткое упражнение);
- 3–4: простая задача с ясной пользой;
- 5–8: средняя задача (анализ, решение, создание);
- 9–10: сложная или проектная задача.

Верни строго JSON: {{"reward_coins": число_от_0_до_50}}

Задача:
{task_text}"""

        coins = await self._parse_json_response(
            prompt=prompt,
            field_name="reward_coins",
            expected_type=int,
            fallback=3,
            max_tokens=50,
            temperature=0.0
        )
        return max(0, min(10, coins))

    async def evaluate_intelligence_reward(
        self,
        title: str,
        description: Optional[str] = None
    ) -> int:
        if not self.llm_available:
            return STUB_REWARD_INTELLIGENCE

        task_text = f"Название: {title}"
        if description:
            task_text += f"\nОписание: {description}"

        prompt = f"""Оцени когнитивную нагрузку задачи в очках интеллекта (0–15).
Правила:
- 0: никакой умственной работы (спам, пусто);
- 1–5: лёгкое мышление (повторение, выбор);
- 6–10: умеренное (решение, сравнение, анализ);
- 11–15: высокая нагрузка (синтез, проектирование, исследование).

Верни строго JSON: {{"reward_intelligence": число_от_0_до_15}}

Задача:
{task_text}"""

        points = await self._parse_json_response(
            prompt=prompt,
            field_name="reward_intelligence",
            expected_type=int,
            fallback=2,
            max_tokens=50,
            temperature=0.0
        )
        return max(0, min(15, points))

    async def evaluate_satisfaction_reward(
        self,
        title: str,
        description: Optional[str] = None
    ) -> int:
        if not self.llm_available:
            return STUB_REWARD_SATISFACTION
        task_text = f"Название: {title}"
        if description:
            task_text += f"\nОписание: {description}"

        prompt = f"""Оцени, сколько очков удовлетворённости (0–20) заслуживает задача.
- 0: никакой мотивации, бессмысленно;
- 1–5: небольшой прогресс;
- 6–12: ощутимое чувство роста;
- 13–20: яркий успех, личный прорыв.

Верни строго JSON: {{"reward_satisfaction": число_от_0_до_20}}

Задача:
{task_text}"""

        points = await self._parse_json_response(
            prompt=prompt,
            field_name="reward_satisfaction",
            expected_type=int,
            fallback=3,
            max_tokens=50,
            temperature=0.0
        )
        return max(0, min(20, points))

    async def is_task_spam(
        self,
        title: str,
        description: Optional[str] = None
    ) -> bool:
        if not self.llm_available:
            return False
        task_text = f"Название: {title}"
        if description:
            task_text += f"\nОписание: {description}"

        prompt = f"""Является ли задача спамом? SPAM = нет образовательной цели, бессмысленно, реклама, мемы, общие фразы без действия.

Примеры SPAM: "классная задача", "ыбыбы", "сделать что-нибудь", "посмотреть TikTok".
Примеры NOT_SPAM: "Выучить 10 слов по английскому", "Решить 3 задачи по физике".

Верни строго JSON: {{"is_spam": true или false}}

Задача:
{task_text}"""

        is_spam = await self._parse_json_response(
            prompt=prompt,
            field_name="is_spam",
            expected_type=bool,
            fallback=False,
            max_tokens=30,
            temperature=0.0
        )
        return bool(is_spam)

    # ==============================
    # 🧩 Генерация задач и декомпозиции
    # ==============================
    async def generate_task(self) -> Dict[str, str]:
        prompt = """Сгенерируй одну полезную, конкретную, образовательную задачу для ежедневного выполнения.
Формат ответа — строго JSON:
{
    "title": "Короткое название (≤100 символов)",
    "description": "2-3 предложения объяснения",
    "priority": "low" | "medium" | "high" | "urgent"
}
Нельзя: шутки, общие фразы, спам, развлечения вне обучения."""

        if not self.llm_available:
            return {
                "title": "Повторить пройденное",
                "description": "Выделите 20 минут на повторение ключевых тем за последнюю неделю.",
                "priority": "medium"
            }

        for attempt in range(3):
            try:
                raw = await self._parse_json_response(
                    prompt=prompt,
                    field_name="__full__",
                    fallback={},
                    max_tokens=200,
                    temperature=0.7
                )
                # Но _parse_json_response не возвращает __full__, поэтому вызываем напрямую:
                if self.provider == LLMProvider.OPENROUTER.value:
                    content = await self._call_openrouter_json(prompt, max_tokens=200, temperature=0.7)
                else:
                    content = await self._call_ollama_json(prompt, max_tokens=200, temperature=0.7)

                task_data = json.loads(content)
                title = str(task_data.get("title", "")).strip()
                description = str(task_data.get("description", "")).strip()
                priority = str(task_data.get("priority", "medium")).lower()

                if priority not in {"low", "medium", "high", "urgent"}:
                    priority = "medium"

                if title and not await self.is_task_spam(title=title, description=description):
                    return {
                        "title": title[:100],
                        "description": description[:500],
                        "priority": priority
                    }
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}/3 генерации задачи провалилась: {e}")

        # Fallback
        return {
            "title": "Повторить пройденное",
            "description": "Выделите 20 минут на повторение ключевых тем за последнюю неделю.",
            "priority": "medium"
        }

    async def generate_goal_breakdown(
        self,
        title: str,
        description: Optional[str] = None,
        min_tasks: int = 4,
        max_tasks: int = 6
    ) -> List[Dict[str, Any]]:
        goal_text = f"Цель: {title.strip()}"
        if description:
            goal_text += f"\nОписание: {description.strip()}"

        if not self.llm_available:
            return self._build_fallback_tasks(title, description, min_tasks, max_tasks)

        prompt = f"""Разложи цель на {min_tasks}–{max_tasks} шагов дорожной карты (ориентированный граф) в JSON:
{{
  "tasks": [
    {{
      "title": "Чёткое действие (≤120 символов)",
      "description": "Как именно сделать, с измеримым результатом",
      "depends_on": []
    }}
  ]
}}
Правила:
- Каждый шаг — реальное действие, не «подумать» и не «мотивироваться».
- depends_on — индексы предыдущих шагов (с 0 по порядку массива), без которых шаг нельзя начать.
- Первый шаг: depends_on = [].
- Можно ветвить: два шага с одним и тем же depends_on идут параллельно.
- Финальный шаг зависит от всех веток, которые нужно свести.
- Нет циклов и ссылок вперёд.
- Строгий JSON без лишнего текста.

{goal_text}"""

        try:
            if self.provider == LLMProvider.OPENROUTER.value:
                content = await self._call_openrouter_json(prompt, max_tokens=900, temperature=0.3)
            else:
                content = await self._call_ollama_json(prompt, max_tokens=900, temperature=0.3)

            payload = json.loads(content)
            tasks_raw = payload.get("tasks", [])
            if not isinstance(tasks_raw, list):
                tasks_raw = []

            tasks = []
            for i, t in enumerate(tasks_raw):
                if not isinstance(t, dict):
                    continue
                title = str(t.get("title", "")).strip()
                desc = str(t.get("description", "")).strip()
                if not title:
                    continue
                tasks.append({
                    "title": title[:120],
                    "description": desc[:500],
                    "order_index": i,
                    "depends_on": t.get("depends_on") or [],
                })
                if len(tasks) >= max_tasks:
                    break

            if len(tasks) >= min_tasks:
                return sanitize_breakdown(tasks)

        except Exception as e:
            logger.warning(f"Ошибка генерации декомпозиции: {e}")

        # Fallback
        return self._build_fallback_tasks(title, description, min_tasks, max_tasks)

    def _build_fallback_tasks(
        self,
        title: str,
        description: Optional[str],
        min_tasks: int,
        max_tasks: int
    ) -> List[Dict[str, Any]]:
        hint = (description or title).strip()[:160]
        n = min(max(min_tasks, 3), max_tasks)
        if n <= 3:
            tasks = [
                {"title": "Собрать вводные по цели", "description": f"Материалы, срок и критерий успеха для: {hint}.", "depends_on": []},
                {"title": "Выполнить основную работу", "description": "Сделать ключевое действие цели.", "depends_on": [0]},
                {"title": "Проверить результат", "description": "Сверить с критерием успеха и зафиксировать прогресс.", "depends_on": [1]},
            ]
        elif n == 4:
            tasks = [
                {"title": "Собрать вводные по цели", "description": f"Материалы и критерий успеха для: {hint}.", "depends_on": []},
                {"title": "Сделать первую ветку работы", "description": "Закрыть первую самостоятельную часть цели.", "depends_on": [0]},
                {"title": "Сделать вторую ветку работы", "description": "Закрыть вторую часть параллельно с первой.", "depends_on": [0]},
                {"title": "Свести и проверить результат", "description": "Объединить ветки и сверить с критерием успеха.", "depends_on": [1, 2]},
            ]
        else:
            tasks = [
                {"title": "Собрать вводные и критерии", "description": f"Что считать успехом для: {hint}.", "depends_on": []},
                {"title": "Наметить дорожную карту", "description": "Выбрать порядок шагов и параллельные ветки.", "depends_on": [0]},
                {"title": "Выполнить первую ветку", "description": "Закрыть первую самостоятельную часть цели.", "depends_on": [1]},
                {"title": "Выполнить вторую ветку", "description": "Закрыть вторую часть, не дожидаясь первой.", "depends_on": [1]},
                {"title": "Свести результаты", "description": "Собрать обе ветки в один проверяемый итог.", "depends_on": [2, 3]},
            ]
            if n >= 6:
                tasks.append({
                    "title": "Проверить и закрепить итог",
                    "description": "Сверить с критериями, записать вывод, закрыть цель.",
                    "depends_on": [4],
                })
        return sanitize_breakdown(tasks[:n])