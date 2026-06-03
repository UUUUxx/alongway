"""
POI search service with fuzzy matching and filtering.
"""
import hashlib
import logging
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import POI
from app.schemas import Point, POIResponse, POISarchResponse
from app.services.call_logger import log_call
from app.services.deal_service import ensure_mock_deals
from app.services.distance import haversine_distance_meters

logger = logging.getLogger(__name__)

KEYWORD_SYNONYMS = {
    "饮品": ["奶茶", "咖啡", "果茶", "茶饮"],
    "奶茶": ["饮品", "茶饮", "果茶"],
    "咖啡": ["饮品", "美式", "拿铁"],
    "吃饭": ["简餐", "食堂", "便当", "轻食", "快餐"],
    "简餐": ["吃饭", "便当", "轻食", "快餐"],
    "水果": ["鲜果", "果切"],
    "快递": ["取件", "寄件", "快递站", "取件柜"],
    "取件": ["快递", "快递站", "取件柜"],
    "打印": ["复印", "彩印", "证件照"],
    "韩餐": ["韩国料理", "餐厅", "吃饭"],
    "烤鱼": ["鱼火锅"],
    "烧烤": ["烤肉"],
    "烤肉": ["烧烤"],
    "火锅": ["涮锅"],
    "日料": ["日本料理", "寿司"],
    "寿司": ["日料", "日本料理"],
    "电影": ["电影院", "影城", "影院", "电影票"],
    "电影院": ["影城", "影院", "电影"],
    "桌游": ["桌游店", "桌游吧", "剧本杀"],
    "桌游店": ["桌游", "桌游吧", "剧本杀"],
    "理发": ["理发店", "美发", "发型设计", "沙龙"],
    "理发店": ["理发", "美发", "发型设计", "沙龙"],
    "美甲": ["美甲店", "美睫美甲", "做指甲"],
    "美甲店": ["美甲", "美睫美甲", "做指甲"],
    "娱乐": ["电影院", "影城", "桌游店", "棋牌室", "密室逃脱", "KTV"],
}


def get_keyword_matches(keyword: str) -> set[str]:
    """
    Get all matching keywords including synonyms.

    Args:
        keyword: Input keyword

    Returns:
        Set of all matching keywords, including synonyms
    """
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
    specific_place_name: Optional[str] = None,
) -> POISarchResponse:
    """
    Search POIs by keywords with optional distance filtering.

    Args:
        db: Database session
        source_keywords: List of keywords to search
        center: Optional center point for distance filter
        radius_meters: Optional radius to filter by
        limit: Max results to return

    Returns:
        POISarchResponse with matching POIs
    """
    all_matching_keywords = set()
    for kw in source_keywords:
        all_matching_keywords.update(get_keyword_matches(kw))
    if specific_place_name:
        all_matching_keywords.add(specific_place_name)

    pois = db.query(POI).all()
    matching_pois = [poi for poi in pois if _matches_poi(poi, all_matching_keywords, specific_place_name)]

    if center and radius_meters:
        filtered_pois = []
        for poi in matching_pois:
            distance = haversine_distance_meters(
                center.longitude,
                center.latitude,
                poi.longitude,
                poi.latitude,
            )
            if distance <= radius_meters:
                filtered_pois.append((poi, distance))
        matching_items = filtered_pois
    else:
        matching_items = [(poi, None) for poi in matching_pois]

    def sort_key(item):
        poi, distance = item
        dist_key = distance if distance is not None else float("inf")
        rating_key = -(poi.rating or 0)
        cost_key = poi.cost or float("inf")
        return (dist_key, rating_key, cost_key)

    matching_items.sort(key=sort_key)

    local_poi_responses = [_to_poi_response(poi, distance) for poi, distance in matching_items[:limit]]
    _ensure_mock_deals_for_responses(db, local_poi_responses)
    poi_responses = list(local_poi_responses)

    if len(poi_responses) < limit:
        amap_pois = _search_amap_pois(
            keywords=source_keywords,
            specific_place_name=specific_place_name,
            center=center,
            radius_meters=radius_meters,
            limit=limit - len(poi_responses),
            existing_names={poi.name for poi, _ in matching_items},
        )
        _upsert_pois(db, amap_pois, source="amap")
        poi_responses.extend(amap_pois)

    log_call(
        "backend.internal_pois.search.result",
        request={
            "source_keywords": source_keywords,
            "center": center,
            "radius_meters": radius_meters,
            "limit": limit,
            "specific_place_name": specific_place_name,
        },
        result={
            "local_count": len(local_poi_responses),
            "total_count": len(poi_responses),
            "pois": poi_responses,
        },
    )

    return POISarchResponse(pois=poi_responses)


