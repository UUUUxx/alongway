from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from itertools import permutations, product
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
        use_real_route: bool = True,
    ) -> RouteEvaluationResult:
        groups = [
            sorted(
                [
                    candidate
                    for candidate in candidates_by_task.get(task.task_id, [])
                    if not self._is_after_destination(start, end, candidate.poi.to_location())
                ],
                key=lambda candidate: self._rough_candidate_key(candidate, request.preferences),
            )
            for task in tasks
        ]
        if not groups or any(not group for group in groups):
            return RouteEvaluationResult(plans=[], route_candidate_count=0)

        max_candidates = request.constraints.max_route_candidates
        candidate_combinations: list[tuple[EnrichedCandidate, ...]] = []
        all_combinations = list(product(*groups))
        # Deduplicate: skip combinations where same POI serves multiple tasks
        deduped_combinations: list[tuple[EnrichedCandidate, ...]] = []
        for combination in all_combinations:
            poi_ids = [c.poi.poi_id for c in combination]
            if len(poi_ids) != len(set(poi_ids)):
                continue  # Same POI reused for different tasks — skip
            deduped_combinations.append(combination)
        all_combinations = deduped_combinations if deduped_combinations else list(product(*groups))
        all_combinations.sort(
            key=lambda combination: self._rough_combination_key(
                combination,
                request.preferences,
                start=start,
                end=end,
            )
        )
        candidate_combinations = all_combinations[:max_candidates]

        plans: list[CandidatePlan] = []
        rejected_plans: list[CandidatePlan] = []
        used_fallback_route = False
        deadline = time.perf_counter() + timeout_seconds
        for index, combination in enumerate(candidate_combinations, start=1):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            ordered_combination = self._optimize_visit_order(start, end, combination)
            points = [start] + [candidate.poi.to_location() for candidate in ordered_combination] + [end]
            if use_real_route:
                try:
                    route = await asyncio.wait_for(
                        self.backend_client.calculate_route(points, request.travel_mode),
                        timeout=remaining,
                    )
                except Exception:
                    route = self._fallback_route(points, request.travel_mode)
                    used_fallback_route = True
            else:
                route = self._fallback_route(points, request.travel_mode)
            detour_distance = max(0, route.distance_meters - base_route.distance_meters)
            extra_time = max(0.0, route.duration_minutes - base_route.duration_minutes)
            estimated_cost = round(
                sum(candidate.deal.price for candidate in combination if candidate.deal),
                2,
            )

            plan = CandidatePlan(
                plan_id=f"plan_{index:03d}",
                stops=self._build_stops(start, end, ordered_combination),
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
    def _rough_candidate_key(candidate: EnrichedCandidate, preferences) -> tuple[float, float, float]:
        price = candidate.deal.price if candidate.deal else candidate.poi.cost
        rating = candidate.deal.rating if candidate.deal and candidate.deal.rating is not None else candidate.poi.rating
        sales = candidate.deal.monthly_sales if candidate.deal and candidate.deal.monthly_sales else 0
        price_key = price if price is not None else 9999
        rating_key = -(rating or 0)
        sales_key = -sales
        if preferences.prefer_low_price:
            return (price_key, rating_key, sales_key)
        if preferences.prefer_high_rating:
            return (rating_key, price_key, sales_key)
        if preferences.prefer_high_sales:
            return (sales_key, rating_key, price_key)
        return (rating_key, price_key, sales_key)

    @classmethod
    def _rough_combination_key(
        cls,
        combination: tuple[EnrichedCandidate, ...],
        preferences,
        start: Location | None = None,
        end: Location | None = None,
    ) -> tuple[float, float, float, float]:
        prices = [
            candidate.deal.price if candidate.deal else candidate.poi.cost
            for candidate in combination
            if (candidate.deal and candidate.deal.price is not None) or candidate.poi.cost is not None
        ]
        ratings = [
            candidate.deal.rating if candidate.deal and candidate.deal.rating is not None else candidate.poi.rating
            for candidate in combination
            if (candidate.deal and candidate.deal.rating is not None) or candidate.poi.rating is not None
        ]
        sales = [
            candidate.deal.monthly_sales or 0
            for candidate in combination
            if candidate.deal is not None
        ]
        total_price = sum(prices) if prices else 9999
        avg_rating = sum(ratings) / len(ratings) if ratings else 0
        max_sales = max(sales, default=0)
        route_distance = (
            cls._shortest_order_distance(start, end, combination)
            if start is not None and end is not None and preferences.prefer_less_detour
            else 0.0
        )
        if preferences.prefer_low_price:
            return (total_price, route_distance, -avg_rating, -max_sales)
        if preferences.prefer_high_rating:
            return (-avg_rating, route_distance, total_price, -max_sales)
        if preferences.prefer_high_sales:
            return (-max_sales, route_distance, -avg_rating, total_price)
        return (route_distance, -avg_rating, total_price, -max_sales)

    @classmethod
    def _optimize_visit_order(
        cls,
        start: Location,
        end: Location,
        candidates: tuple[EnrichedCandidate, ...],
    ) -> tuple[EnrichedCandidate, ...]:
        if len(candidates) <= 1:
            return candidates
        best_order = candidates
        best_distance = cls._path_distance([start] + [c.poi.to_location() for c in candidates] + [end])

        if len(candidates) <= 6:
            candidate_orders = permutations(candidates)
        else:
            candidate_orders = [cls._nearest_neighbor_order(start, end, candidates)]

        for order in candidate_orders:
            distance = cls._path_distance([start] + [c.poi.to_location() for c in order] + [end])
            if distance < best_distance:
                best_distance = distance
                best_order = order
        return tuple(best_order)

    @classmethod
    def _shortest_order_distance(
        cls,
        start: Location,
        end: Location,
        candidates: tuple[EnrichedCandidate, ...],
    ) -> float:
        ordered = cls._optimize_visit_order(start, end, candidates)
        return cls._path_distance([start] + [c.poi.to_location() for c in ordered] + [end])

    @classmethod
    def _nearest_neighbor_order(
        cls,
        start: Location,
        end: Location,
        candidates: tuple[EnrichedCandidate, ...],
    ) -> tuple[EnrichedCandidate, ...]:
        remaining = list(candidates)
        current = start
        ordered: list[EnrichedCandidate] = []
        while remaining:
            next_index = min(
                range(len(remaining)),
                key=lambda index: (
                    cls._location_distance(current, remaining[index].poi.to_location())
                    + cls._location_distance(remaining[index].poi.to_location(), end) * 0.15
                ),
            )
            next_candidate = remaining.pop(next_index)
            ordered.append(next_candidate)
            current = next_candidate.poi.to_location()
        return tuple(ordered)

    @classmethod
    def _path_distance(cls, points: list[Location]) -> float:
        return sum(
            cls._location_distance(start, end)
            for start, end in zip(points, points[1:])
        )

    @classmethod
    def _location_distance(cls, start: Location, end: Location) -> float:
        return cls._haversine_meters(
            start.longitude or 0,
            start.latitude or 0,
            end.longitude or 0,
            end.latitude or 0,
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

    @classmethod
    def _is_after_destination(
        cls,
        start: Location,
        end: Location,
        poi: Location,
    ) -> bool:
        if not start.has_coordinates() or not end.has_coordinates() or not poi.has_coordinates():
            return False
        if cls._haversine_meters(
            end.longitude or 0,
            end.latitude or 0,
            poi.longitude or 0,
            poi.latitude or 0,
        ) <= 200:
            return False

        sx, sy = start.longitude or 0, start.latitude or 0
        ex, ey = end.longitude or 0, end.latitude or 0
        px, py = poi.longitude or 0, poi.latitude or 0
        dx, dy = ex - sx, ey - sy
        length_squared = dx * dx + dy * dy
        if length_squared <= 0:
            return False
        projection = ((px - sx) * dx + (py - sy) * dy) / length_squared
        return projection > 1.20  # Allow POIs slightly past destination for realistic routing

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

    # Road-network circuity factor: real path ≈ Haversine × factor
    _CIRCUITY_FACTOR = {
        "walking": 1.35,
        "bicycling": 1.25,
        "driving": 1.30,
    }

    @staticmethod
    def _fallback_route(points: list[Location], travel_mode: str) -> RouteResult:
        speed = {
            "walking": 75.0,
            "bicycling": 180.0,
            "driving": 420.0,
        }.get(travel_mode, 75.0)
        circuity = RouteEvaluator._CIRCUITY_FACTOR.get(travel_mode, 1.30)
        total = 0
        segments: list[RouteSegment] = []
        for start, end in zip(points, points[1:]):
            haversine_dist = RouteEvaluator._haversine_meters(
                start.longitude or 0,
                start.latitude or 0,
                end.longitude or 0,
                end.latitude or 0,
            )
            distance = int(round(haversine_dist * circuity))
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
