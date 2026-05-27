"""
Deterministic mock group-buy deals for fetched POIs.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.models import Deal, POI


DEAL_ELIGIBLE_TYPES = {"drink", "food", "entertainment"}


def ensure_mock_deals_for_poi(db: Session, poi: POI) -> None:
    """Create stable mock deals for eligible POIs that do not have deals yet."""
    if poi.type not in DEAL_ELIGIBLE_TYPES:
        return
    existing = db.query(Deal).filter(Deal.poi_id == poi.poi_id).first()
    if existing:
        return

    for deal in build_mock_deals(poi):
        db.merge(deal)
    db.commit()


def build_mock_deals(poi: POI) -> list[Deal]:
    base = _stable_number(poi.poi_id, 0, 100)
    category = poi.source_keyword or _category_for_type(poi.type)
    business_time = poi.business_time or _business_time_for_type(poi.type)

    templates = _templates_for_type(poi.type)
    deals: list[Deal] = []
    for index, template in enumerate(templates, start=1):
        price = _price_for_type(poi.type, base, index)
        original_price = round(price * (1.25 + (base % 4) * 0.08), 1)
        deal_hash = hashlib.sha1(f"{poi.poi_id}:{index}".encode("utf-8")).hexdigest()[:12]
        deals.append(
            Deal(
                deal_id=f"mock_{deal_hash}_{index}",
                poi_id=poi.poi_id,
                name=poi.name,
                category=category,
                deal_title=template["title"],
                price=price,
                original_price=original_price,
                included_items=json.dumps(template["items"], ensure_ascii=False),
                additional_information="系统根据 POI 分类生成的演示团购，实际以门店为准",
                valid_time=template["valid_time"],
                rating=round(min(5.0, max(3.8, (poi.rating or 4.2) - 0.1 + index * 0.05)), 1),
                monthly_sales=120 + base * 7 + index * 43,
                reviews=json.dumps(template["reviews"], ensure_ascii=False),
                business_time=business_time,
            )
        )
    return deals


def _templates_for_type(poi_type: str) -> list[dict]:
    if poi_type == "drink":
        return [
            {
                "title": "招牌饮品单人券",
                "items": ["招牌饮品1杯", "可选小料1份"],
                "valid_time": "10:00-21:30",
                "reviews": ["价格划算", "出餐稳定"],
            },
            {
                "title": "下午茶双杯券",
                "items": ["任选饮品2杯"],
                "valid_time": "12:00-20:30",
                "reviews": ["适合顺路带走", "口味稳定"],
            },
        ]
    if poi_type == "entertainment":
        return [
            {
                "title": "休闲娱乐单人体验券",
                "items": ["单人体验1次"],
                "valid_time": "10:00-22:00",
                "reviews": ["位置方便", "适合放松"],
            }
        ]
    return [
        {
            "title": "午餐单人套餐",
            "items": ["主食1份", "配菜1份", "饮品/汤1份"],
            "valid_time": "10:30-14:00",
            "reviews": ["分量足", "适合赶时间"],
        },
        {
            "title": "轻食简餐券",
            "items": ["简餐1份"],
            "valid_time": "11:00-20:00",
            "reviews": ["性价比不错", "顺路方便"],
        },
    ]


def _price_for_type(poi_type: str, seed: int, index: int) -> float:
    if poi_type == "drink":
        base_price = 9.9 + (seed % 5) * 1.5
    elif poi_type == "entertainment":
        base_price = 29.9 + (seed % 6) * 4
    else:
        base_price = 9.9 + (seed % 3) * 1.5
    return round(base_price + (index - 1) * 4, 1)


def _business_time_for_type(poi_type: str) -> str:
    return {
        "drink": "10:00-22:00",
        "food": "10:30-20:00",
        "entertainment": "10:00-22:30",
    }.get(poi_type, "09:00-21:00")


def _category_for_type(poi_type: str) -> str:
    return {
        "drink": "饮品",
        "food": "餐饮",
        "entertainment": "娱乐",
    }.get(poi_type, "推荐")


def _stable_number(value: str, start: int, end: int) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    span = end - start + 1
    return start + (int(digest[:8], 16) % span)
