"""
POI search service with cache-first AMap enrichment.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import POI
from app.schemas import Point, POIResponse, POISarchResponse
from app.services.amap_service import AMapClient, NormalizedPOI
from app.services.distance import haversine_distance_meters
from app.services.mock_deal_service import ensure_mock_deals_for_poi


DEMO_CENTER_LONGITUDE = 114.126
DEMO_CENTER_LATITUDE = 30.459
DEMO_AREA_RADIUS_METERS = 3000

KEYWORD_SYNONYMS = {
    "饮品": ["奶茶", "咖啡", "冷饮", "喝的", "茶"],
    "奶茶": ["饮品", "冷饮", "茶"],
    "咖啡": ["饮品"],
    "快递": ["菜鸟驿站", "快递柜", "驿站"],
    "菜鸟驿站": ["快递", "驿站"],
    "吃饭": ["食堂", "小吃", "快餐", "餐厅", "餐饮"],
    "饭": ["食堂", "小吃", "快餐", "餐厅", "餐饮"],
    "午饭": ["食堂", "小吃", "快餐", "餐厅", "餐饮"],
    "娱乐": ["休闲", "运动", "健身", "电影", "KTV"],
}


def get_keyword_matches(keyword: str) -> set[str]:
    matches = {keyword}
    if keyword in KEYWORD_SYNONYMS:
        matches.update(KEYWORD_SYNONYMS[keyword])
    for key, synonyms in KEYWORD_SYNONYMS.items():
        if keyword in synonyms:
            matches.add(key)
    return matches


def search_pois(
    db: Session,
    source_keywords: list[str],
    center: Optional[Point] = None,
    radius_meters: Optional[int] = None,
    limit: int = 5,
) -> POISarchResponse:
    """
    Search POIs by keywords. Use local DB first, then fill the cache from AMap.
    """
    settings = get_settings()
    effective_radius = radius_meters or settings.amap_default_radius_meters
    local_matches = _find_local_matches(db, source_keywords, center, effective_radius)

    if _should_fetch_amap(local_matches, limit, center):
        _fetch_and_store_amap_pois(
            db=db,
            source_keywords=source_keywords,
            center=center,
            radius_meters=effective_radius,
            limit=max(limit, settings.poi_cache_min_results),
        )
        local_matches = _find_local_matches(db, source_keywords, center, effective_radius)

    local_matches.sort(key=_sort_key)
    return POISarchResponse(
        pois=[_to_response(poi, distance) for poi, distance in local_matches[:limit]]
    )


def _find_local_matches(
    db: Session,
    source_keywords: list[str],
    center: Optional[Point],
    radius_meters: int,
) -> list[tuple[POI, Optional[float]]]:
    all_matching_keywords = set()
    for keyword in source_keywords:
        all_matching_keywords.update(get_keyword_matches(keyword))

    matched: list[tuple[POI, Optional[float]]] = []
    for poi in db.query(POI).all():
        if not _matches_keywords(poi, all_matching_keywords):
            continue

        distance: Optional[float] = None
        if center:
            distance = haversine_distance_meters(
                center.longitude,
                center.latitude,
                poi.longitude,
                poi.latitude,
            )
            if distance > radius_meters:
                continue
        matched.append((poi, distance))
    return matched


def _matches_keywords(poi: POI, keywords: set[str]) -> bool:
    fields = [
        poi.source_keyword,
        poi.source_key,
        poi.name,
        poi.type,
        poi.category_major,
        poi.category_minor,
        poi.source_type,
    ]
    haystack = " ".join(str(value or "") for value in fields)
    return any(keyword and keyword in haystack for keyword in keywords)


def _should_fetch_amap(
    local_matches: list[tuple[POI, Optional[float]]],
    limit: int,
    center: Optional[Point],
) -> bool:
    settings = get_settings()
    if not settings.amap_key or center is None:
        return False

    # If the request center is clearly outside the seeded demo campus, do not let
    # old seed/mock data suppress the first real AMap fetch for this area.
    if _is_outside_demo_area(center) and not _has_amap_match(local_matches):
        return True

    return len(local_matches) < min(limit, settings.poi_cache_min_results)


def _has_amap_match(local_matches: list[tuple[POI, Optional[float]]]) -> bool:
    return any((poi.source_provider or "").lower() == "amap" for poi, _ in local_matches)


def _is_outside_demo_area(center: Point) -> bool:
    return (
        haversine_distance_meters(
            DEMO_CENTER_LONGITUDE,
            DEMO_CENTER_LATITUDE,
            center.longitude,
            center.latitude,
        )
        > DEMO_AREA_RADIUS_METERS
    )


def _fetch_and_store_amap_pois(
    db: Session,
    source_keywords: list[str],
    center: Point,
    radius_meters: int,
    limit: int,
) -> None:
    settings = get_settings()
    client = AMapClient()
    fetched_count = 0
    seen_source_ids: set[str] = set()
    for keyword in source_keywords[: settings.amap_max_keywords_per_request]:
        pois = client.search_around(
            keyword=keyword,
            longitude=center.longitude,
            latitude=center.latitude,
            radius_meters=radius_meters,
            limit=limit,
        )
        for normalized in pois:
            if normalized.source_id in seen_source_ids:
                continue
            seen_source_ids.add(normalized.source_id)
            poi = _upsert_normalized_poi(db, normalized)
            ensure_mock_deals_for_poi(db, poi)
            fetched_count += 1
    if fetched_count:
        db.commit()


def _upsert_normalized_poi(db: Session, normalized: NormalizedPOI) -> POI:
    poi = (
        db.query(POI)
        .filter(POI.source_provider == "amap", POI.source_id == normalized.source_id)
        .first()
    )
    if poi is None:
        poi = db.query(POI).filter(POI.poi_id == normalized.poi_id).first()
    if poi is None:
        poi = POI(poi_id=normalized.poi_id)
        db.add(poi)

    poi.name = normalized.name
    poi.type = normalized.type
    poi.address = normalized.address
    poi.location = normalized.location
    poi.longitude = normalized.longitude
    poi.latitude = normalized.latitude
    poi.rating = normalized.rating
    poi.cost = normalized.cost
    poi.source_keyword = normalized.source_keyword
    poi.source_provider = "amap"
    poi.source_id = normalized.source_id
    poi.source_key = normalized.source_keyword
    poi.category_major = normalized.category_major
    poi.category_minor = normalized.category_minor
    poi.source_type = normalized.source_type
    poi.source_typecode = normalized.source_typecode
    poi.phone = normalized.phone
    poi.business_time = normalized.business_time
    return poi


def _sort_key(item: tuple[POI, Optional[float]]) -> tuple[float, float, float]:
    poi, distance = item
    dist_key = distance if distance is not None else float("inf")
    rating_key = -(poi.rating or 0)
    cost_key = poi.cost or float("inf")
    return (dist_key, rating_key, cost_key)


def _to_response(poi: POI, distance: Optional[float]) -> POIResponse:
    return POIResponse(
        poi_id=poi.poi_id,
        name=poi.name,
        type=poi.type,
        address=poi.address or "",
        location=poi.location or "",
        longitude=poi.longitude,
        latitude=poi.latitude,
        rating=poi.rating,
        cost=poi.cost,
        source_keyword=poi.source_keyword,
        source_provider=poi.source_provider,
        source_id=poi.source_id,
        source_key=poi.source_key,
        category_major=poi.category_major,
        category_minor=poi.category_minor,
        source_type=poi.source_type,
        source_typecode=poi.source_typecode,
        distance_meters=distance,
    )
