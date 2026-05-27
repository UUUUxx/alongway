"""
POI admin CRUD endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import POI
from app.schemas import POICreate, POIResponse, POIUpdate

router = APIRouter(prefix="/api/pois", tags=["admin"])


@router.get("", response_model=list[POIResponse])
def list_pois(
    db: Session = Depends(get_db),
    keyword: Optional[str] = Query(None),
    type_: Optional[str] = Query(None, alias="type"),
    source_keyword: Optional[str] = Query(None),
) -> list[POIResponse]:
    """
    List POIs with optional filters.

    Args:
        db: Database session
        keyword: Search by name (contains)
        type_: Filter by type
        source_keyword: Filter by source_keyword

    Returns:
        List of POIs
    """
    query = db.query(POI)

    if keyword:
        query = query.filter(POI.name.ilike(f"%{keyword}%"))
    if type_:
        query = query.filter(POI.type == type_)
    if source_keyword:
        query = query.filter(POI.source_keyword == source_keyword)

    pois = query.all()
    return [
        POIResponse(
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
        )
        for poi in pois
    ]


@router.post("", response_model=POIResponse)
def create_poi(
    request: POICreate,
    db: Session = Depends(get_db),
) -> POIResponse:
    """
    Create a new POI.

    Args:
        request: POICreate request
        db: Database session

    Returns:
        Created POI
    """
    # Check if poi_id exists - generate one if needed
    # For MVP, we'll auto-generate poi_id from name
    poi_id = f"poi_{request.name.lower().replace(' ', '_')}_{db.query(POI).count() + 1}"

    poi = POI(
        poi_id=poi_id,
        name=request.name,
        type=request.type,
        address=request.address,
        location=request.location,
        longitude=request.longitude,
        latitude=request.latitude,
        rating=request.rating,
        cost=request.cost,
        source_keyword=request.source_keyword,
    )
    db.add(poi)
    db.commit()
    db.refresh(poi)

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
    )


@router.get("/{poi_id}", response_model=POIResponse)
def get_poi(
    poi_id: str,
    db: Session = Depends(get_db),
) -> POIResponse:
    """
    Get a single POI by ID.

    Args:
        poi_id: POI ID
        db: Database session

    Returns:
        POI details

    Raises:
        HTTPException: If POI not found
    """
    poi = db.query(POI).filter(POI.poi_id == poi_id).first()
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

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
    )


@router.put("/{poi_id}", response_model=POIResponse)
def update_poi(
    poi_id: str,
    request: POIUpdate,
    db: Session = Depends(get_db),
) -> POIResponse:
    """
    Update a POI.

    Args:
        poi_id: POI ID
        request: POIUpdate request
        db: Database session

    Returns:
        Updated POI

    Raises:
        HTTPException: If POI not found
    """
    poi = db.query(POI).filter(POI.poi_id == poi_id).first()
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

    # Update fields if provided
    if request.name is not None:
        poi.name = request.name
    if request.type is not None:
        poi.type = request.type
    if request.address is not None:
        poi.address = request.address
    if request.location is not None:
        poi.location = request.location
    if request.longitude is not None:
        poi.longitude = request.longitude
    if request.latitude is not None:
        poi.latitude = request.latitude
    if request.rating is not None:
        poi.rating = request.rating
    if request.cost is not None:
        poi.cost = request.cost
    if request.source_keyword is not None:
        poi.source_keyword = request.source_keyword

    db.commit()
    db.refresh(poi)

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
    )


@router.delete("/{poi_id}")
def delete_poi(
    poi_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete a POI.

    Args:
        poi_id: POI ID
        db: Database session

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: If POI not found
    """
    poi = db.query(POI).filter(POI.poi_id == poi_id).first()
    if not poi:
        raise HTTPException(status_code=404, detail="POI not found")

    db.delete(poi)
    db.commit()

    return {"message": "POI deleted successfully"}
