import sys
from pathlib import Path

# Add quickstart to sys.path
quickstart_dir = Path("../temperature-api-quickstart").resolve()
sys.path.insert(0, str(quickstart_dir))

from fortyguard import FortyGuardClient
from app.config import get_settings

settings = get_settings()

client = FortyGuardClient(api_key=settings.fortyguard_api_key, base_url=settings.fortyguard_base_url)

print("Testing satellite_segmentation...", flush=True)
try:
    res = client.satellite_segmentation(
        latitude=33.448,
        longitude=-112.045,
        start_date="2026-08-03",
        filter_type=3,
        granularity=100,
        wait=True,
        timeout=60.0,
        verbose=True
    )
    print("Success!", res, flush=True)
except Exception as e:
    print(f"Failed: {type(e).__name__}: {e}", flush=True)
