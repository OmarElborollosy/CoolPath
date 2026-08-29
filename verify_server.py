"""
Verification script: wait for the server to accept requests, hit /health,
then send a real /api/evaluate/rider POST and report the full response.
"""
import time
import requests
import json

PORT = 8300
BASE = f"http://127.0.0.1:{PORT}"

print(f"Waiting for server on port {PORT}...", flush=True)

boot_start = time.perf_counter()
while True:
    try:
        r = requests.get(f"{BASE}/health", timeout=2)
        boot_elapsed = (time.perf_counter() - boot_start) * 1000
        print(f"\n--- SERVER IS UP (booted in {boot_elapsed:.0f}ms) ---\n", flush=True)
        print("=== GET /health ===")
        print(json.dumps(r.json(), indent=2))
        break
    except Exception:
        time.sleep(1)

# Now send the actual evaluate/rider POST
payload = {
    "rider_id": "R_DEMO",
    "lat": 33.448,
    "lng": -112.045,
    "speed_kmh": 15.0,
}

print("\n=== POST /api/evaluate/rider (33.448, -112.045) ===", flush=True)
t0 = time.perf_counter()
resp = requests.post(f"{BASE}/api/evaluate/rider", json=payload, timeout=10)
elapsed = (time.perf_counter() - t0) * 1000
print(f"HTTP round-trip: {elapsed:.1f}ms, status: {resp.status_code}")
data = resp.json()

heat = data.get("heat_perception", {})
trace = data.get("execution_trace", [])
heat_node = next((t for t in trace if t.get("node") == "heat_perception"), {})

print(f"\nexecution_trace.heat_perception.duration_ms: {heat_node.get('duration_ms')}")
print(f"spatial_resolution: {heat.get('spatial_resolution')}")
print(f"is_synthesized: {heat.get('is_synthesized')}")
print(f"\nFull JSON response:")
print(json.dumps(data, indent=2))
