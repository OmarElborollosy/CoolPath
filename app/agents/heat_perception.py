"""Agent 1: Heat Perception Agent.

Responsible for:
1. Fast-path sub-10ms spatial point-in-tile lookup against FortyGuard pre-warmed cache.
2. Ingesting surface temperature, FortyGuard persistence hours, exceedance hours, Heat Index, and solar irradiance.
3. Quantifying baseline canopy and street shade for the rider's immediate location.
"""
from __future__ import annotations

import logging
from app.core.phoenix_aois import AOI_BASELINE_METRICS, PHOENIX_AOIS, get_aoi_for_coordinate
from app.core.spatial import haversine_distance_km, point_in_polygon
from app.schemas.assessments import HeatPerceptionAssessment
from app.schemas.common import Coordinates
from app.schemas.fleet import RiderTelemetry
from app.services.heat_service import HeatService, get_global_heat_service

logger = logging.getLogger("coolpath.agents.heat_perception")


class HeatPerceptionAgent:
    """Specialist agent extracting microclimate exposure metrics for an active rider."""

    def __init__(self, heat_service: HeatService | None = None) -> None:
        self.heat_service = heat_service or get_global_heat_service()

    async def run(self, telemetry: RiderTelemetry, allow_live: bool = False) -> HeatPerceptionAssessment:
        """Evaluate microclimate heat metrics for the rider's current coordinate."""
        coord = telemetry.coordinate
        aoi = get_aoi_for_coordinate(coord)

        if not aoi:
            # Out-of-bounds short circuit
            return HeatPerceptionAssessment(
                rider_id=telemetry.rider_id,
                coordinate=coord,
                tile_temperature_c=0.0,
                heat_index_c=0.0,
                apparent_temperature_c=0.0,
                wet_bulb_c=0.0,
                relative_humidity_pct=0.0,
                solar_irradiance_ghi=0.0,
                aqi=0.0,
                status="expanding_coverage_please_wait",
            )

        aoi_id = aoi.aoi_id

        # Fast-path cache reads / FortyGuard query:
        # 1. Fetch thermal heatmap tiles (snapshot, persistence, exceedance)
        heatmap = self.heat_service.fetch_aoi_heatmap(aoi_id, analytic_type="tcm", allow_live=allow_live)
        persistence_map = self.heat_service.fetch_aoi_heatmap(aoi_id, analytic_type="persistence", allow_live=allow_live)
        exceedance_map = self.heat_service.fetch_aoi_heatmap(aoi_id, analytic_type="exceedance", allow_live=allow_live)

        # 2. Spatial Point-in-Tile matching
        matched_tile_id = None
        matched_temp = heatmap.stats.mean_c
        matched_persistence = persistence_map.stats.mean_c
        matched_exceedance = exceedance_map.stats.mean_c

        # Primary: Exact polygon geometry inclusion
        for tile in heatmap.tiles:
            if tile.geometry_polygon and point_in_polygon(coord.lat, coord.lng, tile.geometry_polygon):
                matched_tile_id = tile.tile_id
                matched_temp = tile.temperature_c
                break

        # Secondary: Nearest centroid fallback if boundary edge case
        if not matched_tile_id and heatmap.tiles:
            min_dist = float("inf")
            best_tile = None
            for tile in heatmap.tiles:
                if tile.centroid:
                    dist = haversine_distance_km(coord.lat, coord.lng, tile.centroid.lat, tile.centroid.lng)
                    if dist < min_dist:
                        min_dist = dist
                        best_tile = tile
            if best_tile:
                matched_tile_id = best_tile.tile_id
                matched_temp = best_tile.temperature_c

        # Match persistence & exceedance metrics for the matched tile ID
        if matched_tile_id:
            for pt in persistence_map.tiles:
                if pt.tile_id == matched_tile_id and pt.persistence_hours is not None:
                    matched_persistence = pt.persistence_hours
                    break
            for et in exceedance_map.tiles:
                if et.tile_id == matched_tile_id and et.exceedance_hours is not None:
                    matched_exceedance = et.exceedance_hours
                    break

        # Snap to nearest pre-warmed Anchor Tile if available
        anchor_lookup = self.heat_service.cache.get(f"anchor_lookup:{aoi_id}") or {}
        anchor_coord_dict = anchor_lookup.get(matched_tile_id)
        if anchor_coord_dict:
            snapped_coord = Coordinates(lat=anchor_coord_dict["lat"], lng=anchor_coord_dict["lng"])
            spatial_resolution = "anchor_centroid_snapped"
        else:
            snapped_coord = coord
            spatial_resolution = "exact_coordinate"

        # 3. Point Environmental Parameters
        env_params = self.heat_service.fetch_env_params(
            snapped_coord,
            temperature_anchor_c=matched_temp,
            allow_live=allow_live,
        )

        # 4. Satellite & Street View Segmentation
        sat_seg = self.heat_service.fetch_satellite_segmentation(snapped_coord, allow_live=allow_live)
        sv_seg = self.heat_service.fetch_streetview_segmentation(snapped_coord, allow_live=allow_live)

        assessment = HeatPerceptionAssessment(
            rider_id=telemetry.rider_id,
            coordinate=coord,
            matched_tile_id=matched_tile_id,
            tile_temperature_c=round(matched_temp, 1),
            heat_index_c=round(env_params.heat_index_c, 1),
            apparent_temperature_c=round(env_params.apparent_temperature_c, 1),
            wet_bulb_c=round(env_params.wet_bulb_temperature_c, 1),
            relative_humidity_pct=round(env_params.relative_humidity_pct, 1),
            solar_irradiance_ghi=round(env_params.solar_irradiance_ghi, 1),
            aqi=round(env_params.aqi_idx, 1),
            persistence_hours=round(matched_persistence, 1),
            exceedance_hours=round(matched_exceedance, 1),
            canopy_percentage=round(sat_seg.canopy_percentage, 1),
            street_shade_percentage=round(sv_seg.street_shade_percentage, 1),
            source="fast_path_cache",
            confidence=1.0,
            is_synthesized=env_params.is_synthesized or sat_seg.is_synthesized or sv_seg.is_synthesized,
            data_source_summary={
                "env_params": "synthesized_baseline" if env_params.is_synthesized else "live_fortyguard_api",
                "satellite_segmentation": "synthesized_baseline" if sat_seg.is_synthesized else "live_fortyguard_api",
                "streetview_segmentation": "synthesized_baseline" if sv_seg.is_synthesized else "live_fortyguard_api",
                "heatmap_tiles": "synthesized_baseline" if matched_tile_id is None else "live_fortyguard_api",
            },
            spatial_resolution=spatial_resolution,
            status="success",
        )
        return assessment


__all__ = ["HeatPerceptionAgent"]
