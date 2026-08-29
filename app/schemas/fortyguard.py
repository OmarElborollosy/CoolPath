"""FortyGuard API data schemas and response representations."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from .common import Coordinates


class TaskPollingStatus(BaseModel):
    """Status metadata for an asynchronous FortyGuard task."""
    activity_id: str
    status: str = Field(description="pending, processing, succeeded, failed, error, not_ready, timeout")
    progress_pct: float = 0.0
    message: str = ""
    result: dict[str, Any] | None = None
    elapsed_seconds: float = 0.0


class HeatmapTile(BaseModel):
    """A single spatial tile from a FortyGuard heatmap."""
    tile_id: str
    temperature_c: float = Field(description="Tile temperature in Celsius")
    min_temperature_c: float | None = None
    max_temperature_c: float | None = None
    average_temperature_c: float | None = None
    exceedance_hours: float | None = Field(default=None, description="Hours past threshold")
    persistence_hours: float | None = Field(default=None, description="Longest continuous streak in hours")
    geometry_polygon: list[list[float]] = Field(default_factory=list, description="GeoJSON coordinates [lng, lat]")
    centroid: Coordinates | None = None


class HeatmapStats(BaseModel):
    """Aggregate statistics for an AOI heatmap."""
    min_c: float = 0.0
    max_c: float = 0.0
    mean_c: float = 0.0
    std_c: float = 0.0
    tile_count: int = 0
    temperature_distribution: list[float] = Field(default_factory=list)


class HeatmapResult(BaseModel):
    """Parsed result of POST /v1/heatmap."""
    activity_id: str
    aoi_id: str
    analytic_type: str = "tcm"
    date: str
    hour: str | None = None
    granularity: int = 100
    stats: HeatmapStats = Field(default_factory=HeatmapStats)
    tiles: list[HeatmapTile] = Field(default_factory=list)
    raw_geojson: dict[str, Any] = Field(default_factory=dict)
    is_synthesized: bool = Field(
        default=False,
        description="True when values come from AOI_BASELINE_METRICS fallback, not a live API call.",
    )


class EnvParamsResult(BaseModel):
    """Result of POST /v1/env_params for a specific point."""
    activity_id: str
    coordinate: Coordinates
    temperature_anchor_c: float
    heat_index_c: float
    apparent_temperature_c: float
    wet_bulb_temperature_c: float
    relative_humidity_pct: float
    solar_irradiance_ghi: float = Field(default=850.0, description="Global Horizontal Irradiance (W/m2)")
    solar_irradiance_dni: float = Field(default=750.0, description="Direct Normal Irradiance (W/m2)")
    solar_irradiance_dhi: float = Field(default=100.0, description="Diffuse Horizontal Irradiance (W/m2)")
    aqi_idx: float = Field(default=55.0, description="Overall Air Quality Index")
    aqi_pm25: float | None = None
    aqi_o3: float | None = None
    cloud_cover_octas: float = 0.0
    timestamps: list[str] = Field(default_factory=list)
    is_synthesized: bool = Field(
        default=False,
        description="True when values come from AOI_BASELINE_METRICS fallback, not a live API call.",
    )


class SatelliteSegmentationResult(BaseModel):
    """Land-cover composition from POST /v1/satellite."""
    coordinate: Coordinates
    canopy_percentage: float = Field(description="Tree and tall vegetation canopy 0-100%")
    vegetation_percentage: float = Field(description="Low grass / shrubs 0-100%")
    impervious_percentage: float = Field(description="Asphalt, concrete, roofing 0-100%")
    water_percentage: float = Field(default=0.0)
    bare_soil_percentage: float = Field(default=0.0)
    is_synthesized: bool = Field(
        default=False,
        description="True when values come from AOI_BASELINE_METRICS fallback, not a live API call.",
    )


class StreetViewSegmentationResult(BaseModel):
    """Ground-level street view shade from POST /v1/streetview."""
    coordinate: Coordinates
    street_shade_percentage: float = Field(description="Ground-level vertical shade 0-100%")
    sky_view_factor: float = Field(default=0.6, description="Sky openness 0-1")
    building_obstruction_pct: float = Field(default=20.0)
    tree_obstruction_pct: float = Field(default=15.0)
    is_synthesized: bool = Field(
        default=False,
        description="True when values come from AOI_BASELINE_METRICS fallback, not a live API call.",
    )


__all__ = [
    "TaskPollingStatus",
    "HeatmapTile",
    "HeatmapStats",
    "HeatmapResult",
    "EnvParamsResult",
    "SatelliteSegmentationResult",
    "StreetViewSegmentationResult",
]
