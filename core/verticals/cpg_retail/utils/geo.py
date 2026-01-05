"""
Geospatial utilities for CPG Field Sales.

NO dependencies on PostGIS or external libs. Pure Python.
"""

import math
from typing import Optional, Dict, Any


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two GPS coordinates using Haversine formula.

    Args:
        lat1, lon1: First coordinate (visit location)
        lat2, lon2: Second coordinate (POS location)

    Returns:
        Distance in meters

    Example:
        >>> calculate_distance(19.4326, -99.1332, 19.4330, -99.1340)
        89.2  # meters
    """
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2) * math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def validate_geofence(
    visit_lat: Optional[float],
    visit_lon: Optional[float],
    pos_lat: Optional[float],
    pos_lon: Optional[float],
    threshold_meters: int = 200
) -> Dict[str, Any]:
    """
    Validate that visit location is within threshold of POS location.

    Args:
        visit_lat, visit_lon: Coordinates from GPS check-in
        pos_lat, pos_lon: Coordinates from POS record
        threshold_meters: Maximum allowed distance (default: 200m)

    Returns:
        Dict with:
            - valid: bool
            - distance_meters: float (if calculable)
            - error: str (if invalid)

    Example:
        >>> validate_geofence(19.4326, -99.1332, 19.4330, -99.1340, threshold_meters=100)
        {"valid": True, "distance_meters": 89.2}
    """
    # Validate inputs
    if not all([visit_lat, visit_lon, pos_lat, pos_lon]):
        return {
            "valid": False,
            "error": "Missing GPS coordinates (visit or POS)"
        }

    # Calculate distance
    try:
        distance = calculate_distance(visit_lat, visit_lon, pos_lat, pos_lon)
    except Exception as e:
        return {
            "valid": False,
            "error": f"Distance calculation failed: {e}"
        }

    # Validate threshold
    if distance > threshold_meters:
        return {
            "valid": False,
            "distance_meters": round(distance, 2),
            "threshold_meters": threshold_meters,
            "error": f"Visit location {distance:.0f}m away from POS (max: {threshold_meters}m)"
        }

    return {
        "valid": True,
        "distance_meters": round(distance, 2)
    }
