from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from agent.models import AlternativePlanSummary, CandidatePlan, UserPreferences


class LLMClient(ABC):
    @abstractmethod
    async def parse_intent(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[dict]:
        raise NotImplementedError

    @abstractmethod
    async def generate_explanation(
        self,
        user_query: str,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> Optional[dict]:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def parse_intent(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[dict]:
        return None

    async def generate_explanation(
        self,
        user_query: str,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> Optional[dict]:
        return None
