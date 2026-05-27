"""
Tests for /api/plan proxy endpoint and Agent service integration.
"""
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import PlanRequest

client = TestClient(app)


def _make_plan_request(**overrides):
    defaults = {
        "user_query": "从宿舍去图书馆，路上取快递，买奶茶",
        "start_location": {
            "name": "学生宿舍",
            "address": "某大学学生宿舍",
            "location": "宿舍区",
            "longitude": 114.123,
            "latitude": 30.456,
        },
        "end_location": {
            "name": "图书馆",
            "address": "某大学图书馆",
            "location": "教学区",
            "longitude": 114.128,
            "latitude": 30.462,
        },
        "city": "武汉",
        "travel_mode": "walking",
        "budget": 20,
    }
    defaults.update(overrides)
    return defaults


def _agent_success_response(request_id=None):
    return {
        "success": True,
        "request_id": request_id,
        "summary": "顺路且价格合适",
        "selected_plan": {
            "plan_id": "plan_001",
            "stops": [
                {
                    "order": 1,
                    "stop_type": "start",
                    "name": "学生宿舍",
                    "location": {
                        "name": "学生宿舍",
                        "address": "某大学学生宿舍",
                        "location": "宿舍区",
                        "longitude": 114.123,
                        "latitude": 30.456,
                    },
                },
                {
                    "order": 2,
                    "stop_type": "deal",
                    "name": "茶百道",
                    "location": {
                        "name": "茶百道",
                        "address": "学校商业街一楼",
                        "location": "商业街",
                        "longitude": 114.126,
                        "latitude": 30.459,
                    },
                    "poi": {
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
                    "deal": {
                        "poi_id": "poi_001",
                        "name": "茶百道",
                        "category": "奶茶",
                        "deal_id": "deal_001",
                        "deal_title": "招牌奶茶单人套餐",
                        "price": 16.8,
                        "original_price": 22,
                        "included_items": ["招牌奶茶1杯"],
                        "rating": 4.7,
                        "monthly_sales": 300,
                    },
                },
                {
                    "order": 3,
                    "stop_type": "end",
                    "name": "图书馆",
                    "location": {
                        "name": "图书馆",
                        "address": "某大学图书馆",
                        "location": "教学区",
                        "longitude": 114.128,
                        "latitude": 30.462,
                    },
                },
            ],
            "route": {
                "distance_meters": 900,
                "duration_minutes": 12.0,
                "polyline": [[114.123, 30.456], [114.126, 30.459], [114.128, 30.462]],
                "segments": [
                    {
                        "from_name": "学生宿舍",
                        "to_name": "茶百道",
                        "distance_meters": 450,
                        "duration_minutes": 6.0,
                    },
                    {
                        "from_name": "茶百道",
                        "to_name": "图书馆",
                        "distance_meters": 450,
                        "duration_minutes": 6.0,
                    },
                ],
            },
            "base_distance_meters": 800,
            "base_duration_minutes": 10.0,
            "detour_distance_meters": 100,
            "extra_time_minutes": 2.0,
            "estimated_cost": 16.8,
            "score": 0.92,
            "recommendation_reason": "顺路且价格合适",
        },
        "alternative_plans": [],
        "warnings": [],
    }


def test_plan_agent_unavailable():
    """Test /api/plan returns error when Agent service is unavailable."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "AGENT_SERVICE_UNAVAILABLE"
    assert data["message"] is not None


def test_plan_agent_timeout():
    """Test /api/plan returns error when Agent service times out."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_code"] == "AGENT_SERVICE_TIMEOUT"


def test_plan_auto_generates_request_id():
    """Test /api/plan auto-generates request_id if missing."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = _agent_success_response()

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        payload = _make_plan_request()
        assert "request_id" not in payload
        response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] is not None
    assert data["request_id"].startswith("req_")


def test_plan_preserves_request_id():
    """Test /api/plan preserves request_id when provided."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = _agent_success_response("my_req_001")

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post("/api/plan", json=_make_plan_request(request_id="my_req_001"))

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "my_req_001"


def test_plan_agent_success():
    """Test /api/plan returns Agent response on success."""
    agent_plan = _agent_success_response("req_001")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = agent_plan

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        response = client.post("/api/plan", json=_make_plan_request())

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"] is not None
    assert data["plan"]["summary"]["total_cost"] == 16.8
    assert len(data["plan"]["route_overview"]["waypoints"]) == 3
    assert len(data["plan"]["pois"]) == 1


def test_plan_agent_http_error():
    """Test /api/plan returns error on Agent HTTP error."""
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
