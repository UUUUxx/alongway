"""
Deal (团购) search service with filtering and sorting.
"""
import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Deal, POI
from app.schemas import DealResponse, DealsSearchResponse
from app.services.mock_deal_service import ensure_mock_deals_for_poi


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
    poi = db.query(POI).filter(POI.poi_id == poi_id).first()
    if poi is not None:
        ensure_mock_deals_for_poi(db, poi)

    deals = db.query(Deal).filter(Deal.poi_id == poi_id).all()

    if categories:
        deals = [deal for deal in deals if _deal_matches_categories(deal, categories)]

    if max_price is not None:
        deals = [deal for deal in deals if deal.price <= max_price]

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

    return DealsSearchResponse(deals=deal_responses)


def _deal_matches_categories(deal: Deal, categories: list[str]) -> bool:
    category_text = f"{deal.category} {deal.deal_title}".lower()
    normalized = [category.lower() for category in categories if category]
    return any(category in category_text or category_text in category for category in normalized)


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
