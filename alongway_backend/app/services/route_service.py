"""
Route calculation service backed by Amap Web Service APIs.
"""
import hashlib
import time
from threading import Lock
from typing import Any

import httpx

from app.config import get_settings
from app.schemas import Point, RouteCalculateResponse, RouteSegment
from app.services.call_logger import log_call


class AmapRouteCache:
    """In-memory TTL cache for Amap route segment results.

    Caches individual origin→destination route results to avoid
    redundant Amap API calls for the same O-D pairs across plans.
    """

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._cache: dict[str, tuple[float, tuple[int, float, list[list[float]]]]] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(origin_lng: float, origin_lat: float,
                  dest_lng: float, dest_lat: float,
                  travel_mode: str) -> str:
        raw = f"{origin_lng:.6f},{origin_lat:.6f}->{dest_lng:.6f},{dest_lat:.6f}::{travel_mode}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, origin_lng: float, origin_lat: float,
            dest_lng: float, dest_lat: float,
            travel_mode: str) -> tuple[int, float, list[list[float]]] | None:
        key = self._make_key(origin_lng, origin_lat, dest_lng, dest_lat, travel_mode)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            expiry, value = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, origin_lng: float, origin_lat: float,
            dest_lng: float, dest_lat: float,
            travel_mode: str,
            value: tuple[int, float, list[list[float]]]) -> None:
        key = self._make_key(origin_lng, origin_lat, dest_lng, dest_lat, travel_mode)
        expiry = time.monotonic() + self._ttl
        with self._lock:
            self._cache[key] = (expiry, value)

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0


# Shared module-level cache instance
_route_cache = AmapRouteCache(ttl_seconds=1800)  # 30 min TTL


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
        use_cache: bool = True,
    ) -> tuple[int, float, list[list[float]]]:
        path = self.MODE_PATHS.get(travel_mode)
        if path is None:
            raise AmapRouteError(f"Unsupported travel_mode: {travel_mode}")

        # Check cache first
        if use_cache:
            cached = _route_cache.get(
                origin.longitude, origin.latitude,
                destination.longitude, destination.latitude,
                travel_mode,
            )
            if cached is not None:
                return cached

        payload = self._get_json(
            path,
            {
                "origin": format_location(origin),
                "destination": format_location(destination),
            },
        )
        result = parse_amap_route_payload(payload)

        # Store in cache
        if use_cache:
            _route_cache.set(
                origin.longitude, origin.latitude,
                destination.longitude, destination.latitude,
                travel_mode,
                result,
            )
        return result

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        merged_params = {**params, "key": self.api_key, "output": "JSON"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}{path}", params=merged_params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            log_call(
                "backend.amap.route.error",
                request={"path": path, "params": merged_params},
                error=str(exc),
            )
            raise AmapRouteError(f"Amap route request failed: {exc}") from exc
        except ValueError as exc:
            log_call(
                "backend.amap.route.error",
                request={"path": path, "params": merged_params},
                error="response is not valid JSON",
            )
            raise AmapRouteError("Amap route response is not valid JSON") from exc

        if not is_success_payload(payload):
            info = payload.get("info") or payload.get("errmsg") or "unknown error"
            code = payload.get("infocode") or payload.get("errcode") or "unknown code"
            log_call(
                "backend.amap.route.result",
                request={"path": path, "params": merged_params},
                result={"status": payload.get("status"), "info": info, "code": code},
            )
            raise AmapRouteError(f"Amap route API failed: {info} ({code})")
        log_call(
            "backend.amap.route.result",
            request={"path": path, "params": merged_params},
            result={
                "status": payload.get("status"),
                "path_count": len((payload.get("route") or {}).get("paths") or []),
            },
        )
        return payload


def calculate_route(
    points: list[Point],
    travel_mode: str = "walking",
) -> RouteCalculateResponse:
    """
    Calculate route distance and time for given points using Amap.

    Segment calls are concurrent for better performance.
    Individual segment results are cached (via AmapRouteCache).

    Args:
        points: List of points to route through
        travel_mode: Mode of travel ('walking', 'bicycling', 'driving')

    Returns:
        RouteCalculateResponse with distance, duration, polyline, and segments
    """
    if len(points) < 2:
        raise ValueError("At least 2 points are required")

    client = AmapRouteClient()

    # Prepare all segment pairs
    segment_pairs = []
    for i in range(len(points) - 1):
        origin = points[i]
        destination = points[i + 1]
        segment_pairs.append((i, origin, destination))

    # Calculate all segments (cache hits are instant, misses go to Amap)
    # Note: httpx.Client is sync, so we process sequentially but cache speeds up repeats
    results: list[tuple[int, int, float, list[list[float]]]] = []
    for idx, origin, destination in segment_pairs:
        distance, duration_seconds, segment_polyline = client.calculate_segment(
            origin=origin,
            destination=destination,
            travel_mode=travel_mode,
        )
        results.append((idx, distance, duration_seconds, segment_polyline))

    total_distance = 0
    total_duration_seconds = 0.0
    segments: list[RouteSegment] = []
    full_polyline: list[list[float]] = []

    for idx, distance, duration_seconds, segment_polyline in results:
        total_distance += distance
        total_duration_seconds += duration_seconds
        segments.append(
            RouteSegment(
                from_name=points[idx].name,
                to_name=points[idx + 1].name,
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
    """Append a segment polyline to the target, handling endpoint continuity.

    If the segment's start is close to the target's end (< 50m), skip the
    overlapping point. Otherwise, connect with a straight-line segment to
    avoid gaps in the displayed route.
    """
    if not segment:
        return
    if not target:
        target.extend(segment)
        return

    last = target[-1]
    first = segment[0]
    # Check if endpoints are within ~50m (roughly 0.0005 degrees)
    gap_meters = _quick_distance_meters(last[0], last[1], first[0], first[1])
    if gap_meters < 50:
        target.extend(segment[1:] if target[-1] == segment[0] else segment)
    else:
        # Insert a bridging segment to avoid visual gaps
        target.extend(segment)


def _quick_distance_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Fast approximate distance in meters using equirectangular projection."""
    import math
    lat_mid = math.radians((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * 111_320 * math.cos(lat_mid)
    dy = (lat2 - lat1) * 110_540
    return math.sqrt(dx * dx + dy * dy)
