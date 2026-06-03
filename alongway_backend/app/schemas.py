"""
Pydantic request and response models for MVP API.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


# ==================== Request Models ====================


class LocationInput(BaseModel):
    """Location input model."""

    name: str
    address: str
    location: str
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    accuracy_meters: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None


class PreferencesInput(BaseModel):
    """User preferences."""

    prefer_less_detour: bool = True
    prefer_low_price: bool = True
    prefer_high_rating: bool = False
    prefer_high_sales: bool = False
    prefer_fast_arrival: bool = False


class ConstraintsInput(BaseModel):
    """Constraints on the plan."""

    max_detour_meters: int = 800
    max_extra_time_minutes: int = 15
    search_radius_meters: int = 1500
    max_pois_per_task: int = 5
    max_deals_per_poi: int = 3
    max_route_candidates: int = 10


class PlanRequest(BaseModel):
    """POST /api/plan request."""

    request_id: Optional[str] = None
    user_query: str
    start_location: Optional[LocationInput] = None
    end_location: Optional[LocationInput] = None
    current_location: Optional[LocationInput] = None
    city: str
    travel_mode: str = "walking"
    budget: Optional[float] = None
    preferences: PreferencesInput = Field(default_factory=PreferencesInput)
    constraints: ConstraintsInput = Field(default_factory=ConstraintsInput)


class Point(BaseModel):
    """A geographic point."""

    name: str
    longitude: float
    latitude: float


class RouteCalculateRequest(BaseModel):
    """POST /internal/route/calculate request."""

    points: list[Point]
    travel_mode: str = "walking"
    use_real_route: bool = True  # if True, use Amap API instead of Haversine


class POISearchRequest(BaseModel):
    """POST /internal/pois/search request."""

    source_keywords: list[str]
    center: Optional[Point] = None
    radius_meters: Optional[int] = None
    limit: int = 5
    specific_place_name: Optional[str] = None


class DealSearchRequest(BaseModel):
    """POST /internal/deals/search request."""

    poi_id: str
    categories: Optional[list[str]] = None
    max_price: Optional[float] = None
    limit: int = 3


# ==================== Response Models ====================


class POIResponse(BaseModel):
    """POI response item."""

    poi_id: str
    name: str
    type: str
    address: str
    location: str
    longitude: float
    latitude: float
    rating: Optional[float] = None
    cost: Optional[float] = None
    source_keyword: str
    distance_meters: Optional[float] = None


class POISarchResponse(BaseModel):
    """POST /internal/pois/search response."""

    pois: list[POIResponse]


class DealResponse(BaseModel):
    """Deal response item."""

    poi_id: str
    name: str
    category: str
    deal_id: str
    deal_title: str
    price: float
    original_price: Optional[float] = None
    included_items: Optional[list[str]] = None
    additional_information: Optional[str] = None
    valid_time: Optional[str] = None
    rating: Optional[float] = None
    monthly_sales: Optional[int] = None
    reviews: Optional[list[str]] = None
    business_time: Optional[str] = None


class DealsSearchResponse(BaseModel):
    """POST /internal/deals/search response."""

    deals: list[DealResponse]


class RouteSegment(BaseModel):
    """A segment of a route."""

    from_name: str
    to_name: str
    distance_meters: int
    duration_minutes: float


class RouteCalculateResponse(BaseModel):
    """POST /internal/route/calculate response."""

    distance_meters: int
    duration_minutes: float
    polyline: list[list[float]]
    segments: list[RouteSegment]


class PlanResponse(BaseModel):
    """Response from /api/plan - from Agent service."""

    success: bool
    request_id: Optional[str] = None
    plan: Optional[dict[str, Any]] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    fallback_suggestions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_type: Optional[str] = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str


# ==================== Admin Models ====================


class POICreate(BaseModel):
    """Create/update POI."""

    name: str
    type: str
    address: str
    location: str
    longitude: float
    latitude: float
    rating: Optional[float] = None
    cost: Optional[float] = None
    source_keyword: str


class POIUpdate(BaseModel):
    """Update POI (all fields optional)."""

    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    rating: Optional[float] = None
    cost: Optional[float] = None
    source_keyword: Optional[str] = None


class DealCreate(BaseModel):
    """Create/update Deal."""

    poi_id: str
    name: str
    category: str
    deal_title: str
    price: float
    original_price: Optional[float] = None
    included_items: Optional[list[str]] = None
    additional_information: Optional[str] = None
    valid_time: Optional[str] = None
    rating: Optional[float] = None
    monthly_sales: Optional[int] = None
    reviews: Optional[list[str]] = None
    business_time: Optional[str] = None


class DealUpdate(BaseModel):
    """Update Deal (all fields optional)."""

    poi_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    deal_title: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    included_items: Optional[list[str]] = None
    additional_information: Optional[str] = None
    valid_time: Optional[str] = None
    rating: Optional[float] = None
    monthly_sales: Optional[int] = None
    reviews: Optional[list[str]] = None
    business_time: Optional[str] = None


# ==================== Geocode Models ====================


class GeocodeRequest(BaseModel):
    """POST /api/geocode request — address to coordinates."""

    address: str
    city: str = "武汉"


class GeocodeResult(BaseModel):
    """Single geocode result."""

    name: str
    address: str
    location: str  # "longitude,latitude"
    longitude: float
    latitude: float


class GeocodeResponse(BaseModel):
    """POST /api/geocode response."""

    success: bool
    results: list[GeocodeResult] = []
    error_message: Optional[str] = None


# ==================== History Cache Models (Task 4) ====================


class PlanHistoryEntry(BaseModel):
    """A cached history entry of a previous plan request + its response."""

    request_id: str
    user_query: str
    city: str
    travel_mode: str
    preferences: PreferencesInput
    constraints: ConstraintsInput
    response_plan: Optional[dict[str, Any]] = None
    created_at: str  # ISO format timestamp


class PlanHistoryResponse(BaseModel):
    """Response with cached history entries."""

    entries: list[PlanHistoryEntry]
    count: int


# ==================== Map Config Models ====================


class MapConfigResponse(BaseModel):
    """GET /api/config/map response — Amap JS API configuration for frontend."""

    amap_js_key: str
    amap_version: str = "2.0"
    default_center: list[float] = [114.4052, 30.5078]
    default_zoom: int = 14
