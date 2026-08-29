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

            if eval_state.alert and eval_state.alert.alert_triggered:
                state.last_alert_level = eval_state.alert.alert_level
                active_alerts.append({
                    "rider_id": rider_id,
                    "alert": eval_state.alert.model_dump(mode="json"),
                })

        return FleetSimulationState(
            simulation_time=sim_time,
            riders=self.riders,
            active_alerts=active_alerts,
            active_reroutes=active_reroutes,
        )


__all__ = ["FleetSimulator", "RIDER_CONFIGS"]
