from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.models import (
    CandidatePlan,
    Deal,
    Location,
    POI,
    PlanConstraints,
    PlanStop,
    RouteResult,
    StopType,
    UserPreferences,
)
from agent.scorer import PlanScorer


def _plan(
    plan_id: str,
    detour: int,
    extra_time: float,
    cost: float,
    rating: float = 4.6,
    monthly_sales: int = 300,
) -> CandidatePlan:
    poi = POI(
        poi_id=f"poi_{plan_id}",
        name=f"候选{plan_id}",
        type="drink",
        longitude=114.12,
        latitude=30.45,
        rating=rating,
        source_keyword="奶茶",
    )
    deal = Deal(
        poi_id=poi.poi_id,
        name=poi.name,
        category="奶茶",
        deal_id=f"deal_{plan_id}",
        deal_title="饮品套餐",
        price=cost,
        rating=rating,
        monthly_sales=monthly_sales,
    )
    return CandidatePlan(
        plan_id=plan_id,
        stops=[
            PlanStop(
                order=1,
                stop_type=StopType.START,
                name="起点",
                location=Location(name="起点", longitude=114.1, latitude=30.4),
            ),
            PlanStop(
                order=2,
                stop_type=StopType.DEAL,
                task_id="task_1",
                name=poi.name,
                location=poi.to_location(),
                poi=poi,
                deal=deal,
                is_open=True,
            ),
            PlanStop(
                order=3,
                stop_type=StopType.END,
                name="终点",
                location=Location(name="终点", longitude=114.2, latitude=30.5),
            ),
        ],
        route=RouteResult(
            distance_meters=1000 + detour,
            duration_minutes=12 + extra_time,
            polyline=[],
        ),
        base_distance_meters=1000,
        base_duration_minutes=12,
        detour_distance_meters=detour,
        extra_time_minutes=extra_time,
        estimated_cost=cost,
    )


def test_scorer_prefers_less_detour_when_requested() -> None:
    plans = [
        _plan("A", detour=50, extra_time=1, cost=19),
        _plan("B", detour=450, extra_time=5, cost=2),
        _plan("C", detour=250, extra_time=3, cost=10),
    ]
    ranked = PlanScorer().rank_plans(
        plans,
        UserPreferences(prefer_less_detour=True, prefer_low_price=False),
        PlanConstraints(),
        budget=20,
    )

    assert ranked[0].plan_id == "A"


def test_scorer_prefers_low_price_when_requested() -> None:
    plans = [
        _plan("A", detour=50, extra_time=1, cost=19),
        _plan("B", detour=450, extra_time=5, cost=2),
        _plan("C", detour=250, extra_time=3, cost=10),
    ]
    ranked = PlanScorer().rank_plans(
        plans,
        UserPreferences(prefer_less_detour=False, prefer_low_price=True),
        PlanConstraints(),
        budget=20,
    )

    assert ranked[0].plan_id == "B"


def test_scorer_prefers_high_rating_when_requested() -> None:
    plans = [
        _plan("A", detour=100, extra_time=1, cost=10, rating=3.2),
        _plan("B", detour=100, extra_time=1, cost=10, rating=4.9),
    ]
    ranked = PlanScorer().rank_plans(
        plans,
        UserPreferences(prefer_less_detour=False, prefer_high_rating=True),
        PlanConstraints(),
        budget=30,
    )

    assert ranked[0].plan_id == "B"


def test_scorer_prefers_high_sales_when_requested() -> None:
    plans = [
        _plan("A", detour=100, extra_time=1, cost=10, monthly_sales=30),
        _plan("B", detour=100, extra_time=1, cost=10, monthly_sales=900),
    ]
    ranked = PlanScorer().rank_plans(
        plans,
        UserPreferences(prefer_less_detour=False, prefer_high_sales=True),
        PlanConstraints(),
        budget=30,
    )

    assert ranked[0].plan_id == "B"


def test_scorer_prefers_fast_arrival_when_requested() -> None:
    plans = [
        _plan("A", detour=120, extra_time=1, cost=15),
        _plan("B", detour=80, extra_time=10, cost=3),
    ]
    ranked = PlanScorer().rank_plans(
        plans,
        UserPreferences(prefer_less_detour=False, prefer_low_price=False, prefer_fast_arrival=True),
        PlanConstraints(max_extra_time_minutes=15),
        budget=20,
    )

    assert ranked[0].plan_id == "A"
