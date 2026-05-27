"""
Admin endpoints for data seeding and import.
"""
import json as _json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deal, POI
from app.seed import seed_deals, seed_pois

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/seed")
def run_seed(db: Session = Depends(get_db)):
    """
    Seed the database with built-in mock data.

    This will merge (upsert) all built-in POIs and Deals into the database.
    """
    seed_pois(db)
    seed_deals(db)
    return {"status": "ok", "message": "Mock data seeded successfully"}


@router.post("/import/pois")
def import_pois(
    pois: list[dict],
    db: Session = Depends(get_db),
):
    """
    Import POIs from JSON array.

    Each item must have: poi_id, name, type, address, location,
    longitude, latitude, source_keyword.
    Optional: rating, cost.
    """
    count = 0
    for item in pois:
        if "poi_id" not in item:
            continue
        existing = db.get(POI, item["poi_id"])
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
        else:
            db.add(POI(**item))
        count += 1
    db.commit()
    return {"status": "ok", "imported": count}


@router.post("/import/deals")
def import_deals(
    deals: list[dict],
    db: Session = Depends(get_db),
):
    """
    Import Deals from JSON array.

    Each item must have: deal_id, poi_id, name, category, deal_title, price.
    Optional: original_price, included_items, additional_information,
    valid_time, rating, monthly_sales, reviews, business_time.
    """
    count = 0
    for item in deals:
        if "deal_id" not in item:
            continue
        if "included_items" in item and isinstance(item["included_items"], list):
            item["included_items"] = _json.dumps(item["included_items"])
        if "reviews" in item and isinstance(item["reviews"], list):
            item["reviews"] = _json.dumps(item["reviews"])
        existing = db.get(Deal, item["deal_id"])
        if existing:
            for key, value in item.items():
                setattr(existing, key, value)
        else:
            db.add(Deal(**item))
        count += 1
    db.commit()
    return {"status": "ok", "imported": count}
