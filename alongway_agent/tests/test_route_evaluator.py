from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.backend_client import BackendClient
from agent.models import (
    EnrichedCandidate,
    Location,
    PlanConstraints,
    PlanRequest,
    POI,
    RouteResult,
    TaskSpec,
    TaskType,
)
from agent.route_evaluator import RouteEvaluator


class FailingRouteBackend(BackendClient):
    async def search_pois(self, source_keywords, center, radius_meters, limit, specific_place_name=None):
        return []

    async def search_deals(self, poi_id, categories, max_price, limit):
        return []

    async def calculate_route(self, points, travel_mode):
        raise TimeoutError("route timeout")

    async def geocode(self, address, city, limit=3):
        return []


def test_route_evaluator_keeps_candidate_when_real_route_fails() -> None:
    start = Location(name="Wuda", longitude=114.3645, latitude=30.5378)
    end = Location(name="Guanggu", longitude=114.4030, latitude=30.5054)
    poi = POI(
        poi_id="mock_food",
        name="Food",
        type="food",
        longitude=114.3695,
        latitude=30.5196,
        rating=4.2,
        cost=12,
        source_keyword="food",
    )
    task = TaskSpec(
        task_id="task_1",
        type=TaskType.EAT_MEAL,
        raw_text="food",
        source_keywords=["food"],
        category="food",
    )
    request = PlanRequest(
        request_id="req_route_fallback",
        user_query="from wuda to guanggu find food",
        constraints=PlanConstraints(max_detour_meters=10_000, max_extra_time_minutes=120),
    )
    evaluator = RouteEvaluator(FailingRouteBackend())

    result = asyncio.run(
        evaluator.evaluate(
            request=request,
            start=start,
            end=end,
            tasks=[task],
            candidates_by_task={
                task.task_id: [
                    EnrichedCandidate(
                        task_id=task.task_id,
                        task_type=task.type,
                        poi=poi,
                    )
                ]
            },
            base_route=RouteResult(distance_meters=5000, duration_minutes=70, polyline=[]),
            timeout_seconds=0.1,
        )
    )

    assert result.plans
    assert result.used_fallback_route is True
    assert result.plans[0].stops[1].name == "Food"


def test_route_evaluator_returns_best_candidate_when_constraints_are_too_strict() -> None:
    start = Location(name="A", longitude=114.0, latitude=30.0)
    end = Location(name="B", longitude=114.02, latitude=30.0)
    poi = POI(
        poi_id="poi_far",
        name="Far Food",
        type="food",
        longitude=114.01,
        latitude=30.03,
        source_keyword="food",
    )
    task = TaskSpec(
        task_id="task_1",
        type=TaskType.EAT_MEAL,
        raw_text="food",
        source_keywords=["food"],
        category="food",
    )
    request = PlanRequest(
        request_id="req_relaxed",
        user_query="find food",
        constraints=PlanConstraints(max_detour_meters=1, max_extra_time_minutes=1),
    )
    evaluator = RouteEvaluator(FailingRouteBackend())

    result = asyncio.run(
        evaluator.evaluate(
            request=request,
            start=start,
            end=end,
            tasks=[task],
            candidates_by_task={
                task.task_id: [
                    EnrichedCandidate(
                        task_id=task.task_id,
                        task_type=task.type,
                        poi=poi,
                    )
                ]
            },
            base_route=RouteResult(distance_meters=1000, duration_minutes=10, polyline=[]),
            timeout_seconds=0.1,
        )
    )

    assert result.plans
    assert result.relaxed_constraints_used is True
