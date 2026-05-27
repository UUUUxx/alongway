"""
Tests for route calculation functionality.
"""
import pytest

from app.schemas import Point, RouteCalculateRequest
from app.services.distance import haversine_distance_meters
from app.services.route_service import calculate_route


def test_haversine_distance():
    """Test Haversine distance calculation."""
    # Distance from student dorm to tea shop (approx 400-500m)
    distance = haversine_distance_meters(
        lon1=114.123,
        lat1=30.456,
        lon2=114.126,
        lat2=30.459,
    )

    assert distance > 0
    assert 300 < distance < 600  # Expected range


def test_route_calculate_three_points():
    """Test route calculation with three points."""
    points = [
        Point(name="学生宿舍", longitude=114.123, latitude=30.456),
        Point(name="茶百道", longitude=114.126, latitude=30.459),
        Point(name="图书馆", longitude=114.128, latitude=30.462),
    ]

    response = calculate_route(points=points, travel_mode="walking")

    assert response.distance_meters > 0
    assert response.duration_minutes > 0
    assert len(response.polyline) == 3
    assert len(response.segments) == 2


def test_route_polyline_format():
    """Test polyline is returned as [lon, lat] pairs."""
    points = [
        Point(name="点1", longitude=114.123, latitude=30.456),
        Point(name="点2", longitude=114.126, latitude=30.459),
    ]

    response = calculate_route(points=points, travel_mode="walking")

    assert len(response.polyline) == 2
    for point in response.polyline:
        assert len(point) == 2
        assert isinstance(point[0], float)
        assert isinstance(point[1], float)


def test_route_segments():
    """Test route segments are correct."""
    points = [
        Point(name="起点", longitude=114.123, latitude=30.456),
        Point(name="中点", longitude=114.125, latitude=30.458),
        Point(name="终点", longitude=114.128, latitude=30.462),
    ]

    response = calculate_route(points=points, travel_mode="walking")

    assert len(response.segments) == 2
    assert response.segments[0].from_name == "起点"
    assert response.segments[0].to_name == "中点"
    assert response.segments[1].from_name == "中点"
    assert response.segments[1].to_name == "终点"
    assert response.segments[0].distance_meters > 0
    assert response.segments[0].duration_minutes > 0


def test_route_travel_modes():
    """Test different travel modes affect duration."""
    points = [
        Point(name="起点", longitude=114.123, latitude=30.456),
        Point(name="终点", longitude=114.128, latitude=30.462),
    ]

    walking = calculate_route(points=points, travel_mode="walking")
    bicycling = calculate_route(points=points, travel_mode="bicycling")
    driving = calculate_route(points=points, travel_mode="driving")

    # All should have same distance
    assert walking.distance_meters == bicycling.distance_meters
    assert bicycling.distance_meters == driving.distance_meters

    # But different durations
    assert walking.duration_minutes > bicycling.duration_minutes
    assert bicycling.duration_minutes > driving.duration_minutes


def test_route_raises_on_insufficient_points():
    """Test route calculation raises error with < 2 points."""
    points = [Point(name="单点", longitude=114.123, latitude=30.456)]

    with pytest.raises(ValueError):
        calculate_route(points=points, travel_mode="walking")
