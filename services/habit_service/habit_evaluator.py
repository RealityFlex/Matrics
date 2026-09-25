"""Оценка полезности привычек с помощью LLM"""
import os
import re
import json
import httpx
from typing import Optional, Tuple
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class HabitLLMProvider(str, Enum):
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class HabitEvaluator:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", HabitLLMProvider.OPENROUTER.value)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3")

        self._harmful_keywords = {
            "начать курить", "купить сигареты", "выпивать", "алкоголь",
            "пить пиво", "фастфуд", "junk food", "газировка", "энергетик",
            "ничего не делать", "лениться", "прокрастинировать", "играть весь день"
        }
        self._beneficial_anti_keywords = {
            "бросить курить", "не курить", "отказ от курения", "перестать курить",
            "не пить алкоголь", "отказ от алкоголя", "не есть фастфуд", "без фастфуда"
        }

    async def is_habit_harmful(self, name: str, description: Optional[str]) -> bool:
        text = f"{name} {description or ''}".lower()
        normalized = re.sub(r"\s+", " ", text)

        for keyword in self._beneficial_anti_keywords:
            if keyword in normalized:
                return False

        for keyword in self._harmful_keywords:
            if keyword in normalized:
                return True

        prompt = f"""Оцени полезность привычки. 
Возвращай только одно слово: HARMFUL, NEUTRAL или BENEFICIAL.
HARMFUL — если привычка ухудшает здоровье, поощряет вредные зависимости, бездействие или нездоровый образ жизни.
NEUTRAL — если привычка не несет явной пользы или вреда.
BENEFICIAL — если привычка способствует обучению, развитию навыков, здоровью, дисциплине.

Привычка:
Название: {name}
Описание: {description or '—'}
"""

        try:
            verdict = await self._classify_text(prompt)
        except Exception as exc:
            print(f"Ошибка при классификации привычки: {exc}")
            return False

        verdict_upper = verdict.upper()
        if "HARMFUL" in verdict_upper:
            return True
        return False

    async def evaluate_rewards(
        self,
        name: str,
        description: Optional[str],
        frequency: str,
        target_count: int
    ) -> Tuple[int, int, int]:
        """Возвращает тройку (coins, intelligence, satisfaction)"""
        prompt = self._build_reward_prompt(name, description, frequency, target_count)

        try:
            result = await self._request_rewards(prompt)
            coins = int(result.get("coins", 0))
            intelligence = int(result.get("intelligence", 0))
            satisfaction = int(result.get("satisfaction", 0))
        except Exception as exc:
            print(f"Ошибка при оценке привычки: {exc}")
            coins = 0
            intelligence = 0
            satisfaction = 0

        coins, intelligence = self._apply_heuristics(
            name=name,
            description=description,
            frequency=frequency,
            target_count=target_count,
            coins=coins,
            intelligence=intelligence
        )

        satisfaction = self._adjust_satisfaction(
            name=name,
            description=description,
            frequency=frequency,
            target_count=target_count,
            coins=coins,
            intelligence=intelligence,
            raw_satisfaction=satisfaction
        )

        coins = max(0, min(40, coins))
        intelligence = max(0, min(15, intelligence))
        if coins <= 0:
            satisfaction = 0
        satisfaction = max(0, min(20, satisfaction))
        return coins, intelligence, satisfaction

    def _build_reward_prompt(
        self,
        name: str,
        description: Optional[str],
        frequency: str,
        target_count: int
    ) -> str:
        description = description or "—"
        return (
            "Ты оцениваешь полезность привычек для образовательного приложения. "
            "Верни JSON с полями coins (0-40), intelligence (0-15) и satisfaction (0-20). Используй всю шкалу."
            "\nЕсли привычка вредная — все значения должны быть 0."
            "\nПравила оценки:"
            "\n- Обучающие и развивающие привычки (например, чтение, изучение языков, программирование) получают высокие очки интеллекта (10-15) и достойные монеты (20-40)."
            "\n- Привычки по укреплению здоровья и дисциплины (спорт, режим сна, отказ от вредных привычек) получают средние монеты (10-25), умеренный интеллект (4-9) и заметную удовлетворённость (8-15)."
            "\n- Очень простые, но полезные действия (пить воду, делать растяжку) получают небольшие награды (3-10 монет, 1-3 интеллекта, 5-9 удовлетворённости)."
            "\n- Вредные или бесполезные привычки — нулевые значения."
            "\nТакже учитывай частоту и целевое количество: ежедневные задачи с большим target_count требуют больше усилий."
            "\nОтвет должен быть в формате JSON без дополнительных комментариев."
            f"\n{{\n  \"habit\": {{\n    \"name\": \"{name}\",\n    \"description\": \"{description}\",\n    \"frequency\": \"{frequency}\",\n    \"target_count\": {target_count}\n  }},\n  \"coins\": <число>,\n  \"intelligence\": <число>,\n  \"satisfaction\": <число>\n}}"
        )

    async def _classify_text(self, prompt: str) -> str:
        if self.provider == HabitLLMProvider.OPENROUTER.value:
            if not self.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY не установлен")
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "qwen/qwen3-30b-a3b:free",
                "messages": [
                    {"role": "system", "content": "Отвечай только одним словом."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 5
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()

        # Ollama
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 5
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return (data.get("response", "") or "").strip()

    async def _request_rewards(self, prompt: str) -> dict:
        if self.provider == HabitLLMProvider.OPENROUTER.value:
            if not self.openrouter_api_key:
                raise ValueError("OPENROUTER_API_KEY не установлен")
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
                        "content": "Ты ассистент, который отвечает строго валидным JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 150
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                return self._extract_json(content)

        # Ollama
        url = f"{self.ollama_base_url}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 200
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data.get("response", "").strip()
            return self._extract_json(content)

    def _extract_json(self, text: str) -> dict:
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]

        return json.loads(text)

    def _categorize_habit(self, name: str, description: Optional[str]) -> str:
        text = f"{name} {description or ''}".lower()

        learning_keywords = {
            "читать", "книга", "книг", "страниц", "учить", "изучать", "учеб", "курс",
            "программировать", "язык", "англий", "математ", "образован", "конспект"
        }
        fitness_keywords = {
            "зал", "трениров", "спорт", "бег", "присед", "отжим", "кардио", "йога",
            "растяж", "физк", "силов", "фитнес", "гимнаст"
        }
        quit_keywords = {
            "бросить курить", "не курить", "не пить", "без алкоголя", "отказ от", "перестать" 
        }
        wellness_keywords = {
            "сон", "спать", "вода", "здоров", "питани", "медита", "осанка", "прогул"
        }

        def contains_any(keys):
            return any(keyword in text for keyword in keys)

        if contains_any(learning_keywords):
            return "learning"
        if contains_any(fitness_keywords):
            return "fitness"
        if contains_any(quit_keywords):
            return "quit"
        if contains_any(wellness_keywords):
            return "wellness"
        return "general"

    def _frequency_multiplier(self, frequency: str) -> float:
        frequency = (frequency or "daily").lower()
        if frequency == "daily":
            return 1.0
        if frequency == "weekly":
            return 0.75
        if frequency == "monthly":
            return 0.6
        return 1.0

    def _target_multiplier(self, target_count: int) -> float:
        if target_count <= 1:
            return 1.0
        return min(1.7, 1.0 + (target_count - 1) * 0.15)

    def _apply_heuristics(
        self,
        name: str,
        description: Optional[str],
        frequency: str,
        target_count: int,
        coins: int,
        intelligence: int
    ) -> Tuple[int, int]:
        category = self._categorize_habit(name, description)
        freq_mult = self._frequency_multiplier(frequency)
        target_mult = self._target_multiplier(target_count)

        def boost(base_coins: int, base_intel: int) -> Tuple[int, int]:
            adjusted_coins = int(round(base_coins * freq_mult * target_mult))
            adjusted_intel = int(round(base_intel * freq_mult))
            return adjusted_coins, adjusted_intel

        suggested_coins = coins
        suggested_intel = intelligence

        if category == "learning":
            base_coins, base_intel = boost(32, 12)
            suggested_coins = max(coins, base_coins)
            suggested_intel = max(intelligence, base_intel)
        elif category == "fitness":
            base_coins, base_intel = boost(24, 7)
            suggested_coins = max(coins, base_coins)
            suggested_intel = max(intelligence, base_intel)
        elif category == "quit":
            base_coins, base_intel = boost(20, 5)
            suggested_coins = max(coins, base_coins)
            suggested_intel = max(intelligence, base_intel)
        elif category == "wellness":
            base_coins, base_intel = boost(15, 4)
            suggested_coins = max(coins, base_coins)
            suggested_intel = max(intelligence, base_intel)
        else:  # general
            base_coins, base_intel = boost(10, 3)
            suggested_coins = max(coins, base_coins)
            suggested_intel = max(intelligence, base_intel)

        return suggested_coins, suggested_intel

    def _adjust_satisfaction(
        self,
        name: str,
        description: Optional[str],
        frequency: str,
        target_count: int,
        coins: int,
        intelligence: int,
        raw_satisfaction: int
    ) -> int:
        if coins <= 0:
            return 0

        category = self._categorize_habit(name, description)
        freq_mult = self._frequency_multiplier(frequency)
        target_mult = self._target_multiplier(target_count)

        baseline_from_coins = int(round(coins * 0.35))
        category_floor = {
            "learning": 12,
            "fitness": 11,
            "quit": 14,
            "wellness": 10,
            "general": 8
        }.get(category, 8)

        scaled_floor = int(round(category_floor * freq_mult * target_mult))
        satisfaction = max(raw_satisfaction, baseline_from_coins, scaled_floor)

        if intelligence >= 10:
            satisfaction = max(satisfaction, int(round(intelligence * 1.2)))

        if coins >= 30:
            satisfaction = max(satisfaction, 16)

        satisfaction = max(satisfaction, 6)
        return satisfaction

