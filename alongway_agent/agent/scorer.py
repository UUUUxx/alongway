from __future__ import annotations

from typing import Optional

from agent.models import (
    CandidatePlan,
    PlanConstraints,
    ScoreDetail,
    StopType,
    UserPreferences,
)


class PlanScorer:
    def rank_plans(
        self,
        plans: list[CandidatePlan],
        preferences: UserPreferences,
        constraints: PlanConstraints,
        budget: Optional[float],
    ) -> list[CandidatePlan]:
        for plan in plans:
            self.score_plan(plan, preferences, constraints, budget)
        return sorted(plans, key=self._sort_key)

    def score_plan(
        self,
        plan: CandidatePlan,
        preferences: UserPreferences,
        constraints: PlanConstraints,
        budget: Optional[float],
    ) -> CandidatePlan:
        detail = ScoreDetail(
            detour_score=self._detour_score(plan, constraints),
            time_score=self._time_score(plan, constraints),
            price_score=self._price_score(plan, budget),
            rating_score=self._rating_score(plan),
            sales_score=self._sales_score(plan),
            open_score=self._open_score(plan),
        )
        weights = self._weights(preferences)
        score = (
            weights["detour_score"] * detail.detour_score
            + weights["time_score"] * detail.time_score
            + weights["price_score"] * detail.price_score
            + weights["rating_score"] * detail.rating_score
            + weights["sales_score"] * detail.sales_score
            + weights["open_score"] * detail.open_score
        )
        plan.score_detail = ScoreDetail(
            detour_score=round(detail.detour_score, 4),
            time_score=round(detail.time_score, 4),
            price_score=round(detail.price_score, 4),
            rating_score=round(detail.rating_score, 4),
            sales_score=round(detail.sales_score, 4),
            open_score=round(detail.open_score, 4),
        )
        plan.score = round(score, 4)
        return plan

    @staticmethod
    def _weights(preferences: UserPreferences) -> dict[str, float]:
        weights = {
            "detour_score": 0.35,
            "time_score": 0.20,
            "price_score": 0.20,
            "rating_score": 0.10,
            "sales_score": 0.10,
            "open_score": 0.05,
        }
        if preferences.prefer_less_detour:
            weights["detour_score"] += 0.45
        if preferences.prefer_low_price:
            weights["price_score"] += 0.80
        if preferences.prefer_high_rating:
            weights["rating_score"] += 0.65
        if preferences.prefer_high_sales:
            weights["sales_score"] += 0.65
        if preferences.prefer_fast_arrival:
            weights["time_score"] += 0.45

        total = sum(weights.values())
        return {key: value / total for key, value in weights.items()}

    @staticmethod
    def _detour_score(plan: CandidatePlan, constraints: PlanConstraints) -> float:
        max_detour = max(1, constraints.max_detour_meters)
        return max(0.0, 1 - plan.detour_distance_meters / max_detour)

    @staticmethod
    def _time_score(plan: CandidatePlan, constraints: PlanConstraints) -> float:
        max_extra_time = max(1, constraints.max_extra_time_minutes)
        return max(0.0, 1 - plan.extra_time_minutes / max_extra_time)

    @staticmethod
    def _price_score(plan: CandidatePlan, budget: Optional[float]) -> float:
        estimated_cost = plan.estimated_cost
        if estimated_cost == 0:
            poi_costs = [
                stop.poi.cost
                for stop in plan.stops
                if stop.poi and stop.poi.cost is not None
            ]
            if poi_costs:
                estimated_cost = sum(poi_costs)
            elif any(stop.poi is not None for stop in plan.stops):
                return 0.55
        if budget is None:
            return 0.7
        if budget <= 0:
            return 0.0
        if estimated_cost > budget:
            return 0.0
        return max(0.0, 1 - 0.5 * estimated_cost / budget)

    @staticmethod
    def _rating_score(plan: CandidatePlan) -> float:
        ratings: list[float] = []
        for stop in plan.stops:
            if stop.poi and stop.poi.rating is not None:
                ratings.append(stop.poi.rating)
            if stop.deal and stop.deal.rating is not None:
                ratings.append(stop.deal.rating)
        if not ratings:
            return 0.6
        return min(1.0, sum(ratings) / len(ratings) / 5)

    @staticmethod
    def _sales_score(plan: CandidatePlan) -> float:
        sales = [
            stop.deal.monthly_sales
            for stop in plan.stops
            if stop.deal and stop.deal.monthly_sales is not None
        ]
        if not sales:
            return 0.5
        best_sales = max(sales)
        if best_sales >= 500:
            return 1.0
        if best_sales >= 200:
            return 0.8
        if best_sales >= 50:
            return 0.6
        if best_sales > 0:
            return 0.4
        return 0.5

    @staticmethod
    def _open_score(plan: CandidatePlan) -> float:
        scores: list[float] = []
        for stop in plan.stops:
            if stop.stop_type not in {StopType.TASK, StopType.DEAL}:
                continue
            if stop.is_open is False:
                scores.append(0.3)
            elif any("未知" in reason for reason in stop.availability_reasons):
                scores.append(0.8)
            else:
                scores.append(1.0)
        return min(scores) if scores else 1.0

    def _sort_key(self, plan: CandidatePlan) -> tuple[float, int, float, int, float]:
        return (
            -plan.score,
            plan.detour_distance_meters,
            plan.estimated_cost,
            -self._max_monthly_sales(plan),
            plan.route.duration_minutes,
        )

    @staticmethod
    def _max_monthly_sales(plan: CandidatePlan) -> int:
        return max(
            [
                stop.deal.monthly_sales or 0
                for stop in plan.stops
                if stop.deal is not None
            ],
            default=0,
        )
