from __future__ import annotations

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
    StopType,
    TaskSpec,
)


@dataclass
class RouteEvaluationResult:
    plans: List[CandidatePlan]
    route_candidate_count: int


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
        for index, combination in enumerate(candidate_combinations, start=1):
            points = [start] + [candidate.poi.to_location() for candidate in combination] + [end]
            route = await self.backend_client.calculate_route(points, request.travel_mode)
            detour_distance = max(0, route.distance_meters - base_route.distance_meters)
            extra_time = max(0.0, route.duration_minutes - base_route.duration_minutes)
            estimated_cost = round(
                sum(candidate.deal.price for candidate in combination if candidate.deal),
                2,
            )

            if detour_distance > request.constraints.max_detour_meters:
                continue
            if extra_time > request.constraints.max_extra_time_minutes:
                continue
            if request.budget is not None and estimated_cost > request.budget:
                continue

            plans.append(
                CandidatePlan(
                    plan_id=f"plan_{index:03d}",
                    stops=self._build_stops(start, end, combination),
                    route=route,
                    base_distance_meters=base_route.distance_meters,
                    base_duration_minutes=base_route.duration_minutes,
                    detour_distance_meters=detour_distance,
                    extra_time_minutes=round(extra_time, 1),
                    estimated_cost=estimated_cost,
                )
            )

        return RouteEvaluationResult(
            plans=plans,
            route_candidate_count=len(candidate_combinations),
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
