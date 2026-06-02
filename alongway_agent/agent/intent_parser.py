from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Optional

from agent.llm_client import LLMClient
from agent.models import TaskSpec, TaskType, UserIntent, UserPreferences


@dataclass(frozen=True)
class IntentParseResult:
    intent: UserIntent
    used_fallback: bool
    llm_ms: int
    fallback_reason: Optional[str] = None
    # ── v2 fields ──
    llm_called: bool = False
    cache_hit: bool = False


class IntentParser:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        llm_timeout_seconds: float = 3.0,
        rule_first: bool = True,
        llm_cache: Optional[object] = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_timeout_seconds = llm_timeout_seconds
        self.rule_first = rule_first
        self.llm_cache = llm_cache

    async def parse(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> UserIntent:
        return (
            await self.parse_with_metadata(
                user_query=user_query,
                budget=budget,
                preferences=preferences,
            )
        ).intent

    async def parse_with_metadata(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> IntentParseResult:
        started = time.perf_counter()
        fallback_reason: Optional[str] = None
        llm_called = False
        cache_hit = False

        # ── v2: rule-first path ──
        if self.rule_first:
            intent = self._parse_by_rules(user_query, budget, preferences)
            if intent and intent.tasks:
                return IntentParseResult(
                    intent=intent,
                    used_fallback=False,
                    llm_ms=int((time.perf_counter() - started) * 1000),
                    llm_called=False,
                    cache_hit=False,
                )

        # ── v2: check LLM cache ──
        if self.llm_cache is not None:
            cached = self.llm_cache.get(user_query)
            if cached is not None:
                cache_hit = True
                try:
                    intent = UserIntent.model_validate(cached)
                    if intent and intent.tasks:
                        return IntentParseResult(
                            intent=intent,
                            used_fallback=False,
                            llm_ms=int((time.perf_counter() - started) * 1000),
                            llm_called=False,
                            cache_hit=True,
                        )
                except Exception:
                    pass  # Cache data corrupted, fall through to LLM

        # ── v1 path: LLM-first (or v2: rules already tried and failed) ──
        if self.llm_client is not None:
            try:
                parsed = await asyncio.wait_for(
                    self.llm_client.parse_intent(
                        user_query=user_query,
                        budget=budget,
                        preferences=preferences,
                    ),
                    timeout=self.llm_timeout_seconds,
                )
                llm_called = True
                intent = self._try_validate_llm_result(parsed, budget, preferences)
                if intent and intent.tasks:
                    # Cache successful LLM result
                    if self.llm_cache is not None and parsed:
                        self.llm_cache.set(user_query, parsed)
                    return IntentParseResult(
                        intent=intent,
                        used_fallback=False,
                        llm_ms=int((time.perf_counter() - started) * 1000),
                        llm_called=True,
                        cache_hit=False,
                    )
                if fallback_reason is None:
                    fallback_reason = "LLM returned no valid tasks"
            except Exception as exc:
                llm_called = True
                if fallback_reason is None:
                    fallback_reason = f"LLM failed: {type(exc).__name__}"

        # ── Final fallback: rule-based parsing ──
        intent = self._parse_by_rules(user_query, budget, preferences)
        return IntentParseResult(
            intent=intent,
            used_fallback=True,
            llm_ms=int((time.perf_counter() - started) * 1000),
            fallback_reason=fallback_reason,
            llm_called=llm_called,
            cache_hit=cache_hit,
        )

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
        tasks = payload.get("tasks") or []
        for index, task in enumerate(tasks, start=1):
            if isinstance(task, dict):
                task.setdefault("task_id", f"task_{index}")
                task.setdefault("required", True)
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

        pickup_pos = self._first_keyword_position(user_query, ["取快递", "快递", "驿站", "菜鸟", "快递柜"])
        if pickup_pos is not None:
            specific_place = self._extract_specific_place(
                user_query,
                ["菜鸟驿站", "快递柜", "快递站", "驿站"],
                pickup_pos,
            )
            keywords = (
                [specific_place, "菜鸟驿站", "快递"]
                if specific_place
                else ["快递", "菜鸟驿站", "快递柜"]
            )
            detected_tasks.append(
                (
                    pickup_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.PICKUP_EXPRESS,
                        raw_text=self._raw_text(
                            user_query, pickup_pos, ["取快递", "快递", "驿站", "菜鸟", "快递柜"]
                        ),
                        source_keywords=keywords,
                        category="express",
                        specific_place_name=specific_place,
                    ),
                )
            )

        drink_pos = self._first_keyword_position(
            user_query, ["星巴克", "瑞幸", "幸运咖", "奶茶", "饮品", "咖啡", "喝的", "买杯喝的", "冷饮"]
        )
        if drink_pos is not None:
            specific_place = self._extract_specific_brand(
                user_query,
                ["星巴克", "瑞幸", "幸运咖", "茶百道", "喜茶", "蜜雪冰城"],
            )
            keywords = (
                [specific_place, "咖啡", "饮品"]
                if specific_place
                else ["奶茶", "饮品", "咖啡"]
            )
            detected_tasks.append(
                (
                    drink_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.BUY_DRINK,
                        raw_text=self._raw_text(
                            user_query, drink_pos, ["星巴克", "瑞幸", "奶茶", "饮品", "咖啡", "喝的", "买杯喝的", "冷饮"]
                        ),
                        source_keywords=keywords,
                        category="drink",
                        specific_place_name=specific_place,
                        budget=effective_budget,
                    ),
                )
            )

        meal_pos = self._first_keyword_position(
            user_query, ["韩餐", "韩国料理", "吃饭", "吃的", "找点吃", "午饭", "晚饭", "小吃", "快餐", "食堂", "餐厅"]
        )
        if meal_pos is not None:
            if any(word in user_query for word in ["韩餐", "韩国料理"]):
                keywords = ["韩餐", "韩国料理", "餐厅"]
                raw_keywords = ["韩餐", "韩国料理"]
                specific_place = None
            else:
                keywords = ["食堂", "小吃", "快餐", "餐厅"]
                raw_keywords = ["吃饭", "吃的", "找点吃", "午饭", "晚饭", "小吃", "快餐", "食堂", "餐厅"]
                specific_place = self._extract_specific_place(user_query, ["餐厅", "食堂"], meal_pos)
            detected_tasks.append(
                (
                    meal_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.EAT_MEAL,
                        raw_text=self._raw_text(
                            user_query, meal_pos, raw_keywords
                        ),
                        source_keywords=keywords if specific_place is None else [specific_place, *keywords],
                        category="food",
                        specific_place_name=specific_place,
                        budget=effective_budget,
                    ),
                )
            )

        entertainment_pos = self._first_keyword_position(
            user_query, ["娱乐", "电影", "电影院", "桌游", "棋牌", "密室", "KTV", "ktv"]
        )
        if entertainment_pos is not None:
            detected_tasks.append(
                (
                    entertainment_pos,
                    TaskSpec(
                        task_id="pending",
                        type=TaskType.CUSTOM,
                        raw_text=self._raw_text(
                            user_query,
                            entertainment_pos,
                            ["娱乐", "电影", "电影院", "桌游", "棋牌", "密室", "KTV", "ktv"],
                        ),
                        source_keywords=["娱乐", "电影院", "桌游", "棋牌", "密室", "KTV"],
                        category="entertainment",
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
        manual = IntentParser._extract_start_end_manually(user_query)
        if manual != (None, None):
            return manual

        match = re.search(
            r"(?:我)?从(?P<start>.+?)(?:去|到)(?P<end>[^，,。；;]+)",
            user_query,
        )
        if match:
            start = match.group("start").strip(" 我")
            end = match.group("end").strip()
            return start or None, end or None

        end_match = re.search(r"(?:去|到|前往)(?P<end>[^，,。；;]+)", user_query)
        if not end_match:
            return None, None
        start = None
        end = end_match.group("end").strip()
        return start or None, end or None

    @staticmethod
    def _extract_start_end_manually(user_query: str) -> tuple[Optional[str], Optional[str]]:
        separators = ["到", "去", "前往", "→"]
        end_marks = ["，", ",", "。", "；", ";"]
        if "从" in user_query:
            start_from = user_query.find("从") + 1
            separator_positions = [
                (user_query.find(separator, start_from), separator)
                for separator in separators
                if user_query.find(separator, start_from) >= 0
            ]
            if separator_positions:
                sep_pos, separator = min(separator_positions, key=lambda item: item[0])
                start = user_query[start_from:sep_pos].strip(" 我")
                end_start = sep_pos + len(separator)
                end_stop = len(user_query)
                for mark in end_marks:
                    pos = user_query.find(mark, end_start)
                    if pos >= 0:
                        end_stop = min(end_stop, pos)
                end = user_query[end_start:end_stop].strip()
                return start or None, end or None

        for separator in separators:
            pos = user_query.find(separator)
            if pos >= 0:
                end_start = pos + len(separator)
                end_stop = len(user_query)
                for mark in end_marks:
                    mark_pos = user_query.find(mark, end_start)
                    if mark_pos >= 0:
                        end_stop = min(end_stop, mark_pos)
                end = user_query[end_start:end_stop].strip()
                if end:
                    return None, end
        return None, None

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

    @staticmethod
    def _extract_specific_brand(user_query: str, brands: list[str]) -> Optional[str]:
        for brand in brands:
            if brand in user_query:
                return brand
        return None

    @staticmethod
    def _extract_specific_place(
        user_query: str,
        suffixes: list[str],
        position: int,
    ) -> Optional[str]:
        window_start = max(0, position - 12)
        window_end = min(len(user_query), position + 18)
        window = user_query[window_start:window_end]
        for suffix in suffixes:
            pattern = rf"([\u4e00-\u9fffA-Za-z0-9·（）()_-]{{0,12}}{re.escape(suffix)})"
            match = re.search(pattern, window)
            if match:
                value = match.group(1).strip("，,。；; 想去到")
                return value or suffix
        return None

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
                category="study" if matched_keyword in {"图书馆", "教学楼"} else "life",
            ),
        )
