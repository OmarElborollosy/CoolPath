"""Phoenix 6-Rider Fleet Simulation Engine for CoolPath (2026-08-03).

Simulates the 6 demonstration riders across the 4 Phoenix AOIs (1 PM - 4 PM window):
- R1: Downtown Phoenix -> Van Buren Corridor (13:00 - 14:00, Exposure escalation)
- R2: Arcadia Residential -> Encanto Park (13:15 - 14:15, Shaded detour demo)
- R3 (Anchor): Van Buren Industrial Corridor (14:00 - 15:00, Stuck in worst-case heat zone -> Critical Alert demo)
- R4: Downtown Phoenix -> Arcadia Residential (14:30 - 15:30, Urban to residential baseline)
- R5: Encanto Park -> Downtown Phoenix (15:00 - 16:00, Safe park refuge to hot urban core)
- R6 (Anchor): Van Buren Corridor -> Encanto Park (15:40 - 16:40, Extreme heat -> Autonomous Reroute hero story)
"""
from __future__ import annotations

import logging
from typing import Any
from app.agents.coordinator import DecisionCoordinatorAgent
from app.core.phoenix_aois import PHOENIX_AOIS, get_aoi_for_coordinate
from app.core.spatial import interpolate_coordinates
from app.schemas.common import Coordinates
from app.schemas.fleet import FleetSimulationState, RiderState, RiderTelemetry

logger = logging.getLogger("coolpath.simulation")

RIDER_CONFIGS = [
    {
        "rider_id": "R1",
        "name": "Alex Martinez",
        "route_aois": ["downtown_phoenix", "van_buren_corridor"],
        "start_time": "13:00",
        "end_time": "14:00",
        "speed_kmh": 15.0,
        "narrative": "Downtown commercial hub to Van Buren industrial delivery — heat exposure escalates rapidly.",
    },
    {
        "rider_id": "R2",
        "name": "Sarah Chen",
        "route_aois": ["arcadia_residential", "encanto_park"],
        "start_time": "13:15",
        "end_time": "14:15",
        "speed_kmh": 15.0,
        "narrative": "Suburban delivery passing near Encanto Park — candidate for shaded corridor recommendation.",
    },
    {
        "rider_id": "R3",
        "name": "Marcus Vance",
        "route_aois": ["van_buren_corridor"],
        "start_time": "14:00",
        "end_time": "15:00",
        "speed_kmh": 8.0,
        "narrative": "Stuck in Van Buren unshaded industrial parking (0% canopy, 46.2°C surface) — triggers OSHA Critical Alert.",
    },
    {
        "rider_id": "R4",
        "name": "Jordan Taylor",
        "route_aois": ["downtown_phoenix", "arcadia_residential"],
        "start_time": "14:30",
        "end_time": "15:30",
        "speed_kmh": 15.0,
        "narrative": "Standard urban to suburban corridor, fleet baseline variety.",
    },
    {
        "rider_id": "R5",
        "name": "Elena Rodriguez",
        "route_aois": ["encanto_park", "downtown_phoenix"],
        "start_time": "15:00",
        "end_time": "16:00",
        "speed_kmh": 14.0,
        "narrative": "Departs shaded Encanto Park (48.5% canopy, 33.4°C) into urban core — shows thermal contrast.",
    },
    {
        "rider_id": "R6",
        "name": "David Kim",
        "route_aois": ["van_buren_corridor", "encanto_park"],
        "start_time": "15:40",
        "end_time": "16:40",
        "speed_kmh": 12.0,
        "narrative": "Dispatched near Van Buren extreme heat — autonomous reroute cascades to Encanto Park shaded refuge.",
    },
]


def _time_to_minutes(hh_mm: str) -> int:
    parts = hh_mm.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


