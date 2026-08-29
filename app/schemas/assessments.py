"""Assessments produced by the 6 specialist agents."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from .common import Coordinates


class HeatPerceptionAssessment(BaseModel):
    """Output of Agent 1: Heat Perception."""
    rider_id: str
    coordinate: Coordinates
    matched_tile_id: str | None = None
    tile_temperature_c: float
    heat_index_c: float
    apparent_temperature_c: float
    wet_bulb_c: float
    relative_humidity_pct: float
    solar_irradiance_ghi: float
    aqi: float
    persistence_hours: float = Field(default=0.0, description="FortyGuard persistence metric")
    exceedance_hours: float = Field(default=0.0, description="FortyGuard exceedance metric")
    canopy_percentage: float = 0.0
    street_shade_percentage: float = 0.0
    source: str = "cache_read"
    confidence: float = 1.0
    is_synthesized: bool = Field(
        default=False,
        description="True if any underlying FortyGuard call returned synthesized (non-live) data.",
    )
    data_source_summary: dict[str, str] = Field(
        default_factory=dict,
        description="Per-field data provenance: 'live' or 'synthesized_baseline' for each FortyGuard layer.",
    )
    spatial_resolution: str = Field(
        default="exact_coordinate",
        description="Whether data reflects exact coordinate or snapped to an anchor tile centroid.",
    )
    status: str = "success"



class RiskScoringAssessment(BaseModel):
    """Output of Agent 2: Risk Scoring."""
    rider_id: str
    thermal_risk_score: float = Field(ge=0.0, le=1.0, description="Normalized risk score 0.0 to 1.0")
    risk_tier: str = Field(description="Low (<0.35), Moderate (0.35-0.54), High (0.55-0.74), Critical (>=0.75)")
    osha_heat_category: str = Field(description="Caution, Extreme Caution, Danger, Extreme Danger")
    norm_heat_index: float
    norm_persistence: float
    norm_solar: float
    norm_aqi: float
    breakdown: dict[str, float] = Field(default_factory=dict)
    risk_factors: list[str] = Field(default_factory=list)
    action_required: str = Field(description="none, advisory, reroute, mandatory_stop")
    confidence: float = 1.0


class RerouteOption(BaseModel):
    """Candidate route evaluated by Agent 4: Reroute."""
    option_id: str
    refuge_name: str
    refuge_coordinate: Coordinates
    detour_distance_km: float
    estimated_extra_minutes: float
    corridor_mean_temp_c: float
    corridor_canopy_pct: float
    street_shade_pct: float
    delta_temperature_c: float = Field(description="Temperature drop compared to original path (negative is cooler)")
    raw_refuge_score: float
    refuge_score: float = Field(ge=0.0, le=1.0, description="Clamped [0.0, 1.0] refuge quality score")
    polyline: list[Coordinates] = Field(default_factory=list)
    tier_level: str = Field(description="tier1_300m, tier2_1km, tier3_3km")


class RerouteAssessment(BaseModel):
    """Output of Agent 4: Reroute."""
    rider_id: str
    reroute_recommended: bool
    selected_option: RerouteOption | None = None
    all_evaluated_options: list[RerouteOption] = Field(default_factory=list)
    cascade_tier_used: str = "none"
    tradeoff_summary: str = ""
    status: str = "success"  # success, no_refuge_found, not_needed


class AlertAssessment(BaseModel):
    """Output of Agent 5: Alert Automation."""
    rider_id: str
    alert_triggered: bool
    alert_level: str = "none"  # none, advisory, warning, critical
    title: str = ""
    message: str = ""
    osha_guidelines: list[str] = Field(default_factory=list)
    mandatory_stop_required: bool = False
    cooldown_minutes_recommended: int = 0
    hydration_oz_recommended: int = 0
    dispatch_escalated: bool = False


class ExplanationAssessment(BaseModel):
    """Output of Agent 6: Explanation."""
    rider_id: str
    summary_headline: str
    briefing_narrative: str
    driver_safety_brief: str
    fleet_manager_brief: str
    action_items: list[str] = Field(default_factory=list)
    scientific_basis: list[str] = Field(default_factory=list)
