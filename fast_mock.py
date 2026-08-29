import asyncio
import time
from fastapi.testclient import TestClient
from app.api.server import app
from app.services.cache import get_global_cache
from app.services.fortyguard_service import FortyGuardService
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.common import Coordinates
import app.services.background_worker

def main():
    cache = get_global_cache()
    if hasattr(cache, "clear"): cache.clear()
    
    # Manually populate cache to simulate the worker having finished
    fg = FortyGuardService()
    aoi_id = "van_buren_corridor"
    
    # 1. Heatmap tiles
    hm = fg.fetch_aoi_heatmap(aoi_id, analytic_type="tcm")
    fg.fetch_aoi_heatmap(aoi_id, analytic_type="persistence")
    fg.fetch_aoi_heatmap(aoi_id, analytic_type="exceedance")
    
    # We'll just take ONE tile as the anchor to mock the full worker
    anchor = hm.tiles[0]
    lookup_table = {}
    for tile in hm.tiles:
        lookup_table[tile.tile_id] = {"lat": anchor.centroid.lat, "lng": anchor.centroid.lng}
        
    cache.set(f"anchor_lookup:{aoi_id}", lookup_table, ttl_seconds=86400)
    
    # Pre-warm env params for that anchor
    fg.fetch_env_params(anchor.centroid, temperature_anchor_c=anchor.temperature_c)
    fg.fetch_satellite_segmentation(anchor.centroid)
    fg.fetch_streetview_segmentation(anchor.centroid)
    
    # 3. Send HTTP request
    client = TestClient(app)
    payload = {
        "rider_id": "rider_demo",
        "timestamp": "2026-08-03T14:00:00Z",
        "coordinate": {"lat": 33.448, "lng": -112.045},
        "speed_kmh": 15.0,
        "current_aoi_id": "van_buren_corridor"
    }
    
    start_time = time.perf_counter()
    response = client.post("/api/evaluate/rider", json=payload)
    end_time = time.perf_counter()
    
    data = response.json()
    trace = data.get("execution_trace", [])
    heat_dur = next((t["duration_ms"] for t in trace if t["node"] == "heat_perception"), None)
    
    print(f"HTTP Request Time: {(end_time - start_time) * 1000:.2f}ms")
    print(f"Heat Perception Duration: {heat_dur}ms")
    heat = data.get("heat_perception", {})
    print(f"Spatial Resolution: {heat.get('spatial_resolution')}")

if __name__ == "__main__":
    main()