class FleetSimulator:
    """Simulates fleet positions and coordinates multi-agent evaluations per frame."""

    def __init__(self, coordinator: DecisionCoordinatorAgent | None = None) -> None:
        self.coordinator = coordinator or DecisionCoordinatorAgent()
        self.riders: dict[str, RiderState] = {}
        self.incident_journal: list[dict[str, Any]] = [
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
        self._initialize_riders()

    def _initialize_riders(self) -> None:
        for cfg in RIDER_CONFIGS:
            start_aoi = PHOENIX_AOIS[cfg["route_aois"][0]]
            self.riders[cfg["rider_id"]] = RiderState(
                rider_id=cfg["rider_id"],
                current_coordinate=start_aoi.center,
                speed_kmh=cfg["speed_kmh"],
                current_aoi_id=cfg["route_aois"][0],
                active_route_aois=cfg["route_aois"],
                start_time=cfg["start_time"],
                current_time=cfg["start_time"],
                narrative_history=[cfg["narrative"]],
            )

    def get_rider_position_at_time(self, rider_id: str, sim_time: str) -> Coordinates:
        """Calculate GPS interpolation for a rider at a given simulation timestamp."""
        cfg = next((c for c in RIDER_CONFIGS if c["rider_id"] == rider_id), None)
        if not cfg:
            return PHOENIX_AOIS["downtown_phoenix"].center

        start_min = _time_to_minutes(cfg["start_time"])
        end_min = _time_to_minutes(cfg["end_time"])
        curr_min = _time_to_minutes(sim_time)

        start_aoi = PHOENIX_AOIS[cfg["route_aois"][0]]

        if len(cfg["route_aois"]) == 1 or curr_min <= start_min:
            # Stationary or just starting: small pseudo-movement jitter
            offset = ((curr_min % 10) - 5) * 0.0003
            return Coordinates(lat=start_aoi.center.lat + offset, lng=start_aoi.center.lng + offset)

        end_aoi = PHOENIX_AOIS[cfg["route_aois"][-1]]

        if curr_min >= end_min:
            return end_aoi.center

        fraction = (curr_min - start_min) / max(1, (end_min - start_min))
        return interpolate_coordinates(start_aoi.center, end_aoi.center, fraction)

    def generate_telemetry(self, rider_id: str, sim_time: str) -> RiderTelemetry:
        """Generate real-time telemetry ping for a single rider at a given timestamp."""
        pos = self.get_rider_position_at_time(rider_id, sim_time)
        aoi = get_aoi_for_coordinate(pos)
        aoi_id = aoi.aoi_id if aoi else "downtown_phoenix"
        cfg = next((c for c in RIDER_CONFIGS if c["rider_id"] == rider_id), None)
        speed = cfg["speed_kmh"] if cfg else 15.0

        return RiderTelemetry(
            rider_id=rider_id,
            timestamp=sim_time,
            coordinate=pos,
            speed_kmh=speed,
            current_aoi_id=aoi_id,
        )

    def generate_fleet_telemetry_batch(self, sim_time: str) -> list[RiderTelemetry]:
        """Generate telemetry pings for all 6 fleet riders at the specified timestamp."""
        return [self.generate_telemetry(cfg["rider_id"], sim_time) for cfg in RIDER_CONFIGS]

    async def step_simulation(self, sim_time: str = "14:15") -> FleetSimulationState:
        """Step all active riders forward and run CoolPath multi-agent evaluation."""
        active_alerts: list[dict[str, Any]] = []
        active_reroutes: list[dict[str, Any]] = []

        for rider_id, state in self.riders.items():
            pos = self.get_rider_position_at_time(rider_id, sim_time)
            aoi = get_aoi_for_coordinate(pos)
            aoi_id = aoi.aoi_id if aoi else "downtown_phoenix"

            state.current_coordinate = pos
            state.current_aoi_id = aoi_id
            state.current_time = sim_time

            # Telemetry ping
            telemetry = self.generate_telemetry(rider_id, sim_time)

            # Evaluate through Decision Coordinator
            eval_state = await self.coordinator.evaluate_rider(telemetry)

            if eval_state.risk_scoring:
                state.current_risk_score = eval_state.risk_scoring.thermal_risk_score
                state.current_risk_tier = eval_state.risk_scoring.risk_tier

            if eval_state.reroute and eval_state.reroute.reroute_recommended:
                state.active_reroute = eval_state.reroute.model_dump(mode="json")
                active_reroutes.append({
                    "rider_id": rider_id,
                    "reroute": eval_state.reroute.model_dump(mode="json"),
                })
                # Auto-record into incident journal
                inc_id = f"INC-{sim_time.replace(':', '')}-{rider_id}-REROUTE"
                if not any(j["incident_id"] == inc_id for j in self.incident_journal):
                    cfg = next((c for c in RIDER_CONFIGS if c["rider_id"] == rider_id), None)
                    r_name = cfg["name"] if cfg else rider_id
                    sel = eval_state.reroute.selected_option
                    entry = {
                        "incident_id": inc_id,
                        "timestamp": sim_time,
                        "rider_id": rider_id,
                        "rider_name": r_name,
                        "aoi_id": state.current_aoi_id or "van_buren_corridor",
                        "incident_type": "SHADED_CORRIDOR_REROUTE",
                        "action_taken": "AUTONOMOUS_REROUTE_ACTIVATED",
                        "surface_temp_c": round(getattr(eval_state.heat_perception, "surface_temp_c", 46.0), 1) if eval_state.heat_perception else 46.0,
                        "heat_index_c": round(getattr(eval_state.heat_perception, "heat_index_c", 48.0), 1) if eval_state.heat_perception else 48.0,
                        "risk_score": round(state.current_risk_score or 0.75, 4),
                        "destination_refuge": getattr(sel, "refuge_name", "Encanto Park Shaded Refuge") if sel else "Encanto Park Shaded Refuge",
                        "delta_temp_c": round(getattr(sel, "delta_temperature_c", -10.8), 1) if sel else -10.8,
                        "detour_distance_km": round(getattr(sel, "distance_km", 2.21), 2) if sel else 2.21,
                        "status": "REROUTED_TO_SHADE",
                    }
                    self.incident_journal.insert(0, entry)

            if eval_state.alert and eval_state.alert.alert_triggered:
                state.last_alert_level = eval_state.alert.alert_level
                active_alerts.append({
                    "rider_id": rider_id,
                    "alert": eval_state.alert.model_dump(mode="json"),
                })
                # Auto-record into incident journal
                is_crit = eval_state.alert.alert_level == "critical"
                inc_id = f"INC-{sim_time.replace(':', '')}-{rider_id}-ALERT"
                if not any(j["incident_id"] == inc_id for j in self.incident_journal):
                    cfg = next((c for c in RIDER_CONFIGS if c["rider_id"] == rider_id), None)
                    r_name = cfg["name"] if cfg else rider_id
                    entry = {
                        "incident_id": inc_id,
                        "timestamp": sim_time,
                        "rider_id": rider_id,
                        "rider_name": r_name,
                        "aoi_id": state.current_aoi_id or "downtown_phoenix",
                        "incident_type": "CRITICAL_HEAT_WARNING" if is_crit else "HEAT_WARNING",
                        "action_taken": "MANDATORY_STOP_REQUIRED" if getattr(eval_state.alert, "mandatory_stop_required", False) else "DETOUR_RECOMMENDED",
                        "surface_temp_c": round(getattr(eval_state.heat_perception, "surface_temp_c", 46.4), 1) if eval_state.heat_perception else 46.4,
                        "heat_index_c": round(getattr(eval_state.heat_perception, "heat_index_c", 48.2), 1) if eval_state.heat_perception else 48.2,
                        "risk_score": round(state.current_risk_score or 0.75, 4),
                        "risk_tier": state.current_risk_tier or ("Critical" if is_crit else "High"),
                        "osha_guideline": getattr(eval_state.alert, "osha_guideline", "") or "Mandatory cooling break and fluid replenishment.",
                        "status": "DISPATCH_ESCALATED" if is_crit else "ADVISORY_ACTIVE",
                    }
                    self.incident_journal.insert(0, entry)

        return FleetSimulationState(
            simulation_time=sim_time,
            riders=self.riders,
            active_alerts=active_alerts,
            active_reroutes=active_reroutes,
        )


__all__ = ["FleetSimulator", "RIDER_CONFIGS"]
