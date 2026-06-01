"""
Tests for POI search functionality.
"""
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from app.database import get_engine, get_session_factory
from app.models import Base, POI
from app.schemas import Point
from app.services.poi_service import search_pois


@pytest.fixture(autouse=True)
def disable_amap_for_local_poi_tests(monkeypatch):
    class Settings:
        amap_key = ""
        amap_base_url = "https://restapi.amap.com"
        amap_timeout_seconds = 10

    monkeypatch.setattr("app.services.poi_service.get_settings", lambda: Settings())


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    SessionLocal = get_session_factory()
    db = SessionLocal()

    test_pois = [
        POI(
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
        ),
        POI(
            poi_id="poi_002",
            name="东九咖啡角",
            type="drink",
            address="华中科技大学东九教学楼A座旁",
            location="东九教学楼",
            longitude=114.42180,
            latitude=30.51140,
            rating=4.8,
            cost=32,
            source_keyword="咖啡",
        ),
        POI(
            poi_id="poi_003",
            name="西十二轻食窗口",
            type="food",
            address="华中科技大学西十二教学楼负一层",
            location="西十二教学楼",
            longitude=114.41070,
            latitude=30.51810,
            rating=4.2,
            cost=12,
            source_keyword="简餐",
        ),
    ]

    for poi in test_pois:
        db.add(poi)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_poi_search_by_keyword(db_session: Session):
    response = search_pois(
        db=db_session,
        source_keywords=["奶茶"],
        limit=5,
    )

    assert [poi.poi_id for poi in response.pois] == ["poi_001"]


def test_poi_search_with_synonym(db_session: Session):
    response = search_pois(
        db=db_session,
        source_keywords=["饮品"],
        limit=5,
    )

    poi_ids = [p.poi_id for p in response.pois]
    assert "poi_001" in poi_ids
    assert "poi_002" in poi_ids


def test_poi_search_with_distance(db_session: Session):
    center = Point(name="韵苑宿舍", longitude=114.41480, latitude=30.51590)

    response = search_pois(
        db=db_session,
        source_keywords=["饮品"],
        center=center,
        radius_meters=1000,
        limit=5,
    )

    assert len(response.pois) > 0
    for poi in response.pois:
        assert poi.distance_meters is not None
        assert poi.distance_meters <= 1000


def test_poi_search_returns_fields(db_session: Session):
    response = search_pois(
        db=db_session,
        source_keywords=["奶茶"],
        limit=1,
    )

    poi = response.pois[0]
    assert poi.poi_id == "poi_001"
    assert poi.name == "韵苑奶茶铺"
    assert poi.longitude is not None
    assert poi.latitude is not None
    assert poi.source_keyword == "奶茶"


def test_poi_search_prioritizes_specific_place_name(db_session: Session):
    response = search_pois(
        db=db_session,
        source_keywords=["咖啡", "饮品"],
        specific_place_name="东九咖啡角",
        limit=5,
    )

    assert response.pois[0].poi_id == "poi_002"


def test_poi_search_falls_back_to_amap(monkeypatch, db_session: Session):
    class Settings:
        amap_key = "fake-key"
        amap_base_url = "https://restapi.amap.com"
        amap_timeout_seconds = 10

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": "1",
        "pois": [
            {
                "id": "amap_001",
                "name": "星巴克",
                "address": "华中科技大学附近",
                "location": "114.4160,30.5160",
                "biz_ext": {"rating": "4.6", "cost": "35"},
            }
        ],
    }

    monkeypatch.setattr("app.services.poi_service.get_settings", lambda: Settings())
    with patch("httpx.Client.get", return_value=response) as get:
        result = search_pois(
            db=db_session,
            source_keywords=["星巴克", "咖啡"],
            specific_place_name="星巴克",
            center=Point(name="韵苑宿舍", longitude=114.4148, latitude=30.5159),
            radius_meters=1500,
            limit=3,
        )

    assert get.called
    assert result.pois[0].name == "星巴克"
    assert result.pois[0].type == "drink"
    persisted = db_session.get(POI, result.pois[0].poi_id)
    assert persisted is not None
    assert persisted.name == result.pois[0].name


def test_poi_search_generates_mock_when_amap_empty(monkeypatch, db_session: Session):
    class Settings:
        amap_key = "fake-key"
        amap_base_url = "https://restapi.amap.com"
        amap_timeout_seconds = 10

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"status": "1", "pois": []}

    monkeypatch.setattr("app.services.poi_service.get_settings", lambda: Settings())
    with patch("httpx.Client.get", return_value=response):
        result = search_pois(
            db=db_session,
            source_keywords=["吃的", "餐厅"],
            center=Point(name="搜索中心", longitude=114.384, latitude=30.522),
            radius_meters=1500,
            limit=3,
        )

    assert result.pois
    assert result.pois[0].type == "food"
    assert result.pois[0].poi_id.startswith("mock_")
    persisted = db_session.get(POI, result.pois[0].poi_id)
    assert persisted is not None
    assert persisted.name == result.pois[0].name
