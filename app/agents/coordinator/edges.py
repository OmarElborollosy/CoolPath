"""LangGraph dynamic routing conditional edges for CoolPath."""
from __future__ import annotations

from typing import Literal
from app.schemas.graph_state import CoolPathGraphState


def triage_routing_edge(state: CoolPathGraphState) -> Literal["reroute", "alert_automation", "critic_scoring", "__end__"]:
    """Dynamic triage gate based on thermal risk score and coverage status."""
    if state.heat_perception and state.heat_perception.status == "expanding_coverage_please_wait":
        return "__end__"

    if not state.risk_scoring:
        return "critic_scoring"

    score = state.risk_scoring.thermal_risk_score

    # Reroute triggered for High / Critical risk (>= 0.55)
    if score >= 0.55:
        return "reroute"

    # Direct alert triggered for Moderate risk (>= 0.35)
    if score >= 0.35:
        return "alert_automation"

    # Low risk bypasses reroute and alert automation
    return "critic_scoring"


def post_reroute_edge(state: CoolPathGraphState) -> Literal["alert_automation"]:
    """After reroute evaluation, proceed to alert automation."""
    return "alert_automation"


def post_alert_edge(state: CoolPathGraphState) -> Literal["critic_scoring"]:
    """After alert automation, proceed to critic scoring verification."""
    return "critic_scoring"


def post_critic_edge(state: CoolPathGraphState) -> Literal["explanation"]:
    """After critic scoring verification, proceed to explanation synthesis."""
    return "explanation"


__all__ = [
    "triage_routing_edge",
    "post_reroute_edge",
    "post_alert_edge",
    "post_critic_edge",
]
