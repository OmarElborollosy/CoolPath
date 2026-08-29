import asyncio
import json
import time
from datetime import datetime, timezone
import time
from app.schemas.fleet import RiderTelemetry
from app.schemas.common import Coordinates
from app.agents.coordinator import DecisionCoordinatorAgent
from app.services.cache import get_global_cache
from app.services.fortyguard_service import FortyGuardService

async def run_tests():
    coordinator = DecisionCoordinatorAgent()
    
    print("\n--- TEST 1: Van Buren Corridor Cache Snap ---")
    telemetry1 = RiderTelemetry(
        rider_id="rider_1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        coordinate=Coordinates(lat=33.4480, lng=-112.0450),
        heart_rate_bpm=120,
        core_temp_c=37.8,
        hydration_ml=500
    )
    start_time = time.perf_counter()
    state1 = await coordinator.evaluate_rider(telemetry1)
    end_time = time.perf_counter()
    
    heat_dur = [t["duration_ms"] for t in state1.execution_trace if t["node"] == "heat_perception"][0]
    
    print(f"Heat Perception Duration: {heat_dur}ms")
    print(f"Total Pipeline Duration: {(end_time - start_time)*1000:.2f}ms")
    
    if state1.heat_perception:
        print(f"Status: {state1.heat_perception.status}")
        print(f"Spatial Resolution: {state1.heat_perception.spatial_resolution}")
        print(f"Is Synthesized: {state1.heat_perception.is_synthesized}")
        print(f"Tile Temp: {state1.heat_perception.tile_temperature_c}")
        
    print("\n--- RAW JSON ---")
    print(state1.model_dump_json(indent=2))
        
    print("\n--- TEST 2: Out of Bounds (Tucson) ---")
    telemetry2 = RiderTelemetry(
        rider_id="rider_2",
        timestamp=datetime.now(timezone.utc).isoformat(),
        coordinate=Coordinates(lat=32.2226, lng=-110.9747),
        heart_rate_bpm=120,
        core_temp_c=37.8,
        hydration_ml=500
    )
    start_time = time.perf_counter()
    state2 = await coordinator.evaluate_rider(telemetry2)
    end_time = time.perf_counter()
    
    heat_dur2 = [t["duration_ms"] for t in state2.execution_trace if t["node"] == "heat_perception"][0]
    print(f"Heat Perception Duration: {heat_dur2}ms")
    print(f"Total Pipeline Duration: {(end_time - start_time)*1000:.2f}ms")
    
    if state2.heat_perception:
        print(f"Status: {state2.heat_perception.status}")
        print(f"Tile Temp: {state2.heat_perception.tile_temperature_c}")

asyncio.run(run_tests())
