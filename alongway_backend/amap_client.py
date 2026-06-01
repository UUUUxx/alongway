from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from app.config import get_settings

MAX_RETRIES = int(os.getenv("AMAP_MAX_RETRIES", "3"))
PAGE_SIZE = int(os.getenv("AMAP_PAGE_SIZE", "20"))
REQUEST_INTERVAL_SECONDS = float(os.getenv("AMAP_REQUEST_INTERVAL_SECONDS", "0"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("AMAP_TIMEOUT_SECONDS", "10"))


class AmapAPIError(RuntimeError):
    pass


class AmapClient:
    def __init__(
        self,
        api_key: str,
        logger: logging.Logger | None = None,
        request_interval_seconds: float = REQUEST_INTERVAL_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)
        self.request_interval_seconds = request_interval_seconds
        self.max_retries = max_retries
        self.session = requests.Session()

    def geocode(self, address: str, city: str = "上海") -> list[dict[str, Any]]:
        payload = self._get(
            "/geocode/geo",
            {
                "address": address,
                "city": city,
            },
        )
        return payload.get("geocodes", [])

    def search_around(
        self,
        location: str,
        keywords: str,
        radius: int,
        city: str = "上海",
        page: int = 1,
        offset: int = PAGE_SIZE,
    ) -> dict[str, Any]:
        return self._get(
            "/place/around",
            {
                "location": location,
                "keywords": keywords,
                "radius": radius,
                "city": city,
                "offset": offset,
                "page": page,
                "extensions": "all",
                "sortrule": "distance",
            },
        )

    def search_text(
        self,
        keywords: str,
        city: str = "上海",
        citylimit: bool = True,
        page: int = 1,
        offset: int = PAGE_SIZE,
    ) -> dict[str, Any]:
        return self._get(
            "/place/text",
            {
                "keywords": keywords,
                "city": city,
                "citylimit": "true" if citylimit else "false",
                "offset": offset,
                "page": page,
                "extensions": "all",
            },
        )

    def walking_route(self, origin: str, destination: str) -> dict[str, Any]:
        return self._get(
            "/direction/walking",
            {
                "origin": origin,
                "destination": destination,
            },
        )

    def driving_route(
        self, origin: str, destination: str, strategy: int = 0
    ) -> dict[str, Any]:
        """Get driving route between two points.

        Args:
            origin: "lng,lat" string
            destination: "lng,lat" string
            strategy: 0=fastest, 1=cheapest, 2=shortest, 3=consider traffic(no highways)
        """
        return self._get(
            "/direction/driving",
            {
                "origin": origin,
                "destination": destination,
                "strategy": str(strategy),
            },
        )

    def transit_route(
        self, origin: str, destination: str, city: str = "武汉", strategy: int = 0
    ) -> dict[str, Any]:
        """Get public transit route between two points.

        Args:
            origin: "lng,lat" string
            destination: "lng,lat" string
            city: city name for transit
            strategy: 0=fastest, 1=least transfers, 2=least walking, 3=most comfortable
        """
        return self._get(
            "/direction/transit/integrated",
            {
                "origin": origin,
                "destination": destination,
                "city": city,
                "strategy": str(strategy),
            },
        )

    def bicycling_route(self, origin: str, destination: str) -> dict[str, Any]:
        """Get bicycling route between two points."""
        return self._get(
            "/v4/direction/bicycling",
            {
                "origin": origin,
                "destination": destination,
            },
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        base_url = get_settings().amap_base_url
        api_path = path if path.startswith("/v") else f"/v3{path}"
        url = f"{base_url}{api_path}"
        merged_params = {**params, "key": self.api_key, "output": "JSON"}
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            time.sleep(self.request_interval_seconds)
            try:
                response = self.session.get(url, params=merged_params, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "1":
                    info = payload.get("info", "unknown error")
                    infocode = payload.get("infocode", "unknown infocode")
                    raise AmapAPIError(f"Amap API failed: {info} ({infocode})")
                return payload
            except (requests.RequestException, ValueError, AmapAPIError) as exc:
                last_error = exc
                wait_seconds = min(2**attempt, 10)
                self.logger.warning(
                    "Amap request failed attempt=%s/%s path=%s params=%s error=%s",
                    attempt,
                    self.max_retries,
                    path,
                    {k: v for k, v in merged_params.items() if k != "key"},
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(wait_seconds)

        raise AmapAPIError(f"Amap request failed after {self.max_retries} retries: {last_error}")
