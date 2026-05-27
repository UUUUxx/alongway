from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Deal, POI
from app.services.mock_deal_service import ensure_mock_deals_for_poi


def test_mock_deals_are_created_once_for_food_poi():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        poi = POI(
            poi_id="amap_B001",
            name="测试餐厅",
            type="food",
            address="校园商业街",
            location="商业街",
            longitude=114.126,
            latitude=30.459,
            rating=4.6,
            cost=18,
            source_keyword="餐厅",
            source_provider="amap",
            source_id="B001",
            source_key="餐厅",
            category_major="餐饮服务",
        )
        db.add(poi)
        db.commit()

        ensure_mock_deals_for_poi(db, poi)
        first_ids = [deal.deal_id for deal in db.query(Deal).all()]
        ensure_mock_deals_for_poi(db, poi)
        second_ids = [deal.deal_id for deal in db.query(Deal).all()]

        assert len(first_ids) == 2
        assert second_ids == first_ids
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
