"""
Deal (团购) search service with filtering and sorting.
"""
import hashlib
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Deal, POI
from app.schemas import DealResponse, DealsSearchResponse
from app.services.call_logger import log_call

logger = logging.getLogger(__name__)


def search_deals(
    db: Session,
    poi_id: str,
    categories: Optional[list[str]] = None,
    max_price: Optional[float] = None,
    limit: int = 3,
) -> DealsSearchResponse:
    """
    Search deals by POI ID with optional category and price filtering.

    Args:
        db: Database session
        poi_id: POI ID to search deals for
        categories: Optional list of categories to filter by
        max_price: Optional max price to filter by
        limit: Max results to return

    Returns:
        DealsSearchResponse with matching deals
    """
    # Query deals by POI ID
    query = db.query(Deal).filter(Deal.poi_id == poi_id)

    # Filter by categories if provided
    if categories:
        query = query.filter(Deal.category.in_(categories))

    # Filter by price if provided
    if max_price is not None:
        query = query.filter(Deal.price <= max_price)

    deals = query.all()
    if not deals:
        ensure_mock_deals(
            db=db,
            poi_id=poi_id,
            categories=categories,
            max_price=max_price,
        )
        query = db.query(Deal).filter(Deal.poi_id == poi_id)
        if categories:
            query = query.filter(Deal.category.in_(categories))
        if max_price is not None:
            query = query.filter(Deal.price <= max_price)
        deals = query.all()

    # Sort by: price (asc), monthly_sales (desc), rating (desc)
    def sort_key(deal: Deal):
        price_key = deal.price
        sales_key = -(deal.monthly_sales or 0)  # Negative for descending
        rating_key = -(deal.rating or 0)  # Negative for descending
        return (price_key, sales_key, rating_key)

    deals.sort(key=sort_key)

    # Convert to response items
    deal_responses = [
        DealResponse(
            poi_id=deal.poi_id,
            name=deal.name,
            category=deal.category,
            deal_id=deal.deal_id,
            deal_title=deal.deal_title,
            price=deal.price,
            original_price=deal.original_price,
            included_items=parse_json_field(deal.included_items),
            additional_information=deal.additional_information,
            valid_time=deal.valid_time,
            rating=deal.rating,
            monthly_sales=deal.monthly_sales,
            reviews=parse_json_field(deal.reviews),
            business_time=deal.business_time,
        )
        for deal in deals[:limit]
    ]

    response = DealsSearchResponse(deals=deal_responses)
    log_call(
        "backend.internal_deals.search.result",
        request={
            "poi_id": poi_id,
            "categories": categories,
            "max_price": max_price,
            "limit": limit,
        },
        result={"count": len(deal_responses), "deals": deal_responses},
    )
    return response


def parse_json_field(value: Optional[str]) -> Optional[list | dict]:
    """
    Parse JSON field from database.

    Args:
        value: JSON string value

    Returns:
        Parsed JSON object or None
    """
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def ensure_mock_deals(
    db: Session,
    poi_id: str,
    categories: Optional[list[str]],
    max_price: Optional[float],
) -> None:
    poi = db.get(POI, poi_id)
    if poi is None:
        return

    category = (categories or [poi.source_keyword or poi.type or "顺路"])[0]
    base_price = poi.cost if poi.cost is not None else _default_price_for_type(poi.type)
    if max_price is not None:
        base_price = min(base_price, max(max_price * 0.85, 1.0))

    templates = [
        ("顺路单人优惠券", round(base_price, 1), round(base_price * 1.25, 1), 240),
        ("工作日轻量套餐", round(max(base_price * 0.82, 1.0), 1), round(base_price * 1.15, 1), 120),
    ]
    saved = []
    for title, price, original_price, sales in templates:
        deal_id = f"mock_{hashlib.md5((poi_id + category + title).encode('utf-8')).hexdigest()[:12]}"
        if db.get(Deal, deal_id) is not None:
            continue
        deal = Deal(
            deal_id=deal_id,
            poi_id=poi_id,
            name=poi.name,
            category=category,
            deal_title=f"{poi.name}{title}",
            price=price,
            original_price=original_price,
            included_items=json.dumps([category, "到店核销"], ensure_ascii=False),
            additional_information="高德 POI 暂无真实团购时生成的演示团购",
            valid_time="09:00-22:00",
            rating=poi.rating or 4.2,
            monthly_sales=sales,
            reviews=json.dumps(["顺路方便", "价格可参考"], ensure_ascii=False),
            business_time="09:00-22:00",
        )
        db.add(deal)
        saved.append({"deal_id": deal_id, "poi_id": poi_id, "title": deal.deal_title})

    if not saved:
        return
    try:
        db.commit()
        log_call("backend.deal.mock.persist.result", result={"count": len(saved), "deals": saved})
    except Exception as exc:
        db.rollback()
        log_call("backend.deal.mock.persist.error", result={"deals": saved}, error=str(exc))
        logger.warning("Failed to persist mock deals: %s", exc)


def _default_price_for_type(poi_type: Optional[str]) -> float:
    return {
        "food": 18.0,
        "drink": 22.0,
        "entertainment": 38.0,
        "express": 6.0,
    }.get(str(poi_type or ""), 20.0)
