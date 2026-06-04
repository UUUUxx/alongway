"""
Geocode proxy endpoint — avoids exposing AMAP_KEY to frontend.
"""
import logging

import httpx
from fastapi import APIRouter

from app.config import get_settings
from app.schemas import GeocodeRequest, GeocodeResponse, GeocodeResult
from app.services.call_logger import log_call

logger = logging.getLogger(__name__)
router = APIRouter(tags=["geocode"])


LOCAL_GEOCODE_FALLBACKS = {
    "汉口火车站": GeocodeResult(
        name="汉口火车站",
        address="武汉市江汉区发展大道185号",
        location="114.2540,30.6180",
        longitude=114.2540,
        latitude=30.6180,
    ),
    "武汉大学": GeocodeResult(
        name="武汉大学",
        address="武汉市武昌区八一路299号",
        location="114.3645,30.5378",
        longitude=114.3645,
        latitude=30.5378,
    ),
    "武大": GeocodeResult(
        name="武汉大学",
        address="武汉市武昌区八一路299号",
        location="114.3645,30.5378",
        longitude=114.3645,
        latitude=30.5378,
    ),
    "华中科技大学": GeocodeResult(
        name="华中科技大学",
        address="武汉市洪山区珞喻路1037号",
        location="114.4148,30.5159",
        longitude=114.4148,
        latitude=30.5159,
    ),
    "华科": GeocodeResult(
        name="华中科技大学",
        address="武汉市洪山区珞喻路1037号",
        location="114.4148,30.5159",
        longitude=114.4148,
        latitude=30.5159,
    ),
    "光谷": GeocodeResult(
        name="光谷",
        address="武汉市洪山区光谷广场",
        location="114.402994,30.505446",
        longitude=114.402994,
        latitude=30.505446,
    ),
    "光谷广场": GeocodeResult(
        name="光谷广场",
        address="武汉市洪山区光谷广场",
        location="114.402994,30.505446",
        longitude=114.402994,
        latitude=30.505446,
    ),
    "世界城广场": GeocodeResult(
        name="世界城广场",
        address="武汉市洪山区珞喻路766号",
        location="114.4036,30.5068",
        longitude=114.4036,
        latitude=30.5068,
    ),
    "世界城": GeocodeResult(
        name="世界城广场",
        address="武汉市洪山区珞喻路766号",
        location="114.4036,30.5068",
        longitude=114.4036,
        latitude=30.5068,
    ),
    "江汉路": GeocodeResult(
        name="江汉路",
        address="武汉市江汉区江汉路步行街",
        location="114.2830,30.5820",
        longitude=114.2830,
        latitude=30.5820,
    ),
    "江汉路步行街": GeocodeResult(
        name="江汉路步行街",
        address="武汉市江汉区江汉路步行街",
        location="114.2830,30.5820",
        longitude=114.2830,
        latitude=30.5820,
    ),
    "主图书馆": GeocodeResult(
        name="主图书馆",
        address="华中科技大学主图书馆",
        location="114.4143,30.5126",
        longitude=114.4143,
        latitude=30.5126,
    ),
    "图书馆": GeocodeResult(
        name="主图书馆",
        address="华中科技大学主图书馆",
        location="114.4143,30.5126",
        longitude=114.4143,
        latitude=30.5126,
    ),
    "韵苑宿舍": GeocodeResult(
        name="韵苑宿舍",
        address="华中科技大学韵苑学生公寓",
        location="114.4148,30.5159",
        longitude=114.4148,
        latitude=30.5159,
    ),
    "光谷步行街": GeocodeResult(
        name="光谷步行街",
        address="武汉市洪山区光谷步行街",
        location="114.4013,30.5058",
        longitude=114.4013,
        latitude=30.5058,
    ),
    "群光广场": GeocodeResult(
        name="群光广场",
        address="武汉市洪山区珞喻路6号",
        location="114.3578,30.5262",
        longitude=114.3578,
        latitude=30.5262,
    ),
    "华中师范大学": GeocodeResult(
        name="华中师范大学",
        address="武汉市洪山区珞喻路152号",
        location="114.3650,30.5213",
        longitude=114.3650,
        latitude=30.5213,
    ),
    "华师": GeocodeResult(
        name="华中师范大学",
        address="武汉市洪山区珞喻路152号",
        location="114.3650,30.5213",
        longitude=114.3650,
        latitude=30.5213,
    ),
    "远洋世界": GeocodeResult(
        name="远洋世界",
        address="武汉市洪山区华中科技大学东侧",
        location="114.4280,30.5185",
        longitude=114.4280,
        latitude=30.5185,
    ),
}


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
    local_results = _local_geocode(request.address)
    if local_results and _should_use_local_immediately(request.address):
        logger.info(
            "Geocode local fallback: address=%s city=%s -> %d results",
            request.address,
            request.city,
            len(local_results),
        )
        result = GeocodeResponse(success=True, results=local_results)
        log_call("backend.geocode.result", request=request, result=result)
        return result

    if not settings.amap_key:
        logger.warning("AMAP_KEY not configured, geocode unavailable")
        result = GeocodeResponse(success=False, error_message="Amap API key not configured on server")
        log_call("backend.geocode.result", request=request, result=result)
        return result

    try:
        async with httpx.AsyncClient(timeout=settings.amap_timeout_seconds) as client:
            response = await client.get(
                f"{settings.amap_base_url}/v3/geocode/geo",
                params={
                    "key": settings.amap_key,
                    "address": request.address,
                    "city": request.city,
                    "output": "JSON",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if payload.get("status") != "1":
            info = payload.get("info") or "Amap geocode failed"
            infocode = payload.get("infocode")
            detail = f"{info} ({infocode})" if infocode else info
            result = GeocodeResponse(success=False, error_message=detail)
            log_call("backend.geocode.result", request=request, result=result)
            return result

        results = []
        for gc in payload.get("geocodes", []):
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
        result = GeocodeResponse(success=True, results=results)
        log_call("backend.geocode.result", request=request, result=result)
        return result

    except (httpx.HTTPError, ValueError) as e:
        logger.error("Geocode failed: address=%s error=%s", request.address, e)
        result = GeocodeResponse(
            success=False,
            error_message=str(e),
        )
        log_call("backend.geocode.result", request=request, result=result, error=str(e))
        return result


def _local_geocode(address: str) -> list[GeocodeResult]:
    text = address.strip()
    results = []
    for key, value in LOCAL_GEOCODE_FALLBACKS.items():
        if key in text or text in key:
            results.append(value)
    return results[:3]


def _should_use_local_immediately(address: str) -> bool:
    text = address.strip()
    fast_aliases = {
        "汉口火车站",
        "武汉大学",
        "武大",
        "华中科技大学",
        "华科",
        "光谷",
        "光谷广场",
        "光谷步行街",
        "世界城广场",
        "世界城",
        "江汉路",
        "江汉路步行街",
        "群光广场",
        "华中师范大学",
        "华师",
        "远洋世界",
    }
    return text in fast_aliases
