from __future__ import annotations

from typing import Optional

from agent.llm_client import LLMClient
from agent.models import AlternativePlanSummary, CandidatePlan, PlanRequest, StopType


class Explainer:
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client

    async def explain(
        self,
        request: PlanRequest,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> str:
        if self.llm_client is not None:
            generated = await self.llm_client.generate_explanation(
                user_query=request.user_query,
                selected_plan=selected_plan,
                alternative_plans=alternative_plans,
            )
            if generated:
                return self._apply_generated_text(
                    generated,
                    selected_plan,
                    alternative_plans,
                )

        return self._template_explain(selected_plan, alternative_plans)

    def _apply_generated_text(
        self,
        generated: dict,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> str:
        summary = str(generated.get("summary") or "").strip()
        recommendation_reason = str(generated.get("recommendation_reason") or "").strip()
        if recommendation_reason:
            selected_plan.recommendation_reason = recommendation_reason

        stop_reasons = generated.get("stop_reasons") or {}
        if isinstance(stop_reasons, dict):
            for stop in selected_plan.stops:
                reason = stop_reasons.get(str(stop.order)) or stop_reasons.get(stop.name)
                if reason:
                    stop.reason = str(reason)

        alternative_reasons = generated.get("alternative_reasons") or {}
        if isinstance(alternative_reasons, dict):
            for alternative in alternative_plans:
                reason = alternative_reasons.get(alternative.plan_id)
                if reason:
                    alternative.brief_reason = str(reason)

        if summary:
            return summary
        return self._template_explain(selected_plan, alternative_plans)

    def _template_explain(
        self,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> str:
        self._fill_stop_reasons(selected_plan)
        selected_plan.recommendation_reason = (
            f"这条路线全程约{selected_plan.route.distance_meters}米，预计"
            f"{selected_plan.route.duration_minutes:.1f}分钟；相比直接前往目的地，"
            f"仅增加约{selected_plan.detour_distance_meters}米、"
            f"{selected_plan.extra_time_minutes:.1f}分钟，"
            f"预估花费{selected_plan.estimated_cost:.1f}元。"
        )

        for alternative in alternative_plans:
            alternative.brief_reason = self._alternative_reason(
                alternative,
                selected_plan,
            )

        middle_names = [
            stop.name
            for stop in selected_plan.stops
            if stop.stop_type in {StopType.TASK, StopType.DEAL}
        ]
        start_name = selected_plan.stops[0].name if selected_plan.stops else "起点"
        end_name = selected_plan.stops[-1].name if selected_plan.stops else "终点"
        middle = "，再去".join(middle_names)
        if middle:
            return (
                f"推荐你从{start_name}出发，先去{middle}，最后到达{end_name}。"
                f"预计全程{selected_plan.route.distance_meters}米，"
                f"约{selected_plan.route.duration_minutes:.1f}分钟，"
                f"花费{selected_plan.estimated_cost:.1f}元。"
            )
        return f"推荐你从{start_name}直接前往{end_name}。"

    @staticmethod
    def _fill_stop_reasons(plan: CandidatePlan) -> None:
        for stop in plan.stops:
            if stop.stop_type == StopType.START:
                stop.reason = "出发点"
            elif stop.stop_type == StopType.END:
                stop.reason = "目的地"
            elif stop.deal:
                stop.reason = (
                    f"{stop.deal.deal_title}团购价{stop.deal.price:.1f}元，"
                    f"评分{stop.deal.rating or stop.poi.rating if stop.poi else '暂无'}，"
                    f"月销量{stop.deal.monthly_sales or 0}。"
                )
                if stop.availability_reasons:
                    stop.reason += f" 注意：{'、'.join(stop.availability_reasons)}。"
            elif stop.poi:
                stop.reason = (
                    f"{stop.poi.name}可完成该顺路任务，位置在{stop.poi.location or '路线附近'}，"
                    "整体绕路较少。"
                )

    @staticmethod
    def _alternative_reason(
        alternative: AlternativePlanSummary,
        selected_plan: CandidatePlan,
    ) -> str:
        if alternative.estimated_cost < selected_plan.estimated_cost:
            return "价格更低，但综合绕路、耗时或评分略逊于推荐方案。"
        if alternative.detour_distance_meters > selected_plan.detour_distance_meters:
            return "也能完成任务，但绕路距离更长。"
        return "综合得分略低，可作为备选方案。"
