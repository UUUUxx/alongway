from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List

from agent.backend_client import BackendClient
from agent.exceptions import AgentError, ErrorCode
from agent.filters import assess_availability, is_within_budget
from agent.models import EnrichedCandidate, Location, POI, PlanRequest, TaskSpec, TaskType, UserIntent


@dataclass
class CandidateGenerationResult:
    candidates_by_task: Dict[str, List[EnrichedCandidate]]
    poi_candidate_count: int = 0
    deal_candidate_count: int = 0
    warnings: list[str] = field(default_factory=list)


class CandidateGenerator:
    def __init__(self, backend_client: BackendClient) -> None:
        self.backend_client = backend_client

    async def generate(
        self,
        intent: UserIntent,
        request: PlanRequest,
        center: Location,
        timeout_seconds: float = 3.0,
    ) -> CandidateGenerationResult:
        candidates_by_task: dict[str, list[EnrichedCandidate]] = {}
        poi_candidate_count = 0
        deal_candidate_count = 0
        warnings: set[str] = set()
        deadline = time.perf_counter() + timeout_seconds

        for task in intent.tasks:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                warnings.add("POI_SEARCH_TIMEOUT")
                break
            try:
                pois = await asyncio.wait_for(
                    self.backend_client.search_pois(
                        source_keywords=task.source_keywords,
                        center=center,
                        radius_meters=request.constraints.search_radius_meters,
                        limit=request.constraints.max_pois_per_task,
                        specific_place_name=task.specific_place_name,
                    ),
                    timeout=remaining,
                )
            except Exception:
                pois = self._fallback_pois_for_task(
                    task=task,
                    center=center,
                    limit=request.constraints.max_pois_per_task,
                )
                warnings.add("POI_SEARCH_TIMEOUT_OR_ERROR")
                if pois:
                    warnings.add("POI_SEARCH_FALLBACK_USED")
            deduped_pois = list({poi.poi_id: poi for poi in pois}.values())
            poi_candidate_count += len(deduped_pois)

            if not deduped_pois and task.required:
                raise AgentError(
                    ErrorCode.NO_POI_FOR_REQUIRED_TASK,
                    "没有找到可以完成该任务的地点。",
                )

            task_candidates: list[EnrichedCandidate] = []
            budget = task.budget if task.budget is not None else request.budget

            if task.type in {TaskType.BUY_DRINK, TaskType.EAT_MEAL}:
                for poi in deduped_pois:
                    remaining = deadline - time.perf_counter()
                    deal_timeout = max(1.5, min(2.0, remaining))
                    try:
                        deals = await asyncio.wait_for(
                            self.backend_client.search_deals(
                                poi_id=poi.poi_id,
                                categories=task.source_keywords,
                                max_price=budget,
                                limit=request.constraints.max_deals_per_poi,
                            ),
                            timeout=deal_timeout,
                        )
                    except Exception:
                        deals = []
                        warnings.add("DEAL_SEARCH_TIMEOUT_OR_ERROR")
                    deal_candidate_count += len(deals)

                    if deals:
                        for deal in deals:
                            if not is_within_budget(deal, budget):
                                continue
                            is_open, reasons, availability_warnings = assess_availability(
                                deal,
                                request.departure_time,
                            )
                            warnings.update(availability_warnings)
                            task_candidates.append(
                                EnrichedCandidate(
                                    task_id=task.task_id,
                                    task_type=task.type,
                                    poi=poi,
                                    deal=deal,
                                    is_open=is_open,
                                    filter_reasons=reasons,
                                )
                            )
                    else:
                        reason = (
                            "没有符合预算的团购，仍作为顺路地点候选"
                            if budget is not None
                            else "暂无团购，仍作为顺路地点候选"
                        )
                        warnings.add(f"{poi.name}{reason}")
                        task_candidates.append(
                            EnrichedCandidate(
                                task_id=task.task_id,
                                task_type=task.type,
                                poi=poi,
                                deal=None,
                                is_open=True,
                                filter_reasons=[reason],
                            )
                        )
            else:
                task_candidates = [
                    EnrichedCandidate(
                        task_id=task.task_id,
                        task_type=task.type,
                        poi=poi,
                        deal=None,
                    )
                    for poi in deduped_pois
                ]

            if not task_candidates and task.required:
                raise AgentError(
                    ErrorCode.NO_POI_FOR_REQUIRED_TASK,
                    "没有找到可以完成该任务的地点。",
                )

            candidates_by_task[task.task_id] = task_candidates

        return CandidateGenerationResult(
            candidates_by_task=candidates_by_task,
            poi_candidate_count=poi_candidate_count,
            deal_candidate_count=deal_candidate_count,
            warnings=sorted(warnings),
        )

    @staticmethod
    def _fallback_pois_for_task(
        task: TaskSpec,
        center: Location,
        limit: int,
    ) -> list[POI]:
        if not center.has_coordinates() or limit <= 0:
            return []
        poi_type = task.category or "custom"
        keyword = task.specific_place_name or (task.source_keywords[0] if task.source_keywords else task.raw_text)
        templates = {
            "food": [("顺路简餐", 18.0), ("附近小吃", 12.0), ("沿途餐厅", 22.0)],
            "drink": [("顺路咖啡", 24.0), ("附近饮品", 16.0), ("咖啡小站", 28.0)],
            "express": [("附近菜鸟驿站", None), ("顺路快递柜", None)],
            "entertainment": [("顺路娱乐场所", 38.0), ("附近桌游", 35.0)],
            "study": [("附近学习空间", None), ("顺路图书馆", None)],
            "life": [("顺路服务点", None)],
            "custom": [(f"{keyword}候选点", None)],
        }
        pois: list[POI] = []
        for index, (name, cost) in enumerate(templates.get(poi_type, templates["custom"])[:limit], start=1):
            lon = (center.longitude or 0) + 0.001 * index
            lat = (center.latitude or 0) + 0.0007 * index
            display_name = task.specific_place_name or name
            pois.append(
                POI(
                    poi_id=f"mock_{task.task_id}_{index}",
                    name=display_name,
                    type=poi_type,
                    address="高德 POI 超时后生成的临时候选点",
                    location=f"{lon:.6f},{lat:.6f}",
                    longitude=lon,
                    latitude=lat,
                    rating=4.2,
                    cost=cost,
                    source_keyword=keyword,
                )
            )
        return pois
