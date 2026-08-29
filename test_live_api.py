import os
import sys
import time
from pathlib import Path

# Add quickstart to sys.path
quickstart_dir = Path("temperature-api-quickstart").resolve()
sys.path.insert(0, str(quickstart_dir))

from fortyguard import FortyGuardClient
from app.config import get_settings

settings = get_settings()

client = FortyGuardClient(api_key=settings.fortyguard_api_key, base_url=settings.fortyguard_base_url)

print("Testing env_params...", flush=True)
try:
    res = client.environmental_parameters(
        latitude=33.448,
        longitude=-112.045,
        temperature=45.0,
        start_date="2026-08-03",
        filter_type=1,
        start_time="14:00",
        wait=True,
        timeout=30.0,
        verbose=True
    )
    print("Success!", res, flush=True)
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}", flush=True)

print("Testing heatmap...", flush=True)
try:
    from app.core.phoenix_aois import PHOENIX_AOIS
    aoi = PHOENIX_AOIS["van_buren_corridor"].geojson
    res = client.create_heatmap(
        polygon_aoi=aoi,
        start_date="2026-08-03",
        start_time="14:00",
        filter_type=1,
        granularity=100,
        wait=True,
        timeout=30.0,
        verbose=True
    )
    print("Success!", type(res), flush=True)
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}", flush=True)
