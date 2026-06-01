from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.backend_client import HttpBackendClient
from agent.models import Location


def test_http_backend_client_requests_real_route() -> None:
    captured = {}
    client = HttpBackendClient("http://backend.test")

    async def fake_post(path, payload):
        captured["path"] = path
        captured["payload"] = payload
        return {
            "distance_meters": 100,
            "duration_minutes": 2,
            "polyline": [[114.1, 30.4], [114.2, 30.5]],
            "segments": [],
        }

    client._post = fake_post

    asyncio.run(
        client.calculate_route(
            [
                Location(name="起点", longitude=114.1, latitude=30.4),
                Location(name="终点", longitude=114.2, latitude=30.5),
            ],
            "walking",
        )
    )

    assert captured["path"] == "/internal/route/calculate"
    assert captured["payload"]["use_real_route"] is True
