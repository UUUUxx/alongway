"""
Basic CRUD operations for POI and Deal — SQLite MVP compatible.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Deal, POI


# ---------- POI CRUD ----------


def get_poi(db: Session, poi_id: str) -> Optional[POI]:
    return db.query(POI).filter(POI.poi_id == poi_id).first()


def list_pois(
    db: Session,
    keyword: Optional[str] = None,
    type_: Optional[str] = None,
    source_keyword: Optional[str] = None,
) -> list[POI]:
    query = db.query(POI)
    if keyword:
        query = query.filter(POI.name.ilike(f"%{keyword}%"))
    if type_:
        query = query.filter(POI.type == type_)
    if source_keyword:
        query = query.filter(POI.source_keyword == source_keyword)
    return query.all()


def create_poi(db: Session, poi: POI) -> POI:
    db.add(poi)
    db.commit()
    db.refresh(poi)
    return poi


def update_poi(db: Session, poi_id: str, updates: dict) -> Optional[POI]:
    poi = get_poi(db, poi_id)
    if not poi:
        return None
    for key, value in updates.items():
        if value is not None:
            setattr(poi, key, value)
    db.commit()
    db.refresh(poi)
    return poi


def delete_poi(db: Session, poi_id: str) -> bool:
    poi = get_poi(db, poi_id)
    if not poi:
        return False
    db.delete(poi)
    db.commit()
    return True


# ---------- Deal CRUD ----------


def get_deal(db: Session, deal_id: str) -> Optional[Deal]:
    return db.query(Deal).filter(Deal.deal_id == deal_id).first()


def list_deals(
    db: Session,
    poi_id: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
) -> list[Deal]:
    query = db.query(Deal)
    if poi_id:
        query = query.filter(Deal.poi_id == poi_id)
    if category:
        query = query.filter(Deal.category == category)
    if max_price is not None:
        query = query.filter(Deal.price <= max_price)
    return query.all()


def create_deal(db: Session, deal: Deal) -> Deal:
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def update_deal(db: Session, deal_id: str, updates: dict) -> Optional[Deal]:
    deal = get_deal(db, deal_id)
    if not deal:
        return None
    for key, value in updates.items():
        if value is not None:
            setattr(deal, key, value)
    db.commit()
    db.refresh(deal)
    return deal


def delete_deal(db: Session, deal_id: str) -> bool:
    deal = get_deal(db, deal_id)
    if not deal:
        return False
    db.delete(deal)
    db.commit()
    return True
