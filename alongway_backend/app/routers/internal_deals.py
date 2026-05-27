"""
Internal Deal search endpoint for Agent service.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import DealSearchRequest, DealsSearchResponse
from app.services.deal_service import search_deals

router = APIRouter(tags=["internal"])


@router.post("/internal/deals/search", response_model=DealsSearchResponse)
def search_deals_endpoint(
    request: DealSearchRequest,
    db: Session = Depends(get_db),
) -> DealsSearchResponse:
    """
    Search deals by POI ID with optional category and price filtering.

    This endpoint is called by Agent service.

    Args:
        request: DealSearchRequest with poi_id, optional categories/max_price, limit
        db: Database session

    Returns:
        DealsSearchResponse with matching deals
    """
    return search_deals(
        db=db,
        poi_id=request.poi_id,
        categories=request.categories,
        max_price=request.max_price,
        limit=request.limit,
    )
