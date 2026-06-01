"""
Tests for built-in mock data templates.
"""
from app.seed import DEALS_DATA, POIS_DATA


def test_seed_data_counts_are_in_target_range():
    assert 10 <= len(POIS_DATA) <= 20, f"Expected 10-20 POIs, got {len(POIS_DATA)}"
    assert 20 <= len(DEALS_DATA) <= 30, f"Expected 20-30 Deals, got {len(DEALS_DATA)}"


def test_seed_deal_titles_are_distinct():
    titles = [deal["deal_title"] for deal in DEALS_DATA]

    assert len(titles) == len(set(titles))


def test_seed_data_covers_price_distance_tradeoffs():
    poi_by_id = {poi["poi_id"]: poi for poi in POIS_DATA}

    # 价格高但近: deals with price >= 20 at near-campus POIs
    near_locations = {"韵苑生活区·武汉", "东九教学楼·武汉", "百景园·武汉", "主图书馆·武汉"}
    near_expensive = [
        deal
        for deal in DEALS_DATA
        if deal["price"] >= 20 and any(
            loc in poi_by_id[deal["poi_id"]]["location"] for loc in near_locations
        )
    ]
    # 价格低但远: deals with price <= 10 at far POIs
    far_locations = {"东操场·武汉", "南一门·武汉", "国权路·上海"}
    far_cheap = [
        deal
        for deal in DEALS_DATA
        if deal["price"] <= 10 and any(
            loc in poi_by_id[deal["poi_id"]]["location"] for loc in far_locations
        )
    ]
    # 高评分低销量
    high_rating_low_sales = [
        deal
        for deal in DEALS_DATA
        if deal["rating"] >= 4.8 and deal["monthly_sales"] <= 100
    ]
    # 高销量中等评分
    high_sales_mid_rating = [
        deal
        for deal in DEALS_DATA
        if deal["monthly_sales"] >= 500 and deal["rating"] <= 4.2
    ]

    assert near_expensive, "Should have at least one 'high price, near' deal"
    assert far_cheap, "Should have at least one 'low price, far' deal"
    assert high_rating_low_sales, "Should have at least one 'high rating, low sales' deal"
    assert high_sales_mid_rating, "Should have at least one 'high sales, mid rating' deal"


def test_seed_deals_reference_existing_pois():
    poi_ids = {poi["poi_id"] for poi in POIS_DATA}

    for deal in DEALS_DATA:
        assert deal["poi_id"] in poi_ids
