"""
Map configuration endpoint for frontend Amap rendering.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.schemas import MapConfigResponse

router = APIRouter(tags=["frontend"])


@router.get("/api/config/map", response_model=MapConfigResponse)
def map_config_endpoint() -> MapConfigResponse:
    settings = get_settings()
    return MapConfigResponse(amap_js_key=settings.amap_js_key)
