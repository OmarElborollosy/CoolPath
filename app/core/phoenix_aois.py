"""Phoenix, Arizona Areas of Interest (AOIs) and microclimate baseline metrics.

Locked date for simulation: 2026-08-03 (Peak extreme Arizona heat window).
Locked AOIs:
  1. Downtown Phoenix (dense_urban_core)
  2. Arcadia Residential Grid (suburban_residential)
  3. Encanto Park Shaded Refuge (park_shaded_refuge)
  4. Van Buren Industrial Corridor (exposed_industrial)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.schemas.common import BoundingBox, Coordinates, PolygonAOI

logger = logging.getLogger("coolpath.aoi")

# ---------------------------------------------------------------------------
# Central JSON Fixture Loading with Resilient In-Memory Fallback
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "phoenix_aois.json"


def _build_square_polygon(center_lat: float, center_lng: float, delta_deg: float = 0.005) -> dict:
    """Create a standard GeoJSON Polygon FeatureCollection box around center coordinates."""
    min_lat = center_lat - delta_deg
    max_lat = center_lat + delta_deg
    min_lng = center_lng - delta_deg
    max_lng = center_lng + delta_deg
    return {
        "type": "FeatureCollection",
        "features": [
          {
            "type": "Feature",
            "properties": {},
            "geometry": {
              "type": "Polygon",
              "coordinates": [
                [
                  [min_lng, min_lat],
                  [max_lng, min_lat],
                  [max_lng, max_lat],
                  [min_lng, max_lat],
                  [min_lng, min_lat],
                ]
              ],
            },
          }
        ],
    }


def _load_aois_and_baselines() -> tuple[dict[str, PolygonAOI], dict[str, dict[str, Any]]]:
    """Load 4 Phoenix AOIs and baseline metrics from JSON fixture or fallback."""
    if FIXTURE_PATH.is_file():
        try:
            with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            aois: dict[str, PolygonAOI] = {}
            for aoi_id, aoi_data in data.get("aois", {}).items():
                aois[aoi_id] = PolygonAOI.model_validate(aoi_data)
            baselines: dict[str, dict[str, Any]] = data.get("baselines", {})
            if len(aois) == 4 and len(baselines) == 4:
                return aois, baselines
        except Exception as exc:
            logger.warning("Failed to load phoenix_aois.json fixture (%s); using in-code baselines.", exc)

    # In-memory hardcoded fallback
    fallback_aois = {
        "downtown_phoenix": PolygonAOI(
            aoi_id="downtown_phoenix",
            name="Downtown Phoenix",
            aoi_type="dense_urban_core",
            center=Coordinates(lat=33.4484, lng=-112.0740),
            bbox=BoundingBox(min_lat=33.4434, max_lat=33.4534, min_lng=-112.0790, max_lng=-112.0690),
            geojson=_build_square_polygon(33.4484, -112.0740, 0.005),
            description="Classic urban heat island: tall commercial buildings, low tree canopy, high restaurant & delivery density.",
        ),
        "arcadia_residential": PolygonAOI(
            aoi_id="arcadia_residential",
            name="Arcadia Residential Grid",
            aoi_type="suburban_residential",
            center=Coordinates(lat=33.4580, lng=-112.0300),
            bbox=BoundingBox(min_lat=33.4530, max_lat=33.4630, min_lng=-112.0350, max_lng=-112.0250),
            geojson=_build_square_polygon(33.4580, -112.0300, 0.005),
            description="Single-family residential neighborhood with wide exposed asphalt streets and moderate tree coverage.",
        ),
        "encanto_park": PolygonAOI(
            aoi_id="encanto_park",
            name="Encanto Park Shaded Refuge",
            aoi_type="park_shaded_refuge",
            center=Coordinates(lat=33.4270, lng=-112.0870),
            bbox=BoundingBox(min_lat=33.4220, max_lat=33.4320, min_lng=-112.0920, max_lng=-112.0820),
            geojson=_build_square_polygon(33.4270, -112.0870, 0.005),
            description="Key shaded urban park refuge: mature tree canopy (48%), lagoon water cooling effect, and shaded ramadas.",
        ),
        "van_buren_corridor": PolygonAOI(
            aoi_id="van_buren_corridor",
            name="Van Buren Industrial Corridor",
            aoi_type="exposed_industrial",
            center=Coordinates(lat=33.4480, lng=-112.0450),
            bbox=BoundingBox(min_lat=33.4430, max_lat=33.4530, min_lng=-112.0500, max_lng=-112.0400),
            geojson=_build_square_polygon(33.4480, -112.0450, 0.005),
            description="Worst-case heat zone: vast unshaded asphalt parking, industrial roofs, 0% tree canopy, intense persistence.",
        ),
    }

    fallback_baselines = {
        "downtown_phoenix": {
            "surface_temp_c": 42.8,
            "heat_index_c": 44.5,
            "apparent_temp_c": 43.1,
            "wet_bulb_c": 22.4,
            "humidity_pct": 21.0,
            "persistence_hours": 6.5,
            "exceedance_hours": 8.0,
            "canopy_percentage": 9.5,
            "street_shade_percentage": 24.0,
            "solar_ghi": 880.0,
            "aqi": 62.0,
        },
        "arcadia_residential": {
            "surface_temp_c": 39.5,
            "heat_index_c": 40.8,
            "apparent_temp_c": 39.8,
            "wet_bulb_c": 21.0,
            "humidity_pct": 22.0,
            "persistence_hours": 4.5,
            "exceedance_hours": 6.0,
            "canopy_percentage": 18.0,
            "street_shade_percentage": 16.0,
            "solar_ghi": 870.0,
            "aqi": 52.0,
        },
        "encanto_park": {
            "surface_temp_c": 33.4,
            "heat_index_c": 34.2,
            "apparent_temp_c": 33.0,
            "wet_bulb_c": 19.5,
            "humidity_pct": 28.0,
            "persistence_hours": 1.0,
            "exceedance_hours": 2.0,
            "canopy_percentage": 48.5,
            "street_shade_percentage": 58.0,
            "solar_ghi": 720.0,
            "aqi": 42.0,
        },
        "van_buren_corridor": {
            "surface_temp_c": 46.2,
            "heat_index_c": 48.9,
            "apparent_temp_c": 47.5,
            "wet_bulb_c": 23.8,
            "humidity_pct": 19.0,
            "persistence_hours": 9.5,
            "exceedance_hours": 11.5,
            "canopy_percentage": 1.2,
            "street_shade_percentage": 4.0,
            "solar_ghi": 920.0,
            "aqi": 78.0,
        },
    }

    return fallback_aois, fallback_baselines


PHOENIX_AOIS, AOI_BASELINE_METRICS = _load_aois_and_baselines()


def get_aoi_for_coordinate(coord: Coordinates) -> PolygonAOI | None:
    """Find which Phoenix AOI bounding box contains the coordinate."""
    for aoi in PHOENIX_AOIS.values():
        if aoi.bbox.contains(coord):
            return aoi
    return None


def get_aoi_by_id(aoi_id: str) -> PolygonAOI | None:
    """Lookup an AOI by its unique ID."""
    return PHOENIX_AOIS.get(aoi_id)


def get_all_aois() -> dict[str, PolygonAOI]:
    """Return all configured Phoenix AOIs."""
    return PHOENIX_AOIS


def get_aoi_baseline(aoi_id: str) -> dict[str, Any] | None:
    """Return baseline microclimate metrics for the given AOI ID."""
    return AOI_BASELINE_METRICS.get(aoi_id)


__all__ = [
    "PHOENIX_AOIS",
    "AOI_BASELINE_METRICS",
    "get_aoi_for_coordinate",
    "get_aoi_by_id",
    "get_all_aois",
    "get_aoi_baseline",
]
