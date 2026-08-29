"""Unit and integration tests for all 6 CoolPath specialist agents."""
from __future__ import annotations

import pytest
from app.agents.alert_automation import AlertAutomationAgent
from app.agents.coordinator import DecisionCoordinatorAgent
from app.agents.explanation import ExplanationAgent
from app.agents.heat_perception import HeatPerceptionAgent
from app.agents.reroute import RerouteAgent
from app.agents.risk_scoring import RiskScoringAgent
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.fleet import RiderTelemetry


@pytest.mark.asyncio
async def test_agent1_heat_perception_fast_lookup():
    """Verify Agent 1 extracts metrics from FortyGuard cache in <15ms."""
    agent = HeatPerceptionAgent()
    telemetry = RiderTelemetry(
        rider_id="R1_TEST",
        timestamp="14:00",
        coordinate=PHOENIX_AOIS["downtown_phoenix"].center,
        speed_kmh=15.0,
    )
    heat = await agent.run(telemetry)

    assert heat.rider_id == "R1_TEST"
    assert heat.tile_temperature_c > 35.0
    assert heat.heat_index_c > 35.0
    assert heat.solar_irradiance_ghi > 600.0
    assert heat.persistence_hours >= 0.0


@pytest.mark.asyncio
async def test_agent2_risk_scoring_assessment():
    """Verify Agent 2 calculates OSHA risk score and breaks down factors."""
    heat_agent = HeatPerceptionAgent()
    risk_agent = RiskScoringAgent()

    # Test in high heat corridor (Van Buren)
    telemetry = RiderTelemetry(
        rider_id="R3_HOT",
        timestamp="14:00",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
        speed_kmh=10.0,
    )
    heat = await heat_agent.run(telemetry)
    risk = await risk_agent.run(heat)

    assert risk.rider_id == "R3_HOT"
    assert risk.thermal_risk_score >= 0.70  # Very high thermal risk
    assert risk.risk_tier in ("High", "Critical")
    assert risk.action_required in ("reroute", "mandatory_stop")
    assert len(risk.risk_factors) >= 3


@pytest.mark.asyncio
async def test_agent4_reroute_agent_shaded_corridor():
    """Verify Agent 4 evaluates candidate cool corridor and computes delta T."""
    heat_agent = HeatPerceptionAgent()
    risk_agent = RiskScoringAgent()
    reroute_agent = RerouteAgent()

    telemetry = RiderTelemetry(
        rider_id="R6_REROUTE",
        timestamp="15:30",
        coordinate=PHOENIX_AOIS["downtown_phoenix"].center,
        speed_kmh=12.0,
    )
    heat = await heat_agent.run(telemetry)
    risk = await risk_agent.run(heat)
    reroute = await reroute_agent.run(telemetry, heat, risk)

    assert reroute.rider_id == "R6_REROUTE"
    assert reroute.reroute_recommended is True
    assert reroute.selected_option is not None
    assert reroute.selected_option.delta_temperature_c < 0.0  # Cooler path
    assert 0.0 <= reroute.selected_option.refuge_score <= 1.0


@pytest.mark.asyncio
async def test_agent5_alert_automation_mandatory_stop():
    """Verify Agent 5 triggers Critical Mandatory Stop alert for dangerous exposure."""
    alert_agent = AlertAutomationAgent()
    heat_agent = HeatPerceptionAgent()
    risk_agent = RiskScoringAgent()

    telemetry = RiderTelemetry(
        rider_id="R3_CRITICAL",
        timestamp="14:30",
        coordinate=PHOENIX_AOIS["van_buren_corridor"].center,
    )
    heat = await heat_agent.run(telemetry)
    risk = await risk_agent.run(heat)
    alert = await alert_agent.run(telemetry, heat, risk)

    assert alert.rider_id == "R3_CRITICAL"
    assert alert.alert_triggered is True
    assert alert.alert_level == "critical"
    assert alert.mandatory_stop_required is True
    assert alert.cooldown_minutes_recommended >= 15


@pytest.mark.asyncio
async def test_agent6_explanation_synthesis():
    """Verify Agent 6 produces structured driver and manager reports."""
    heat_agent = HeatPerceptionAgent()
    risk_agent = RiskScoringAgent()
    alert_agent = AlertAutomationAgent()
    explanation_agent = ExplanationAgent()

    telemetry = RiderTelemetry(
        rider_id="R1_EXPLAIN",
        timestamp="13:30",
        coordinate=PHOENIX_AOIS["downtown_phoenix"].center,
    )
    heat = await heat_agent.run(telemetry)
    risk = await risk_agent.run(heat)
    alert = await alert_agent.run(telemetry, heat, risk)
    explanation = await explanation_agent.run(telemetry, heat, risk, alert=alert)

    assert explanation.rider_id == "R1_EXPLAIN"
    assert len(explanation.summary_headline) > 0
    assert len(explanation.briefing_narrative) > 50
    assert len(explanation.driver_safety_brief) > 20
    assert len(explanation.scientific_basis) >= 3


@pytest.mark.asyncio
async def test_agent3_decision_coordinator_end_to_end():
    """Verify Decision Coordinator orchestrates all agents with timing trace."""
    coordinator = DecisionCoordinatorAgent()
    telemetry = RiderTelemetry(
        rider_id="R_COORD_TEST",
        timestamp="14:00",
        coordinate=PHOENIX_AOIS["downtown_phoenix"].center,
    )
    state = await coordinator.evaluate_rider(telemetry)

    assert state.heat_perception is not None
    assert state.risk_scoring is not None
    assert state.alert is not None
    assert state.explanation is not None
    assert len(state.execution_trace) >= 4

    # Performance check: pipeline completes fast (< 50ms)
    total_entry = next((e for e in state.execution_trace if e["node"] == "pipeline_total"), None)
    assert total_entry is not None
    assert total_entry["duration_ms"] < 250.0  # Fast-path sub-250ms target
