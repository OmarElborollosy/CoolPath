import sys
import time
from datetime import datetime
from pathlib import Path
import json

quickstart_dir = Path("../temperature-api-quickstart").resolve()
sys.path.insert(0, str(quickstart_dir))

from fortyguard import FortyGuardClient
from fortyguard.exceptions import ActivityNotReadyError
from app.config import get_settings

settings = get_settings()
client = FortyGuardClient(api_key=settings.fortyguard_api_key, base_url=settings.fortyguard_base_url)

requests_to_make = [
    {
        "endpoint": "satellite_segmentation",
        "kwargs": {
            "latitude": 33.448, 
            "longitude": -112.074, 
            "start_date": "2026-08-03", 
            "filter_type": 3, 
            "granularity": 100,
            "wait": False
        },
        "name": "Downtown Phoenix"
    },
    {
        "endpoint": "street_view_segmentation",
        "kwargs": {
            "latitude": 33.448, 
            "longitude": -112.074,
            "wait": False
        },
        "name": "Downtown Phoenix"
    },
    {
        "endpoint": "satellite_segmentation",
        "kwargs": {
            "latitude": 33.448, 
            "longitude": -112.045, 
            "start_date": "2026-08-03", 
            "filter_type": 3, 
            "granularity": 100,
            "wait": False
        },
        "name": "Van Buren Corridor"
    }
]

results = []

print("=== FORTYGUARD API BUG REPORT: STUCK PREMIUM ENDPOINTS ===\n")
print("## 1. Request Payloads")
for idx, req in enumerate(requests_to_make):
    endpoint = req["endpoint"]
    kwargs = req["kwargs"].copy()
    kwargs.pop("wait", None) # Don't print wait=False as it's SDK specific
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    
    if endpoint == "satellite_segmentation":
        activity_id = client.satellite_segmentation(**req["kwargs"])
    else:
        activity_id = client.street_view_segmentation(**req["kwargs"])
        
    req["activity_id"] = activity_id
    req["submitted_at"] = timestamp
    
    print(f"**Request {idx+1}**: `{endpoint}`")
    print(f"- Submitted At: {timestamp}")
    print(f"- Payload: `{json.dumps(kwargs)}`")
    print(f"- Returned Activity ID: `{activity_id}`\n")
    results.append(req)

print("Waiting 5 seconds for propagation to status endpoint...\n")
time.sleep(5)

print("## 2. Raw Status Responses")
for req in results:
    try:
        status_data = client.get_status(req["activity_id"])
        req["status"] = status_data.get("status", "unknown")
        req["raw_status"] = json.dumps(status_data, indent=2)
    except ActivityNotReadyError:
        req["status"] = "404 Not Ready"
        req["raw_status"] = "{}"
    except Exception as e:
        req["status"] = f"Error: {e}"
        req["raw_status"] = ""
        
    print(f"**Activity ID: {req['activity_id']}**")
    print("```json")
    print(req["raw_status"])
    print("```\n")

print("## 3. Summary Table")
print("| Endpoint | `activity_id` | Submitted At | Status At Check | Coordinates |")
print("|---|---|---|---|---|")
for req in results:
    lat = req['kwargs']['latitude']
    lon = req['kwargs']['longitude']
    coords_str = f"{lat}, {lon} ({req['name']})"
    print(f"| `{req['endpoint']}` | `{req['activity_id']}` | {req['submitted_at']} | `{req['status']}` | {coords_str} |")
