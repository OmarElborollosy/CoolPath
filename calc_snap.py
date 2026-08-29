import asyncio
from app.core.phoenix_aois import PHOENIX_AOIS
from app.services.fortyguard_service import FortyGuardService
from app.core.spatial import haversine_distance_km

def main():
    fg = FortyGuardService()
    date = "2026-08-03"
    
    for aoi_id, aoi in PHOENIX_AOIS.items():
        hm = fg.fetch_aoi_heatmap(aoi_id, analytic_type="tcm", date=date)
        tiles = hm.tiles
        total_tiles = len(tiles)
        
        if aoi_id == "downtown_phoenix":
            target_anchors = 25
        elif aoi_id == "van_buren_corridor":
            target_anchors = 15
        else:
            target_anchors = 10
            
        step = max(1, total_tiles // target_anchors)
        anchor_tiles = tiles[::step]
        
        snap_distances = []
        for tile in tiles:
            if not tile.centroid: continue
            min_dist = float('inf')
            for anchor in anchor_tiles:
                if not anchor.centroid: continue
                dist = haversine_distance_km(tile.centroid.lat, tile.centroid.lng, anchor.centroid.lat, anchor.centroid.lng)
                if dist < min_dist:
                    min_dist = dist
            snap_distances.append(min_dist)
            
        if snap_distances:
            avg_snap = sum(snap_distances) / len(snap_distances)
            max_snap = max(snap_distances)
            print(f"AOI {aoi_id}: {total_tiles} tiles -> {len(anchor_tiles)} anchors. Snap dist: avg={avg_snap*1000:.0f}m, max={max_snap*1000:.0f}m")

if __name__ == "__main__":
    main()
