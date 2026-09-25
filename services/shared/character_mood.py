"""
Настроение и стадия роста персонажа — единые правила для бэкенда, бота и фронтенда.
Фронтенд дублирует пороги в features/character/mood.js.
"""
from typing import Tuple

MOODS = (
    (85, "ecstatic", "в восторге"),
    (65, "happy", "доволен"),
    (40, "neutral", "спокоен"),
    (20, "sad", "грустит"),
    (0, "depressed", "подавлен"),
)

GROWTH_STAGES = (
    (6, "adult", "взрослый"),
    (3, "teen", "подросток"),
    (1, "baby", "малыш"),
)


def mood_from_satisfaction(satisfaction: int) -> Tuple[str, str]:
    value = max(0, min(100, int(satisfaction or 0)))
    for threshold, code, label in MOODS:
        if value >= threshold:
            return code, label
    return MOODS[-1][1], MOODS[-1][2]


def growth_stage(level: int) -> Tuple[str, str]:
    value = max(1, int(level or 1))
    for threshold, code, label in GROWTH_STAGES:
        if value >= threshold:
            return code, label
    return GROWTH_STAGES[-1][1], GROWTH_STAGES[-1][2]


def mood_emoji(code: str) -> str:
    return {
        "ecstatic": "🤩",
        "happy": "😊",
        "neutral": "😐",
        "sad": "😔",
        "depressed": "😢",
    }.get(code, "🙂")
