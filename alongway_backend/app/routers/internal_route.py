"""
Internal route calculation endpoint for Agent service.
"""
from fastapi import APIRouter

from app.schemas import RouteCalculateRequest, RouteCalculateResponse
from app.services.route_service import calculate_route

router = APIRouter(tags=["internal"])


@router.post("/internal/route/calculate", response_model=RouteCalculateResponse)
def calculate_route_endpoint(request: RouteCalculateRequest) -> RouteCalculateResponse:
    """
    Calculate route distance and time using Haversine approximation.

    This endpoint is called by Agent service.

    Args:
        request: RouteCalculateRequest with points and travel_mode

    Returns:
        RouteCalculateResponse with distance, duration, polyline, segments
    """
    return calculate_route(points=request.points, travel_mode=request.travel_mode)
