"""
Resolve user-entered locations before forwarding plan requests to the Agent.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

from app.schemas import LocationInput, PlanRequest
from app.services.amap_service import AMapClient


KNOWN_LOCATIONS = {
    "学生宿舍": {
        "name": "学生宿舍",
        "address": "学生宿舍区",
        "location": "学生宿舍区",
        "longitude": 114.1230,
        "latitude": 30.4560,
    },
    "宿舍": {
        "name": "学生宿舍",
        "address": "学生宿舍区",
        "location": "学生宿舍区",
        "longitude": 114.1230,
        "latitude": 30.4560,
    },
    "图书馆": {
        "name": "图书馆",
        "address": "校内图书馆",
        "location": "教学区",
        "longitude": 114.1280,
        "latitude": 30.4620,
    },
    "教学区": {
        "name": "教学区",
        "address": "教学区",
        "location": "教学区",
        "longitude": 114.1290,
        "latitude": 30.4630,
    },
    "商业街": {
        "name": "商业街",
        "address": "学校商业街",
        "location": "商业街",
        "longitude": 114.1260,
        "latitude": 30.4590,
    },
    "生活区": {
        "name": "生活区",
        "address": "生活区",
        "location": "生活区",
        "longitude": 114.1250,
        "latitude": 30.4584,
    },
    "学生服务中心": {
        "name": "学生服务中心",
        "address": "学生服务中心",
        "location": "宿舍区附近",
        "longitude": 114.1250,
        "latitude": 30.4580,
    },
    "一食堂": {
        "name": "一食堂",
        "address": "教学区旁",
        "location": "教学区",
        "longitude": 114.1290,
        "latitude": 30.4630,
    },
}


async def resolve_plan_locations(request: PlanRequest) -> PlanRequest:
    """Resolve arbitrary start/end names to coordinates when possible."""
    parsed_start, parsed_end = extract_start_end(request.user_query)
    city = request.city or "武汉"

    start_location, end_location = await asyncio.gather(
        resolve_location(request.start_location, parsed_start, city),
        resolve_location(request.end_location, parsed_end, city),
    )
    request.start_location = start_location
    request.end_location = end_location
    request.city = city
    return request


async def resolve_location(
    current: LocationInput,
    parsed_name: Optional[str],
    city: str,
) -> LocationInput:
    raw_name = (parsed_name or current.name or "").strip()
    if not raw_name:
        return current

    known = lookup_known_location(raw_name)
    if known:
        return LocationInput(**known)

    should_geocode = parsed_name is not None or not has_coordinates(current)
    if should_geocode:
        resolved = await AMapClient().geocode(raw_name, city=city)
        if resolved:
            return LocationInput(**resolved)

    if parsed_name is not None:
        return current.model_copy(update={"name": raw_name, "address": current.address or raw_name})
    return current


def lookup_known_location(name: str) -> Optional[dict]:
    compact = re.sub(r"\s+", "", name)
    for key, value in KNOWN_LOCATIONS.items():
        if key in compact or compact in key:
            return value
    return None


def has_coordinates(location: LocationInput) -> bool:
    return location.longitude is not None and location.latitude is not None


def extract_start_end(user_query: str) -> tuple[Optional[str], Optional[str]]:
    match = re.search(
        r"(?:从|自|由)\s*(?P<start>.+?)\s*(?:到|去|前往|->|→)\s*(?P<end>[^，,。；;]+)",
        user_query,
    )
    if not match:
        return None, None
    start = _clean_location_text(match.group("start"))
    end = _clean_location_text(match.group("end"))
    return start or None, end or None


def _clean_location_text(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^(我|我们|现在|当前位置|目前)\s*", "", value)
    value = re.sub(r"\s*(路上|顺路|途中|然后|再|，|,).*$", "", value)
    return value.strip()
