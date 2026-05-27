"""
AMap Web service integration and POI normalization.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import get_settings


FOOD_MAJOR = "餐饮服务"
ENTERTAINMENT_MAJOR = "体育休闲服务"
SCENIC_MAJOR = "风景名胜"
LIFE_MAJOR = "生活服务"
SHOPPING_MAJOR = "购物服务"

BLOCKED_TYPE_TERMS = {
    "停车场",
    "交通设施服务",
    "汽车服务",
    "汽车维修",
    "摩托车服务",
    "政府机构",
    "公司企业",
    "商务住宅",
    "住宅区",
    "公共设施",
    "道路附属设施",
    "地名地址信息",
    "出入口",
    "收费站",
    "桥",
    "隧道",
    "加油站",
    "充电站",
}

LIGHT_LIFE_TERMS = {
    "快递",
    "菜鸟",
    "驿站",
    "快递柜",
    "打印",
    "文印",
    "复印",
    "洗衣",
    "便利店",
    "超市",
}

ENTERTAINMENT_TERMS = {
    "影剧院",
    "电影院",
    "KTV",
    "歌厅",
    "网吧",
    "游戏厅",
    "游乐",
    "健身",
    "运动",
    "桌游",
    "密室",
    "娱乐",
    "休闲",
}

DRINK_TERMS = {"奶茶", "饮品", "咖啡", "冷饮", "茶", "甜品"}
FOOD_TERMS = {"吃饭", "午饭", "晚饭", "食堂", "小吃", "快餐", "餐厅", "餐馆", "美食"}


@dataclass
class NormalizedPOI:
    source_id: str
    name: str
    type: str
    address: str
    location: str
    longitude: float
    latitude: float
    rating: Optional[float]
    cost: Optional[float]
    source_keyword: str
    category_major: Optional[str]
    category_minor: Optional[str]
    source_type: Optional[str]
    source_typecode: Optional[str]
    phone: Optional[str]
    business_time: Optional[str]

    @property
    def poi_id(self) -> str:
        return f"amap_{self.source_id}"


class AMapClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.key = settings.amap_key
        self.base_url = settings.amap_base_url.rstrip("/")
        self.timeout = settings.amap_timeout
        self.city = settings.amap_city

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    async def geocode(self, address: str, city: Optional[str] = None) -> Optional[dict[str, Any]]:
        if not self.enabled or not address:
            return None
        params = {
            "key": self.key,
            "address": address,
            "city": city or self.city,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/geocode/geo", params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None

        if data.get("status") != "1":
            return await self.search_place_text(address, city=city)
        geocodes = data.get("geocodes") or []
        if not geocodes:
            return await self.search_place_text(address, city=city)
        item = geocodes[0]
        longitude, latitude = _parse_location(item.get("location"))
        if longitude is None or latitude is None:
            return await self.search_place_text(address, city=city)
        return {
            "name": item.get("formatted_address") or address,
            "address": item.get("formatted_address") or address,
            "location": item.get("formatted_address") or address,
            "longitude": longitude,
            "latitude": latitude,
        }

    async def search_place_text(
        self,
        keyword: str,
        city: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Use AMap POI text search as a fallback for campus buildings/landmarks."""
        if not self.enabled or not keyword:
            return None
        params = {
            "key": self.key,
            "keywords": keyword,
            "city": city or self.city,
            "offset": 1,
            "page": 1,
            "extensions": "base",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/place/text", params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None

        if data.get("status") != "1":
            return None
        pois = data.get("pois") or []
        if not pois:
            return None
        item = pois[0]
        longitude, latitude = _parse_location(item.get("location"))
        if longitude is None or latitude is None:
            return None
        return {
            "name": item.get("name") or keyword,
            "address": item.get("address") or keyword,
            "location": item.get("adname") or item.get("business_area") or keyword,
            "longitude": longitude,
            "latitude": latitude,
        }

    def search_around(
        self,
        keyword: str,
        longitude: float,
        latitude: float,
        radius_meters: int,
        limit: int,
    ) -> list[NormalizedPOI]:
        if not self.enabled:
            return []

        params = {
            "key": self.key,
            "location": f"{longitude},{latitude}",
            "keywords": to_amap_keyword(keyword),
            "radius": max(200, min(radius_meters, 5000)),
            "offset": max(1, min(limit, 20)),
            "page": 1,
            "extensions": "all",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/place/around", params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return []

        if data.get("status") != "1":
            return []
        normalized: list[NormalizedPOI] = []
        for raw_poi in data.get("pois") or []:
            poi = normalize_amap_poi(raw_poi, keyword)
            if poi is not None:
                normalized.append(poi)
        return normalized


def to_amap_keyword(keyword: str) -> str:
    text = keyword.strip()
    if any(term in text for term in DRINK_TERMS):
        return "奶茶"
    if any(term in text for term in FOOD_TERMS):
        return "餐饮"
    if any(term in text for term in LIGHT_LIFE_TERMS):
        return "快递"
    if any(term in text for term in ENTERTAINMENT_TERMS):
        return "娱乐"
    return text


def normalize_amap_poi(raw_poi: dict[str, Any], source_keyword: str) -> Optional[NormalizedPOI]:
    name = str(raw_poi.get("name") or "").strip()
    source_type = str(raw_poi.get("type") or "").strip()
    typecode = str(raw_poi.get("typecode") or "").strip() or None
    if not name:
        return None

    longitude, latitude = _parse_location(raw_poi.get("location"))
    if longitude is None or latitude is None:
        return None

    type_parts = [part.strip() for part in source_type.split(";") if part.strip()]
    category_major = type_parts[0] if type_parts else None
    category_minor = type_parts[-1] if len(type_parts) > 1 else None
    poi_text = ";".join([name, source_type])
    blocked_text = ";".join([name, source_type, source_keyword])

    if any(term in blocked_text for term in BLOCKED_TYPE_TERMS):
        return None

    if category_major == FOOD_MAJOR:
        internal_type = "drink" if any(term in poi_text for term in DRINK_TERMS) else "food"
    elif category_major in {ENTERTAINMENT_MAJOR, SCENIC_MAJOR} or any(
        term in poi_text for term in ENTERTAINMENT_TERMS
    ):
        internal_type = "entertainment"
    elif category_major in {LIFE_MAJOR, SHOPPING_MAJOR} and any(
        term in poi_text for term in LIGHT_LIFE_TERMS
    ):
        internal_type = "express" if any(term in poi_text for term in {"快递", "菜鸟", "驿站", "快递柜"}) else "life"
    else:
        return None

    source_id = str(raw_poi.get("id") or "").strip()
    if not source_id:
        source_id = hashlib.sha1(f"{name}:{longitude}:{latitude}".encode("utf-8")).hexdigest()[:16]

    biz_ext = raw_poi.get("biz_ext") or {}
    if not isinstance(biz_ext, dict):
        biz_ext = {}

    return NormalizedPOI(
        source_id=source_id,
        name=name,
        type=internal_type,
        address=str(raw_poi.get("address") or raw_poi.get("pname") or "").strip(),
        location=str(raw_poi.get("adname") or raw_poi.get("business_area") or "").strip(),
        longitude=longitude,
        latitude=latitude,
        rating=_parse_float(biz_ext.get("rating")),
        cost=_parse_float(biz_ext.get("cost")),
        source_keyword=source_keyword,
        category_major=category_major,
        category_minor=category_minor,
        source_type=source_type or None,
        source_typecode=typecode,
        phone=str(raw_poi.get("tel") or "").strip() or None,
        business_time=str(biz_ext.get("opentime") or biz_ext.get("business_time") or "").strip()
        or None,
    )


def _parse_location(value: Any) -> tuple[Optional[float], Optional[float]]:
    if not value or not isinstance(value, str) or "," not in value:
        return None, None
    raw_lon, raw_lat = value.split(",", 1)
    try:
        return float(raw_lon), float(raw_lat)
    except ValueError:
        return None, None


def _parse_float(value: Any) -> Optional[float]:
    if value in (None, "", "[]"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
