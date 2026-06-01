"""
Tests for Deal search functionality.
"""
import json

import pytest
from sqlalchemy.orm import Session

from app.database import get_engine, get_session_factory
from app.models import Base, Deal, POI
from app.services.deal_service import search_deals


@pytest.fixture(scope="function")
def db_session_with_deals():
    """Create a test database session with POI and Deal data."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    db = SessionLocal()

    poi = POI(
        poi_id="poi_001",
        name="韵苑奶茶铺",
        type="drink",
        address="华中科技大学韵苑生活区商业街1层",
        location="韵苑生活区",
        longitude=114.41520,
        latitude=30.51520,
        rating=4.5,
        cost=18,
        source_keyword="奶茶",
    )
    db.add(poi)
    db.commit()

    deals = [
        Deal(
            deal_id="deal_001",
            poi_id="poi_001",
            name="韵苑奶茶铺",
            category="奶茶",
            deal_title="近距离厚乳拿铁单杯券",
            price=21.9,
            original_price=28,
            included_items=json.dumps(["厚乳拿铁1杯", "珍珠或椰果任选1份"], ensure_ascii=False),
            additional_information="距离宿舍近，价格偏高，适合赶时间",
            valid_time="10:00-22:00",
            rating=4.6,
            monthly_sales=180,
            reviews=json.dumps(["出杯快", "离宿舍近"], ensure_ascii=False),
            business_time="09:30-22:30",
        ),
        Deal(
            deal_id="deal_002",
            poi_id="poi_001",
            name="韵苑奶茶铺",
            category="奶茶",
            deal_title="双拼水果茶下午券",
            price=17.5,
            original_price=24,
            included_items=json.dumps(["水果茶1杯", "脆波波1份"], ensure_ascii=False),
            additional_information="14:00后可用",
            valid_time="14:00-21:30",
            rating=4.4,
            monthly_sales=260,
            reviews=json.dumps(["水果量足", "排队时间短"], ensure_ascii=False),
            business_time="09:30-22:30",
        ),
    ]

    for deal in deals:
        db.add(deal)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_deal_search_by_poi_id(db_session_with_deals: Session):
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=3,
    )

    assert len(response.deals) == 2
    for deal in response.deals:
        assert deal.poi_id == "poi_001"


def test_deal_search_with_category_filter(db_session_with_deals: Session):
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
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        max_price=20,
        limit=3,
    )

    assert len(response.deals) == 1
    assert response.deals[0].deal_id == "deal_002"
    assert response.deals[0].price <= 20


def test_deal_search_sorting_by_price(db_session_with_deals: Session):
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=3,
    )

    assert [deal.price for deal in response.deals] == [17.5, 21.9]


def test_deal_search_returns_all_fields(db_session_with_deals: Session):
    response = search_deals(
        db=db_session_with_deals,
        poi_id="poi_001",
        limit=1,
    )

    deal = response.deals[0]
    assert deal.name == "韵苑奶茶铺"
    assert deal.category == "奶茶"
    assert deal.included_items is not None
    assert deal.reviews is not None


def test_deal_search_generates_mock_deals_when_missing(db_session_with_deals: Session):
    poi = POI(
        poi_id="amap_food_001",
        name="Amap Food",
        type="food",
        address="near route",
        location="114.1,30.1",
        longitude=114.1,
        latitude=30.1,
        rating=4.1,
        cost=16,
        source_keyword="food",
    )
    db_session_with_deals.add(poi)
    db_session_with_deals.commit()

    response = search_deals(
        db=db_session_with_deals,
        poi_id=poi.poi_id,
        categories=["food"],
        limit=3,
    )

    assert response.deals
    assert response.deals[0].deal_id.startswith("mock_")
    assert response.deals[0].poi_id == poi.poi_id
    assert db_session_with_deals.get(Deal, response.deals[0].deal_id) is not None
