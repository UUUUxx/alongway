from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional

try:
    import httpx
except ImportError:  # pragma: no cover - exercised only without optional dependency
    httpx = None  # type: ignore[assignment]

from agent.call_logger import log_call
from agent.models import Deal, Location, POI, RouteResult, RouteSegment


class BackendClient(ABC):
    @abstractmethod
    async def search_pois(
        self,
        source_keywords: List[str],
        center: Optional[Location],
        radius_meters: int,
        limit: int,
        specific_place_name: Optional[str] = None,
    ) -> List[POI]:
        raise NotImplementedError

    @abstractmethod
    async def search_deals(
        self,
        poi_id: str,
        categories: List[str],
        max_price: Optional[float],
        limit: int,
    ) -> List[Deal]:
        raise NotImplementedError

    @abstractmethod
    async def calculate_route(
        self,
        points: List[Location],
        travel_mode: str,
    ) -> RouteResult:
        raise NotImplementedError

    @abstractmethod
    async def geocode(
        self,
        address: str,
        city: Optional[str],
        limit: int = 3,
    ) -> List[Location]:
        raise NotImplementedError


class HttpBackendClient(BackendClient):
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required to use HttpBackendClient")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
            try:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                data = response.json()
                log_call(
                    "agent.backend_client.post.result",
                    request={"path": path, "payload": payload},
                    result=data,
                )
                return data
            except Exception as exc:
                log_call(
                    "agent.backend_client.post.error",
                    request={"path": path, "payload": payload},
                    error=str(exc),
                )
                raise

    async def search_pois(
        self,
        source_keywords: List[str],
        center: Optional[Location],
        radius_meters: int,
        limit: int,
        specific_place_name: Optional[str] = None,
    ) -> List[POI]:
        payload = {
            "source_keywords": source_keywords,
            "center": center.model_dump(exclude_none=True) if center else None,
            "radius_meters": radius_meters,
            "limit": limit,
            "specific_place_name": specific_place_name,
        }
        data = await self._post("/internal/pois/search", payload)
        return [POI.model_validate(item) for item in data.get("pois", [])]

    async def search_deals(
        self,
        poi_id: str,
        categories: List[str],
        max_price: Optional[float],
        limit: int,
    ) -> List[Deal]:
        payload = {
            "poi_id": poi_id,
            "categories": categories,
            "max_price": max_price,
            "limit": limit,
        }
        data = await self._post("/internal/deals/search", payload)
        return [Deal.model_validate(item) for item in data.get("deals", [])]

    async def calculate_route(
        self,
        points: List[Location],
        travel_mode: str,
    ) -> RouteResult:
        payload = {
            "points": [point.model_dump(exclude_none=True) for point in points],
            "travel_mode": travel_mode,
            "use_real_route": True,
        }
        data = await self._post("/internal/route/calculate", payload)
        return RouteResult.model_validate(data)

    async def geocode(
        self,
        address: str,
        city: Optional[str],
        limit: int = 3,
    ) -> List[Location]:
        data = await self._post(
            "/api/geocode",
            {"address": address, "city": city or "武汉"},
        )
        if not data.get("success"):
            return []
        locations = []
        for item in data.get("results", [])[:limit]:
            locations.append(
                Location(
                    name=item.get("name") or address,
                    address=item.get("address"),
                    location=item.get("location"),
                    longitude=item.get("longitude"),
                    latitude=item.get("latitude"),
                )
            )
        return locations


