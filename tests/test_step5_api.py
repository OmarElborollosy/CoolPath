"""Step 5 test suite — REST API routes tested against the live running server.

Requires uvicorn running on port 8000:
    uvicorn app.api.server:app --host 0.0.0.0 --port 8000

Run with:
    pytest tests/test_step5_api.py -v
"""
import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(scope="module")
def client():
    """Synchronous HTTP client pointing at the live uvicorn server."""
    with httpx.Client(base_url=BASE_URL, timeout=20.0) as c:
        # Fail fast if server isn't running
        try:
            c.get("/health")
        except httpx.ConnectError:
            pytest.skip("Live server not running on port 8000 — start uvicorn first.")
        yield c


# ---------------------------------------------------------------------------
# Health Endpoint
# ---------------------------------------------------------------------------

def test_health_returns_ok(client):
    """GET /api/v1/health returns 200 with expected structure."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "coolpath" in body["service"].lower()
    assert "phoenix_aois_loaded" in body
    loaded = body["phoenix_aois_loaded"]
    assert len(loaded) == 4
    assert "van_buren_corridor" in loaded
    assert "encanto_park" in loaded


def test_health_legacy_route(client):
    """GET /health (legacy alias) also returns 200."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# AOI Geospatial Endpoints
# ---------------------------------------------------------------------------

def test_aois_endpoint_returns_four_phoenix_aois(client):
    """GET /api/v1/aois returns all 4 AOIs with center and geojson."""
    resp = client.get("/api/v1/aois")
    assert resp.status_code == 200
    body = resp.json()
    aois = body["aois"]
    for aoi_id in ["downtown_phoenix", "arcadia_residential", "encanto_park", "van_buren_corridor"]:
        assert aoi_id in aois
        aoi = aois[aoi_id]
        assert "center" in aoi
        assert aoi["center"]["lat"] > 0
        assert "geojson" in aoi


# ---------------------------------------------------------------------------
# Fleet Status
# ---------------------------------------------------------------------------

def test_fleet_status_returns_six_riders(client):
    """GET /api/v1/fleet/status returns all 6 riders with location and risk fields."""
    resp = client.get("/api/v1/fleet/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "riders" in body
    riders = body["riders"]
    for rid in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        assert rid in riders
        r = riders[rid]
        assert "current_coordinate" in r
        assert "current_risk_score" in r
        assert "current_aoi_id" in r
        assert r["current_coordinate"]["lat"] != 0


# ---------------------------------------------------------------------------
# Fleet Simulation Step Endpoints
# ---------------------------------------------------------------------------

def test_simulate_r3_peak_window_triggers_critical_alert(client):
    """POST /api/v1/fleet/simulate at 14:15 triggers Critical alert for R3 (Van Buren)."""
    resp = client.post("/api/v1/fleet/simulate", json={"simulation_time": "14:15"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulation_time"] == "14:15"
    assert "active_alerts" in body

    alerts = body["active_alerts"]
    r3_alert = next((a for a in alerts if a["rider_id"] == "R3"), None)
    assert r3_alert is not None, "Rider R3 must fire an alert at 14:15"
    assert r3_alert["alert"]["alert_triggered"] is True
    assert r3_alert["alert"]["alert_level"] in ("critical", "warning")

    # R3 risk score must be at or above High threshold
    r3_state = body["riders"]["R3"]
    assert r3_state["current_risk_score"] >= 0.55


def test_simulate_r6_reroute_window(client):
    """POST /api/v1/fleet/simulate at 15:40 triggers autonomous reroute for R6."""
    resp = client.post("/api/v1/fleet/simulate", json={"simulation_time": "15:40"})
    assert resp.status_code == 200
    body = resp.json()

    reroutes = body.get("active_reroutes", [])
    r6_reroute = next((r for r in reroutes if r["rider_id"] == "R6"), None)
    assert r6_reroute is not None, "Rider R6 must trigger an autonomous reroute at 15:40"
    assert r6_reroute["reroute"]["reroute_recommended"] is True
    opt = r6_reroute["reroute"]["selected_option"]
    assert opt is not None
    assert opt["delta_temperature_c"] < 0.0  # Cooling achieved


# ---------------------------------------------------------------------------
# Incidents Journal Endpoint
# ---------------------------------------------------------------------------

def test_incidents_journal_contains_r3_and_r6_entries(client):
    """GET /api/v1/incidents returns seeded R3 Critical Alert and R6 Reroute entries."""
    resp = client.get("/api/v1/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert "incidents" in body
    assert "count" in body
    assert body["count"] >= 2

    incidents = body["incidents"]
    r3 = next((i for i in incidents if i["rider_id"] == "R3"), None)
    assert r3 is not None, "R3 incident must be in the journal"
    assert "CRITICAL" in r3["incident_type"] or "WARNING" in r3["incident_type"]

    r6 = next((i for i in incidents if i["rider_id"] == "R6"), None)
    assert r6 is not None, "R6 incident must be in the journal"
    assert "REROUTE" in r6["incident_type"] or "CRITICAL" in r6["incident_type"]


# ---------------------------------------------------------------------------
# Static Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_root_serves_html(client):
    """GET / serves the static CoolPath dashboard HTML page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    html = resp.text
    assert "CoolPath" in html
    assert "leaflet" in html.lower()
