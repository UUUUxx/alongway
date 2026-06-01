"""
Internal POI search endpoint for Agent service.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import POISarchResponse, POISearchRequest
from app.services.poi_service import search_pois

router = APIRouter(tags=["internal"])


@router.post("/internal/pois/search", response_model=POISarchResponse)
def search_pois_endpoint(
    request: POISearchRequest,
    db: Session = Depends(get_db),
) -> POISarchResponse:
    """
    Search POIs by keywords with optional distance filtering.

    This endpoint is called by Agent service.

    Args:
        request: POISearchRequest with keywords, optional center/radius, limit
        db: Database session

    Returns:
        POISarchResponse with matching POIs
    """
    return search_pois(
        db=db,
        source_keywords=request.source_keywords,
        center=request.center,
        radius_meters=request.radius_meters,
        limit=request.limit,
        specific_place_name=request.specific_place_name,
    )
