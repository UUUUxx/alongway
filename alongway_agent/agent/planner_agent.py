from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Optional

from agent.backend_client import BackendClient, MockBackendClient
from agent.candidate_generator import CandidateGenerator
from agent.exceptions import AgentError, ErrorCode
from agent.explainer import Explainer
from agent.haversine_filter import HaversinePreFilter
from agent.intent_parser import IntentParser
from agent.llm_client import LLMClient, MockLLMClient
from agent.models import (
    AlternativePlanSummary,
    DebugTrace,
    EnrichedCandidate,
    Location,
    PlanRequest,
    PlanResponse,
    PlanConstraints,
    RouteResult,
    RouteSegment,
)
from agent.perf_logger import PerfMetrics
from agent.route_evaluator import RouteEvaluator
from agent.scorer import PlanScorer

logger = logging.getLogger(__name__)


class PlanAgent:
    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
        llm_client: Optional[LLMClient] = None,
        llm_timeout_seconds: float = 3.0,
        poi_timeout_seconds: float = 3.0,
        route_timeout_seconds: float = 3.0,
        # ── v2 parameters ──
        v2_enabled: bool = True,
        haversine_filter: Optional[HaversinePreFilter] = None,
        llm_cache: Optional[object] = None,
        rule_first: bool = True,
    ) -> None:
        self.backend_client = backend_client or MockBackendClient()
        self.llm_client = llm_client or MockLLMClient()
        self.intent_parser = IntentParser(
            self.llm_client,
            llm_timeout_seconds,
            rule_first=rule_first,
            llm_cache=llm_cache,
        )
        self.candidate_generator = CandidateGenerator(self.backend_client)
        self.route_evaluator = RouteEvaluator(self.backend_client)
        self.scorer = PlanScorer()
        self.explainer = Explainer(self.llm_client)
        self.poi_timeout_seconds = poi_timeout_seconds
        self.route_timeout_seconds = route_timeout_seconds
        self.v2_enabled = v2_enabled
        self.haversine_filter = haversine_filter

    async def plan(self, request: PlanRequest) -> PlanResponse:
        total_started = time.perf_counter()
        timings: dict[str, int] = {}
        metrics = PerfMetrics(request_id=request.request_id or "unknown")
        metrics.start()

        try:
            self._validate_user_query(request)

            parse_result = await self.intent_parser.parse_with_metadata(
                user_query=request.user_query,
                budget=request.budget,
                preferences=request.preferences,
            )
            intent = parse_result.intent
            timings["llm_ms"] = parse_result.llm_ms
            metrics.intent_parse_ms = parse_result.llm_ms
            metrics.llm_called = parse_result.llm_called
            metrics.llm_cache_hit = parse_result.cache_hit
            metrics.rule_parse_used = parse_result.used_fallback

            start, end = await asyncio.gather(
                self._resolve_start(request, intent.start_text),
                self._resolve_end(request, intent.end_text),
            )
            self._validate_locations(start, end)

            if not intent.tasks:
                raise AgentError(
                    ErrorCode.NO_TASK_PARSED,
                    "没有解析出顺路任务。",
                    fallback_suggestions=["可以说明想顺路完成的事项，例如取快递、买奶茶或吃饭。"],
                )

            center = self._search_center(start, end)
            route_started = time.perf_counter()
            poi_started = time.perf_counter()
            base_route_task = asyncio.create_task(
                self._calculate_route_with_timeout(
                    [start, end],
                    request.travel_mode,
                    self.route_timeout_seconds,
                )
            )
            candidate_task = asyncio.create_task(
                self.candidate_generator.generate(
                    intent=intent,
                    request=request,
                    center=center,
                    timeout_seconds=self.poi_timeout_seconds,
                )
            )
            base_route, candidate_result = await asyncio.gather(
                base_route_task,
                candidate_task,
            )
            timings["base_route_ms"] = int((time.perf_counter() - route_started) * 1000)
            timings["poi_ms"] = int((time.perf_counter() - poi_started) * 1000)
            metrics.base_route_ms = timings["base_route_ms"]
            metrics.poi_candidates_total = candidate_result.poi_candidate_count
            metrics.task_count = len(intent.tasks)

            # ── v2: Haversine pre-filter ──
            candidates_by_task = candidate_result.candidates_by_task
            if self.v2_enabled and self.haversine_filter is not None:
                filtered = self.haversine_filter.filter(start, end, candidates_by_task)
                haversine_count = sum(len(v) for v in filtered.values())
                metrics.haversine_topk_used = True
                metrics.haversine_topk_count = haversine_count
                # Unwrap filtered candidates back to EnrichedCandidate lists
                candidates_by_task = {
                    task_id: [fc.candidate for fc in fcs]
                    for task_id, fcs in filtered.items()
                }

            route_started = time.perf_counter()
            route_result = await self.route_evaluator.evaluate(
                request=request,
                start=start,
                end=end,
                tasks=intent.tasks,
                candidates_by_task=candidates_by_task,
                base_route=base_route,
                timeout_seconds=self.route_timeout_seconds,
            )
            timings["route_ms"] = int((time.perf_counter() - route_started) * 1000)
            metrics.amap_route_total_ms = timings["route_ms"]
            metrics.candidate_routes_evaluated = route_result.route_candidate_count

            # Estimate Amap route call count:
            # Each candidate route is a multi-point route: start→...→end
            # For N candidates, there are ~(poi_count_in_route) * N segments
            # The base route is 1 segment (start→end)
            # Approximate: base (1) + routes_evaluated * avg_points_per_route
            avg_points = sum(
                len(intent.tasks) for _ in range(route_result.route_candidate_count)
            ) if route_result.route_candidate_count > 0 else 0
            # Each evaluated route with k POIs = k+1 segments
            # With Haversine topk, routes have fewer POIs
            est_segments = 1 + route_result.route_candidate_count * (len(intent.tasks) + 1)
            metrics.amap_route_calls_count = est_segments

            relaxed_route_constraints = False

            if not route_result.plans and candidate_result.poi_candidate_count > 0:
                relaxed_request = request.model_copy(
                    update={
                        "constraints": request.constraints.model_copy(
                            update={
                                "max_detour_meters": max(request.constraints.max_detour_meters, 5000),
                                "max_extra_time_minutes": max(
                                    request.constraints.max_extra_time_minutes,
                                    60,
                                ),
                            }
                        )
                    }
                )
                route_result = await self.route_evaluator.evaluate(
                    request=relaxed_request,
                    start=start,
                    end=end,
                    tasks=intent.tasks,
                    candidates_by_task=candidates_by_task,
                    base_route=base_route,
                    timeout_seconds=self.route_timeout_seconds,
                )
                relaxed_route_constraints = bool(route_result.plans)
                metrics.candidate_routes_evaluated += route_result.route_candidate_count

            if not route_result.plans:
                raise AgentError(
                    ErrorCode.NO_VALID_PLAN,
                    "附近没有找到符合预算和绕路限制的方案。",
                    fallback_suggestions=[
                        "可以放宽预算",
                        "可以把最大绕路距离放宽到1200米",
                        "可以减少需要顺路完成的任务",
                    ],
                )

            ranked_plans = self.scorer.rank_plans(
                route_result.plans,
                intent.preferences,
                request.constraints,
                intent.budget if intent.budget is not None else request.budget,
            )
            selected_plan = ranked_plans[0]
            alternative_plans = [
                self._to_alternative_summary(plan) for plan in ranked_plans[1:4]
            ]
            summary = await self.explainer.explain(
                request,
                selected_plan,
                alternative_plans,
            )
            warnings = list(candidate_result.warnings)
            if relaxed_route_constraints or route_result.relaxed_constraints_used:
                warnings.append("RELAXED_ROUTE_CONSTRAINTS")
            if route_result.used_fallback_route:
                warnings.append("ROUTE_FALLBACK_USED")
            if parse_result.used_fallback:
                warnings.append("LLM_FALLBACK_USED")
            if parse_result.fallback_reason:
                warnings.append(parse_result.fallback_reason)

            timings["total_ms"] = int((time.perf_counter() - total_started) * 1000)
            metrics.warnings = warnings
            metrics.selected_poi_count = len(selected_plan.stops) - 2  # minus start/end
            metrics.log()
            logger.info("Agent plan timings: %s", timings)

            return PlanResponse(
                success=True,
                request_id=request.request_id,
                summary=summary,
                intent=intent,
                selected_plan=selected_plan,
                alternative_plans=alternative_plans,
                warnings=warnings,
                debug_trace=DebugTrace(
                    parsed_task_count=len(intent.tasks),
                    poi_candidate_count=candidate_result.poi_candidate_count,
                    deal_candidate_count=candidate_result.deal_candidate_count,
                    route_candidate_count=route_result.route_candidate_count,
                ),
            )
        except AgentError as error:
            timings["total_ms"] = int((time.perf_counter() - total_started) * 1000)
            metrics.warnings.append(f"error: {error.code.value}")
            metrics.log()
            logger.info("Agent plan failed timings: %s", timings)
            return self._error_response(request, error)
        except Exception as exc:
            timings["total_ms"] = int((time.perf_counter() - total_started) * 1000)
            metrics.warnings.append(f"error: {type(exc).__name__}")
            metrics.log()
            logger.info("Agent plan failed timings: %s", timings)
            return self._error_response(
                request,
                AgentError(
                    ErrorCode.BACKEND_TOOL_ERROR,
                    f"调用后端工具或编排流程失败：{exc}",
                ),
            )

    @staticmethod
    def _validate_user_query(request: PlanRequest) -> None:
        if not request.user_query or not request.user_query.strip():
            raise AgentError(
                ErrorCode.MISSING_USER_QUERY,
                "用户没有输入需求。",
                missing_fields=["user_query"],
            )

    async def _resolve_start(
        self,
        request: PlanRequest,
        start_text: Optional[str],
    ) -> Optional[Location]:
        if request.start_location and request.start_location.has_coordinates():
            return request.start_location
        if start_text:
            locations = await self.backend_client.geocode(start_text, request.city, limit=1)
            if locations:
                return locations[0]
        return request.current_location

    async def _resolve_end(
        self,
        request: PlanRequest,
        end_text: Optional[str],
    ) -> Optional[Location]:
        if request.end_location and request.end_location.has_coordinates():
            return request.end_location
        if not end_text:
            return None
        locations = await self.backend_client.geocode(end_text, request.city, limit=1)
        return locations[0] if locations else None

    @staticmethod
    def _validate_locations(
        start: Optional[Location],
        end: Optional[Location],
    ) -> None:
        missing_fields: list[str] = []
        if start is None or not start.has_coordinates():
            missing_fields.append("start_location_or_current_location")
        if end is None or not end.has_coordinates():
            missing_fields.append("end_location")
        if missing_fields:
            raise AgentError(
                ErrorCode.MISSING_LOCATION,
                "缺少起点或终点经纬度，请先在前端选择地点。",
                missing_fields=missing_fields,
            )

    @staticmethod
    def _search_center(start: Optional[Location], end: Optional[Location]) -> Location:
        if start is None or end is None:
            raise AgentError(
                ErrorCode.MISSING_LOCATION,
                "缺少起点或终点经纬度，请先在前端选择地点。",
            )
        return Location(
            name="搜索中心",
            longitude=((start.longitude or 0) + (end.longitude or 0)) / 2,
            latitude=((start.latitude or 0) + (end.latitude or 0)) / 2,
        )

    @staticmethod
    def _to_alternative_summary(plan) -> AlternativePlanSummary:
        return AlternativePlanSummary(
            plan_id=plan.plan_id,
            score=plan.score,
            total_distance_meters=plan.route.distance_meters,
            total_duration_minutes=plan.route.duration_minutes,
            detour_distance_meters=plan.detour_distance_meters,
            extra_time_minutes=plan.extra_time_minutes,
            estimated_cost=plan.estimated_cost,
            brief_reason="综合得分略低，可作为备选方案。",
        )

    async def _calculate_route_with_timeout(
        self,
        points: list[Location],
        travel_mode: str,
        timeout_seconds: float,
    ) -> RouteResult:
        try:
            return await asyncio.wait_for(
                self.backend_client.calculate_route(points, travel_mode),
                timeout=timeout_seconds,
            )
        except Exception:
            return self._fallback_route(points, travel_mode)

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
                    PlanAgent._haversine_meters(
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
                    from_name=start.name or "起点",
                    to_name=end.name or "终点",
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

    @staticmethod
    def _error_response(request: PlanRequest, error: AgentError) -> PlanResponse:
        return PlanResponse(
            success=False,
            request_id=request.request_id,
            error_code=error.code.value,
            message=error.message,
            missing_fields=error.missing_fields,
            fallback_suggestions=error.fallback_suggestions,
        )
