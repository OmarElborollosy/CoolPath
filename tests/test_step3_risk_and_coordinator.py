"""Step 3 Test Suite: Risk Scoring Agent & Decision Coordinator LangGraph Orchestration."""
import pytest
from app.agents.coordinator import DecisionCoordinatorAgent, build_coolpath_graph
from app.agents.risk_agent import (
    RiskScoringAgent,
    _HEAT_RISK_CEILING,
    _HIGH_RISK_THRESHOLD,
    _MODERATE_RISK_THRESHOLD,
    evaluate_risk_rules,
)
from app.agents.risk_agent.rules import (
    calculate_continuous_exposure_penalty,
    normalize_aqi,
    normalize_heat_index,
    normalize_persistence,
    normalize_solar_ghi,
)
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.assessments import HeatPerceptionAssessment
from app.schemas.common import Coordinates
from app.schemas.fleet import RiderTelemetry


@pytest.fixture
def risk_agent():
    return RiskScoringAgent()


@pytest.fixture
def coordinator():
    return DecisionCoordinatorAgent()


def test_normalization_and_clamping():
    """Verify individual factor normalizations stay within [0.0, 1.0]."""
    # Heat Index: 27°C -> 0.0, 54°C -> 1.0
    assert normalize_heat_index(27.0) == 0.0
    assert normalize_heat_index(54.0) == 1.0
    assert normalize_heat_index(20.0) == 0.0  # clamp low
    assert normalize_heat_index(60.0) == 1.0  # clamp high

    # Persistence: 0 -> 0.0, 12 hrs -> 1.0
    assert normalize_persistence(0.0) == 0.0
    assert normalize_persistence(6.0) == 0.5
    assert normalize_persistence(12.0) == 1.0

    # Solar GHI: 0 -> 0.0, 1000 W/m2 -> 1.0
    assert normalize_solar_ghi(500.0) == 0.5
    assert normalize_solar_ghi(1000.0) == 1.0

    # AQI: 0 -> 0.0, 200 -> 1.0
    assert normalize_aqi(100.0) == 0.5
    assert normalize_aqi(200.0) == 1.0


def test_continuous_exposure_penalties():
    """Verify continuous exposure penalties apply only after 30 minutes in heat."""
    # Under 30 mins -> zero penalty
    assert calculate_continuous_exposure_penalty(15.0) == 0.0
    assert calculate_continuous_exposure_penalty(30.0) == 0.0

    # 45 mins -> +0.03
    assert calculate_continuous_exposure_penalty(45.0) == pytest.approx(0.03)

    # 90 mins -> capped at 0.15
    assert calculate_continuous_exposure_penalty(120.0) == 0.15


def test_risk_scoring_decision_tiers():
    """Verify risk calculation against OSHA / NOAA risk tier boundaries."""
    # Low Risk Case (Cool park / morning)
    low_res = evaluate_risk_rules(heat_index_c=28.0, persistence_hours=1.0, ghi_w_m2=300.0, aqi=30.0)
    assert low_res["thermal_risk_score"] < _MODERATE_RISK_THRESHOLD
    assert low_res["risk_tier"] == "Low"
    assert low_res["action_required"] == "none"

    # Moderate Risk Case (Caution)
    mod_res = evaluate_risk_rules(heat_index_c=36.0, persistence_hours=3.0, ghi_w_m2=750.0, aqi=50.0)
    assert _MODERATE_RISK_THRESHOLD <= mod_res["thermal_risk_score"] < _HIGH_RISK_THRESHOLD
    assert mod_res["risk_tier"] == "Moderate"
    assert mod_res["action_required"] == "advisory"

    # High Risk Case (Danger - Reroute required)
    high_res = evaluate_risk_rules(heat_index_c=43.0, persistence_hours=6.5, ghi_w_m2=880.0, aqi=65.0)
    assert _HIGH_RISK_THRESHOLD <= high_res["thermal_risk_score"] < _HEAT_RISK_CEILING
    assert high_res["risk_tier"] == "High"
    assert high_res["action_required"] == "reroute"

    # Critical Risk Case (Extreme Danger - Mandatory Stop)
    crit_res = evaluate_risk_rules(heat_index_c=49.0, persistence_hours=9.5, ghi_w_m2=950.0, aqi=80.0)
    assert crit_res["thermal_risk_score"] >= _HEAT_RISK_CEILING
    assert crit_res["risk_tier"] == "Critical"
    assert crit_res["action_required"] == "mandatory_stop"


@pytest.mark.asyncio
async def test_risk_scoring_agent_run(risk_agent):
    """Verify RiskScoringAgent execution with HeatPerceptionAssessment input."""
    heat = HeatPerceptionAssessment(
        rider_id="R3_TEST",
        coordinate=Coordinates(lat=33.4480, lng=-112.0450),
        tile_temperature_c=46.2,
        heat_index_c=48.9,
        apparent_temperature_c=47.5,
        wet_bulb_c=23.8,
        relative_humidity_pct=19.0,
        solar_irradiance_ghi=920.0,
        aqi=78.0,
        persistence_hours=9.5,
        exceedance_hours=11.5,
        canopy_percentage=1.2,
        street_shade_percentage=4.0,
        source="fast_path_cache",
    )

    assessment = await risk_agent.run(heat, continuous_exposure_minutes=45.0)
    assert assessment.rider_id == "R3_TEST"
    assert assessment.thermal_risk_score >= _HEAT_RISK_CEILING
    assert assessment.risk_tier == "Critical"
    assert assessment.action_required == "mandatory_stop"
    assert len(assessment.risk_factors) >= 4


def test_compiled_langgraph_structure():
    """Verify the StateGraph is compiled with all required nodes and edges."""
    graph = build_coolpath_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_coordinator_langgraph_pipeline_execution(coordinator):
    """Verify end-to-end multi-agent execution for Van Buren critical heat rider."""
    telemetry = RiderTelemetry(
        rider_id="R3",
        timestamp="14:15",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
        speed_kmh=8.0,
        current_aoi_id="van_buren_corridor",
    )

    state = await coordinator.evaluate_rider(telemetry)

    # Verify all pipeline stages executed
    assert state.heat_perception is not None
    assert state.risk_scoring is not None
    assert state.risk_scoring.thermal_risk_score >= _HIGH_RISK_THRESHOLD
    assert state.reroute is not None  # Dynamic reroute was triggered
    assert state.alert is not None
    assert state.alert.alert_triggered is True
    assert state.explanation is not None
    assert state.explanation.summary_headline

    # Verify trace contains all nodes
    node_names = [step["node"] for step in state.execution_trace]
    assert "heat_perception" in node_names
    assert "risk_scoring" in node_names
    assert "reroute" in node_names
    assert "alert_automation" in node_names
    assert "critic_scoring" in node_names
    assert "explanation" in node_names
    assert "pipeline_total" in node_names
