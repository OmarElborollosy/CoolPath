"""Step 5 smoke-test verification script: REST endpoints + WebSocket handshake.

Run from coolpath/ directory:
    python verify_step5.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import httpx


BASE = "http://127.0.0.1:8000"


async def check(label: str, resp: httpx.Response, *, expect_keys: list[str] | None = None) -> bool:
    ok = resp.status_code == 200
    body = None
    if ok and expect_keys:
        try:
            body = resp.json()
            for k in expect_keys:
                if k not in body:
                    ok = False
                    print(f"  [FAIL] Missing key '{k}' in response")
        except Exception:
            ok = False
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} -> HTTP {resp.status_code}")
    return ok


async def main() -> None:
    print("=" * 70)
    print("COOLPATH STEP 5: REST API + WEBSOCKET SMOKE TEST")
    print("=" * 70)
    print(f"\nTarget server: {BASE}\n")

    all_pass = True

    async with httpx.AsyncClient(base_url=BASE, timeout=20.0) as client:
        # 1. Health
        print("[1] GET /api/v1/health")
        r = await client.get("/api/v1/health")
        ok = await check("Service health OK", r, expect_keys=["status", "phoenix_aois_loaded"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            data = r.json()
            print(f"     service    : {data.get('service')}")
            print(f"     aois_loaded: {data.get('phoenix_aois_loaded')}")
            print(f"     cache_status: {data.get('cache_status', 'n/a')}")

        # 2. AOIs
        print("\n[2] GET /api/v1/aois")
        r = await client.get("/api/v1/aois")
        ok = await check("4 Phoenix AOIs returned", r, expect_keys=["aois"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            aois = r.json()["aois"]
            for aoi_id, aoi in aois.items():
                print(f"     {aoi_id}: center ({aoi['center']['lat']:.4f}, {aoi['center']['lng']:.4f})")

        # 3. Fleet status (pre-simulation)
        print("\n[3] GET /api/v1/fleet/status")
        r = await client.get("/api/v1/fleet/status")
        ok = await check("Fleet status with 6 riders", r, expect_keys=["riders"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            riders = r.json()["riders"]
            for rid, rstate in riders.items():
                tier = rstate.get("current_risk_tier", "?")
                score = rstate.get("current_risk_score", 0)
                print(f"     {rid}: [{tier}] score={score:.4f}  aoi={rstate.get('current_aoi_id')}")

        # 4. Simulate 14:15 (R3 alert trigger)
        print("\n[4] POST /api/v1/fleet/simulate  time=14:15  (R3 Van Buren Heat Trap)")
        r = await client.post("/api/v1/fleet/simulate", json={"simulation_time": "14:15"})
        ok = await check("Simulation step returns fleet frame", r, expect_keys=["riders", "active_alerts"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            data = r.json()
            alerts = data.get("active_alerts", [])
            print(f"     active_alerts : {len(alerts)}")
            for al in alerts:
                lvl = al.get("alert", {}).get("alert_level", "?")
                print(f"     => Rider {al['rider_id']} -> [{lvl.upper()}] {al['alert'].get('title', '')}")
            r3_rider = data["riders"].get("R3", {})
            print(f"     R3 risk_score : {r3_rider.get('current_risk_score', '?'):.4f} [{r3_rider.get('current_risk_tier', '?')}]")

        # 5. Simulate 15:40 (R6 reroute trigger)
        print("\n[5] POST /api/v1/fleet/simulate  time=15:40  (R6 Autonomous Reroute)")
        r = await client.post("/api/v1/fleet/simulate", json={"simulation_time": "15:40"})
        ok = await check("Simulation step triggers R6 reroute", r, expect_keys=["active_reroutes"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            data = r.json()
            reroutes = data.get("active_reroutes", [])
            print(f"     active_reroutes: {len(reroutes)}")
            for rr in reroutes:
                opt = rr.get("reroute", {}).get("selected_option") or {}
                print(f"     => Rider {rr['rider_id']} -> refuge: {opt.get('refuge_name')}  deltaT: {opt.get('delta_temperature_c')}°C")

        # 6. Incidents journal
        print("\n[6] GET /api/v1/incidents")
        r = await client.get("/api/v1/incidents")
        ok = await check("Incident journal with seeded R3 + R6 entries", r, expect_keys=["incidents", "count"])
        all_pass = all_pass and ok
        if r.status_code == 200:
            data = r.json()
            print(f"     total_incidents: {data['count']}")
            for inc in data["incidents"][:3]:
                print(f"     [{inc['timestamp']}] {inc['rider_id']} -> {inc['incident_type']}")

        # 7. Dashboard HTML
        print("\n[7] GET /  (Dashboard HTML)")
        r = await client.get("/")
        ok = r.status_code == 200 and "text/html" in r.headers.get("content-type", "")
        print(f"  [{'PASS' if ok else 'FAIL'}] Static dashboard served -> HTTP {r.status_code}")
        all_pass = all_pass and ok

    # 8. WebSocket handshake
    print("\n[8] WS /ws/fleet  (WebSocket fleet stream handshake)")
    try:
        import websockets
        uri = BASE.replace("http://", "ws://") + "/ws/fleet"
        async with websockets.connect(uri, open_timeout=5) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)
            assert msg.get("type") == "fleet_update", f"Unexpected msg type: {msg.get('type')}"
            sim_time = msg.get("simulation_time", "?")
            n_riders = len(msg.get("data", {}).get("riders", {}))
            print(f"  [PASS] WebSocket connected -> first frame: time={sim_time}, riders={n_riders}")
    except ModuleNotFoundError:
        print("  [SKIP] websockets package not installed — install with: pip install websockets")
    except Exception as exc:
        print(f"  [FAIL] WebSocket error: {exc}")
        all_pass = False

    print("\n" + "=" * 70)
    if all_pass:
        print("STEP 5 VERIFICATION SUCCESSFUL: All API endpoints + WebSocket operational.")
    else:
        print("STEP 5 VERIFICATION: Some checks FAILED (see above).")
    print("=" * 70)

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
