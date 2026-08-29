"""LangGraph node execution functions for CoolPath."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.alert_automation import AlertAutomationAgent
from app.agents.explanation import ExplanationAgent
from app.agents.heat_perception import HeatPerceptionAgent
from app.agents.reroute import RerouteAgent
from app.agents.risk_scoring import RiskScoringAgent
from app.schemas.graph_state import CoolPathGraphState

logger = logging.getLogger("coolpath.coordinator.nodes")


async def heat_perception_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Agent 1: Heat Perception."""
    t0 = time.perf_counter()
    agent = HeatPerceptionAgent()
    heat = await agent.run(state.rider_telemetry)
    duration = round((time.perf_counter() - t0) * 1000, 2)

    trace_entry = {
        "node": "heat_perception",
        "status": heat.status,
        "duration_ms": duration,
    }
    return {
        "heat_perception": heat,
        "execution_trace": state.execution_trace + [trace_entry],
    }


async def risk_scoring_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Agent 2: Risk Scoring."""
    t0 = time.perf_counter()
    if not state.heat_perception:
        return {"errors": state.errors + ["Missing heat perception data for risk scoring"]}

    agent = RiskScoringAgent()
    risk = await agent.run(state.heat_perception)
    duration = round((time.perf_counter() - t0) * 1000, 2)

    trace_entry = {
        "node": "risk_scoring",
        "status": "success",
        "duration_ms": duration,
    }
    return {
        "risk_scoring": risk,
        "execution_trace": state.execution_trace + [trace_entry],
    }


async def reroute_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Agent 4: Shaded Corridor Reroute."""
    t0 = time.perf_counter()
    if not state.heat_perception or not state.risk_scoring:
        return {"errors": state.errors + ["Missing prerequisites for reroute agent"]}

    agent = RerouteAgent()
    reroute = await agent.run(state.rider_telemetry, state.heat_perception, state.risk_scoring)
    duration = round((time.perf_counter() - t0) * 1000, 2)

    trace_entry = {
        "node": "reroute",
        "status": "success",
        "duration_ms": duration,
    }
    return {
        "reroute": reroute,
        "selected_agents": state.selected_agents + ["reroute"] if "reroute" not in state.selected_agents else state.selected_agents,
        "execution_trace": state.execution_trace + [trace_entry],
    }


async def alert_automation_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Agent 5: Alert Automation."""
    t0 = time.perf_counter()
    if not state.heat_perception or not state.risk_scoring:
        return {"errors": state.errors + ["Missing prerequisites for alert automation agent"]}

    agent = AlertAutomationAgent()
    alert = await agent.run(state.rider_telemetry, state.heat_perception, state.risk_scoring, state.reroute)
    duration = round((time.perf_counter() - t0) * 1000, 2)

    trace_entry = {
        "node": "alert_automation",
        "status": "success",
        "duration_ms": duration,
    }
    return {
        "alert": alert,
        "selected_agents": state.selected_agents + ["alert_automation"] if "alert_automation" not in state.selected_agents else state.selected_agents,
        "execution_trace": state.execution_trace + [trace_entry],
    }


async def critic_scoring_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Critic Verification Gate — inspects risk consistency and OSHA compliance."""
    t0 = time.perf_counter()
    critique_notes = []

    if state.risk_scoring and state.risk_scoring.thermal_risk_score >= 0.75:
        # Strict enforcement: Critical score MUST have alert triggered and mandatory stop
        if state.alert and not state.alert.mandatory_stop_required:
            critique_notes.append("Enforced mandatory_stop_required for critical risk score")
            state.alert.mandatory_stop_required = True

    duration = round((time.perf_counter() - t0) * 1000, 2)
    trace_entry = {
        "node": "critic_scoring",
        "status": "verified" if not critique_notes else "adjusted",
        "critique_notes": critique_notes,
        "duration_ms": duration,
    }
    return {
        "execution_trace": state.execution_trace + [trace_entry],
    }


async def explanation_node(state: CoolPathGraphState) -> dict[str, Any]:
    """Execute Agent 6: Explanation Agent for structured debrief."""
    t0 = time.perf_counter()
    if not state.heat_perception or not state.risk_scoring or not state.alert:
        return {"errors": state.errors + ["Missing prerequisites for explanation agent"]}

    agent = ExplanationAgent()
    explanation = await agent.run(
        state.rider_telemetry,
        state.heat_perception,
        state.risk_scoring,
        state.reroute,
        state.alert,
    )
    duration = round((time.perf_counter() - t0) * 1000, 2)

    trace_entry = {
        "node": "explanation",
        "status": "success",
        "duration_ms": duration,
    }
    return {
        "explanation": explanation,
        "selected_agents": state.selected_agents + ["explanation"] if "explanation" not in state.selected_agents else state.selected_agents,
        "execution_trace": state.execution_trace + [trace_entry],
    }


__all__ = [
    "heat_perception_node",
    "risk_scoring_node",
    "reroute_node",
    "alert_automation_node",
    "critic_scoring_node",
    "explanation_node",
]
