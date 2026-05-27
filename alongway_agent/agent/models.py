from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator


class TaskType(str, Enum):
    PICKUP_EXPRESS = "pickup_express"
    BUY_DRINK = "buy_drink"
    EAT_MEAL = "eat_meal"
    VISIT_PLACE = "visit_place"
    STUDY = "study"
    CUSTOM = "custom"


class StopType(str, Enum):
    START = "start"
    TASK = "task"
    DEAL = "deal"
    END = "end"


class Location(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None

    def has_coordinates(self) -> bool:
        return self.longitude is not None and self.latitude is not None


class UserPreferences(BaseModel):
    prefer_less_detour: bool = True
    prefer_low_price: bool = False
    prefer_high_rating: bool = False
    prefer_high_sales: bool = False
    prefer_fast_arrival: bool = False


class PlanConstraints(BaseModel):
    max_detour_meters: int = 800
    max_extra_time_minutes: int = 15
    search_radius_meters: int = 1500
    max_pois_per_task: int = 5
    max_deals_per_poi: int = 3
    max_route_candidates: int = 20


class PlanRequest(BaseModel):
    request_id: str
    user_query: str
    start_location: Optional[Location] = None
    end_location: Optional[Location] = None
    current_location: Optional[Location] = None
    city: Optional[str] = None
    travel_mode: Literal["walking", "bicycling", "driving"] = "walking"
    budget: Optional[float] = None
    departure_time: Optional[datetime] = None
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    constraints: PlanConstraints = Field(default_factory=PlanConstraints)


class POI(BaseModel):
    poi_id: str
    name: str
    type: str
    address: Optional[str] = None
    location: Optional[str] = None
    longitude: float
    latitude: float
    rating: Optional[float] = None
    cost: Optional[float] = None
    source_keyword: str

    def to_location(self) -> Location:
        return Location(
            name=self.name,
            address=self.address,
            location=self.location,
            longitude=self.longitude,
            latitude=self.latitude,
        )


class Deal(BaseModel):
    poi_id: str
    name: str
    category: str
    deal_id: str
    deal_title: str
    price: float
    original_price: Optional[float] = None
    included_items: List[str] = Field(default_factory=list)
    additional_information: Optional[str] = None
    valid_time: Optional[str] = None
    rating: Optional[float] = None
    monthly_sales: Optional[int] = None
    reviews: List[str] = Field(default_factory=list)
    business_time: Optional[str] = None

    @field_validator("included_items", "reviews", mode="before")
    @classmethod
    def _coerce_string_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class TaskSpec(BaseModel):
    task_id: str
    type: TaskType
    raw_text: str
    source_keywords: List[str]
    budget: Optional[float] = None
    required: bool = True


class UserIntent(BaseModel):
    start_text: Optional[str] = None
    end_text: Optional[str] = None
    tasks: List[TaskSpec]
    budget: Optional[float] = None
    preferences: UserPreferences


class EnrichedCandidate(BaseModel):
    task_id: str
    task_type: TaskType
    poi: POI
    deal: Optional[Deal] = None
    is_open: bool = True
    filter_reasons: List[str] = Field(default_factory=list)


class RouteSegment(BaseModel):
    from_name: str
    to_name: str
    distance_meters: int
    duration_minutes: float


class RouteResult(BaseModel):
    distance_meters: int
    duration_minutes: float
    polyline: List[List[float]]
    segments: List[RouteSegment] = Field(default_factory=list)


class PlanStop(BaseModel):
    order: int
    stop_type: StopType
    task_id: Optional[str] = None
    name: str
    location: Location
    poi: Optional[POI] = None
    deal: Optional[Deal] = None
    reason: Optional[str] = None
    is_open: Optional[bool] = None
    availability_reasons: List[str] = Field(default_factory=list)


class ScoreDetail(BaseModel):
    detour_score: float = 0.0
    time_score: float = 0.0
    price_score: float = 0.0
    rating_score: float = 0.0
    sales_score: float = 0.0
    open_score: float = 0.0


class CandidatePlan(BaseModel):
    plan_id: str
    stops: List[PlanStop]
    route: RouteResult
    base_distance_meters: int
    base_duration_minutes: float
    detour_distance_meters: int
    extra_time_minutes: float
    estimated_cost: float
    score: float = 0.0
    score_detail: ScoreDetail = Field(default_factory=ScoreDetail)
    recommendation_reason: Optional[str] = None

    @computed_field
    @property
    def total_distance_meters(self) -> int:
        return self.route.distance_meters

    @computed_field
    @property
    def total_duration_minutes(self) -> float:
        return self.route.duration_minutes


class AlternativePlanSummary(BaseModel):
    plan_id: str
    score: float
    total_distance_meters: int
    total_duration_minutes: float
    detour_distance_meters: int
    extra_time_minutes: float
    estimated_cost: float
    brief_reason: str


class DebugTrace(BaseModel):
    parsed_task_count: int
    poi_candidate_count: int
    deal_candidate_count: int
    route_candidate_count: int


class PlanResponse(BaseModel):
    success: bool
    request_id: str
    summary: Optional[str] = None
    intent: Optional[UserIntent] = None
    selected_plan: Optional[CandidatePlan] = None
    alternative_plans: List[AlternativePlanSummary] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    debug_trace: Optional[DebugTrace] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    fallback_suggestions: List[str] = Field(default_factory=list)
