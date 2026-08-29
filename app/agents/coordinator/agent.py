"""Decision Coordinator Agent powered by LangGraph orchestration."""
from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.alert_automation import AlertAutomationAgent
from app.agents.coordinator.builder import build_coolpath_graph
from app.agents.explanation import ExplanationAgent
from app.agents.heat_perception import HeatPerceptionAgent
from app.agents.reroute import RerouteAgent
from app.agents.risk_scoring import RiskScoringAgent
from app.schemas.fleet import RiderTelemetry
from app.schemas.graph_state import CoolPathGraphState

logger = logging.getLogger("coolpath.agents.coordinator")


class DecisionCoordinatorAgent:
    """Master orchestrator for multi-agent microclimate risk intelligence."""

    def __init__(
        self,
        heat_agent: HeatPerceptionAgent | None = None,
        risk_agent: RiskScoringAgent | None = None,
        reroute_agent: RerouteAgent | None = None,
        alert_agent: AlertAutomationAgent | None = None,
        explanation_agent: ExplanationAgent | None = None,
    ) -> None:
        self.heat_agent = heat_agent or HeatPerceptionAgent()
        self.risk_agent = risk_agent or RiskScoringAgent()
        self.reroute_agent = reroute_agent or RerouteAgent()
        self.alert_agent = alert_agent or AlertAutomationAgent()
        self.explanation_agent = explanation_agent or ExplanationAgent()
        self.graph = build_coolpath_graph()

    async def evaluate_rider(self, telemetry: RiderTelemetry) -> CoolPathGraphState:
        """Run the complete CoolPath multi-agent assessment pipeline using LangGraph."""
        initial_state = CoolPathGraphState(
            rider_telemetry=telemetry,
            selected_agents=["heat_perception", "risk_scoring"],
        )

        overall_start = time.perf_counter()
        try:
            # Execute compiled StateGraph
            result = await self.graph.ainvoke(initial_state)

            if isinstance(result, dict):
                final_state = CoolPathGraphState.model_validate(result)
            elif isinstance(result, CoolPathGraphState):
                final_state = result
            else:
                final_state = initial_state

            total_ms = round((time.perf_counter() - overall_start) * 1000, 2)
            final_state.execution_trace.append({"node": "pipeline_total", "duration_ms": total_ms})
            return final_state

        except Exception as exc:
            logger.exception("Error executing LangGraph pipeline for rider %s: %s", telemetry.rider_id, exc)
            initial_state.errors.append(f"Pipeline error: {str(exc)}")
            initial_state.execution_trace.append({"node": "coordinator", "status": "error", "error": str(exc)})
            return initial_state


__all__ = ["DecisionCoordinatorAgent"]
