"""Common geographical and coordinate schema definitions."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """WGS84 GPS coordinate pair."""
    lat: float
    lng: float

    def to_tuple(self) -> tuple[float, float]:
        return (self.lat, self.lng)

    def to_geojson_coord(self) -> list[float]:
        """GeoJSON format is [longitude, latitude]."""
        return [self.lng, self.lat]


class BoundingBox(BaseModel):
    """Lat/Lng bounding box."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def contains(self, coord: Coordinates) -> bool:
        return (
            self.min_lat <= coord.lat <= self.max_lat
            and self.min_lng <= coord.lng <= self.max_lng
        )


class PolygonAOI(BaseModel):
    """Area of Interest polygon definition."""
    aoi_id: str
    name: str
    aoi_type: str
    center: Coordinates
    bbox: BoundingBox
    geojson: dict[str, Any]
    description: str = ""
