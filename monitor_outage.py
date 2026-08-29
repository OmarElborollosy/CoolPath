import sys
import time
from datetime import datetime
from pathlib import Path

# Add quickstart to sys.path
quickstart_dir = Path("../temperature-api-quickstart").resolve()
sys.path.insert(0, str(quickstart_dir))

from fortyguard import FortyGuardClient
from app.config import get_settings

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = f"[{timestamp}] {msg}"
    print(out, flush=True)
    with open("outage_log.txt", "a") as f:
        f.write(out + "\n")

def check_endpoints():
    settings = get_settings()
    client = FortyGuardClient(api_key=settings.fortyguard_api_key, base_url=settings.fortyguard_base_url)

    lat, lon = 33.448, -112.045
    date = "2026-08-03"

    log("Testing satellite_segmentation...")
    satellite_ok = False
    try:
        res = client.satellite_segmentation(
            latitude=lat, longitude=lon, start_date=date, filter_type=3, granularity=100,
            wait=True, timeout=120.0, verbose=False
        )
        if isinstance(res, dict) and "activity_id" in res:
            log(f"satellite_segmentation SUCCESS: {res.get('activity_id')}")
        else:
            log(f"satellite_segmentation SUCCESS: {res}")
        satellite_ok = True
    except Exception as e:
        log(f"satellite_segmentation FAILED: {type(e).__name__} - {e}")

    log("Testing street_view_segmentation...")
    streetview_ok = False
    try:
        res = client.street_view_segmentation(
            latitude=lat, longitude=lon, wait=True, timeout=120.0, verbose=False
        )
        if isinstance(res, dict) and "activity_id" in res:
            log(f"street_view_segmentation SUCCESS: {res.get('activity_id')}")
        else:
            log(f"street_view_segmentation SUCCESS: {res}")
        streetview_ok = True
    except Exception as e:
        log(f"street_view_segmentation FAILED: {type(e).__name__} - {e}")

    return satellite_ok and streetview_ok

if __name__ == "__main__":
    while True:
        log("Starting periodic FortyGuard endpoint check...")
        check_endpoints()
        log("Sleeping for 30 minutes...")
        time.sleep(1800)
