from __future__ import annotations

import re
from typing import Optional

from agent.llm_client import LLMClient
from agent.models import TaskSpec, TaskType, UserIntent, UserPreferences


class IntentParser:
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client

    async def parse(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> UserIntent:
        if self.llm_client is not None:
            parsed = await self.llm_client.parse_intent(
                user_query=user_query,
                budget=budget,
                preferences=preferences,
            )
            intent = self._try_validate_llm_result(parsed, budget, preferences)
            if intent and intent.tasks:
                return intent

        return self._parse_by_rules(user_query, budget, preferences)

    def _try_validate_llm_result(
        self,
        parsed: Optional[dict],
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[UserIntent]:
        if not parsed:
            return None
        payload = dict(parsed)
        payload.setdefault("budget", budget)
        payload.setdefault("preferences", preferences.model_dump())
        try:
            return UserIntent.model_validate(payload)
        except Exception:
            return None

    def _parse_by_rules(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> UserIntent:
        extracted_budget = self._extract_budget(user_query)
        effective_budget = budget if budget is not None else extracted_budget
        parsed_preferences = preferences.model_copy()

        if any(word in user_query for word in ["便宜", "省钱", "低价", "划算"]):
            parsed_preferences.prefer_low_price = True
        if any(word in user_query for word in ["不要绕", "少绕", "顺路", "绕太远"]):
            parsed_preferences.prefer_less_detour = True
        if any(word in user_query for word in ["快一点", "尽快", "赶时间"]):
            parsed_preferences.prefer_fast_arrival = True

        start_text, end_text = self._extract_start_end(user_query)
        detected_tasks: list[tuple[int, TaskSpec]] = []

        pickup_pos = self._first_keyword_position(
            user_query, ["取快递", "快递", "驿站", "菜鸟", "快递柜"]
        )
        if pickup_pos is not None:
            detected_tasks.append(
                (
                    pickup_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.PICKUP_EXPRESS,
                        raw_text=self._raw_text(
                            user_query, pickup_pos, ["取快递", "快递", "驿站", "菜鸟", "快递柜"]
                        ),
                        source_keywords=["快递", "菜鸟驿站", "快递柜"],
                    ),
                )
            )

        drink_pos = self._first_keyword_position(
            user_query, ["奶茶", "饮品", "咖啡", "喝的", "买杯喝的", "冷饮"]
        )
        if drink_pos is not None:
            detected_tasks.append(
                (
                    drink_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.BUY_DRINK,
                        raw_text=self._raw_text(
                            user_query, drink_pos, ["奶茶", "饮品", "咖啡", "喝的", "买杯喝的", "冷饮"]
                        ),
                        source_keywords=["奶茶", "饮品", "咖啡"],
                        budget=effective_budget,
                    ),
                )
            )

        meal_pos = self._first_keyword_position(
            user_query, ["吃饭", "午饭", "晚饭", "小吃", "快餐", "食堂", "餐厅"]
        )
        if meal_pos is not None:
            detected_tasks.append(
                (
                    meal_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.EAT_MEAL,
                        raw_text=self._raw_text(
                            user_query, meal_pos, ["吃饭", "午饭", "晚饭", "小吃", "快餐", "食堂", "餐厅"]
                        ),
                        source_keywords=["食堂", "小吃", "快餐", "餐厅"],
                        budget=effective_budget,
                    ),
                )
            )

        visit_task = self._extract_visit_task(user_query, end_text)
        if visit_task is not None:
            detected_tasks.append(visit_task)

        detected_tasks.sort(key=lambda item: item[0])
        tasks = [
            task.model_copy(update={"task_id": f"task_{index}"})
            for index, (_, task) in enumerate(detected_tasks, start=1)
        ]

        return UserIntent(
            start_text=start_text,
            end_text=end_text,
            tasks=tasks,
            budget=effective_budget,
            preferences=parsed_preferences,
        )

    @staticmethod
    def _extract_budget(user_query: str) -> Optional[float]:
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:元|块|块钱)\s*(?:以内|以下|内|之内)?",
            r"(?:预算|不超过|低于|控制在)\s*(\d+(?:\.\d+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, user_query)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def _extract_start_end(user_query: str) -> tuple[Optional[str], Optional[str]]:
        match = re.search(
            r"(?:我)?从(?P<start>.+?)(?:去|到)(?P<end>[^，,。；;]+)",
            user_query,
        )
        if not match:
            return None, None
        start = match.group("start").strip(" 我")
        end = match.group("end").strip()
        return start or None, end or None

    @staticmethod
    def _first_keyword_position(
        user_query: str,
        keywords: list[str],
    ) -> Optional[int]:
        positions = [user_query.find(keyword) for keyword in keywords]
        positions = [position for position in positions if position >= 0]
        if not positions:
            return None
        return min(positions)

    @staticmethod
    def _raw_text(user_query: str, position: int, keywords: list[str]) -> str:
        matched_keyword = next(
            (
                keyword
                for keyword in sorted(keywords, key=len, reverse=True)
                if user_query.find(keyword) == position
            ),
            None,
        )
        if matched_keyword:
            return matched_keyword
        start = max(0, position - 4)
        end = min(len(user_query), position + 10)
        return user_query[start:end].strip("，。；; ")

    def _extract_visit_task(
        self,
        user_query: str,
        end_text: Optional[str],
    ) -> Optional[tuple[int, TaskSpec]]:
        place_keywords = ["公园", "操场", "图书馆", "教学楼", "活动中心"]
        position = self._first_keyword_position(user_query, place_keywords)
        if position is None:
            return None

        matched_keyword = next(
            keyword for keyword in place_keywords if user_query.find(keyword) == position
        )
        if end_text and matched_keyword in end_text:
            return None

        return (
            position,
            TaskSpec(
                task_id="pending",
                type=TaskType.VISIT_PLACE,
                raw_text=matched_keyword,
                source_keywords=[matched_keyword],
            ),
        )
