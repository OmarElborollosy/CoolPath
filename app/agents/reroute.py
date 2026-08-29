"""Agent 4: Reroute Agent (Cool Corridor & Refuge Finder).

Responsible for:
1. Executing the 300m -> 1km -> 3km micro-refuge spatial cascade.
2. Sampling temperature and FortyGuard satellite canopy along the candidate route polyline (every ~175m).
3. Computing clamped [0.0, 1.0] Refuge Scores and thermal delta T (°C reduction).
4. Generating actionable shaded detours to cool refuges (e.g. Encanto Park).
"""
from __future__ import annotations

import logging
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.assessments import (
    HeatPerceptionAssessment,
    RerouteAssessment,
    RiskScoringAssessment,
)
from app.schemas.fleet import RiderTelemetry
from app.services.routing_service import CoolRoutingService

logger = logging.getLogger("coolpath.agents.reroute")


class RerouteAgent:
    """Specialist agent planning heat-mitigating route diversions."""

    def __init__(self, routing_service: CoolRoutingService | None = None) -> None:
        self.routing_service = routing_service or CoolRoutingService()

    async def run(
        self,
        telemetry: RiderTelemetry,
        heat: HeatPerceptionAssessment,
        risk: RiskScoringAssessment,
    ) -> RerouteAssessment:
        """Find the optimal cool detour for an at-risk rider."""
        # Only seek reroute if risk score >= 0.55 (High or Critical) or action_required in (reroute, mandatory_stop)
        if risk.thermal_risk_score < 0.55 and risk.action_required not in ("reroute", "mandatory_stop"):
            return RerouteAssessment(
                rider_id=telemetry.rider_id,
                reroute_recommended=False,
                selected_option=None,
                all_evaluated_options=[],
                cascade_tier_used="not_needed",
                tradeoff_summary="Current route risk is acceptable; no cool detour needed.",
                status="not_needed",
            )

        destination_coord = None
        if telemetry.assigned_route:
            last_aoi_id = telemetry.assigned_route[-1]
            if last_aoi_id in PHOENIX_AOIS:
                destination_coord = PHOENIX_AOIS[last_aoi_id].center

        best_option, all_options, tier_used = self.routing_service.find_cool_refuge_detour(
            current_coord=telemetry.coordinate,
            destination_coord=destination_coord,
            baseline_temp_c=heat.tile_temperature_c,
        )

        if not best_option:
            return RerouteAssessment(
                rider_id=telemetry.rider_id,
                reroute_recommended=False,
                selected_option=None,
                all_evaluated_options=all_options,
                cascade_tier_used=tier_used,
                tradeoff_summary="No qualified shaded refuge located within diversion radius.",
                status="no_refuge_found",
            )

        tradeoff = (
            f"Recommended {best_option.detour_distance_km:.2f} km shaded detour to {best_option.refuge_name} "
            f"via {tier_used}: provides {best_option.delta_temperature_c:+.1f}°C temperature reduction "
            f"({best_option.corridor_canopy_pct:.0f}% corridor canopy, {best_option.street_shade_pct:.0f}% destination shade) "
            f"for +{best_option.estimated_extra_minutes:.1f} min transit."
        )

        return RerouteAssessment(
            rider_id=telemetry.rider_id,
            reroute_recommended=True,
            selected_option=best_option,
            all_evaluated_options=all_options,
            cascade_tier_used=tier_used,
            tradeoff_summary=tradeoff,
            status="success",
        )


__all__ = ["RerouteAgent"]
