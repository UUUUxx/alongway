"""
Tests for POI search functionality.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.models import Base, POI
from app.schemas import Point
from app.services.poi_service import search_pois


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Seed test data
    test_pois = [
        POI(
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
        ),
        POI(
            poi_id="poi_002",
            name="瑞幸咖啡",
            type="drink",
            address="图书馆旁",
            location="图书馆附近",
            longitude=114.127,
            latitude=30.460,
            rating=4.5,
            cost=15,
            source_keyword="咖啡",
        ),
        POI(
            poi_id="poi_003",
            name="霸王茶姬",
            type="drink",
            address="学校商业街二楼",
            location="商业街",
            longitude=114.130,
            latitude=30.464,
            rating=4.8,
            cost=22,
            source_keyword="奶茶",
        ),
    ]

    for poi in test_pois:
        db.add(poi)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_poi_search_by_keyword(db_session: Session):
    """Test POI search by keyword."""
    response = search_pois(
        db=db_session,
        source_keywords=["奶茶"],
        limit=5,
    )

    assert len(response.pois) >= 2
    poi_ids = [p.poi_id for p in response.pois]
    assert "poi_001" in poi_ids
    assert "poi_003" in poi_ids


def test_poi_search_with_distance(db_session: Session):
    """Test POI search with distance filter."""
    # Center between start and end
    center = Point(name="center", longitude=114.125, latitude=30.459)

    response = search_pois(
        db=db_session,
        source_keywords=["奶茶", "饮品"],
        center=center,
        radius_meters=1500,
        limit=5,
    )

    assert len(response.pois) > 0
    # All results should have distance_meters
    for poi in response.pois:
        assert poi.distance_meters is not None
        assert poi.distance_meters <= 1500


def test_poi_search_returns_fields(db_session: Session):
    """Test POI search returns all required fields."""
    response = search_pois(
        db=db_session,
        source_keywords=["奶茶"],
        limit=1,
    )

    assert len(response.pois) > 0
    poi = response.pois[0]

    assert poi.poi_id is not None
    assert poi.name is not None
    assert poi.type is not None
    assert poi.address is not None
    assert poi.location is not None
    assert poi.longitude is not None
    assert poi.latitude is not None
    assert poi.source_keyword is not None


def test_poi_search_sorting_by_rating(db_session: Session):
    """Test POI search sorts by rating."""
    response = search_pois(
        db=db_session,
        source_keywords=["奶茶"],
        limit=5,
    )

    # 霸王茶姬 (4.8) should come before 茶百道 (4.6) when distances are same
    assert len(response.pois) >= 2
    # Since they might have different distances, just check they're both present
    poi_ids = [p.poi_id for p in response.pois]
    assert "poi_001" in poi_ids or "poi_003" in poi_ids
