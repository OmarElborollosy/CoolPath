"""Agent 6: Explanation Agent.

Synthesizes multi-agent findings into natural language incident briefs:
- Incident Headline & Scientific Narrative
- Driver Safety Directives
- Fleet Manager OSHA Compliance Reports
- Action Items & Empirical Ground-Truth Evidence
"""
from __future__ import annotations

import logging
from app.schemas.assessments import (
    AlertAssessment,
    ExplanationAssessment,
    HeatPerceptionAssessment,
    RerouteAssessment,
    RiskScoringAssessment,
)
from app.schemas.fleet import RiderTelemetry

logger = logging.getLogger("coolpath.agents.explanation")


class ExplanationAgent:
    """Specialist agent producing natural language explanations and safety reports."""

    async def run(
        self,
        telemetry: RiderTelemetry,
        heat: HeatPerceptionAssessment,
        risk: RiskScoringAssessment,
        reroute: RerouteAssessment | None = None,
        alert: AlertAssessment | None = None,
    ) -> ExplanationAssessment:
        """Generate a complete structured briefing based on multi-agent findings."""
        score = risk.thermal_risk_score
        tier = risk.risk_tier

        headline = f"Rider {telemetry.rider_id}: {tier.upper()} Heat Risk ({score:.2f}) — {risk.osha_heat_category}"

        # Narrative description
        narrative_parts = [
            f"At coordinates ({telemetry.coordinate.lat:.4f}, {telemetry.coordinate.lng:.4f}), "
            f"FortyGuard thermal layers measure a surface temperature of {heat.tile_temperature_c:.1f}°C "
            f"with a Heat Index of {heat.heat_index_c:.1f}°C and {heat.persistence_hours:.1f} hours of continuous high heat persistence."
        ]

        if heat.canopy_percentage <= 10.0:
            narrative_parts.append(
                f"Satellite segmentation indicates critically low tree canopy ({heat.canopy_percentage:.1f}%), "
                f"resulting in extreme direct solar radiation ({heat.solar_irradiance_ghi:.0f} W/m²)."
            )

        if reroute and reroute.reroute_recommended and reroute.selected_option:
            opt = reroute.selected_option
            narrative_parts.append(
                f"Reroute Agent activated {opt.tier_level} micro-refuge cascade, identifying a verified {opt.detour_distance_km:.2f} km "
                f"shaded corridor to {opt.refuge_name}. This delivers a {opt.delta_temperature_c:+.1f}°C temperature reduction "
                f"with {opt.corridor_canopy_pct:.0f}% corridor tree canopy."
            )

        if alert and alert.alert_triggered:
            narrative_parts.append(f"Alert Automation Agent fired a {alert.alert_level.upper()} alert: {alert.title}.")

        briefing_narrative = " ".join(narrative_parts)

        # Driver Safety Brief
        if alert and alert.mandatory_stop_required:
            driver_brief = (
                f"MANDATORY REST STOP REQUIRED IMMEDIATELY. Extreme thermal persistence zone. "
                f"Halt riding, seek air-conditioned building or deep shade, and consume {alert.hydration_oz_recommended} oz water/electrolytes."
            )
        elif reroute and reroute.reroute_recommended and reroute.selected_option:
            driver_brief = (
                f"Take shaded detour to {reroute.selected_option.refuge_name} ({reroute.selected_option.delta_temperature_c:+.1f}°C cooling). "
                f"Drink cool fluids and rest for {alert.cooldown_minutes_recommended if alert else 10} minutes."
            )
        elif alert and alert.alert_triggered:
            driver_brief = (
                f"{alert.title}: Moderate thermal exposure. Maintain steady hydration ({alert.hydration_oz_recommended} oz) "
                f"and take brief shaded breaks."
            )
        else:
            driver_brief = "Thermal conditions are nominal. Continue assigned route with regular hydration."

        # Fleet Manager Brief
        manager_brief = (
            f"Fleet telemetry status for Rider {telemetry.rider_id}: Risk Score {score:.4f} [{tier}], "
            f"Heat Index {heat.heat_index_c:.1f}°C, Speed {telemetry.speed_kmh:.1f} km/h. "
            f"Action taken: {risk.action_required}. "
            f"Compliance status: {'ALERT ESCALATED' if alert and alert.alert_triggered else 'NOMINAL'}."
        )

        # Action Items
        action_items = []
        if alert and alert.osha_guidelines:
            action_items.extend(alert.osha_guidelines)
        if reroute and reroute.reroute_recommended and reroute.selected_option:
            action_items.append(f"Follow navigation to {reroute.selected_option.refuge_name} via {reroute.selected_option.tier_level}.")
        if not action_items:
            action_items.append("Continue current route under standard thermal monitoring.")

        # Scientific Basis
        scientific_basis = [
            f"FortyGuard tOS Enterprise thermal tile readings ({heat.tile_temperature_c:.1f}°C surface).",
            f"FortyGuard persistence metric ({heat.persistence_hours:.1f} consecutive hours > 38°C).",
            f"FortyGuard satellite land-cover segmentation ({heat.canopy_percentage:.1f}% tree canopy).",
            "OSHA Technical Manual (OTM) Section III: Chapter 4 (Heat Stress).",
            "NOAA National Weather Service Heat Index Risk Classification.",
        ]

        return ExplanationAssessment(
            rider_id=telemetry.rider_id,
            summary_headline=headline,
            briefing_narrative=briefing_narrative,
            driver_safety_brief=driver_brief,
            fleet_manager_brief=manager_brief,
            action_items=action_items,
            scientific_basis=scientific_basis,
        )


__all__ = ["ExplanationAgent"]
