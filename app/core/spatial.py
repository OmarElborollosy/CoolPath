"""Spatial utilities, geodesic distance, point-in-polygon, and polyline sampling."""
from __future__ import annotations

import math
from typing import Sequence
from app.schemas.common import Coordinates


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in kilometres between two WGS84 points.
    
    Pure Python Haversine formula (matches WalkFit reference).
    """
    R = 6371.0088  # Mean Earth radius in km (IUGG)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


def coord_distance_km(c1: Coordinates, c2: Coordinates) -> float:
    """Distance between two Coordinates objects in km."""
    return haversine_distance_km(c1.lat, c1.lng, c2.lat, c2.lng)


def point_in_polygon(lat: float, lng: float, polygon_coords: Sequence[Sequence[float]]) -> bool:
    """Ray-casting algorithm to test whether (lat, lng) is inside a polygon.
    
    polygon_coords is expected to be a list of [lng, lat] or (lng, lat) pairs.
    """
    num_points = len(polygon_coords)
    if num_points < 3:
        return False

    inside = False
    j = num_points - 1

    for i in range(num_points):
        xi, yi = polygon_coords[i][0], polygon_coords[i][1]  # lng, lat
        xj, yj = polygon_coords[j][0], polygon_coords[j][1]

        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i

    return inside


def interpolate_coordinates(start: Coordinates, end: Coordinates, fraction: float) -> Coordinates:
    """Linear interpolation between two coordinates."""
    frac = max(0.0, min(1.0, fraction))
    return Coordinates(
        lat=round(start.lat + (end.lat - start.lat) * frac, 6),
        lng=round(start.lng + (end.lng - start.lng) * frac, 6),
    )


def sample_polyline_corridor(
    waypoints: Sequence[Coordinates],
    interval_meters: float = 175.0,
) -> list[Coordinates]:
    """Sample equidistant points s_1, s_2, ..., s_k along a polyline.
    
    Ensures candidate route evaluation is sampled along the entire physical corridor
    (every ~150-200m) rather than only taking the destination centroid.
    """
    if not waypoints:
        return []
    if len(waypoints) == 1:
        return [waypoints[0]]

    interval_km = interval_meters / 1000.0
    samples: list[Coordinates] = [waypoints[0]]
    accumulated_remainder = 0.0

    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        segment_dist = coord_distance_km(p1, p2)

        if segment_dist <= 1e-6:
            continue

        distance_along = interval_km - accumulated_remainder
        while distance_along <= segment_dist:
            fraction = distance_along / segment_dist
            samples.append(interpolate_coordinates(p1, p2, fraction))
            distance_along += interval_km

        accumulated_remainder = segment_dist - (distance_along - interval_km)

    if coord_distance_km(samples[-1], waypoints[-1]) > (interval_km * 0.5):
        samples.append(waypoints[-1])

    return samples
