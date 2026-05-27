"""
Route calculation service.
"""
from app.schemas import Point, RouteCalculateResponse, RouteSegment
from app.services.distance import get_travel_speed, haversine_distance_meters


def calculate_route(
    points: list[Point],
    travel_mode: str = "walking",
) -> RouteCalculateResponse:
    """
    Calculate route distance and time for given points.

    Args:
        points: List of points to route through
        travel_mode: Mode of travel ('walking', 'bicycling', 'driving')

    Returns:
        RouteCalculateResponse with distance, duration, polyline, and segments
    """
    if len(points) < 2:
        raise ValueError("At least 2 points are required")

    total_distance = 0
    segments: list[RouteSegment] = []
    speed = get_travel_speed(travel_mode)

    # Calculate distance between consecutive points
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]

        distance = haversine_distance_meters(p1.longitude, p1.latitude, p2.longitude, p2.latitude)
        total_distance += distance

        # Calculate duration for this segment
        duration_minutes = distance / speed

        segment = RouteSegment(
            from_name=p1.name,
            to_name=p2.name,
            distance_meters=int(round(distance)),
            duration_minutes=round(duration_minutes, 1),
        )
        segments.append(segment)

    # Calculate total duration
    total_duration_minutes = total_distance / speed

    # Build polyline as list of [lon, lat] pairs
    polyline = [[p.longitude, p.latitude] for p in points]

    return RouteCalculateResponse(
        distance_meters=int(round(total_distance)),
        duration_minutes=round(total_duration_minutes, 1),
        polyline=polyline,
        segments=segments,
    )
