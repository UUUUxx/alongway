from __future__ import annotations

from typing import Optional

from agent.backend_client import BackendClient, MockBackendClient
from agent.candidate_generator import CandidateGenerator
from agent.exceptions import AgentError, ErrorCode
from agent.explainer import Explainer
from agent.intent_parser import IntentParser
from agent.llm_client import LLMClient, MockLLMClient
from agent.models import (
    AlternativePlanSummary,
    DebugTrace,
    Location,
    PlanRequest,
    PlanResponse,
)
from agent.route_evaluator import RouteEvaluator
from agent.scorer import PlanScorer


class PlanAgent:
    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.backend_client = backend_client or MockBackendClient()
        self.llm_client = llm_client or MockLLMClient()
        self.intent_parser = IntentParser(self.llm_client)
        self.candidate_generator = CandidateGenerator(self.backend_client)
        self.route_evaluator = RouteEvaluator(self.backend_client)
        self.scorer = PlanScorer()
        self.explainer = Explainer(self.llm_client)

    async def plan(self, request: PlanRequest) -> PlanResponse:
        try:
            start = self._resolve_start(request)
            end = request.end_location
            self._validate_request(request, start, end)

            intent = await self.intent_parser.parse(
                user_query=request.user_query,
                budget=request.budget,
                preferences=request.preferences,
            )
            if not intent.tasks:
                raise AgentError(
                    ErrorCode.NO_TASK_PARSED,
                    "没有解析出顺路任务。",
                    fallback_suggestions=["可以说明想顺路完成的事项，例如取快递、买奶茶或吃饭。"],
                )

            center = self._search_center(start, end)
            base_route = await self.backend_client.calculate_route(
                [start, end],
                request.travel_mode,
            )

            candidate_result = await self.candidate_generator.generate(
                intent=intent,
                request=request,
                center=center,
            )
            route_result = await self.route_evaluator.evaluate(
                request=request,
                start=start,
                end=end,
                tasks=intent.tasks,
                candidates_by_task=candidate_result.candidates_by_task,
                base_route=base_route,
            )

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

            return PlanResponse(
                success=True,
                request_id=request.request_id,
                summary=summary,
                intent=intent,
                selected_plan=selected_plan,
                alternative_plans=alternative_plans,
                warnings=candidate_result.warnings,
                debug_trace=DebugTrace(
                    parsed_task_count=len(intent.tasks),
                    poi_candidate_count=candidate_result.poi_candidate_count,
                    deal_candidate_count=candidate_result.deal_candidate_count,
                    route_candidate_count=route_result.route_candidate_count,
                ),
            )
        except AgentError as error:
            return self._error_response(request, error)
        except Exception as exc:
            return self._error_response(
                request,
                AgentError(
                    ErrorCode.BACKEND_TOOL_ERROR,
                    f"调用后端工具或编排流程失败：{exc}",
                ),
            )

    @staticmethod
    def _resolve_start(request: PlanRequest) -> Optional[Location]:
        return request.start_location or request.current_location

    @staticmethod
    def _validate_request(
        request: PlanRequest,
        start: Optional[Location],
        end: Optional[Location],
    ) -> None:
        if not request.user_query or not request.user_query.strip():
            raise AgentError(
                ErrorCode.MISSING_USER_QUERY,
                "用户没有输入需求。",
                missing_fields=["user_query"],
            )
        missing_fields: list[str] = []
        if start is None or not start.has_coordinates():
            missing_fields.append("start_location")
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
