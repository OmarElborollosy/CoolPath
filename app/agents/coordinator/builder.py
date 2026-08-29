"""LangGraph StateGraph builder for CoolPath decision coordination."""
from __future__ import annotations

import logging
from langgraph.graph import END, START, StateGraph

from app.agents.coordinator.edges import (
    post_alert_edge,
    post_critic_edge,
    post_reroute_edge,
    triage_routing_edge,
)
from app.agents.coordinator.nodes import (
    alert_automation_node,
    critic_scoring_node,
    explanation_node,
    heat_perception_node,
    reroute_node,
    risk_scoring_node,
)
from app.schemas.graph_state import CoolPathGraphState

logger = logging.getLogger("coolpath.coordinator.builder")


def build_coolpath_graph():
    """Construct and compile the multi-agent LangGraph workflow."""
    workflow = StateGraph(CoolPathGraphState)

    # Add Nodes
    workflow.add_node("heat_perception", heat_perception_node)
    workflow.add_node("risk_scoring", risk_scoring_node)
    workflow.add_node("reroute", reroute_node)
    workflow.add_node("alert_automation", alert_automation_node)
    workflow.add_node("critic_scoring", critic_scoring_node)
    workflow.add_node("explanation", explanation_node)

    # Add Sequential Edges
    workflow.add_edge(START, "heat_perception")
    workflow.add_edge("heat_perception", "risk_scoring")

    # Add Conditional Triage Edge after Risk Scoring
    workflow.add_conditional_edges(
        "risk_scoring",
        triage_routing_edge,
        {
            "reroute": "reroute",
            "alert_automation": "alert_automation",
            "critic_scoring": "critic_scoring",
            "__end__": END,
        },
    )

    # Add Convergence Edges
    workflow.add_edge("reroute", "alert_automation")
    workflow.add_edge("alert_automation", "critic_scoring")
    workflow.add_edge("critic_scoring", "explanation")
    workflow.add_edge("explanation", END)

    compiled = workflow.compile()
    logger.info("CoolPath LangGraph workflow successfully constructed and compiled.")
    return compiled


__all__ = ["build_coolpath_graph"]
