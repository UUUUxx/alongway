from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.intent_parser import IntentParser
from agent.llm_client import LLMClient, MockLLMClient
from agent.models import TaskType, UserPreferences


class StaticLLMClient(LLMClient):
    def __init__(self, payload=None, exc: Exception | None = None) -> None:
        self.payload = payload
        self.exc = exc

    async def parse_intent(self, user_query, budget, preferences):
        if self.exc:
            raise self.exc
        return self.payload

    async def generate_explanation(self, user_query, selected_plan, alternative_plans):
        return None


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


def test_intent_parser_uses_llm_structured_result() -> None:
    parser = IntentParser(
        StaticLLMClient(
            {
                "start_text": None,
                "end_text": "主图书馆",
                "budget": 30,
                "preferences": UserPreferences(prefer_low_price=True).model_dump(),
                "tasks": [
                    {
                        "type": "buy_drink",
                        "raw_text": "喝星巴克",
                        "category": "drink",
                        "specific_place_name": "星巴克",
                        "source_keywords": ["星巴克", "咖啡", "饮品"],
                        "required": True,
                    }
                ],
            }
        )
    )

    result = asyncio.run(
        parser.parse_with_metadata(
            "到主图书馆，路上想喝星巴克",
            budget=None,
            preferences=UserPreferences(),
        )
    )

    assert result.used_fallback is False
    assert result.intent.end_text == "主图书馆"
    assert result.intent.tasks[0].specific_place_name == "星巴克"
    assert result.intent.tasks[0].source_keywords[0] == "星巴克"


def test_intent_parser_falls_back_when_llm_fails() -> None:
    parser = IntentParser(StaticLLMClient(exc=RuntimeError("boom")))

    result = asyncio.run(
        parser.parse_with_metadata(
            "到主图书馆，路上想吃韩餐",
            budget=None,
            preferences=UserPreferences(),
        )
    )

    assert result.used_fallback is True
    assert result.intent.end_text == "主图书馆"
    assert result.intent.tasks[0].category == "food"
    assert "韩餐" in result.intent.tasks[0].source_keywords


def test_fallback_parser_handles_wuda_guanggu_food_query() -> None:
    parser = IntentParser(MockLLMClient())

    result = asyncio.run(
        parser.parse_with_metadata(
            "从武大去光谷，顺路找点吃的",
            budget=None,
            preferences=UserPreferences(),
        )
    )

    assert result.intent.start_text == "武大"
    assert result.intent.end_text == "光谷"
    assert result.intent.tasks
    assert result.intent.tasks[0].category == "food"
