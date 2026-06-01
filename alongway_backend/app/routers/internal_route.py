"""
Internal route calculation endpoint for Agent service.
Supports Amap real road-network routing (use_real_route=True, default)
and Haversine fallback (use_real_route=False).
"""
import logging

from fastapi import APIRouter, HTTPException

from app.schemas import RouteCalculateRequest, RouteCalculateResponse
from app.services.route_service import AmapRouteError, calculate_route as calculate_amap_route
from app.services.call_logger import log_call

logger = logging.getLogger(__name__)
router = APIRouter(tags=["internal"])


@router.post("/internal/route/calculate", response_model=RouteCalculateResponse)
def calculate_route_endpoint(request: RouteCalculateRequest) -> RouteCalculateResponse:
    """
    Calculate route distance and time.

    When use_real_route=True (default for new clients): uses Amap road-network API.
    When use_real_route=False: falls back to Haversine straight-line approximation.

    Args:
        request: RouteCalculateRequest with points, travel_mode, use_real_route

    Returns:
        RouteCalculateResponse with distance, duration, polyline, segments
    """
    # Default: use Amap real route unless explicitly told not to
    if request.use_real_route is not False:
        try:
            response = calculate_amap_route(points=request.points, travel_mode=request.travel_mode)
            log_call("backend.internal_route.result", request=request, result=response)
            return response
        except AmapRouteError as exc:
            logger.warning("Amap route failed: %s — falling back to Haversine", exc)
            # Fall through to Haversine
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Amap route failed: %s — falling back to Haversine", exc)
            # Fall through to Haversine

    # Haversine fallback
    from app.services.distance import get_travel_speed, haversine_distance_meters
    from app.schemas import RouteSegment as RS

    if len(request.points) < 2:
        raise HTTPException(status_code=422, detail="At least 2 points are required")

    total_distance = 0.0
    segments: list[RS] = []
    speed = get_travel_speed(request.travel_mode)

    for i in range(len(request.points) - 1):
        p1 = request.points[i]
        p2 = request.points[i + 1]
        dist = haversine_distance_meters(p1.longitude, p1.latitude, p2.longitude, p2.latitude)
        total_distance += dist
        segments.append(
            RS(
                from_name=p1.name,
                to_name=p2.name,
                distance_meters=int(round(dist)),
                duration_minutes=round(dist / speed, 1),
            )
        )

    total_duration = total_distance / speed
    polyline = [[p.longitude, p.latitude] for p in request.points]

    logger.info("Haversine route: %d points, mode=%s → %dm, %.1fmin",
                len(request.points), request.travel_mode, int(total_distance), total_duration)

    response = RouteCalculateResponse(
        distance_meters=int(round(total_distance)),
        duration_minutes=round(total_duration, 1),
        polyline=polyline,
        segments=segments,
    )
    log_call("backend.internal_route.result", request=request, result=response)
    return response
