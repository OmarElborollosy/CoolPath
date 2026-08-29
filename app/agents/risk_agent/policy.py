"""Policy constants and thresholds for the Risk Scoring Agent (OSHA / NOAA aligned)."""
from __future__ import annotations

# Core Thresholds
_HEAT_RISK_CEILING: float = 0.75       # >= 0.75: Critical / Mandatory Stop / Extreme Danger
_HIGH_RISK_THRESHOLD: float = 0.55     # >= 0.55: High / Autonomous Reroute Trigger / Danger
_MODERATE_RISK_THRESHOLD: float = 0.35 # >= 0.35: Moderate / Advisory / Caution
_LOW_RISK_FLOOR: float = 0.0

# Temperature & Atmospheric Benchmarks (°C / W/m² / AQI)
_HEAT_INDEX_BASE_C: float = 27.0       # 80.6°F (NOAA Caution onset)
_HEAT_INDEX_CEILING_C: float = 54.0    # 130°F (NOAA Extreme Danger ceiling)
_SOLAR_GHI_CEILING_W_M2: float = 1000.0# Desert midday peak solar radiation
_AQI_VERY_UNHEALTHY: float = 200.0     # EPA Very Unhealthy benchmark
_PERSISTENCE_SHIFT_HOURS: float = 12.0 # Standard full shift baseline

# Continuous Exposure Escalation
_CONTINUOUS_EXPOSURE_FREE_MINUTES: float = 30.0
_CONTINUOUS_EXPOSURE_PENALTY_RATE: float = 0.002  # +0.02 risk per 10 min beyond 30 min
_MAX_CONTINUOUS_PENALTY: float = 0.15

# Factor Weights (Sum = 1.0)
_WEIGHT_HEAT_INDEX: float = 0.35
_WEIGHT_PERSISTENCE: float = 0.30
_WEIGHT_SOLAR_GHI: float = 0.20
_WEIGHT_AQI: float = 0.15

__all__ = [
    "_HEAT_RISK_CEILING",
    "_HIGH_RISK_THRESHOLD",
    "_MODERATE_RISK_THRESHOLD",
    "_LOW_RISK_FLOOR",
    "_HEAT_INDEX_BASE_C",
    "_HEAT_INDEX_CEILING_C",
    "_SOLAR_GHI_CEILING_W_M2",
    "_AQI_VERY_UNHEALTHY",
    "_PERSISTENCE_SHIFT_HOURS",
    "_CONTINUOUS_EXPOSURE_FREE_MINUTES",
    "_CONTINUOUS_EXPOSURE_PENALTY_RATE",
    "_MAX_CONTINUOUS_PENALTY",
    "_WEIGHT_HEAT_INDEX",
    "_WEIGHT_PERSISTENCE",
    "_WEIGHT_SOLAR_GHI",
    "_WEIGHT_AQI",
]