class MockBackendClient(BackendClient):
    def __init__(self) -> None:
        self._pois = [
            POI(
                poi_id="poi_001",
                name="茶百道",
                type="drink",
                address="学校商业街一楼",
                location="商业街",
                longitude=114.1258,
                latitude=30.4590,
                rating=4.6,
                cost=18,
                source_keyword="奶茶",
            ),
            POI(
                poi_id="poi_002",
                name="菜鸟驿站",
                type="express",
                address="学生服务中心一楼",
                location="宿舍区附近",
                longitude=114.1243,
                latitude=30.4574,
                rating=4.5,
                source_keyword="快递",
            ),
            POI(
                poi_id="poi_003",
                name="瑞幸咖啡",
                type="drink",
                address="教学楼北侧",
                location="教学区",
                longitude=114.1272,
                latitude=30.4600,
                rating=4.7,
                cost=16,
                source_keyword="咖啡",
            ),
            POI(
                poi_id="poi_004",
                name="校园快递柜",
                type="express",
                address="宿舍区东门",
                location="宿舍区",
                longitude=114.1237,
                latitude=30.4569,
                rating=4.2,
                source_keyword="快递柜",
            ),
            POI(
                poi_id="poi_005",
                name="一食堂",
                type="food",
                address="生活区二楼",
                location="生活区",
                longitude=114.1250,
                latitude=30.4584,
                rating=4.1,
                cost=14,
                source_keyword="食堂",
            ),
            POI(
                poi_id="poi_006",
                name="蜜雪冰城",
                type="drink",
                address="商业街入口",
                location="商业街",
                longitude=114.1264,
                latitude=30.4587,
                rating=4.3,
                cost=10,
                source_keyword="饮品",
            ),
            POI(
                poi_id="poi_007",
                name="图书馆",
                type="study",
                address="某大学图书馆",
                location="教学区",
                longitude=114.1280,
                latitude=30.4620,
                rating=4.8,
                source_keyword="图书馆",
            ),
        ]
        self._deals = [
            Deal(
                poi_id="poi_001",
                name="茶百道",
                category="奶茶",
                deal_id="deal_001",
                deal_title="招牌奶茶单人套餐",
                price=16.8,
                original_price=22,
                included_items=["招牌奶茶1杯", "任选小料1份"],
                additional_information="新人可用，部分门店不可用",
                valid_time="10:00-21:30",
                rating=4.7,
                monthly_sales=300,
                reviews=["价格划算", "味道不错", "出餐快"],
                business_time="10:00-22:00",
            ),
            Deal(
                poi_id="poi_001",
                name="茶百道",
                category="饮品",
                deal_id="deal_002",
                deal_title="轻乳茶下午套餐",
                price=12.9,
                original_price=18,
                included_items=["轻乳茶1杯"],
                valid_time="12:00-20:30",
                rating=4.5,
                monthly_sales=180,
                reviews=["便宜", "口味稳定"],
                business_time="10:00-22:00",
            ),
            Deal(
                poi_id="poi_003",
                name="瑞幸咖啡",
                category="咖啡",
                deal_id="deal_003",
                deal_title="拿铁单杯券",
                price=13.9,
                original_price=29,
                included_items=["拿铁1杯"],
                valid_time="08:00-20:00",
                rating=4.8,
                monthly_sales=520,
                reviews=["出杯快", "适合去图书馆前买"],
                business_time="08:00-21:00",
            ),
            Deal(
                poi_id="poi_006",
                name="蜜雪冰城",
                category="饮品",
                deal_id="deal_004",
                deal_title="柠檬水双杯套餐",
                price=9.9,
                original_price=14,
                included_items=["柠檬水2杯"],
                valid_time="09:00-22:00",
                rating=4.2,
                monthly_sales=760,
                reviews=["很划算", "排队略久"],
                business_time="09:00-23:00",
            ),
            Deal(
                poi_id="poi_005",
                name="一食堂",
                category="食堂",
                deal_id="deal_005",
                deal_title="午餐单人套餐",
                price=13.5,
                original_price=16,
                included_items=["主食1份", "素菜1份", "汤1份"],
                valid_time="10:30-13:30",
                rating=4.2,
                monthly_sales=420,
                reviews=["出餐快", "量足"],
                business_time="07:00-20:00",
            ),
        ]

    async def search_pois(
        self,
        source_keywords: List[str],
        center: Optional[Location],
        radius_meters: int,
        limit: int,
        specific_place_name: Optional[str] = None,
    ) -> List[POI]:
        normalized = [keyword.lower() for keyword in source_keywords]
        if specific_place_name:
            normalized.insert(0, specific_place_name.lower())
        matched: list[tuple[float, POI]] = []
        for poi in self._pois:
            text = f"{poi.source_keyword} {poi.name} {poi.type}".lower()
            if not any(keyword in text or text in keyword for keyword in normalized):
                continue
            distance = 0.0
            if center and center.has_coordinates():
                distance = self._haversine_meters(
                    center.longitude or 0,
                    center.latitude or 0,
                    poi.longitude,
                    poi.latitude,
                )
                if distance > radius_meters:
                    continue
            matched.append((distance, poi))

        matched.sort(key=lambda item: (item[0], -(item[1].rating or 0)))
        return [poi for _, poi in matched[:limit]]

    async def geocode(
        self,
        address: str,
        city: Optional[str],
        limit: int = 3,
    ) -> List[Location]:
        matched = await self.search_pois(
            source_keywords=[address],
            center=None,
            radius_meters=10_000,
            limit=limit,
            specific_place_name=address,
        )
        locations = [poi.to_location() for poi in matched]
        fallback = {
            "宿舍": Location(name="学生宿舍", longitude=114.123, latitude=30.456),
            "图书馆": Location(name="图书馆", longitude=114.128, latitude=30.462),
            "主图书馆": Location(name="主图书馆", longitude=114.128, latitude=30.462),
            "教学楼": Location(name="教学楼", longitude=114.127, latitude=30.46),
        }
        if not locations and address in fallback:
            locations.append(fallback[address])
        return locations[:limit]

    async def search_deals(
        self,
        poi_id: str,
        categories: List[str],
        max_price: Optional[float],
        limit: int,
    ) -> List[Deal]:
        normalized = [category.lower() for category in categories]
        matched = []
        for deal in self._deals:
            category_text = f"{deal.category} {deal.deal_title}".lower()
            if deal.poi_id != poi_id:
                continue
            if not any(item in category_text or category_text in item for item in normalized):
                continue
            if max_price is not None and deal.price > max_price:
                continue
            matched.append(deal)

        matched.sort(
            key=lambda deal: (
                deal.price,
                -(deal.monthly_sales or 0),
                -(deal.rating or 0),
            )
        )
        return matched[:limit]

    async def calculate_route(
        self,
        points: List[Location],
        travel_mode: str,
    ) -> RouteResult:
        if len(points) < 2:
            return RouteResult(distance_meters=0, duration_minutes=0, polyline=[])

        speed_meters_per_minute = {
            "walking": 75.0,
            "bicycling": 180.0,
            "driving": 420.0,
        }.get(travel_mode, 75.0)

        total_distance = 0
        segments: list[RouteSegment] = []
        for start, end in zip(points, points[1:]):
            if not start.has_coordinates() or not end.has_coordinates():
                raise ValueError("all route points must include coordinates")
            distance = int(
                round(
                    self._haversine_meters(
                        start.longitude or 0,
                        start.latitude or 0,
                        end.longitude or 0,
                        end.latitude or 0,
                    )
                )
            )
            total_distance += distance
            segments.append(
                RouteSegment(
                    from_name=start.name or "unknown",
                    to_name=end.name or "unknown",
                    distance_meters=distance,
                    duration_minutes=round(distance / speed_meters_per_minute, 1),
                )
            )

        return RouteResult(
            distance_meters=total_distance,
            duration_minutes=round(total_distance / speed_meters_per_minute, 1),
            polyline=[
                [point.longitude or 0, point.latitude or 0]
                for point in points
                if point.has_coordinates()
            ],
            segments=segments,
        )

    @staticmethod
    def _haversine_meters(
        lon1: float,
        lat1: float,
        lon2: float,
        lat2: float,
    ) -> float:
        earth_radius = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(delta_lambda / 2) ** 2
        )
        return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
