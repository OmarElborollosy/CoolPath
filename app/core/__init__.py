"""Core formulas, spatial geometry, and Phoenix AOIs."""
from .formulas import (
    clamp,
    compute_norm_heat_index,
    compute_norm_persistence,
    compute_norm_solar,
    compute_norm_aqi,
    compute_thermal_risk_score,
    compute_refuge_score,
)
from .spatial import (
    haversine_distance_km,
    coord_distance_km,
    point_in_polygon,
    interpolate_coordinates,
    sample_polyline_corridor,
)
from .phoenix_aois import (
    PHOENIX_AOIS,
    AOI_BASELINE_METRICS,
    get_aoi_for_coordinate,
)

__all__ = [
    "clamp",
    "compute_norm_heat_index",
    "compute_norm_persistence",
    "compute_norm_solar",
    "compute_norm_aqi",
    "compute_thermal_risk_score",
    "compute_refuge_score",
    "haversine_distance_km",
    "coord_distance_km",
    "point_in_polygon",
    "interpolate_coordinates",
    "sample_polyline_corridor",
    "PHOENIX_AOIS",
    "AOI_BASELINE_METRICS",
    "get_aoi_for_coordinate",
]
