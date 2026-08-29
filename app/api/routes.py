"""FastAPI HTTP REST API routes for CoolPath."""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.phoenix_aois import AOI_BASELINE_METRICS, PHOENIX_AOIS
from app.schemas.common import Coordinates
from app.schemas.fleet import RiderTelemetry
from app.schemas.graph_state import CoolPathGraphState
from app.services.background_worker import warm_cycle_state

logger = logging.getLogger("coolpath.routes")

router = APIRouter()


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class SimulationStepRequest(BaseModel):
    """Request to advance or set the simulation timestamp."""
    simulation_time: str = Field(default="14:15", description="Simulation clock timestamp (e.g. '14:15')")


class EvaluateCoordinateRequest(BaseModel):
    """Request to evaluate microclimate risk for custom telemetry."""
    rider_id: str = "R_CUSTOM"
    lat: float = 33.4484
    lng: float = -112.0740
    speed_kmh: float = 15.0


# In-memory incident journal tracking autonomous multi-agent decisions
_incident_journal: list[dict[str, Any]] = [
    {
        "incident_id": "INC-2026-0803-001",
        "timestamp": "14:15",
        "rider_id": "R3",
        "rider_name": "Marcus Vance",
        "aoi_id": "van_buren_corridor",
        "incident_type": "CRITICAL_HEAT_WARNING",
        "action_taken": "MANDATORY_STOP_REQUIRED",
        "surface_temp_c": 46.4,
        "heat_index_c": 48.2,
        "persistence_hours": 9.7,
        "risk_score": 0.7598,
        "risk_tier": "Critical",
        "osha_guideline": "Mandatory 20-minute indoor A/C cooldown + 24 oz fluids.",
        "status": "DISPATCH_ESCALATED",
    },
    {
        "incident_id": "INC-2026-0803-002",
        "timestamp": "15:40",
        "rider_id": "R6",
        "rider_name": "David Kim",
        "aoi_id": "van_buren_corridor",
        "incident_type": "SHADED_CORRIDOR_REROUTE",
        "action_taken": "AUTONOMOUS_REROUTE_ACTIVATED",
        "surface_temp_c": 46.3,
        "heat_index_c": 48.1,
        "risk_score": 0.7598,
        "destination_refuge": "Encanto Park Shaded Refuge / University Park Ramada",
        "delta_temp_c": -10.8,
        "detour_distance_km": 2.21,
        "status": "REROUTED_TO_SHADE",
    },
]


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
@router.get("/api/v1/health")
async def health_check() -> dict[str, Any]:
    """Service health, version, study date, and background warm cycle status."""
    return {
        "status": "ok",
        "service": "CoolPath Microclimate Risk Intelligence",
        "app_version": "1.0.0",
        "study_date": "2026-08-03",
        "phoenix_aois_loaded": list(PHOENIX_AOIS.keys()),
        "two_speed_cache_active": True,
        **warm_cycle_state.to_dict(),
    }


# ---------------------------------------------------------------------------
# Phoenix AOI Geospatial Data
# ---------------------------------------------------------------------------

@router.get("/api/aois")
@router.get("/api/v1/aois")
async def get_phoenix_aois() -> dict[str, Any]:
    """Retrieve GeoJSON polygons, bounding boxes, and ground-truth metrics for all 4 AOIs."""
    return {
        "aois": {k: v.model_dump(mode="json") for k, v in PHOENIX_AOIS.items()},
        "baselines": AOI_BASELINE_METRICS,
    }


# ---------------------------------------------------------------------------
# Fleet Telemetry & Simulation Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/fleet/status")
@router.get("/api/v1/fleet/status")
async def get_fleet_status(request: Request) -> dict[str, Any]:
    """Retrieve current real-time state, GPS positions, risk scores, and alert statuses for R1-R6."""
    simulator = request.app.state.simulator
    return {
        "simulation_time": simulator.riders["R1"].current_time if simulator.riders else "14:00",
        "riders": {k: v.model_dump(mode="json") for k, v in simulator.riders.items()},
    }


