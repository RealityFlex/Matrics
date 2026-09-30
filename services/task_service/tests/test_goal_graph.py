from services.task_service.ai_evaluator import TaskComplexityEvaluator
from services.task_service.goal_graph import sanitize_breakdown


def test_sanitize_reindexes_and_fills_chain():
    tasks = sanitize_breakdown([
        {"title": "A", "depends_on": []},
        {"title": "B", "depends_on": [99]},
        {"title": "C", "depends_on": [0, 1]},
    ])
    assert [item["order_index"] for item in tasks] == [0, 1, 2]
    assert tasks[0]["depends_on"] == []
    assert tasks[1]["depends_on"] == [0]
    assert tasks[2]["depends_on"] == [0, 1]


def test_fallback_breakdown_has_a_branch():
    evaluator = TaskComplexityEvaluator()
    tasks = evaluator._build_fallback_tasks("Сдать курсовую", "По базам данных", 4, 6)
    assert len(tasks) == 4
    assert tasks[0]["depends_on"] == []
    assert tasks[1]["depends_on"] == [0]
    assert tasks[2]["depends_on"] == [0]
    assert tasks[3]["depends_on"] == [1, 2]
