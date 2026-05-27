from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.intent_parser import IntentParser
from agent.llm_client import MockLLMClient
from agent.models import TaskType, UserPreferences


def test_intent_parser_extracts_express_and_drink_tasks() -> None:
    parser = IntentParser(MockLLMClient())

    intent = asyncio.run(
        parser.parse(
            "我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶。",
            budget=None,
            preferences=UserPreferences(),
        )
    )

    task_types = {task.type for task in intent.tasks}
    drink_task = next(task for task in intent.tasks if task.type == TaskType.BUY_DRINK)

    assert len(intent.tasks) == 2
    assert TaskType.PICKUP_EXPRESS in task_types
    assert TaskType.BUY_DRINK in task_types
    assert "奶茶" in drink_task.source_keywords
    assert drink_task.budget == 20
    assert intent.budget == 20
