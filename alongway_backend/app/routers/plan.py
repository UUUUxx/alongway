"""
Frontend plan proxy endpoint.
Logs incoming requests for debugging; caches last N history entries.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import PlanHistoryEntry, PlanHistoryResponse, PlanRequest, PlanResponse
from app.services.agent_client import call_agent_plan

logger = logging.getLogger(__name__)
router = APIRouter(tags=["frontend"])

# In-memory history cache (Task 4: frontend history requirement)
_history_cache: list[PlanHistoryEntry] = []
MAX_HISTORY = 10  # keep up to 10 entries


@router.post("/api/plan", response_model=PlanResponse)
async def plan_endpoint(request: PlanRequest) -> PlanResponse:
    """
    Frontend plan endpoint.

    Validates request, generates request_id if missing,
    calls Agent service, and returns the response.
    Logs request details for debugging (full dump in debug mode).
    Caches history for frontend recall.
    """
    settings = get_settings()

    # Generate request_id if missing
    if not request.request_id:
        request.request_id = f"req_{uuid.uuid4().hex[:8]}"

    # === Debug logging (Task 4: verify frontend options reach backend) ===
    if settings.debug:
        logger.info(
            "PlanRequest FULL: request_id=%s user_query=%s city=%s travel_mode=%s "
            "budget=%s start=(%s, %.6f,%.6f) end=(%s, %.6f,%.6f) "
            "preferences=%s constraints=%s",
            request.request_id,
            request.user_query,
            request.city,
            request.travel_mode,
            request.budget,
            request.start_location.name,
            request.start_location.longitude,
            request.start_location.latitude,
            request.end_location.name,
            request.end_location.longitude,
            request.end_location.latitude,
            request.preferences.model_dump_json(),
            request.constraints.model_dump_json(),
        )
    else:
        logger.info(
            "PlanRequest: request_id=%s user_query=%s city=%s",
            request.request_id,
            request.user_query,
            request.city,
        )

    # Call Agent service
    response = await call_agent_plan(request)

    # Set request_id in response if not already set
    if not response.request_id:
        response.request_id = request.request_id

    # === Cache history entry (Task 4: frontend history) ===
    entry = PlanHistoryEntry(
        request_id=request.request_id,
        user_query=request.user_query,
        city=request.city,
        travel_mode=request.travel_mode,
        preferences=request.preferences,
        constraints=request.constraints,
        response_plan=response.plan,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _history_cache.insert(0, entry)
    if len(_history_cache) > MAX_HISTORY:
        _history_cache.pop()

    logger.debug("History cache size=%d", len(_history_cache))

    return response


@router.get("/api/plan/history", response_model=PlanHistoryResponse)
async def get_plan_history(limit: int = 5) -> PlanHistoryResponse:
    """
    Get cached plan history entries.
    Frontend can use this to recall previously asked questions (at least 1).

    Args:
        limit: Max number of entries to return (default 5)

    Returns:
        PlanHistoryResponse with list of PlanHistoryEntry
    """
    entries = _history_cache[: min(limit, len(_history_cache))]
    return PlanHistoryResponse(entries=entries, count=len(entries))
