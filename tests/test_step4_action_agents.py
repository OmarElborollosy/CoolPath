"""Step 4 Test Suite: Action & Output Agents (Reroute, Alert Automation, Explanation)."""
import pytest
from app.agents.alert_automation import AlertAutomationAgent
from app.agents.coordinator import DecisionCoordinatorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.reroute import RerouteAgent
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.assessments import (
    AlertAssessment,
    ExplanationAssessment,
    HeatPerceptionAssessment,
    RerouteAssessment,
    RiskScoringAssessment,
)
from app.schemas.common import Coordinates
from app.schemas.fleet import RiderTelemetry
from app.services.routing_service import CoolRoutingService


@pytest.fixture
def reroute_agent():
    return RerouteAgent()


@pytest.fixture
def alert_agent():
    return AlertAutomationAgent()


@pytest.fixture
def explanation_agent():
    return ExplanationAgent()


@pytest.fixture
def coordinator():
    return DecisionCoordinatorAgent()


@pytest.mark.asyncio
async def test_reroute_agent_spatial_cascade_and_delta_t(reroute_agent):
    """Verify RerouteAgent executes spatial cascade and computes temperature reduction."""
    # Rider in Downtown Phoenix
    coord = PHOENIX_AOIS["downtown_phoenix"].center
    telemetry = RiderTelemetry(
        rider_id="R_DOWNTOWN",
        timestamp="14:00",
        coordinate=coord,
        speed_kmh=15.0,
        current_aoi_id="downtown_phoenix",
    )

    heat = HeatPerceptionAssessment(
        rider_id="R_DOWNTOWN",
        coordinate=coord,
        tile_temperature_c=43.0,
        heat_index_c=45.0,
        apparent_temperature_c=43.5,
        wet_bulb_c=22.4,
        relative_humidity_pct=21.0,
        solar_irradiance_ghi=880.0,
        aqi=62.0,
        persistence_hours=6.5,
        exceedance_hours=8.0,
    )

    risk = RiskScoringAssessment(
        rider_id="R_DOWNTOWN",
        thermal_risk_score=0.62,
        risk_tier="High",
        osha_heat_category="Danger",
        norm_heat_index=0.66,
        norm_persistence=0.54,
        norm_solar=0.88,
        norm_aqi=0.31,
        action_required="reroute",
    )

    reroute = await reroute_agent.run(telemetry, heat, risk)
    assert reroute.reroute_recommended is True
    assert reroute.selected_option is not None
    assert reroute.selected_option.delta_temperature_c < 0.0  # Cooling achieved
    assert reroute.selected_option.refuge_score > 0.0
    assert len(reroute.all_evaluated_options) >= 1


@pytest.mark.asyncio
async def test_alert_automation_hard_gate_levels(alert_agent):
    """Verify multi-tier alert state machine (Advisory / Warning / Critical)."""
    telemetry = RiderTelemetry(
        rider_id="R_ALERT",
        timestamp="14:00",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
        speed_kmh=10.0,
    )
    heat = HeatPerceptionAssessment(
        rider_id="R_ALERT",
        coordinate=telemetry.coordinate,
        tile_temperature_c=46.2,
        heat_index_c=48.9,
        apparent_temperature_c=47.5,
        wet_bulb_c=23.8,
        relative_humidity_pct=19.0,
        solar_irradiance_ghi=920.0,
        aqi=78.0,
        persistence_hours=9.5,
        exceedance_hours=11.5,
    )

    # 1. Critical Risk (>= 0.75)
    risk_crit = RiskScoringAssessment(
        rider_id="R_ALERT",
        thermal_risk_score=0.78,
        risk_tier="Critical",
        osha_heat_category="Extreme Danger",
        norm_heat_index=0.81,
        norm_persistence=0.79,
        norm_solar=0.92,
        norm_aqi=0.39,
        action_required="mandatory_stop",
    )
    alert_crit = await alert_agent.run(telemetry, heat, risk_crit)
    assert alert_crit.alert_triggered is True
    assert alert_crit.alert_level == "critical"
    assert alert_crit.mandatory_stop_required is True
    assert alert_crit.cooldown_minutes_recommended == 20
    assert alert_crit.hydration_oz_recommended == 24
    assert alert_crit.dispatch_escalated is True

    # 2. High Risk (>= 0.55)
    risk_high = RiskScoringAssessment(
        rider_id="R_ALERT",
        thermal_risk_score=0.60,
        risk_tier="High",
        osha_heat_category="Danger",
        norm_heat_index=0.65,
        norm_persistence=0.50,
        norm_solar=0.85,
        norm_aqi=0.30,
        action_required="reroute",
    )
    alert_high = await alert_agent.run(telemetry, heat, risk_high)
    assert alert_high.alert_triggered is True
    assert alert_high.alert_level == "warning"
    assert alert_high.mandatory_stop_required is False
    assert alert_high.cooldown_minutes_recommended == 10

    # 3. Moderate Risk (>= 0.35)
    risk_mod = RiskScoringAssessment(
        rider_id="R_ALERT",
        thermal_risk_score=0.42,
        risk_tier="Moderate",
        osha_heat_category="Caution",
        norm_heat_index=0.40,
        norm_persistence=0.30,
        norm_solar=0.70,
        norm_aqi=0.25,
        action_required="advisory",
    )
    alert_mod = await alert_agent.run(telemetry, heat, risk_mod)
    assert alert_mod.alert_triggered is True
    assert alert_mod.alert_level == "advisory"


