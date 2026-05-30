"""
Route calculation service backed by Amap Web Service APIs.
"""
from typing import Any

import httpx

from app.config import get_settings
from app.schemas import Point, RouteCalculateResponse, RouteSegment


class AmapRouteError(RuntimeError):
    """Raised when Amap route calculation cannot produce a valid route."""


class AmapRouteClient:
    """Small synchronous client for Amap route APIs."""

    MODE_PATHS = {
        "walking": "/v3/direction/walking",
        "driving": "/v3/direction/driving",
        "bicycling": "/v4/direction/bicycling",
    }

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.amap_key:
            raise AmapRouteError("AMAP_KEY is required for route calculation")
        self.api_key = settings.amap_key
        self.base_url = settings.amap_base_url
        self.timeout = settings.amap_timeout_seconds

    def calculate_segment(
        self,
        origin: Point,
        destination: Point,
        travel_mode: str,
    ) -> tuple[int, float, list[list[float]]]:
        path = self.MODE_PATHS.get(travel_mode)
        if path is None:
            raise AmapRouteError(f"Unsupported travel_mode: {travel_mode}")

        payload = self._get_json(
            path,
            {
                "origin": format_location(origin),
                "destination": format_location(destination),
            },
        )
        return parse_amap_route_payload(payload)

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        merged_params = {**params, "key": self.api_key, "output": "JSON"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}{path}", params=merged_params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise AmapRouteError(f"Amap route request failed: {exc}") from exc
        except ValueError as exc:
            raise AmapRouteError("Amap route response is not valid JSON") from exc

        if not is_success_payload(payload):
            info = payload.get("info") or payload.get("errmsg") or "unknown error"
            code = payload.get("infocode") or payload.get("errcode") or "unknown code"
            raise AmapRouteError(f"Amap route API failed: {info} ({code})")
        return payload


def calculate_route(
    points: list[Point],
    travel_mode: str = "walking",
) -> RouteCalculateResponse:
    """
    Calculate route distance and time for given points using Amap.

    Args:
        points: List of points to route through
        travel_mode: Mode of travel ('walking', 'bicycling', 'driving')

    Returns:
        RouteCalculateResponse with distance, duration, polyline, and segments
    """
    if len(points) < 2:
        raise ValueError("At least 2 points are required")

    client = AmapRouteClient()
    total_distance = 0
    total_duration_seconds = 0.0
    segments: list[RouteSegment] = []
    full_polyline: list[list[float]] = []

    for i in range(len(points) - 1):
        origin = points[i]
        destination = points[i + 1]
        distance, duration_seconds, segment_polyline = client.calculate_segment(
            origin=origin,
            destination=destination,
            travel_mode=travel_mode,
        )

        total_distance += distance
        total_duration_seconds += duration_seconds
        segments.append(
            RouteSegment(
                from_name=origin.name,
                to_name=destination.name,
                distance_meters=distance,
                duration_minutes=round(duration_seconds / 60, 1),
            )
        )
        append_polyline(full_polyline, segment_polyline)

    return RouteCalculateResponse(
        distance_meters=total_distance,
        duration_minutes=round(total_duration_seconds / 60, 1),
        polyline=full_polyline,
        segments=segments,
    )


def format_location(point: Point) -> str:
    return f"{point.longitude},{point.latitude}"


def is_success_payload(payload: dict[str, Any]) -> bool:
    if payload.get("status") == "1":
        return True
    if payload.get("errcode") in (0, "0") or payload.get("errno") in (0, "0"):
        return True
    return False


def parse_amap_route_payload(payload: dict[str, Any]) -> tuple[int, float, list[list[float]]]:
    route = payload.get("route") or payload.get("data") or {}
    paths = route.get("paths") or route.get("path") or []
    if not paths:
        raise AmapRouteError("Amap route response contains no route paths")

    path = paths[0]
    try:
        distance = int(float(path.get("distance", 0)))
        duration_seconds = float(path.get("duration", 0))
    except (TypeError, ValueError) as exc:
        raise AmapRouteError("Amap route response contains invalid distance or duration") from exc

    if distance <= 0 or duration_seconds <= 0:
        raise AmapRouteError("Amap route response contains empty distance or duration")

    polyline = parse_polyline_from_path(path)
    if not polyline:
        raise AmapRouteError("Amap route response contains no polyline")

    return distance, duration_seconds, polyline


def parse_polyline_from_path(path: dict[str, Any]) -> list[list[float]]:
    polylines: list[str] = []
    if path.get("polyline"):
        polylines.append(str(path["polyline"]))
    for step in path.get("steps", []) or []:
        if step.get("polyline"):
            polylines.append(str(step["polyline"]))

    points: list[list[float]] = []
    for polyline in polylines:
        for raw_point in polyline.split(";"):
            if not raw_point:
                continue
            try:
                lon, lat = raw_point.split(",", 1)
                points.append([float(lon), float(lat)])
            except ValueError as exc:
                raise AmapRouteError("Amap route response contains invalid polyline") from exc
    return points


def append_polyline(target: list[list[float]], segment: list[list[float]]) -> None:
    if target and segment and target[-1] == segment[0]:
        target.extend(segment[1:])
    else:
        target.extend(segment)
