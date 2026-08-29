"""Fleet management, rider telemetry, and simulation schemas."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from .common import Coordinates


class RiderTelemetry(BaseModel):
    """Real-time GPS and status ping from a rider."""
    rider_id: str
    timestamp: str
    coordinate: Coordinates
    speed_kmh: float = 15.0
    current_aoi_id: str | None = None
    battery_pct: float = 100.0
    active_delivery: bool = True
    assigned_route: list[str] = Field(default_factory=list)


class RiderState(BaseModel):
    """Persisted live state of a delivery rider."""
    rider_id: str
    current_coordinate: Coordinates
    speed_kmh: float
    current_aoi_id: str
    active_route_aois: list[str]
    start_time: str
    current_time: str
    cumulative_high_heat_minutes: float = 0.0
    current_risk_score: float = 0.0
    current_risk_tier: str = "Low"  # Low, Moderate, High, Critical
    active_reroute: dict[str, Any] | None = None
    last_alert_level: str | None = None
    narrative_history: list[str] = Field(default_factory=list)


class FleetSimulationState(BaseModel):
    """Complete simulation frame state."""
    simulation_time: str
    riders: dict[str, RiderState] = Field(default_factory=dict)
    active_alerts: list[dict[str, Any]] = Field(default_factory=list)
    active_reroutes: list[dict[str, Any]] = Field(default_factory=list)