@pytest.mark.asyncio
async def test_explanation_agent_briefing_synthesis(explanation_agent):
    """Verify ExplanationAgent produces complete natural language debrief."""
    coord = PHOENIX_AOIS["van_buren_corridor"].center
    tel = RiderTelemetry(rider_id="R3", timestamp="14:15", coordinate=coord, speed_kmh=8.0)
    heat = HeatPerceptionAssessment(
        rider_id="R3",
        coordinate=coord,
        tile_temperature_c=46.4,
        heat_index_c=48.2,
        apparent_temperature_c=46.8,
        wet_bulb_c=23.8,
        relative_humidity_pct=19.0,
        solar_irradiance_ghi=920.0,
        aqi=78.0,
        persistence_hours=9.7,
        exceedance_hours=11.7,
        canopy_percentage=1.2,
        street_shade_percentage=4.0,
    )
    risk = RiskScoringAssessment(
        rider_id="R3",
        thermal_risk_score=0.76,
        risk_tier="Critical",
        osha_heat_category="Extreme Danger",
        norm_heat_index=0.79,
        norm_persistence=0.81,
        norm_solar=0.92,
        norm_aqi=0.39,
        action_required="mandatory_stop",
    )
    alert = AlertAssessment(
        rider_id="R3",
        alert_triggered=True,
        alert_level="critical",
        title="CRITICAL HEAT WARNING",
        message="Immediate stop required.",
        mandatory_stop_required=True,
        hydration_oz_recommended=24,
    )

    explanation = await explanation_agent.run(tel, heat, risk, alert=alert)
    assert "CRITICAL" in explanation.summary_headline.upper()
    assert len(explanation.briefing_narrative) > 50
    assert "MANDATORY REST STOP" in explanation.driver_safety_brief.upper()
    assert "FLEET TELEMETRY STATUS" in explanation.fleet_manager_brief.upper()
    assert len(explanation.scientific_basis) >= 3


@pytest.mark.asyncio
async def test_end_to_end_scenarios_r3_and_r6(coordinator):
    """Verify full end-to-end pipeline execution for Rider R3 (alert trigger) and Rider R6 (reroute trigger)."""
    # Rider R3: Locked in Van Buren Corridor (Critical Alert Trigger)
    tel_r3 = RiderTelemetry(
        rider_id="R3",
        timestamp="14:15",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
        speed_kmh=8.0,
        current_aoi_id="van_buren_corridor",
    )
    state_r3 = await coordinator.evaluate_rider(tel_r3)
    assert state_r3.risk_scoring.thermal_risk_score >= 0.75
    assert state_r3.alert.alert_level == "critical"
    assert state_r3.alert.mandatory_stop_required is True

    # Rider R6: Van Buren -> Encanto Park (Reroute Trigger)
    tel_r6 = RiderTelemetry(
        rider_id="R6",
        timestamp="15:40",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
        speed_kmh=12.0,
        current_aoi_id="van_buren_corridor",
        assigned_route=["van_buren_corridor", "encanto_park"],
    )
    state_r6 = await coordinator.evaluate_rider(tel_r6)
    assert state_r6.reroute is not None
    assert state_r6.reroute.reroute_recommended is True
    assert state_r6.reroute.selected_option is not None
    assert state_r6.reroute.selected_option.delta_temperature_c < 0.0
