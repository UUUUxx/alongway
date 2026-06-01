from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from itertools import product
from typing import List

from agent.backend_client import BackendClient
from agent.models import (
    CandidatePlan,
    EnrichedCandidate,
    Location,
    PlanRequest,
    PlanStop,
    RouteResult,
    RouteSegment,
    StopType,
    TaskSpec,
)


@dataclass
class RouteEvaluationResult:
    plans: List[CandidatePlan]
    route_candidate_count: int
    used_fallback_route: bool = False
    relaxed_constraints_used: bool = False


class RouteEvaluator:
    def __init__(self, backend_client: BackendClient) -> None:
        self.backend_client = backend_client

    async def evaluate(
        self,
        request: PlanRequest,
        start: Location,
        end: Location,
        tasks: list[TaskSpec],
        candidates_by_task: dict[str, list[EnrichedCandidate]],
        base_route: RouteResult,
        timeout_seconds: float = 3.0,
    ) -> RouteEvaluationResult:
        groups = [
            sorted(candidates_by_task.get(task.task_id, []), key=self._rough_candidate_key)
            for task in tasks
        ]
        if not groups or any(not group for group in groups):
            return RouteEvaluationResult(plans=[], route_candidate_count=0)

        max_candidates = request.constraints.max_route_candidates
        candidate_combinations: list[tuple[EnrichedCandidate, ...]] = []
        for combination in product(*groups):
            candidate_combinations.append(combination)
            if len(candidate_combinations) >= max_candidates:
                break

        plans: list[CandidatePlan] = []
        rejected_plans: list[CandidatePlan] = []
        used_fallback_route = False
        deadline = time.perf_counter() + timeout_seconds
        for index, combination in enumerate(candidate_combinations, start=1):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            points = [start] + [candidate.poi.to_location() for candidate in combination] + [end]
            try:
                route = await asyncio.wait_for(
                    self.backend_client.calculate_route(points, request.travel_mode),
                    timeout=remaining,
                )
            except Exception:
                route = self._fallback_route(points, request.travel_mode)
                used_fallback_route = True
            detour_distance = max(0, route.distance_meters - base_route.distance_meters)
            extra_time = max(0.0, route.duration_minutes - base_route.duration_minutes)
            estimated_cost = round(
                sum(candidate.deal.price for candidate in combination if candidate.deal),
                2,
            )

            plan = CandidatePlan(
                plan_id=f"plan_{index:03d}",
                stops=self._build_stops(start, end, combination),
                route=route,
                base_distance_meters=base_route.distance_meters,
                base_duration_minutes=base_route.duration_minutes,
                detour_distance_meters=detour_distance,
                extra_time_minutes=round(extra_time, 1),
                estimated_cost=estimated_cost,
            )

            if self._passes_constraints(plan, request):
                plans.append(plan)
            else:
                rejected_plans.append(plan)

        relaxed_constraints_used = False
        if not plans and rejected_plans:
            rejected_plans.sort(key=lambda plan: self._constraint_overage_key(plan, request))
            plans = rejected_plans[: min(3, len(rejected_plans))]
            relaxed_constraints_used = True

        return RouteEvaluationResult(
            plans=plans,
            route_candidate_count=len(candidate_combinations),
            used_fallback_route=used_fallback_route,
            relaxed_constraints_used=relaxed_constraints_used,
        )

    @staticmethod
    def _rough_candidate_key(candidate: EnrichedCandidate) -> tuple[float, float, float]:
        price = candidate.deal.price if candidate.deal else candidate.poi.cost
        return (
            -(candidate.poi.rating or 0),
            price if price is not None else 9999,
            -(candidate.deal.monthly_sales if candidate.deal and candidate.deal.monthly_sales else 0),
        )

    @staticmethod
    def _build_stops(
        start: Location,
        end: Location,
        candidates: tuple[EnrichedCandidate, ...],
    ) -> list[PlanStop]:
        stops = [
            PlanStop(
                order=1,
                stop_type=StopType.START,
                name=start.name or "起点",
                location=start,
                reason="出发点",
            )
        ]

        for offset, candidate in enumerate(candidates, start=2):
            stops.append(
                PlanStop(
                    order=offset,
                    stop_type=StopType.DEAL if candidate.deal else StopType.TASK,
                    task_id=candidate.task_id,
                    name=candidate.poi.name,
                    location=candidate.poi.to_location(),
                    poi=candidate.poi,
                    deal=candidate.deal,
                    is_open=candidate.is_open,
                    availability_reasons=candidate.filter_reasons,
                )
            )

        stops.append(
            PlanStop(
                order=len(stops) + 1,
                stop_type=StopType.END,
                name=end.name or "终点",
                location=end,
                reason="目的地",
            )
        )
        return stops

    @staticmethod
    def _passes_constraints(plan: CandidatePlan, request: PlanRequest) -> bool:
        if plan.detour_distance_meters > request.constraints.max_detour_meters:
            return False
        if plan.extra_time_minutes > request.constraints.max_extra_time_minutes:
            return False
        if request.budget is not None and plan.estimated_cost > request.budget:
            return False
        return True

    @staticmethod
    def _constraint_overage_key(plan: CandidatePlan, request: PlanRequest) -> tuple[float, float, float]:
        detour_over = max(
            0,
            plan.detour_distance_meters - request.constraints.max_detour_meters,
        )
        time_over = max(
            0.0,
            plan.extra_time_minutes - request.constraints.max_extra_time_minutes,
        )
        budget_over = (
            max(0.0, plan.estimated_cost - request.budget)
            if request.budget is not None
            else 0.0
        )
        return (detour_over / 1000, time_over / 10, budget_over / 10)

    @staticmethod
    def _fallback_route(points: list[Location], travel_mode: str) -> RouteResult:
        speed = {
            "walking": 75.0,
            "bicycling": 180.0,
            "driving": 420.0,
        }.get(travel_mode, 75.0)
        total = 0
        segments: list[RouteSegment] = []
        for start, end in zip(points, points[1:]):
            distance = int(
                round(
                    RouteEvaluator._haversine_meters(
                        start.longitude or 0,
                        start.latitude or 0,
                        end.longitude or 0,
                        end.latitude or 0,
                    )
                )
            )
            total += distance
            segments.append(
                RouteSegment(
                    from_name=start.name or "start",
                    to_name=end.name or "end",
                    distance_meters=distance,
                    duration_minutes=round(distance / speed, 1),
                )
            )
        return RouteResult(
            distance_meters=total,
            duration_minutes=round(total / speed, 1),
            polyline=[
                [point.longitude or 0, point.latitude or 0]
                for point in points
                if point.has_coordinates()
            ],
            segments=segments,
        )

    @staticmethod
    def _haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        earth_radius = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
