"""
Tests for Deal search functionality.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.models import Base, Deal, POI
from app.services.deal_service import search_deals


@pytest.fixture(scope="function")
def db_session_with_deals():
    """Create a test database session with POI and Deal data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create POI
    poi = POI(
        poi_id="poi_001",
        name="茶百道",
        type="drink",
        address="学校商业街一楼",
        location="商业街",
        longitude=114.126,
        latitude=30.459,
        rating=4.6,
        cost=18,
        source_keyword="奶茶",
    )
    db.add(poi)
    db.commit()

    # Create deals
    deals = [
        Deal(
            deal_id="deal_001",
            poi_id="poi_001",
            name="茶百道",
            category="奶茶",
            deal_title="招牌奶茶单人套餐",
            price=16.8,
            original_price=22,
            included_items=json.dumps(["招牌奶茶1杯", "任选小料1份"]),
            additional_information="新人可用",
            valid_time="10:00-21:30",
            rating=4.7,
            monthly_sales=300,
            reviews=json.dumps(["价格划算", "味道不错"]),
            business_time="10:00-22:00",
        ),
        Deal(
            deal_id="deal_002",
            poi_id="poi_001",
            name="茶百道",
            category="奶茶",
            deal_title="大杯奶茶券",
            price=25.0,
            original_price=30,
            included_items=json.dumps(["大杯奶茶1杯"]),
            additional_information="可用",
            valid_time="10:00-21:30",
            rating=4.6,
            monthly_sales=200,
            reviews=json.dumps(["划算"]),
            business_time="10:00-22:00",
        ),
    ]

    for deal in deals:
        db.add(deal)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_deal_search_by_poi_id(db_session_with_deals: Session):
    """Test Deal search by POI ID."""
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=3,
    )

    assert len(response.deals) == 2
    for deal in response.deals:
        assert deal.poi_id == "poi_001"


def test_deal_search_with_category_filter(db_session_with_deals: Session):
    """Test Deal search with category filter."""
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        categories=["奶茶"],
        limit=3,
    )

    assert len(response.deals) == 2
    for deal in response.deals:
        assert deal.category == "奶茶"


def test_deal_search_with_max_price(db_session_with_deals: Session):
    """Test Deal search with max price filter."""
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        max_price=20,
        limit=3,
    )

    assert len(response.deals) == 1
    assert response.deals[0].deal_id == "deal_001"
    assert response.deals[0].price <= 20


def test_deal_search_sorting_by_price(db_session_with_deals: Session):
    """Test Deal search sorts by price."""
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=3,
    )

    assert len(response.deals) == 2
    # Cheaper deal should come first (16.8 < 25.0)
    assert response.deals[0].price == 16.8
    assert response.deals[1].price == 25.0


def test_deal_search_returns_all_fields(db_session_with_deals: Session):
    """Test Deal search returns all required fields."""
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=1,
    )

    assert len(response.deals) > 0
    deal = response.deals[0]

    assert deal.poi_id is not None
    assert deal.name is not None
    assert deal.category is not None
    assert deal.deal_id is not None
    assert deal.deal_title is not None
    assert deal.price is not None
    assert deal.included_items is not None
    assert deal.reviews is not None
