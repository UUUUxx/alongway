"""
Deal admin CRUD endpoints.
"""
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deal, POI
from app.schemas import DealCreate, DealResponse, DealUpdate
from app.services.deal_service import parse_json_field

router = APIRouter(prefix="/api/deals", tags=["admin"])


def _to_deal_response(deal: Deal) -> DealResponse:
    """Convert Deal model to response."""
    return DealResponse(
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


@router.get("", response_model=list[DealResponse])
def list_deals(
    db: Session = Depends(get_db),
    poi_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
) -> list[DealResponse]:
    """
    List deals with optional filters.

    Args:
        db: Database session
        poi_id: Filter by POI ID
        category: Filter by category
        max_price: Filter by max price

    Returns:
        List of deals
    """
    query = db.query(Deal)

    if poi_id:
        query = query.filter(Deal.poi_id == poi_id)
    if category:
        query = query.filter(Deal.category == category)
    if max_price is not None:
        query = query.filter(Deal.price <= max_price)

    deals = query.all()
    return [_to_deal_response(deal) for deal in deals]


@router.post("", response_model=DealResponse)
def create_deal(
    request: DealCreate,
    db: Session = Depends(get_db),
) -> DealResponse:
    """
    Create a new deal.

    Args:
        request: DealCreate request
        db: Database session

    Returns:
        Created deal

    Raises:
        HTTPException: If POI not found
    """
    # Check if POI exists
    poi = db.query(POI).filter(POI.poi_id == request.poi_id).first()
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

    # Generate deal_id if not provided
    deal_id = f"deal_{uuid.uuid4().hex[:8]}"

    deal = Deal(
        deal_id=deal_id,
        poi_id=request.poi_id,
        name=request.name,
        category=request.category,
        deal_title=request.deal_title,
        price=request.price,
        original_price=request.original_price,
        included_items=json.dumps(request.included_items) if request.included_items else None,
        additional_information=request.additional_information,
        valid_time=request.valid_time,
        rating=request.rating,
        monthly_sales=request.monthly_sales,
        reviews=json.dumps(request.reviews) if request.reviews else None,
        business_time=request.business_time,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)

    return _to_deal_response(deal)


@router.get("/{deal_id}", response_model=DealResponse)
def get_deal(
    deal_id: str,
    db: Session = Depends(get_db),
) -> DealResponse:
    """
    Get a single deal by ID.

    Args:
        deal_id: Deal ID
        db: Database session

    Returns:
        Deal details

    Raises:
        HTTPException: If deal not found
    """
    deal = db.query(Deal).filter(Deal.deal_id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    return _to_deal_response(deal)


@router.put("/{deal_id}", response_model=DealResponse)
def update_deal(
    deal_id: str,
    request: DealUpdate,
    db: Session = Depends(get_db),
) -> DealResponse:
    """
    Update a deal.

    Args:
        deal_id: Deal ID
        request: DealUpdate request
        db: Database session

    Returns:
        Updated deal

    Raises:
        HTTPException: If deal not found or POI not found
    """
    deal = db.query(Deal).filter(Deal.deal_id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Check if POI exists if updating poi_id
    if request.poi_id is not None:
        poi = db.query(POI).filter(POI.poi_id == request.poi_id).first()
        if not poi:
            raise HTTPException(status_code=404, detail="POI not found")
        deal.poi_id = request.poi_id

    # Update fields if provided
    if request.name is not None:
        deal.name = request.name
    if request.category is not None:
        deal.category = request.category
    if request.deal_title is not None:
        deal.deal_title = request.deal_title
    if request.price is not None:
        deal.price = request.price
    if request.original_price is not None:
        deal.original_price = request.original_price
    if request.included_items is not None:
        deal.included_items = json.dumps(request.included_items)
    if request.additional_information is not None:
        deal.additional_information = request.additional_information
    if request.valid_time is not None:
        deal.valid_time = request.valid_time
    if request.rating is not None:
        deal.rating = request.rating
    if request.monthly_sales is not None:
        deal.monthly_sales = request.monthly_sales
    if request.reviews is not None:
        deal.reviews = json.dumps(request.reviews)
    if request.business_time is not None:
        deal.business_time = request.business_time

    db.commit()
    db.refresh(deal)

    return _to_deal_response(deal)


@router.delete("/{deal_id}")
def delete_deal(
    deal_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete a deal.

    Args:
        deal_id: Deal ID
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: If deal not found
    """
    deal = db.query(Deal).filter(Deal.deal_id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    db.delete(deal)
    db.commit()

    return {"message": "Deal deleted successfully"}
