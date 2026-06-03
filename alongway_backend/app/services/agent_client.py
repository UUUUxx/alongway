"""
Agent service client for calling Agent APIs.
"""
from typing import Any

import httpx

from app.config import get_settings
from app.schemas import PlanRequest, PlanResponse


async def call_agent_plan(request: PlanRequest) -> PlanResponse:
    """
    Call Agent service /agent/plan endpoint.

    Args:
        request: PlanRequest from frontend

    Returns:
        PlanResponse from Agent service or error response

    Raises:
        Exception: If Agent service is unavailable
    """
    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=settings.agent_service_timeout, trust_env=False) as client:
            response = await client.post(
                f"{settings.agent_service_url}/agent/plan",
                json=request.model_dump(exclude_none=True),
            )
            response.raise_for_status()
            return adapt_agent_response(response.json(), request)
    except httpx.TimeoutException:
        return PlanResponse(
            success=False,
            error_code="AGENT_SERVICE_TIMEOUT",
            message="Agent service request timeout",
        )
    except httpx.ConnectError:
        return PlanResponse(
            success=False,
            error_code="AGENT_SERVICE_UNAVAILABLE",
            message="Agent service is not available",
        )
    except httpx.HTTPError as e:
        return PlanResponse(
            success=False,
            error_code="AGENT_SERVICE_ERROR",
            message=f"Agent service error: {str(e)}",
        )
    except Exception as e:
        return PlanResponse(
            success=False,
            error_code="UNKNOWN_ERROR",
            message=f"Unknown error: {str(e)}",
        )


def adapt_agent_response(data: dict[str, Any], request: PlanRequest) -> PlanResponse:
    """Convert the Agent response into the frontend plan shape."""
    if not data.get("success"):
        return PlanResponse(
            success=False,
            request_id=data.get("request_id") or request.request_id,
            error_code=data.get("error_code"),
            message=data.get("message") or "Agent failed to generate a plan",
            missing_fields=data.get("missing_fields") or [],
            fallback_suggestions=data.get("fallback_suggestions") or [],
            needs_clarification=bool(data.get("needs_clarification")),
            clarification_type=data.get("clarification_type"),
            candidates=data.get("candidates") or [],
        )

    if "plan" in data and data.get("plan") is not None:
        return PlanResponse(
            success=True,
            request_id=data.get("request_id") or request.request_id,
            plan=data.get("plan"),
        )

    selected_plan = data.get("selected_plan")
    if not selected_plan:
        return PlanResponse(
            success=False,
            request_id=data.get("request_id") or request.request_id,
            error_code="NO_SELECTED_PLAN",
            message="Agent response did not include selected_plan",
        )

    return PlanResponse(
        success=True,
        request_id=data.get("request_id") or request.request_id,
        plan=_build_frontend_plan(data, selected_plan, request),
    )


def _build_frontend_plan(
    agent_data: dict[str, Any],
    selected_plan: dict[str, Any],
    request: PlanRequest,
) -> dict[str, Any]:
    stops = selected_plan.get("stops") or []
    route = selected_plan.get("route") or {}
    route_segments = route.get("segments") or []
    origin = _summary_location(
        stops[0] if stops else None,
        _location_fallback(request.start_location or request.current_location),
    )
    destination = _summary_location(
        stops[-1] if stops else None,
        _location_fallback(request.end_location),
    )
    poi_stops = [
        (index, stop)
        for index, stop in enumerate(stops)
        if stop.get("stop_type") not in {"start", "end"} and stop.get("poi")
    ]

    return {
        "summary": {
            "origin": origin,
            "destination": destination,
            "total_distance_km": round((route.get("distance_meters") or 0) / 1000, 1),
            "total_time_min": round(route.get("duration_minutes") or 0),
            "total_cost": round(selected_plan.get("estimated_cost") or 0, 2),
            "travel_mode": request.travel_mode,
            "recommend_reason": (
                selected_plan.get("recommendation_reason")
                or agent_data.get("summary")
                or "已为你生成顺路推荐方案"
            ),
        },
        "route_overview": {
            "waypoints": [_to_waypoint(stop, index) for index, stop in enumerate(stops)],
            "polyline": route.get("polyline") or [],
            "segments": [
                {
                    "from": index,
                    "to": index + 1,
                    "distance_m": segment.get("distance_meters") or 0,
                    "time_min": round(segment.get("duration_minutes") or 0),
                    "instruction": _segment_instruction(segment),
                }
                for index, segment in enumerate(route_segments)
            ],
        },
        "pois": [
            _to_frontend_poi(
                stop=stop,
                selected_plan=selected_plan,
                stop_index=stop_index,
                stops=stops,
                route_segments=route_segments,
                travel_mode=request.travel_mode,
            )
            for stop_index, stop in poi_stops
        ],
        "agent": {
            "summary": agent_data.get("summary"),
            "alternative_plans": agent_data.get("alternative_plans") or [],
            "warnings": agent_data.get("warnings") or [],
            "debug_trace": agent_data.get("debug_trace"),
        },
    }


