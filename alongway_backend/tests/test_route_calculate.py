"""
Tests for route calculation functionality.
"""
from unittest.mock import patch

import pytest

from app.schemas import Point
from app.services.distance import haversine_distance_meters
from app.services.route_service import AmapRouteError, calculate_route, parse_amap_route_payload


def test_haversine_distance():
    """Haversine remains available as a local utility."""
    distance = haversine_distance_meters(
        lon1=114.4152,
        lat1=30.5152,
        lon2=114.4143,
        lat2=30.5126,
    )

    assert distance > 0
    assert 250 < distance < 350


def test_route_calculate_three_points_with_amap_mock():
    """Route calculation aggregates Amap segment results."""
    points = [
        Point(name="韵苑宿舍", longitude=114.4148, latitude=30.5159),
        Point(name="韵苑奶茶铺", longitude=114.4152, latitude=30.5152),
        Point(name="主图书馆", longitude=114.4143, latitude=30.5126),
    ]
    mocked_segments = [
        (120, 90.0, [[114.4148, 30.5159], [114.4152, 30.5152]]),
        (360, 300.0, [[114.4152, 30.5152], [114.4143, 30.5126]]),
    ]

    with patch("app.services.route_service.AmapRouteClient") as client_cls:
        client_cls.return_value.calculate_segment.side_effect = mocked_segments
        response = calculate_route(points=points, travel_mode="walking")

    assert response.distance_meters == 480
    assert response.duration_minutes == 6.5
    assert len(response.polyline) == 3
    assert len(response.segments) == 2
    assert response.segments[0].from_name == "韵苑宿舍"
    assert response.segments[1].to_name == "主图书馆"


def test_route_passes_travel_mode_to_amap_client():
    points = [
        Point(name="起点", longitude=114.4148, latitude=30.5159),
        Point(name="终点", longitude=114.4143, latitude=30.5126),
    ]

    with patch("app.services.route_service.AmapRouteClient") as client_cls:
        client = client_cls.return_value
        client.calculate_segment.return_value = (
            100,
            60.0,
            [[114.4148, 30.5159], [114.4143, 30.5126]],
        )
        calculate_route(points=points, travel_mode="bicycling")

    client.calculate_segment.assert_called_once_with(
        origin=points[0],
        destination=points[1],
        travel_mode="bicycling",
    )


def test_parse_amap_v3_route_payload():
    payload = {
        "status": "1",
        "route": {
            "paths": [
                {
                    "distance": "480",
                    "duration": "390",
                    "steps": [
                        {"polyline": "114.4148,30.5159;114.4152,30.5152"},
                        {"polyline": "114.4152,30.5152;114.4143,30.5126"},
                    ],
                }
            ]
        },
    }

    distance, duration, polyline = parse_amap_route_payload(payload)

    assert distance == 480
    assert duration == 390.0
    assert polyline[0] == [114.4148, 30.5159]
    assert polyline[-1] == [114.4143, 30.5126]


def test_route_raises_on_missing_amap_key(monkeypatch):
    class Settings:
        amap_key = ""
        amap_base_url = "https://restapi.amap.com"
        amap_timeout_seconds = 10

    monkeypatch.setattr("app.services.route_service.get_settings", lambda: Settings())
    points = [
        Point(name="起点", longitude=114.4148, latitude=30.5159),
        Point(name="终点", longitude=114.4143, latitude=30.5126),
    ]

    with pytest.raises(AmapRouteError, match="AMAP_KEY"):
        calculate_route(points=points, travel_mode="walking")


def test_route_raises_on_amap_failure_payload(monkeypatch):
    class Settings:
        amap_key = "fake-key"
        amap_base_url = "https://restapi.amap.com"
        amap_timeout_seconds = 10

    monkeypatch.setattr("app.services.route_service.get_settings", lambda: Settings())

    with patch("httpx.Client.get") as get:
        response = get.return_value
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        points = [
            Point(name="起点", longitude=114.4148, latitude=30.5159),
            Point(name="终点", longitude=114.4143, latitude=30.5126),
        ]

        with pytest.raises(AmapRouteError, match="INVALID_USER_KEY"):
            calculate_route(points=points, travel_mode="walking")


def test_route_raises_on_insufficient_points():
    points = [Point(name="单点", longitude=114.4148, latitude=30.5159)]

    with pytest.raises(ValueError):
        calculate_route(points=points, travel_mode="walking")
