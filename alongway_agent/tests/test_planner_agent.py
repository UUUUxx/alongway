from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.backend_client import MockBackendClient
from agent.llm_client import LLMClient, MockLLMClient
from agent.models import Location, PlanRequest, StopType, UserPreferences
from agent.planner_agent import PlanAgent


class FailingLLMClient(LLMClient):
    async def parse_intent(self, user_query, budget, preferences):
        raise TimeoutError("llm timeout")

    async def generate_explanation(self, user_query, selected_plan, alternative_plans):
        return None


def test_planner_agent_returns_valid_plan_with_mock_backend() -> None:
    request = PlanRequest(
        request_id="req_001",
        user_query="我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。",
        start_location=Location(
            name="学生宿舍",
            address="某大学学生宿舍",
            location="宿舍区",
            longitude=114.123,
            latitude=30.456,
        ),
        end_location=Location(
            name="图书馆",
            address="某大学图书馆",
            location="教学区",
            longitude=114.128,
            latitude=30.462,
        ),
        city="武汉",
        travel_mode="walking",
        budget=20,
        departure_time=datetime(2026, 5, 22, 12, 0, 0),
        preferences=UserPreferences(prefer_less_detour=True, prefer_low_price=True),
    )
    agent = PlanAgent(
        backend_client=MockBackendClient(),
        llm_client=MockLLMClient(),
    )

    response = asyncio.run(agent.plan(request))

    assert response.success is True
    assert response.selected_plan is not None
    stop_types = {stop.stop_type for stop in response.selected_plan.stops}
    assert StopType.START in stop_types
    assert StopType.END in stop_types
    assert StopType.TASK in stop_types or StopType.DEAL in stop_types
    assert response.selected_plan.estimated_cost <= 20
    assert response.selected_plan.detour_distance_meters <= request.constraints.max_detour_meters
    assert response.summary


def test_planner_agent_falls_back_and_uses_current_location() -> None:
    request = PlanRequest(
        request_id="req_current_location",
        user_query="到图书馆，路上取快递",
        current_location=Location(
            name="学生宿舍",
            longitude=114.123,
            latitude=30.456,
        ),
        city="武汉",
        travel_mode="walking",
        preferences=UserPreferences(prefer_less_detour=True),
    )
    agent = PlanAgent(
        backend_client=MockBackendClient(),
        llm_client=FailingLLMClient(),
        llm_timeout_seconds=0.1,
    )

    response = asyncio.run(agent.plan(request))

    assert response.success is True
    assert "LLM_FALLBACK_USED" not in response.warnings
    assert response.selected_plan is not None
    assert response.selected_plan.stops[0].name == "学生宿舍"
    assert response.selected_plan.stops[-1].name == "图书馆"


def test_search_center_prefers_destination_for_low_detour() -> None:
    start = Location(name="华中科技大学", longitude=114.4148, latitude=30.5159)
    end = Location(name="世界城广场", longitude=114.4036, latitude=30.5068)

    center = PlanAgent._search_center(start, end, prefer_destination=True)

    assert center.longitude == end.longitude
    assert center.latitude == end.latitude
