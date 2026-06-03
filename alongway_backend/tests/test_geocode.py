"""
Tests for /api/geocode proxy endpoint.
"""
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _Settings:
    amap_key = "fake-key"
    amap_base_url = "https://restapi.amap.com"
    amap_timeout_seconds = 10


def _mock_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_geocode_calls_amap_v3_endpoint(monkeypatch):
    captured = {}

    async def fake_get(url, params):
        captured["url"] = url
        captured["params"] = params
        return _mock_response(
            {
                "status": "1",
                "geocodes": [
                    {
                        "name": "主图书馆",
                        "formatted_address": "华中科技大学主图书馆",
                        "location": "114.4143,30.5126",
                    }
                ],
            }
        )

    monkeypatch.setattr("app.routers.geocode.get_settings", lambda: _Settings())
    with patch("httpx.AsyncClient.get", side_effect=fake_get):
        response = client.post("/api/geocode", json={"address": "主图书馆", "city": "武汉"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["results"][0]["longitude"] == 114.4143
    assert data["results"][0]["latitude"] == 30.5126
    assert captured["url"] == "https://restapi.amap.com/v3/geocode/geo"
    assert captured["params"]["address"] == "主图书馆"
    assert captured["params"]["key"] == "fake-key"


def test_geocode_reports_missing_amap_key(monkeypatch):
    class SettingsWithoutKey(_Settings):
        amap_key = ""

    monkeypatch.setattr("app.routers.geocode.get_settings", lambda: SettingsWithoutKey())
    response = client.post("/api/geocode", json={"address": "不存在的测试地点", "city": "武汉"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not configured" in data["error_message"]


def test_geocode_uses_local_fallback_without_amap_key(monkeypatch):
    class SettingsWithoutKey(_Settings):
        amap_key = ""

    monkeypatch.setattr("app.routers.geocode.get_settings", lambda: SettingsWithoutKey())
    response = client.post("/api/geocode", json={"address": "汉口火车站", "city": "武汉"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["results"][0]["name"] == "汉口火车站"


def test_geocode_uses_local_fallback_for_wuda_without_amap_key(monkeypatch):
    class SettingsWithoutKey(_Settings):
        amap_key = ""

    monkeypatch.setattr("app.routers.geocode.get_settings", lambda: SettingsWithoutKey())
    response = client.post("/api/geocode", json={"address": "武大", "city": "武汉"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["results"][0]["name"] == "武汉大学"


def test_geocode_uses_local_fallback_for_hust_and_world_city(monkeypatch):
    class SettingsWithoutKey(_Settings):
        amap_key = ""

    monkeypatch.setattr("app.routers.geocode.get_settings", lambda: SettingsWithoutKey())

    hust_response = client.post("/api/geocode", json={"address": "华科", "city": "武汉"})
    world_city_response = client.post("/api/geocode", json={"address": "世界城广场", "city": "武汉"})

    hust_data = hust_response.json()
    world_city_data = world_city_response.json()
    assert hust_data["success"] is True
    assert hust_data["results"][0]["name"] == "华中科技大学"
    assert world_city_data["success"] is True
    assert world_city_data["results"][0]["name"] == "世界城广场"