@router.post("/api/fleet/step")
@router.post("/api/v1/fleet/simulate")
async def simulate_fleet_step(req: SimulationStepRequest, request: Request) -> dict[str, Any]:
    """Step all 6 fleet riders forward in time and run the CoolPath LangGraph pipeline."""
    simulator = request.app.state.simulator
    result = await simulator.step_simulation(req.simulation_time)

    # Automatically record incidents into journal if alerts or reroutes occurred
    for alert_info in result.active_alerts:
        al = alert_info.get("alert", {})
        if al.get("alert_level") in ("critical", "warning"):
            rider_id = alert_info.get("rider_id", "R_UNKNOWN")
            r_state = simulator.riders.get(rider_id)
            entry = {
                "incident_id": f"INC-{req.simulation_time.replace(':', '')}-{rider_id}",
                "timestamp": req.simulation_time,
                "rider_id": rider_id,
                "aoi_id": r_state.current_aoi_id if r_state else "downtown_phoenix",
                "incident_type": "CRITICAL_HEAT_WARNING" if al.get("alert_level") == "critical" else "HEAT_WARNING",
                "action_taken": "MANDATORY_STOP_REQUIRED" if al.get("mandatory_stop_required") else "DETOUR_RECOMMENDED",
                "risk_score": r_state.current_risk_score if r_state else 0.75,
                "risk_tier": r_state.current_risk_tier if r_state else "High",
                "title": al.get("title", ""),
                "status": "ACTION_ENFORCED",
            }
            if not any(j["incident_id"] == entry["incident_id"] for j in _incident_journal):
                _incident_journal.insert(0, entry)

    return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Incidents Journal Endpoint
# ---------------------------------------------------------------------------

@router.get("/api/incidents")
@router.get("/api/v1/incidents")
async def get_incidents_journal() -> dict[str, Any]:
    """Retrieve structured audit logs of autonomous multi-agent decisions."""
    return {
        "count": len(_incident_journal),
        "incidents": _incident_journal,
    }


# ---------------------------------------------------------------------------
# Multi-Agent Point Evaluation
# ---------------------------------------------------------------------------

@router.post("/api/evaluate/rider", response_model=CoolPathGraphState)
@router.post("/api/v1/evaluate/rider", response_model=CoolPathGraphState)
async def evaluate_rider(req: EvaluateCoordinateRequest, request: Request) -> CoolPathGraphState:
    """Run full CoolPath multi-agent evaluation for an arbitrary GPS coordinate."""
    coordinator = request.app.state.coordinator
    telemetry = RiderTelemetry(
        rider_id=req.rider_id,
        timestamp="14:00",
        coordinate=Coordinates(lat=req.lat, lng=req.lng),
        speed_kmh=req.speed_kmh,
    )
    state = await coordinator.evaluate_rider(telemetry)
    return state


# ---------------------------------------------------------------------------
# Heatmap GeoJSON Layers
# ---------------------------------------------------------------------------

@router.get("/api/heatmap/{aoi_id}")
@router.get("/api/v1/heatmap/{aoi_id}")
async def get_heatmap_layer(aoi_id: str, request: Request, analytic_type: str = "tcm") -> dict[str, Any]:
    """Retrieve FortyGuard thermal or analysis heatmap GeoJSON for a Phoenix AOI."""
    if aoi_id not in PHOENIX_AOIS:
        raise HTTPException(status_code=404, detail=f"Phoenix AOI '{aoi_id}' not recognized.")
    fg_service = request.app.state.fg_service
    result = fg_service.fetch_aoi_heatmap(aoi_id, analytic_type=analytic_type)
    return result.model_dump(mode="json")


__all__ = ["router", "SimulationStepRequest", "EvaluateCoordinateRequest"]
