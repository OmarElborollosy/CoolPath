import asyncio
import logging
from datetime import datetime, timezone
from app.config import get_settings
from app.core.phoenix_aois import PHOENIX_AOIS
from app.services.fortyguard_service import FortyGuardService
from app.core.spatial import haversine_distance_km

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def run():
    settings = get_settings()
    fg_service = FortyGuardService()
    aoi_id = "van_buren_corridor"
    
    hm = fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="tcm", date=settings.study_date)
    fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="persistence", date=settings.study_date)
    fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="exceedance", date=settings.study_date)
    
    tiles = hm.tiles
    total_tiles = len(tiles)
    step = max(1, total_tiles // 10)
    anchor_tiles = tiles[::step]
    
    for anchor in anchor_tiles:
        if anchor.centroid:
            fg_service.fetch_env_params(
                coord=anchor.centroid,
                temperature_anchor_c=anchor.temperature_c,
                date=settings.study_date
            )
            fg_service.fetch_satellite_segmentation(anchor.centroid, date=settings.study_date)
            fg_service.fetch_streetview_segmentation(anchor.centroid)
            
    lookup_table = {}
    snap_distances = []
    
    for tile in tiles:
        if not tile.centroid:
            continue
        
        min_dist = float('inf')
        best_anchor = None
        for anchor in anchor_tiles:
            if not anchor.centroid:
                continue
            dist = haversine_distance_km(tile.centroid.lat, tile.centroid.lng, anchor.centroid.lat, anchor.centroid.lng)
            if dist < min_dist:
                min_dist = dist
                best_anchor = anchor
        
        if best_anchor and best_anchor.centroid:
            lookup_table[tile.tile_id] = {
                "lat": best_anchor.centroid.lat,
                "lng": best_anchor.centroid.lng
            }
            snap_distances.append(min_dist)
    
    fg_service.cache.set(f"anchor_lookup:{aoi_id}", lookup_table, ttl_seconds=86400)
    
    if snap_distances:
        avg_snap = sum(snap_distances) / len(snap_distances)
        max_snap = max(snap_distances)
        logging.info("AOI %s: Warmed %d anchors (from %d tiles). Snap dist: avg=%.0fm, max=%.0fm",
            aoi_id, len(anchor_tiles), total_tiles, avg_snap * 1000, max_snap * 1000)

asyncio.run(run())
