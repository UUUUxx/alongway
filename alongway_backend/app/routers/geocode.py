"""
Geocode proxy endpoint — avoids exposing AMAP_KEY to frontend.
"""
import logging

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import GeocodeRequest, GeocodeResponse, GeocodeResult

logger = logging.getLogger(__name__)
router = APIRouter(tags=["geocode"])


@router.post("/api/geocode", response_model=GeocodeResponse)
async def geocode_endpoint(request: GeocodeRequest) -> GeocodeResponse:
    """
    Convert an address string to geographic coordinates using Amap Geocode API.

    Proxy endpoint that keeps the AMAP_KEY on the server side.
    Frontend calls this instead of calling Amap directly.

    Args:
        request: GeocodeRequest with address and optional city

    Returns:
        GeocodeResponse with list of GeocodeResult
    """
    settings = get_settings()

    if not settings.amap_key:
        logger.warning("AMAP_KEY not configured, geocode unavailable")
        return GeocodeResponse(
            success=False,
            error_message="Amap API key not configured on server",
        )

    try:
        from data_sources.amap_client import AmapClient

        client = AmapClient(api_key=settings.amap_key)
        geocodes = client.geocode(address=request.address, city=request.city)

        results = []
        for gc in geocodes:
            location_str = gc.get("location", "0,0")
            lon_str, lat_str = location_str.split(",", 1) if "," in location_str else ("0", "0")
            results.append(
                GeocodeResult(
                    name=gc.get("name", request.address),
                    address=gc.get("formatted_address", gc.get("address", request.address)),
                    location=location_str,
                    longitude=float(lon_str),
                    latitude=float(lat_str),
                )
            )

        logger.info("Geocode: address=%s city=%s → %d results", request.address, request.city, len(results))
        return GeocodeResponse(success=True, results=results)

    except Exception as e:
        logger.error("Geocode failed: address=%s error=%s", request.address, e)
        return GeocodeResponse(
            success=False,
            error_message=str(e),
        )
