#!/usr/bin/env python
"""
Quick verification script for MVP backend.
"""
import sys

from app.database import get_engine, get_session_factory
from app.models import Base, Deal, POI
from app.seed import init_db
from app.schemas import Point
from app.services.deal_service import search_deals
from app.services.poi_service import search_pois
from app.services.route_service import calculate_route


def test_database():
    """Test database creation and seeding."""
    print("\nOK Testing database initialization...")
    try:
        init_db()
        print("  OK Database tables created")
        print("  OK Mock data seeded")
        
        SessionLocal = get_session_factory()
        db = SessionLocal()
        
        poi_count = db.query(POI).count()
        deal_count = db.query(Deal).count()
        
        print(f"  OK POIs in database: {poi_count}")
        print(f"  OK Deals in database: {deal_count}")
        
        assert poi_count == 6, f"Expected 6 POIs, got {poi_count}"
        assert deal_count == 4, f"Expected 4 Deals, got {deal_count}"
        
        db.close()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_poi_search():
    """Test POI search functionality."""
    print("\nOK Testing POI search...")
    try:
        SessionLocal = get_session_factory()
        db = SessionLocal()
        
        # Test basic search
        result = search_pois(
            db=db,
            source_keywords=["奶茶"],
            limit=5,
        )
        
        assert len(result.pois) > 0, "No POIs found for '奶茶'"
        print(f"  OK Found {len(result.pois)} POIs for '奶茶'")
        
        # Test with distance
        center = Point(name="center", longitude=114.125, latitude=30.459)
        result_with_distance = search_pois(
            db=db,
            source_keywords=["奶茶", "饮品"],
            center=center,
            radius_meters=1500,
            limit=5,
        )
        
        assert len(result_with_distance.pois) > 0, "No POIs found with distance"
        assert result_with_distance.pois[0].distance_meters is not None
        print(f"  OK Distance filtering works: {result_with_distance.pois[0].distance_meters}m")
        
        db.close()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_deal_search():
    """Test Deal search functionality."""
    print("\nOK Testing Deal search...")
    try:
        SessionLocal = get_session_factory()
        db = SessionLocal()
        
        # Test basic search
        result = search_deals(
            db=db,
            poi_id="poi_001",
            limit=3,
        )
        
        assert len(result.deals) > 0, "No deals found for poi_001"
        print(f"  OK Found {len(result.deals)} deals for poi_001")
        
        # Test with price filter
        result_filtered = search_deals(
            db=db,
            poi_id="poi_001",
            max_price=20,
            limit=3,
        )
        
        for deal in result_filtered.deals:
            assert deal.price <= 20, f"Deal price {deal.price} exceeds max_price 20"
        
        print(f"  OK Price filtering works: {len(result_filtered.deals)} deals <= 20")
        
        db.close()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def test_route_calculation():
    """Test route calculation."""
    print("\nOK Testing route calculation...")
    try:
        points = [
            Point(name="学生宿舍", longitude=114.123, latitude=30.456),
            Point(name="茶百道", longitude=114.126, latitude=30.459),
            Point(name="图书馆", longitude=114.128, latitude=30.462),
        ]
        
        result = calculate_route(points=points, travel_mode="walking")
        
        assert result.distance_meters > 0, "Distance should be positive"
        assert result.duration_minutes > 0, "Duration should be positive"
        assert len(result.polyline) == 3, f"Polyline should have 3 points, got {len(result.polyline)}"
        assert len(result.segments) == 2, f"Should have 2 segments, got {len(result.segments)}"
        
        print(f"  OK Distance: {result.distance_meters}m")
        print(f"  OK Duration: {result.duration_minutes} minutes")
        print(f"  OK Segments: {len(result.segments)}")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 50)
    print("Along-way MVP Backend Verification")
    print("=" * 50)
    
    tests = [
        ("Database", test_database),
        ("POI Search", test_poi_search),
        ("Deal Search", test_deal_search),
        ("Route Calculation", test_route_calculation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("VERIFICATION SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 50)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
