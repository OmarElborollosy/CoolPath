"""State container passed across LangGraph nodes."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from .fleet import RiderTelemetry
from .assessments import (
    HeatPerceptionAssessment,
    RiskScoringAssessment,
    RerouteAssessment,
    AlertAssessment,
    ExplanationAssessment,
)


class CoolPathGraphState(BaseModel):
    """Complete graph execution state."""
    rider_telemetry: RiderTelemetry
    heat_perception: HeatPerceptionAssessment | None = None
    risk_scoring: RiskScoringAssessment | None = None
    reroute: RerouteAssessment | None = None
    alert: AlertAssessment | None = None
    explanation: ExplanationAssessment | None = None

    # Graph orchestration metadata
    selected_agents: list[str] = Field(default_factory=list)
    retry_count: int = 0
    retry_targets: list[str] = Field(default_factory=list)
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
