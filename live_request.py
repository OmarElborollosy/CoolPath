import time
import requests
import json

payload = {
    "rider_id": "R_DEMO",
    "lat": 33.448,
    "lng": -112.045,
    "speed_kmh": 15.0
}

print("Waiting for server to start...")
while True:
    try:
        start_time = time.perf_counter()
        resp = requests.post("http://127.0.0.1:8123/api/evaluate/rider", json=payload, timeout=2.0)
        end_time = time.perf_counter()
        if resp.status_code == 200:
            print("Server is up and processing!")
            print(f"Total HTTP Request Time: {(end_time - start_time)*1000:.2f}ms")
            
            data = resp.json()
            heat = data.get("heat_perception", {})
            trace = data.get("execution_trace", [])
            heat_dur = next((t["duration_ms"] for t in trace if t["node"] == "heat_perception"), None)
            
            print(f"execution_trace.heat_perception.duration_ms: {heat_dur}")
            print(f"spatial_resolution: {heat.get('spatial_resolution')}")
            print("\nRaw JSON Response:")
            print(json.dumps(data, indent=2))
            break
        elif resp.status_code == 422:
            print(f"Got status 422: {resp.text}, retrying...")
        else:
            print(f"Got status {resp.status_code}, retrying...")
    except requests.exceptions.ConnectionError:
        pass
    except requests.exceptions.ReadTimeout:
        pass
    
    time.sleep(5)
