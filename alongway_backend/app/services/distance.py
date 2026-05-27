"""
Haversine distance calculation and travel time estimation.
"""
import math

# Speed in meters per minute by travel mode
TRAVEL_SPEEDS: dict[str, float] = {
    "walking": 80,
    "bicycling": 200,
    "driving": 500,
}


def haversine_distance_meters(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> float:
    """
    Calculate great-circle distance between two points using the Haversine formula.

    Args:
        lon1: Longitude of first point
        lat1: Latitude of first point
        lon2: Longitude of second point
        lat2: Latitude of second point

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return distance


def get_travel_speed(travel_mode: str) -> float:
    """
    Get speed in meters per minute based on travel mode.

    Args:
        travel_mode: 'walking', 'bicycling', or 'driving'

    Returns:
        Speed in meters per minute
    """
    return TRAVEL_SPEEDS.get(travel_mode, 80)
