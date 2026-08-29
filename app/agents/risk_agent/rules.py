"""Rule calculation engine for thermal risk scoring with continuous exposure penalties."""
from __future__ import annotations

from typing import Any
from app.agents.risk_agent.policy import (
    _AQI_VERY_UNHEALTHY,
    _CONTINUOUS_EXPOSURE_FREE_MINUTES,
    _CONTINUOUS_EXPOSURE_PENALTY_RATE,
    _HEAT_INDEX_BASE_C,
    _HEAT_INDEX_CEILING_C,
    _HEAT_RISK_CEILING,
    _HIGH_RISK_THRESHOLD,
    _MAX_CONTINUOUS_PENALTY,
    _MODERATE_RISK_THRESHOLD,
    _PERSISTENCE_SHIFT_HOURS,
    _SOLAR_GHI_CEILING_W_M2,
    _WEIGHT_AQI,
    _WEIGHT_HEAT_INDEX,
    _WEIGHT_PERSISTENCE,
    _WEIGHT_SOLAR_GHI,
)
from app.core.formulas import clamp


def normalize_heat_index(heat_index_c: float) -> float:
    """Normalize Heat Index into [0.0, 1.0]."""
    return clamp((float(heat_index_c) - _HEAT_INDEX_BASE_C) / (_HEAT_INDEX_CEILING_C - _HEAT_INDEX_BASE_C))


def normalize_persistence(persistence_hours: float) -> float:
    """Normalize FortyGuard persistence into [0.0, 1.0]."""
    return clamp(float(persistence_hours) / _PERSISTENCE_SHIFT_HOURS)


def normalize_solar_ghi(ghi_w_m2: float) -> float:
    """Normalize clear-sky GHI into [0.0, 1.0]."""
    return clamp(float(ghi_w_m2) / _SOLAR_GHI_CEILING_W_M2)


def normalize_aqi(aqi: float) -> float:
    """Normalize EPA AQI into [0.0, 1.0]."""
    return clamp(float(aqi) / _AQI_VERY_UNHEALTHY)


def calculate_continuous_exposure_penalty(cumulative_minutes: float = 0.0) -> float:
    """Compute risk penalty for continuous exposure past 30 minutes in direct sunlight."""
    excess = max(0.0, float(cumulative_minutes) - _CONTINUOUS_EXPOSURE_FREE_MINUTES)
    return min(_MAX_CONTINUOUS_PENALTY, excess * _CONTINUOUS_EXPOSURE_PENALTY_RATE)


def evaluate_risk_rules(
    heat_index_c: float,
    persistence_hours: float,
    ghi_w_m2: float = 850.0,
    aqi: float = 55.0,
    continuous_exposure_minutes: float = 0.0,
) -> dict[str, Any]:
    """Evaluate full OSHA/NOAA 4-factor risk equation with exposure duration modifier."""
    norm_hi = normalize_heat_index(heat_index_c)
    norm_pers = normalize_persistence(persistence_hours)
    norm_solar = normalize_solar_ghi(ghi_w_m2)
    norm_aqi = normalize_aqi(aqi)

    exposure_penalty = calculate_continuous_exposure_penalty(continuous_exposure_minutes)

    base_score = (
        _WEIGHT_HEAT_INDEX * norm_hi
        + _WEIGHT_PERSISTENCE * norm_pers
        + _WEIGHT_SOLAR_GHI * norm_solar
        + _WEIGHT_AQI * norm_aqi
    )

    final_score = round(clamp(base_score + exposure_penalty, 0.0, 1.0), 4)

    # Classify Risk Tiers and OSHA Action Levels
    if final_score >= _HEAT_RISK_CEILING:
        risk_tier = "Critical"
        osha_cat = "Extreme Danger"
        action = "mandatory_stop"
    elif final_score >= _HIGH_RISK_THRESHOLD:
        risk_tier = "High"
        osha_cat = "Danger"
        action = "reroute"
    elif final_score >= _MODERATE_RISK_THRESHOLD:
        risk_tier = "Moderate"
        osha_cat = "Caution"
        action = "advisory"
    else:
        risk_tier = "Low"
        osha_cat = "Normal"
        action = "none"

    return {
        "thermal_risk_score": final_score,
        "base_risk_score": round(base_score, 4),
        "exposure_penalty": round(exposure_penalty, 4),
        "risk_tier": risk_tier,
        "osha_heat_category": osha_cat,
        "action_required": action,
        "norm_heat_index": round(norm_hi, 4),
        "norm_persistence": round(norm_pers, 4),
        "norm_solar": round(norm_solar, 4),
        "norm_aqi": round(norm_aqi, 4),
        "breakdown": {
            "heat_index_contribution": round(_WEIGHT_HEAT_INDEX * norm_hi, 4),
            "persistence_contribution": round(_WEIGHT_PERSISTENCE * norm_pers, 4),
            "solar_contribution": round(_WEIGHT_SOLAR_GHI * norm_solar, 4),
            "aqi_contribution": round(_WEIGHT_AQI * norm_aqi, 4),
            "continuous_exposure_penalty": round(exposure_penalty, 4),
        },
    }


__all__ = [
    "normalize_heat_index",
    "normalize_persistence",
    "normalize_solar_ghi",
    "normalize_aqi",
    "calculate_continuous_exposure_penalty",
    "evaluate_risk_rules",
]
