"""
Tests for /api/plan proxy endpoint and Agent service integration.
"""
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_plan_request(**overrides):
    defaults = {
        "user_query": "从韵苑宿舍去图书馆，路上取快递，再买一杯奶茶",
        "start_location": {
            "name": "韵苑宿舍",
            "address": "华中科技大学韵苑学生公寓",
            "location": "韵苑生活区",
            "longitude": 114.4148,
            "latitude": 30.5159,
            "accuracy_meters": 18.5,
            "source": "browser_geolocation",
        },
        "end_location": {
            "name": "主图书馆",
            "address": "华中科技大学主图书馆",
            "location": "主图书馆",
            "longitude": 114.4143,
            "latitude": 30.5126,
        },
        "city": "武汉",
        "travel_mode": "walking",
        "budget": 25,
        "preferences": {
            "prefer_less_detour": True,
            "prefer_low_price": False,
            "prefer_high_rating": True,
            "prefer_high_sales": False,
            "prefer_fast_arrival": True,
        },
        "constraints": {
            "max_detour_meters": 600,
            "max_extra_time_minutes": 12,
            "search_radius_meters": 1200,
            "max_pois_per_task": 4,
            "max_deals_per_poi": 2,
            "max_route_candidates": 10,
        },
    }
    defaults.update(overrides)
    return defaults


def _mock_agent_response(payload=None):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = payload or {"success": True, "plan": {}}
    return mock_response


def test_plan_agent_unavailable():
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "AGENT_SERVICE_UNAVAILABLE"
    assert data["message"] is not None


def test_plan_agent_timeout():
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "AGENT_SERVICE_TIMEOUT"


def test_plan_auto_generates_request_id():
    with patch("httpx.AsyncClient.post", return_value=_mock_agent_response()):
        payload = _make_plan_request()
        assert "request_id" not in payload
        response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] is not None
    assert data["request_id"].startswith("req_")


def test_plan_preserves_request_id():
    with patch("httpx.AsyncClient.post", return_value=_mock_agent_response()):
        response = client.post("/api/plan", json=_make_plan_request(request_id="my_req_001"))

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "my_req_001"


def test_plan_forwards_frontend_options_to_agent():
    captured = {}

    async def fake_post(url, json):
        captured["url"] = url
        captured["json"] = json
        return _mock_agent_response()

    payload = _make_plan_request()
    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    forwarded = captured["json"]
    assert captured["url"].endswith("/agent/plan")
    assert forwarded["request_id"].startswith("req_")
    assert forwarded["budget"] == payload["budget"]
    assert forwarded["travel_mode"] == payload["travel_mode"]
    assert forwarded["preferences"] == payload["preferences"]
    assert forwarded["constraints"] == payload["constraints"]
    assert forwarded["start_location"] == payload["start_location"]
    assert forwarded["end_location"] == payload["end_location"]


def test_plan_accepts_current_location_without_start_or_end():
    captured = {}

    async def fake_post(url, json):
        captured["json"] = json
        return _mock_agent_response({"success": False, "error_code": "NO_TASK_PARSED"})

    payload = _make_plan_request(
        user_query="到主图书馆，路上取快递",
        start_location=None,
        end_location=None,
        current_location={
            "name": "当前位置",
            "address": "浏览器定位",
            "location": "114.4148,30.5159",
            "longitude": 114.4148,
            "latitude": 30.5159,
            "source": "browser_geolocation",
        },
    )
    with patch("httpx.AsyncClient.post", side_effect=fake_post):
        response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    assert "start_location" not in captured["json"]
    assert "end_location" not in captured["json"]
    assert captured["json"]["current_location"]["source"] == "browser_geolocation"


def test_plan_agent_success():
    agent_plan = {
        "success": True,
        "request_id": "req_001",
        "plan": {
            "route": [[114.4148, 30.5159], [114.4152, 30.5152], [114.4143, 30.5126]],
            "stops": [{"poi_id": "poi_001", "deal_id": "deal_001"}],
            "recommendation_reason": "顺路且评分较高",
        },
    }

    with patch("httpx.AsyncClient.post", return_value=_mock_agent_response(agent_plan)):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["plan"]["route"]) == 3
    assert len(data["plan"]["stops"]) == 1


def test_plan_adapts_real_agent_selected_plan_shape():
    agent_response = {
        "success": True,
        "request_id": "req_002",
        "summary": "推荐顺路取快递再去图书馆",
        "selected_plan": {
            "stops": [
                {
                    "stop_type": "start",
                    "name": "韵苑宿舍",
                    "location": {
                        "name": "韵苑宿舍",
                        "address": "华中科技大学韵苑学生公寓",
                        "longitude": 114.4148,
                        "latitude": 30.5159,
                    },
                },
                {
                    "stop_type": "task",
                    "task_id": "task_1",
                    "name": "菜鸟驿站",
                    "location": {
                        "name": "菜鸟驿站",
                        "address": "学生服务中心",
                        "longitude": 114.4152,
                        "latitude": 30.5152,
                    },
                    "poi": {
                        "poi_id": "poi_001",
                        "name": "菜鸟驿站",
                        "type": "express",
                        "address": "学生服务中心",
                        "location": "生活区",
                        "longitude": 114.4152,
                        "latitude": 30.5152,
                        "source_keyword": "快递",
                    },
                    "reason": "绕路少",
                },
                {
                    "stop_type": "end",
                    "name": "主图书馆",
                    "location": {
                        "name": "主图书馆",
                        "address": "华中科技大学主图书馆",
                        "longitude": 114.4143,
                        "latitude": 30.5126,
                    },
                },
            ],
            "route": {
                "distance_meters": 480,
                "duration_minutes": 6.5,
                "polyline": [[114.4148, 30.5159], [114.4152, 30.5152], [114.4143, 30.5126]],
                "segments": [
                    {
                        "from_name": "韵苑宿舍",
                        "to_name": "菜鸟驿站",
                        "distance_meters": 120,
                        "duration_minutes": 1.5,
                    },
                    {
                        "from_name": "菜鸟驿站",
                        "to_name": "主图书馆",
                        "distance_meters": 360,
                        "duration_minutes": 5,
                    },
                ],
            },
            "detour_distance_meters": 80,
            "extra_time_minutes": 1.2,
            "estimated_cost": 0,
            "score": 0.91,
            "recommendation_reason": "顺路且距离短",
        },
    }

    with patch("httpx.AsyncClient.post", return_value=_mock_agent_response(agent_response)):
        response = client.post("/api/plan", json=_make_plan_request(request_id="req_002"))

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["summary"]["origin"]["name"] == "韵苑宿舍"
    assert data["plan"]["summary"]["destination"]["name"] == "主图书馆"
    assert len(data["plan"]["route_overview"]["waypoints"]) == 3
    assert data["plan"]["route_overview"]["segments"][0]["instruction"] == "从韵苑宿舍前往菜鸟驿站"
    assert data["plan"]["pois"][0]["name"] == "菜鸟驿站"
    assert data["plan"]["pois"][0]["type"] == "快递"


def test_plan_agent_http_error():
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=Mock(), response=mock_response
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "AGENT_SERVICE_ERROR"
