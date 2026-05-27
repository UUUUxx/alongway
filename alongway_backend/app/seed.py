"""
Seed script to initialize MVP database with mock data.
"""
import json
from sqlalchemy.orm import Session

from app.database import get_engine, get_session_factory
from app.models import Base, Deal, POI


def seed_pois(db: Session) -> None:
    """Seed POI table with mock data."""
    pois_data = [
        {
            "poi_id": "poi_001",
            "name": "茶百道",
            "type": "drink",
            "address": "学校商业街一楼",
            "location": "商业街",
            "longitude": 114.126,
            "latitude": 30.459,
            "rating": 4.6,
            "cost": 18,
            "source_keyword": "奶茶",
        },
        {
            "poi_id": "poi_002",
            "name": "瑞幸咖啡",
            "type": "drink",
            "address": "图书馆旁",
            "location": "图书馆附近",
            "longitude": 114.127,
            "latitude": 30.460,
            "rating": 4.5,
            "cost": 15,
            "source_keyword": "咖啡",
        },
        {
            "poi_id": "poi_003",
            "name": "霸王茶姬",
            "type": "drink",
            "address": "学校商业街二楼",
            "location": "商业街",
            "longitude": 114.130,
            "latitude": 30.464,
            "rating": 4.8,
            "cost": 22,
            "source_keyword": "奶茶",
        },
        {
            "poi_id": "poi_004",
            "name": "菜鸟驿站",
            "type": "express",
            "address": "学生服务中心一楼",
            "location": "宿舍区附近",
            "longitude": 114.125,
            "latitude": 30.458,
            "rating": 4.5,
            "cost": None,
            "source_keyword": "快递",
        },
        {
            "poi_id": "poi_005",
            "name": "快递柜",
            "type": "express",
            "address": "宿舍楼下",
            "location": "宿舍区",
            "longitude": 114.124,
            "latitude": 30.457,
            "rating": 4.2,
            "cost": None,
            "source_keyword": "快递柜",
        },
        {
            "poi_id": "poi_006",
            "name": "一食堂",
            "type": "food",
            "address": "教学区旁",
            "location": "教学区",
            "longitude": 114.129,
            "latitude": 30.463,
            "rating": 4.3,
            "cost": 12,
            "source_keyword": "食堂",
        },
    ]

    for poi_data in pois_data:
        poi = POI(**poi_data)
        db.merge(poi)

    db.commit()
    print(f"OK Seeded {len(pois_data)} POIs")


def seed_deals(db: Session) -> None:
    """Seed Deal table with mock data."""
    deals_data = [
        {
            "deal_id": "deal_001",
            "poi_id": "poi_001",
            "name": "茶百道",
            "category": "奶茶",
            "deal_title": "招牌奶茶单人套餐",
            "price": 16.8,
            "original_price": 22,
            "included_items": json.dumps(["招牌奶茶1杯", "任选小料1份"]),
            "additional_information": "新人可用，部分门店不可用",
            "valid_time": "10:00-21:30",
            "rating": 4.7,
            "monthly_sales": 300,
            "reviews": json.dumps(["价格划算", "味道不错", "出餐快"]),
            "business_time": "10:00-22:00",
        },
        {
            "deal_id": "deal_002",
            "poi_id": "poi_002",
            "name": "瑞幸咖啡",
            "category": "咖啡",
            "deal_title": "生椰拿铁单杯券",
            "price": 9.9,
            "original_price": 19,
            "included_items": json.dumps(["生椰拿铁1杯"]),
            "additional_information": "新老用户可用",
            "valid_time": "08:00-21:30",
            "rating": 4.6,
            "monthly_sales": 800,
            "reviews": json.dumps(["便宜", "方便", "出餐快"]),
            "business_time": "08:00-22:00",
        },
        {
            "deal_id": "deal_003",
            "poi_id": "poi_003",
            "name": "霸王茶姬",
            "category": "奶茶",
            "deal_title": "招牌单杯券",
            "price": 19.9,
            "original_price": 24,
            "included_items": json.dumps(["招牌奶茶1杯"]),
            "additional_information": "部分新品不可用",
            "valid_time": "10:00-21:30",
            "rating": 4.8,
            "monthly_sales": 500,
            "reviews": json.dumps(["口味好", "排队较久"]),
            "business_time": "10:00-22:00",
        },
        {
            "deal_id": "deal_004",
            "poi_id": "poi_006",
            "name": "一食堂",
            "category": "食堂",
            "deal_title": "午餐套餐",
            "price": 12,
            "original_price": 15,
            "included_items": json.dumps(["主食1份", "素菜1份", "汤1份"]),
            "additional_information": "工作日可用",
            "valid_time": "11:00-13:30",
            "rating": 4.2,
            "monthly_sales": 200,
            "reviews": json.dumps(["便宜", "量大"]),
            "business_time": "10:30-20:00",
        },
    ]

    for deal_data in deals_data:
        deal = Deal(**deal_data)
        db.merge(deal)

    db.commit()
    print(f"OK Seeded {len(deals_data)} Deals")


def init_db() -> None:
    """Initialize database and seed data."""
    engine = get_engine()

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("OK Database tables created")

    # Create session and seed data
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        seed_pois(db)
        seed_deals(db)
        print("OK Mock data seeded successfully")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
