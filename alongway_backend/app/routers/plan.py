"""
Frontend plan proxy endpoint.
"""
import uuid

from fastapi import APIRouter

from app.schemas import PlanRequest, PlanResponse
from app.services.agent_client import call_agent_plan
from app.services.location_resolver import resolve_plan_locations

router = APIRouter(tags=["frontend"])


@router.post("/api/plan", response_model=PlanResponse)
async def plan_endpoint(request: PlanRequest) -> PlanResponse:
    """
    Frontend plan endpoint.

    Validates request, generates request_id if missing,
    calls Agent service, and returns the response.

    Args:
        request: PlanRequest from frontend

    Returns:
        PlanResponse from Agent service or error response
    """
    # Generate request_id if missing
    if not request.request_id:
        request.request_id = f"req_{uuid.uuid4().hex[:8]}"

    request = await resolve_plan_locations(request)

    # Call Agent service
    response = await call_agent_plan(request)

    # Set request_id in response if not already set
    if not response.request_id:
        response.request_id = request.request_id

    return response
