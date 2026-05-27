from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from agent.backend_client import BackendClient
from agent.exceptions import AgentError, ErrorCode
from agent.filters import assess_availability, is_within_budget
from agent.models import EnrichedCandidate, Location, PlanRequest, TaskType, UserIntent


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
    ) -> CandidateGenerationResult:
        candidates_by_task: dict[str, list[EnrichedCandidate]] = {}
        poi_candidate_count = 0
        deal_candidate_count = 0
        warnings: set[str] = set()

        for task in intent.tasks:
            pois = await self.backend_client.search_pois(
                source_keywords=task.source_keywords,
                center=center,
                radius_meters=request.constraints.search_radius_meters,
                limit=request.constraints.max_pois_per_task,
            )
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
                    deals = await self.backend_client.search_deals(
                        poi_id=poi.poi_id,
                        categories=task.source_keywords,
                        max_price=budget,
                        limit=request.constraints.max_deals_per_poi,
                    )
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