def _matches_poi(
    poi: POI,
    keywords: set[str],
    specific_place_name: Optional[str],
) -> bool:
    text = f"{poi.name} {poi.address or ''} {poi.location or ''} {poi.type or ''} {poi.source_keyword}".lower()
    if specific_place_name:
        return specific_place_name.lower() in text
    significant_keywords = _significant_keywords(keywords)
    if significant_keywords:
        return any(keyword.lower() in text for keyword in significant_keywords)
    return any(keyword.lower() in text or text in keyword.lower() for keyword in keywords)


def _to_poi_response(poi: POI, distance: Optional[float]) -> POIResponse:
    return POIResponse(
        poi_id=poi.poi_id,
        name=poi.name,
        type=poi.type,
        address=poi.address,
        location=poi.location,
        longitude=poi.longitude,
        latitude=poi.latitude,
        rating=poi.rating,
        cost=poi.cost,
        source_keyword=poi.source_keyword,
        distance_meters=distance if distance is not None else None,
    )


def _search_amap_pois(
    keywords: list[str],
    specific_place_name: Optional[str],
    center: Optional[Point],
    radius_meters: Optional[int],
    limit: int,
    existing_names: set[str],
) -> list[POIResponse]:
    settings = get_settings()
    if limit <= 0 or not settings.amap_key:
        return []
    search_keyword = specific_place_name or " ".join(keywords[:3])
    if not search_keyword.strip():
        return []

    path = "/v3/place/around" if center else "/v3/place/text"
    params = {
        "key": settings.amap_key,
        "keywords": search_keyword,
        "offset": str(limit),
        "page": "1",
        "extensions": "all",
        "output": "JSON",
    }
    if center:
        params.update(
            {
                "location": f"{center.longitude},{center.latitude}",
                "radius": str(radius_meters or 1500),
                "sortrule": "distance",
            }
        )
    else:
        params["citylimit"] = "false"

    try:
        with httpx.Client(timeout=settings.amap_timeout_seconds) as client:
            response = client.get(f"{settings.amap_base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log_call(
            "backend.amap.poi.error",
            request={"path": path, "params": params},
            error=str(exc),
        )
        logger.warning("Amap POI search failed: %s", exc)
        return []

    if payload.get("status") != "1":
        log_call(
            "backend.amap.poi.result",
            request={"path": path, "params": params},
            result={"status": payload.get("status"), "info": payload.get("info")},
        )
        logger.warning("Amap POI search failed: %s", payload.get("info"))
        return []

    results: list[POIResponse] = []
    for item in payload.get("pois", []) or []:
        name = item.get("name") or search_keyword
        if name in existing_names:
            continue
        if not _matches_amap_item(item, keywords, specific_place_name):
            continue
        location = item.get("location") or ""
        if "," not in location:
            continue
        try:
            lon_str, lat_str = location.split(",", 1)
            lon = float(lon_str)
            lat = float(lat_str)
        except ValueError:
            continue
        distance = None
        if center:
            distance = haversine_distance_meters(center.longitude, center.latitude, lon, lat)
        results.append(
            POIResponse(
                poi_id=f"amap_{hashlib.md5((item.get('id') or name + location).encode('utf-8')).hexdigest()[:12]}",
                name=name,
                type=_infer_type(keywords, specific_place_name),
                address=item.get("address") or "",
                location=location,
                longitude=lon,
                latitude=lat,
                rating=_parse_float(((item.get("biz_ext") or {}).get("rating"))),
                cost=_parse_float(((item.get("biz_ext") or {}).get("cost"))),
                source_keyword=specific_place_name or (keywords[0] if keywords else search_keyword),
                distance_meters=distance,
            )
        )
    results = results[:limit]
    log_call(
        "backend.amap.poi.result",
        request={"path": path, "params": params},
        result={
            "status": payload.get("status"),
            "count": len(results),
            "pois": results,
        },
    )
    return results


def _matches_amap_item(
    item: dict,
    keywords: list[str],
    specific_place_name: Optional[str],
) -> bool:
    text = _amap_item_text(item)
    if specific_place_name:
        return specific_place_name.lower() in text
    significant_keywords = _significant_keywords(set(keywords))
    if not significant_keywords:
        return True
    return any(keyword.lower() in text for keyword in significant_keywords)


