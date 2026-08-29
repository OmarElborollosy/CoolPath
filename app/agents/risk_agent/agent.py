"""Agent 2: Risk Scoring Agent."""
from __future__ import annotations

import logging
from typing import Any
from app.agents.risk_agent.rules import evaluate_risk_rules
from app.schemas.assessments import HeatPerceptionAssessment, RiskScoringAssessment

logger = logging.getLogger("coolpath.agents.risk_scoring")


class RiskScoringAgent:
    """Specialist agent calculating worker thermal exposure and safety tiers."""

    async def run(
        self,
        heat: HeatPerceptionAssessment,
        continuous_exposure_minutes: float = 0.0,
    ) -> RiskScoringAssessment:
        """Compute the thermal risk score for the rider."""
        score_res = evaluate_risk_rules(
            heat_index_c=heat.heat_index_c,
            persistence_hours=heat.persistence_hours,
            ghi_w_m2=heat.solar_irradiance_ghi,
            aqi=heat.aqi,
            continuous_exposure_minutes=continuous_exposure_minutes,
        )

        risk_factors: list[str] = []
        if heat.tile_temperature_c >= 42.0:
            risk_factors.append(f"extreme_surface_temperature_{heat.tile_temperature_c:.1f}C")
        if heat.heat_index_c >= 40.0:
            risk_factors.append(f"severe_heat_index_{heat.heat_index_c:.1f}C")
        if heat.persistence_hours >= 6.0:
            risk_factors.append(f"prolonged_persistence_{heat.persistence_hours:.1f}hrs_above_threshold")
        if heat.solar_irradiance_ghi >= 850.0:
            risk_factors.append(f"intense_solar_radiation_{heat.solar_irradiance_ghi:.0f}W_m2")
        if heat.canopy_percentage <= 5.0:
            risk_factors.append("unshaded_open_asphalt_corridor")
        if heat.aqi >= 70.0:
            risk_factors.append(f"elevated_pollution_aqi_{heat.aqi:.0f}")
        if continuous_exposure_minutes > 30.0:
            risk_factors.append(f"prolonged_continuous_exposure_{continuous_exposure_minutes:.0f}min")

        assessment = RiskScoringAssessment(
            rider_id=heat.rider_id,
            thermal_risk_score=score_res["thermal_risk_score"],
            risk_tier=score_res["risk_tier"],
            osha_heat_category=score_res["osha_heat_category"],
            norm_heat_index=score_res["norm_heat_index"],
            norm_persistence=score_res["norm_persistence"],
            norm_solar=score_res["norm_solar"],
            norm_aqi=score_res["norm_aqi"],
            breakdown=score_res["breakdown"],
            risk_factors=risk_factors,
            action_required=score_res["action_required"],
            confidence=1.0,
        )
        return assessment


__all__ = ["RiskScoringAgent"]
