import asyncio
import time
from fastapi.testclient import TestClient
from app.api.server import app
from app.services.cache import get_global_cache
from app.services.background_worker import MicroclimateBackgroundWorker

def main():
    # 1. Flush/reset the in-process RuntimeCache
    cache = get_global_cache()
    if hasattr(cache, "clear"):
        cache.clear()
    
    # 2. Run a partial warm cycle for just Van Buren
    print("Starting background worker warm cycle for Van Buren...")
    worker = MicroclimateBackgroundWorker()
    
    from app.core.phoenix_aois import PHOENIX_AOIS
    PHOENIX_AOIS_VAN = {"van_buren_corridor": PHOENIX_AOIS["van_buren_corridor"]}
    import unittest.mock
    with unittest.mock.patch('app.services.background_worker.PHOENIX_AOIS', PHOENIX_AOIS_VAN):
        asyncio.run(worker.warm_cache_for_all_aois())
    print("Warm cycle complete.\n")
    
    # 3. Send a live HTTP request to the running server (via TestClient which shares memory)
    client = TestClient(app)
    
    payload = {
        "rider_id": "rider_demo",
        "timestamp": "2026-08-03T14:00:00Z",
        "coordinate": {
            "lat": 33.448,
            "lng": -112.045
        },
        "speed_kmh": 15.0,
        "current_aoi_id": "van_buren_corridor"
    }
    
    print("Sending POST request to /api/evaluate/rider for (33.448, -112.045)...")
    start_time = time.perf_counter()
    response = client.post("/api/evaluate/rider", json=payload)
    end_time = time.perf_counter()
    
    print(f"\n--- RESULTS ---")
    print(f"HTTP Request Total Time: {(end_time - start_time) * 1000:.2f}ms")
    
    data = response.json()
    heat_perception = data.get("heat_perception", {})
    
    # Find heat perception duration in execution_trace
    trace = data.get("execution_trace", [])
    heat_dur = next((t["duration_ms"] for t in trace if t["node"] == "heat_perception"), None)
    
    print(f"Heat Perception Trace Duration: {heat_dur}ms")
    print(f"Spatial Resolution: {heat_perception.get('spatial_resolution')}")
    print(f"Is Synthesized: {heat_perception.get('is_synthesized')}")
    print(f"\nRaw Heat Perception JSON:")
    import json
    print(json.dumps(heat_perception, indent=2))

if __name__ == "__main__":
    main()
