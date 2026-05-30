"""
Amap route service — thin wrapper re-exporting from route_service.py.
route_service.py is the canonical implementation with AmapRouteClient.
"""
# Re-export from the canonical route_service module
from app.services.route_service import (  # noqa: F401
    AmapRouteClient,
    AmapRouteError,
    append_polyline,
    calculate_route,
    format_location,
    is_success_payload,
    parse_amap_route_payload,
)