def _summary_location(
    stop: dict[str, Any] | None,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    location = (stop or {}).get("location") or fallback
    return {
        "name": (stop or {}).get("name") or location.get("name") or fallback.get("name"),
        "address": location.get("address") or fallback.get("address") or "",
    }


def _location_fallback(location: Any) -> dict[str, Any]:
    return location.model_dump() if location is not None else {}


def _to_waypoint(stop: dict[str, Any], index: int) -> dict[str, Any]:
    location = stop.get("location") or {}
    stop_type = stop.get("stop_type")
    if stop_type == "start":
        waypoint_type = "origin"
    elif stop_type == "end":
        waypoint_type = "destination"
    else:
        waypoint_type = "poi"

    return {
        "order": index,
        "name": stop.get("name") or location.get("name") or f"途经点{index + 1}",
        "type": waypoint_type,
        "longitude": location.get("longitude"),
        "latitude": location.get("latitude"),
    }


def _segment_instruction(segment: dict[str, Any]) -> str:
    from_name = segment.get("from_name") or "上一站"
    to_name = segment.get("to_name") or "下一站"
    return f"从{from_name}前往{to_name}"


def _to_frontend_poi(
    stop: dict[str, Any],
    selected_plan: dict[str, Any],
    stop_index: int,
    stops: list[dict[str, Any]],
    route_segments: list[dict[str, Any]],
    travel_mode: str,
) -> dict[str, Any]:
    poi = stop.get("poi") or {}
    location = stop.get("location") or {}
    deal = stop.get("deal")
    deals = [deal] if deal else []
    detour = _stop_marginal_detour(
        stop_index=stop_index,
        stops=stops,
        route_segments=route_segments,
        travel_mode=travel_mode,
    )
    return {
        "poi_id": poi.get("poi_id") or stop.get("task_id") or stop.get("name"),
        "name": poi.get("name") or stop.get("name"),
        "type": _display_type(poi.get("type")),
        "address": poi.get("address") or location.get("address") or "",
        "longitude": poi.get("longitude") or location.get("longitude"),
        "latitude": poi.get("latitude") or location.get("latitude"),
        "rating": poi.get("rating"),
        "cost": poi.get("cost"),
        "detour_meters": detour["meters"],
        "detour_time_min": detour["minutes"],
        "recommend_score": selected_plan.get("score"),
        "recommend_reason": stop.get("reason")
        or selected_plan.get("recommendation_reason")
        or "真实顺路 POI",
        "deals": deals,
    }


def _stop_marginal_detour(
    stop_index: int,
    stops: list[dict[str, Any]],
    route_segments: list[dict[str, Any]],
    travel_mode: str,
) -> dict[str, int]:
    if stop_index <= 0 or stop_index >= len(stops) - 1:
        return {"meters": 0, "minutes": 0}

    prev_location = (stops[stop_index - 1] or {}).get("location") or {}
    next_location = (stops[stop_index + 1] or {}).get("location") or {}
    direct_distance = _distance_between_locations(prev_location, next_location)
    if direct_distance is None:
        return {"meters": None, "minutes": None}

    inbound = route_segments[stop_index - 1] if stop_index - 1 < len(route_segments) else {}
    outbound = route_segments[stop_index] if stop_index < len(route_segments) else {}
    actual_distance = (inbound.get("distance_meters") or 0) + (outbound.get("distance_meters") or 0)
    actual_minutes = (inbound.get("duration_minutes") or 0) + (outbound.get("duration_minutes") or 0)
    direct_minutes = direct_distance / _speed_meters_per_minute(travel_mode)

    return {
        "meters": max(0, int(round(actual_distance - direct_distance))),
        "minutes": max(0, int(round(actual_minutes - direct_minutes))),
    }


def _distance_between_locations(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    try:
        lon1 = float(a.get("longitude"))
        lat1 = float(a.get("latitude"))
        lon2 = float(b.get("longitude"))
        lat2 = float(b.get("latitude"))
    except (TypeError, ValueError):
        return None

    import math

    earth_radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return earth_radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _speed_meters_per_minute(travel_mode: str) -> float:
    return {
        "walking": 75.0,
        "bicycling": 180.0,
        "driving": 420.0,
    }.get(travel_mode, 75.0)


def _display_type(value: Any) -> str:
    return {
        "drink": "饮品",
        "express": "快递",
        "food": "餐饮",
        "movie": "电影",
        "board_game": "桌游",
        "hair": "理发",
        "nail": "美甲",
        "entertainment": "娱乐",
        "study": "学习",
    }.get(str(value), str(value or "推荐"))
