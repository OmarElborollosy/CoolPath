"""Agent 5: Alert Automation Agent.

Responsible for:
1. Evaluating worker safety thresholds and escalating autonomous alerts.
2. Managing the Multi-Tier Safety Alert State Machine (Advisory / Warning / Critical).
3. Enforcing OSHA mandatory cooling breaks when risk is critical or no refuge is reachable.
"""
from __future__ import annotations

import logging
from app.schemas.assessments import (
    AlertAssessment,
    HeatPerceptionAssessment,
    RerouteAssessment,
    RiskScoringAssessment,
)
from app.schemas.fleet import RiderTelemetry

logger = logging.getLogger("coolpath.agents.alert_automation")


class AlertAutomationAgent:
    """Specialist agent managing real-time heat hazard alerting and mandatory interventions."""

    async def run(
        self,
        telemetry: RiderTelemetry,
        heat: HeatPerceptionAssessment,
        risk: RiskScoringAssessment,
        reroute: RerouteAssessment | None = None,
    ) -> AlertAssessment:
        """Evaluate whether to fire an autonomous worker safety alert."""
        score = risk.thermal_risk_score
        no_refuge = reroute is not None and reroute.status == "no_refuge_found"

        # Tier 4 Safe Fail / Critical Threshold
        if score >= 0.75 or (score >= 0.55 and no_refuge):
            # Critical Mandatory Stop Alert
            title = "CRITICAL HEAT WARNING — MANDATORY REST STOP"
            message = (
                f"Rider {telemetry.rider_id} is in an extreme danger thermal zone ({heat.heat_index_c:.1f}°C heat index, "
                f"{heat.persistence_hours:.1f} hrs continuous heat persistence). "
                f"Immediate delivery halt required. Seek immediate indoor air conditioning or shaded shelter."
            )
            osha_rules = [
                "OSHA Heat Illness Prevention: Mandatory 20-minute rest cooldown immediately.",
                "Hydrate with at least 24 oz cool electrolyte fluids.",
                "Do not resume cycling until core temperature stabilizes and manager acknowledges.",
            ]
            return AlertAssessment(
                rider_id=telemetry.rider_id,
                alert_triggered=True,
                alert_level="critical",
                title=title,
                message=message,
                osha_guidelines=osha_rules,
                mandatory_stop_required=True,
                cooldown_minutes_recommended=20,
                hydration_oz_recommended=24,
                dispatch_escalated=True,
            )

        elif score >= 0.55:
            # High Warning Alert
            title = "HIGH HEAT ALERT — SHADED DETOUR RECOMMENDED"
            message = (
                f"High thermal exposure detected ({heat.tile_temperature_c:.1f}°C surface, {heat.solar_irradiance_ghi:.0f} W/m² solar). "
                f"Reroute Agent has identified a shaded corridor to reduce heat burden."
            )
            osha_rules = [
                "OSHA Standard: Increase fluid intake to 1 cup (8 oz) every 15-20 minutes.",
                "Take a 10-minute rest in shade along the detour route.",
            ]
            return AlertAssessment(
                rider_id=telemetry.rider_id,
                alert_triggered=True,
                alert_level="warning",
                title=title,
                message=message,
                osha_guidelines=osha_rules,
                mandatory_stop_required=False,
                cooldown_minutes_recommended=10,
                hydration_oz_recommended=16,
                dispatch_escalated=False,
            )

        elif score >= 0.35:
            # Moderate Advisory
            title = "HEAT CAUTION ADVISORY"
            message = f"Moderate thermal conditions ({heat.heat_index_c:.1f}°C heat index). Stay hydrated."
            osha_rules = [
                "Drink 16 oz water hourly.",
                "Monitor for early symptoms of heat exhaustion (dizziness, excessive sweating).",
            ]
            return AlertAssessment(
                rider_id=telemetry.rider_id,
                alert_triggered=True,
                alert_level="advisory",
                title=title,
                message=message,
                osha_guidelines=osha_rules,
                mandatory_stop_required=False,
                cooldown_minutes_recommended=5,
                hydration_oz_recommended=12,
                dispatch_escalated=False,
            )

        # Low Risk
        return AlertAssessment(
            rider_id=telemetry.rider_id,
            alert_triggered=False,
            alert_level="none",
            title="",
            message="Thermal risk within normal parameters.",
            osha_guidelines=[],
            mandatory_stop_required=False,
            cooldown_minutes_recommended=0,
            hydration_oz_recommended=0,
            dispatch_escalated=False,
        )