def _amap_item_text(item: dict) -> str:
    fields = [
        item.get("name"),
        item.get("type"),
        item.get("address"),
        item.get("tag"),
        item.get("keytag"),
        item.get("atag"),
    ]
    biz_ext = item.get("biz_ext") or {}
    if isinstance(biz_ext, dict):
        fields.extend([biz_ext.get("tag"), biz_ext.get("cost")])
    return " ".join(str(value) for value in fields if value not in (None, "", [])).lower()


def _significant_keywords(keywords: set[str]) -> set[str]:
    generic_keywords = {
        "餐厅",
        "吃饭",
        "吃的",
        "食堂",
        "小吃",
        "快餐",
        "饮品",
        "茶饮",
        "娱乐",
        "商场",
    }
    strict_roots = {
        "烧烤",
        "烤肉",
        "烤鱼",
        "韩餐",
        "韩国料理",
        "火锅",
        "日料",
        "日本料理",
        "寿司",
        "蛋糕",
        "甜品",
        "甜点",
        "面包",
        "奶茶",
        "咖啡",
        "理发",
        "理发店",
        "美发",
        "美甲",
        "美甲店",
        "电影院",
        "影城",
        "影院",
        "桌游",
        "桌游店",
        "KTV",
    }
    expanded = set()
    for keyword in keywords:
        if keyword in generic_keywords:
            continue
        if keyword in strict_roots:
            expanded.update(get_keyword_matches(keyword))
    return {keyword for keyword in expanded if keyword not in generic_keywords}


def _parse_float(value: object) -> Optional[float]:
    try:
        if value in (None, "", "[]"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_type(keywords: list[str], specific_place_name: Optional[str]) -> str:
    text = " ".join([specific_place_name or "", *keywords])
    if any(word in text for word in ["咖啡", "奶茶", "饮品", "星巴克", "瑞幸"]):
        return "drink"
    if any(
        word in text
        for word in [
            "韩餐",
            "韩国料理",
            "烧烤",
            "烤肉",
            "烤鱼",
            "火锅",
            "日料",
            "日本料理",
            "寿司",
            "蛋糕",
            "甜品",
            "甜点",
            "面包",
            "餐厅",
            "吃饭",
            "食堂",
        ]
    ):
        return "food"
    if any(word in text for word in ["快递", "驿站", "菜鸟", "取件"]):
        return "express"
    if any(word in text for word in ["电影", "电影院", "影城", "影院"]):
        return "movie"
    if any(word in text for word in ["桌游", "桌游店", "桌游吧", "剧本杀"]):
        return "board_game"
    if any(word in text for word in ["理发", "理发店", "美发", "发型设计", "沙龙"]):
        return "hair"
    if any(word in text for word in ["美甲", "美甲店", "美睫美甲", "做指甲"]):
        return "nail"
    if any(word in text for word in ["娱乐", "KTV", "密室", "棋牌"]):
        return "entertainment"
    return "custom"


def _upsert_pois(db: Session, poi_responses: list[POIResponse], source: str) -> None:
    if not poi_responses:
        return

    saved = []
    for poi in poi_responses:
        existing = db.get(POI, poi.poi_id)
        if existing is None:
            existing = POI(poi_id=poi.poi_id)
            db.add(existing)
        existing.name = poi.name
        existing.type = poi.type
        existing.address = poi.address
        existing.location = poi.location
        existing.longitude = poi.longitude
        existing.latitude = poi.latitude
        existing.rating = poi.rating
        existing.cost = poi.cost
        existing.source_keyword = poi.source_keyword
        ensure_mock_deals(
            db=db,
            poi_id=poi.poi_id,
            categories=[poi.source_keyword or poi.type],
            max_price=None,
        )
        saved.append({"poi_id": poi.poi_id, "name": poi.name, "source": source})

    try:
        db.commit()
        log_call("backend.poi.persist.result", result={"count": len(saved), "pois": saved})
    except Exception as exc:
        db.rollback()
        log_call("backend.poi.persist.error", result={"pois": saved}, error=str(exc))
        logger.warning("Failed to persist POIs: %s", exc)


def _ensure_mock_deals_for_responses(db: Session, poi_responses: list[POIResponse]) -> None:
    for poi in poi_responses:
        if poi.poi_id.startswith(("amap_", "mock_")):
            ensure_mock_deals(
                db=db,
                poi_id=poi.poi_id,
                categories=[poi.source_keyword or poi.type],
                max_price=None,
            )
