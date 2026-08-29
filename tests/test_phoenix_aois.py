"""Tests for Phoenix AOIs central configuration, fixture loading, and spatial bounding boxes."""
import pytest
from app.core.phoenix_aois import (
    PHOENIX_AOIS,
    AOI_BASELINE_METRICS,
    get_aoi_for_coordinate,
    get_aoi_by_id,
    get_all_aois,
    get_aoi_baseline,
)
from app.schemas.common import Coordinates


def test_locked_4_phoenix_aois_present():
    """Verify exactly the 4 locked Phoenix AOIs exist with correct IDs."""
    expected_ids = {
        "downtown_phoenix",
        "arcadia_residential",
        "encanto_park",
        "van_buren_corridor",
    }
    assert set(PHOENIX_AOIS.keys()) == expected_ids
    assert set(get_all_aois().keys()) == expected_ids


def test_aoi_properties_and_geojson():
    """Verify each AOI has valid centroid, bounding box, and GeoJSON Polygon structure."""
    for aoi_id, aoi in PHOENIX_AOIS.items():
        assert aoi.aoi_id == aoi_id
        assert aoi.name
        assert aoi.aoi_type in (
            "dense_urban_core",
            "suburban_residential",
            "park_shaded_refuge",
            "exposed_industrial",
        )
        assert aoi.center.lat > 33.0 and aoi.center.lat < 34.0
        assert aoi.center.lng > -113.0 and aoi.center.lng < -111.0

        # Verify bbox bounds center
        assert aoi.bbox.min_lat <= aoi.center.lat <= aoi.bbox.max_lat
        assert aoi.bbox.min_lng <= aoi.center.lng <= aoi.bbox.max_lng

        # Verify GeoJSON polygon format
        geojson = aoi.geojson
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 1
        feature = geojson["features"][0]
        assert feature["geometry"]["type"] == "Polygon"
        coords = feature["geometry"]["coordinates"][0]
        assert len(coords) >= 4
        # First and last coordinate must close polygon
        assert coords[0] == coords[-1]


def test_aoi_baseline_metrics_coverage():
    """Verify baseline microclimate ground-truth values for all 4 AOIs."""
    for aoi_id in PHOENIX_AOIS:
        base = get_aoi_baseline(aoi_id)
        assert base is not None
        assert "surface_temp_c" in base
        assert "heat_index_c" in base
        assert "apparent_temp_c" in base
        assert "wet_bulb_c" in base
        assert "humidity_pct" in base
        assert "persistence_hours" in base
        assert "exceedance_hours" in base
        assert "canopy_percentage" in base
        assert "street_shade_percentage" in base
        assert "solar_ghi" in base
        assert "aqi" in base

    # Check key relative truths
    # Van Buren Corridor is hottest / most exposed
    assert AOI_BASELINE_METRICS["van_buren_corridor"]["surface_temp_c"] > AOI_BASELINE_METRICS["downtown_phoenix"]["surface_temp_c"]
    assert AOI_BASELINE_METRICS["van_buren_corridor"]["canopy_percentage"] < 3.0

    # Encanto park is coolest / highest canopy
    assert AOI_BASELINE_METRICS["encanto_park"]["surface_temp_c"] < AOI_BASELINE_METRICS["downtown_phoenix"]["surface_temp_c"]
    assert AOI_BASELINE_METRICS["encanto_park"]["canopy_percentage"] > 40.0


def test_get_aoi_for_coordinate_containment():
    """Verify coordinate lookup returns the containing AOI."""
    # Downtown center
    dt_coord = Coordinates(lat=33.4484, lng=-112.0740)
    aoi = get_aoi_for_coordinate(dt_coord)
    assert aoi is not None
    assert aoi.aoi_id == "downtown_phoenix"

    # Encanto center
    encanto_coord = Coordinates(lat=33.4270, lng=-112.0870)
    aoi = get_aoi_for_coordinate(encanto_coord)
    assert aoi is not None
    assert aoi.aoi_id == "encanto_park"

    # Out of bounds point (e.g. Flagstaff, AZ)
    flagstaff = Coordinates(lat=35.1983, lng=-111.6513)
    assert get_aoi_for_coordinate(flagstaff) is None


def test_get_aoi_by_id():
    """Verify lookup by ID helper."""
    aoi = get_aoi_by_id("arcadia_residential")
    assert aoi is not None
    assert aoi.name == "Arcadia Residential Grid"

    assert get_aoi_by_id("non_existent_aoi") is None
