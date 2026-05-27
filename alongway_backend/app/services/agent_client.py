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
        async with httpx.AsyncClient(timeout=settings.agent_service_timeout) as client:
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
    origin = _summary_location(stops[0] if stops else None, request.start_location.model_dump())
    destination = _summary_location(
        stops[-1] if stops else None,
        request.end_location.model_dump(),
    )
    poi_stops = [
        stop
        for stop in stops
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
        "pois": [_to_frontend_poi(stop, selected_plan) for stop in poi_stops],
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
) -> dict[str, Any]:
    poi = stop.get("poi") or {}
    location = stop.get("location") or {}
    deal = stop.get("deal")
    deals = [deal] if deal else []
    return {
        "poi_id": poi.get("poi_id") or stop.get("task_id") or stop.get("name"),
        "name": poi.get("name") or stop.get("name"),
        "type": _display_type(poi.get("type")),
        "address": poi.get("address") or location.get("address") or "",
        "longitude": poi.get("longitude") or location.get("longitude"),
        "latitude": poi.get("latitude") or location.get("latitude"),
        "rating": poi.get("rating"),
        "cost": poi.get("cost"),
        "detour_meters": selected_plan.get("detour_distance_meters"),
        "detour_time_min": selected_plan.get("extra_time_minutes"),
        "recommend_score": selected_plan.get("score"),
        "recommend_reason": stop.get("reason")
        or selected_plan.get("recommendation_reason")
        or "顺路候选点",
        "deals": deals,
    }


def _display_type(value: Any) -> str:
    return {
        "drink": "饮品",
        "express": "快递",
        "food": "餐饮",
        "study": "学习",
    }.get(str(value), str(value or "推荐"))
