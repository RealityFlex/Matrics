import asyncio
from typing import Tuple

from services.task_service.ai_evaluator import TaskComplexityEvaluator


class ChallengeRewardEvaluator:
    """
    Обертка над TaskComplexityEvaluator для расчета награды за челлендж.
    Награда рассчитывается аналогично задачам: монеты (0-50) и интеллект (0-15).
    """

    def __init__(self) -> None:
        self._task_evaluator = TaskComplexityEvaluator()

    async def evaluate_rewards(
        self,
        metric_type: str,
        target_value: int,
        deadline_iso: str,
        challenger_name: str,
        opponent_name: str,
    ) -> Tuple[int, int]:
        """
        Вычисляет награду в монетах и интеллекте.
        """
        title = f"Челлендж по метрике {metric_type}"
        description = (
            f"Участники {challenger_name} и {opponent_name} соревнуются, чтобы достичь {target_value} "
            f"по метрике {metric_type} до {deadline_iso}. "
            "Награда должна отражать сложность и полезность такого челленджа."
        )

        coins_task = self._task_evaluator.evaluate_task_complexity(title=title, description=description)
        intellect_task = self._task_evaluator.evaluate_intelligence_reward(title=title, description=description)

        coins, intellect = await asyncio.gather(coins_task, intellect_task)
        return coins, intellect

