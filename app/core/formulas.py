"""Core mathematical and scientific scoring functions for CoolPath.

Includes:
1. OSHA / NOAA grounded 4-factor Thermal Risk Scoring Formula.
2. Clamped [0.0, 1.0] Refuge Scoring Formula with corridor polyline sampling.
"""
from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a floating point value between low and high bounds."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, val))


# ---------------------------------------------------------------------------
# 1. OSHA / NOAA Grounded Thermal Risk Scoring
# ---------------------------------------------------------------------------

def compute_norm_heat_index(heat_index_c: float) -> float:
    """Normalize Heat Index (°C) into [0.0, 1.0].
    
    Grounded in NOAA/OSHA heat index categories:
    - 27.0°C (80°F): Caution threshold (baseline start).
    - 54.0°C (130°F): Extreme Danger ceiling.
    """
    return clamp((float(heat_index_c) - 27.0) / (54.0 - 27.0))


def compute_norm_persistence(persistence_hours: float) -> float:
    """Normalize FortyGuard persistence (continuous hours > threshold) into [0.0, 1.0].
    
    Grounded in an 8-12 hour outdoor work shift ceiling.
    """
    return clamp(float(persistence_hours) / 12.0)


def compute_norm_solar(ghi_w_m2: float) -> float:
    """Normalize clear-sky Global Horizontal Irradiance (W/m²) into [0.0, 1.0].
    
    1000 W/m² corresponds to intense desert midday solar radiation.
    """
    return clamp(float(ghi_w_m2) / 1000.0)


def compute_norm_aqi(aqi: float) -> float:
    """Normalize EPA Air Quality Index into [0.0, 1.0].
    
    200 AQI is EPA's Very Unhealthy threshold.
    """
    return clamp(float(aqi) / 200.0)


def compute_thermal_risk_score(
    heat_index_c: float,
    persistence_hours: float,
    ghi_w_m2: float = 850.0,
    aqi: float = 55.0,
) -> dict:
    """Compute OSHA-grounded 4-factor thermal risk score and determine risk tier.

    Formula:
        Thermal Risk = 0.35 * NormHeatIndex + 0.30 * NormPersistence + 0.20 * NormSolar + 0.15 * NormAQI

    Returns:
        Dictionary containing:
        - thermal_risk_score: float in [0.0, 1.0]
        - risk_tier: 'Low', 'Moderate', 'High', or 'Critical'
        - osha_heat_category: 'Normal', 'Caution', 'Danger', 'Extreme Danger'
        - action_required: 'none', 'advisory', 'reroute', 'mandatory_stop'
        - breakdown: dict of normalized factors
    """
    norm_hi = compute_norm_heat_index(heat_index_c)
    norm_pers = compute_norm_persistence(persistence_hours)
    norm_solar = compute_norm_solar(ghi_w_m2)
    norm_aqi = compute_norm_aqi(aqi)

    raw_score = (
        0.35 * norm_hi
        + 0.30 * norm_pers
        + 0.20 * norm_solar
        + 0.15 * norm_aqi
    )
    score = round(clamp(raw_score, 0.0, 1.0), 4)

    # Decision Boundaries (strictly aligned with >= 0.55 for High and >= 0.75 for Critical):
    if score >= 0.75:
        risk_tier = "Critical"
        osha_cat = "Extreme Danger"
        action = "mandatory_stop"
    elif score >= 0.55:
        risk_tier = "High"
        osha_cat = "Danger"
        action = "reroute"
    elif score >= 0.35:
        risk_tier = "Moderate"
        osha_cat = "Caution"
        action = "advisory"
    else:
        risk_tier = "Low"
        osha_cat = "Normal"
        action = "none"

    return {
        "thermal_risk_score": score,
        "risk_tier": risk_tier,
        "osha_heat_category": osha_cat,
        "action_required": action,
        "norm_heat_index": round(norm_hi, 4),
        "norm_persistence": round(norm_pers, 4),
        "norm_solar": round(norm_solar, 4),
        "norm_aqi": round(norm_aqi, 4),
        "breakdown": {
            "heat_index_contribution": round(0.35 * norm_hi, 4),
            "persistence_contribution": round(0.30 * norm_pers, 4),
            "solar_contribution": round(0.20 * norm_solar, 4),
            "aqi_contribution": round(0.15 * norm_aqi, 4),
        },
    }


# ---------------------------------------------------------------------------
# 2. Clamped [0.0, 1.0] Refuge Scoring Formula
# ---------------------------------------------------------------------------

def compute_refuge_score(
    corridor_mean_temp_c: float,
    corridor_canopy_pct: float,
    street_shade_pct: float,
    detour_distance_km: float,
) -> dict:
    """Compute clamped [0.0, 1.0] Refuge Score for a candidate route corridor.

    Formula:
        Raw Score = 0.40 * (1 - NormCorridorTemp) + 0.35 * Canopy% + 0.25 * StreetShade% - 0.20 * (DetourDistanceKm / 3.0)
        Refuge Score = max(0.0, min(1.0, Raw Score))

    Parameters:
        corridor_mean_temp_c: Mean FortyGuard surface temp along the polyline path (°C).
        corridor_canopy_pct: Mean satellite canopy percentage along the polyline (0-100%).
        street_shade_pct: Ground-level street view shade at the destination stop (0-100%).
        detour_distance_km: Added detour distance in km (capped at 3.0 km max cascade).

    Returns:
        dict with raw_score, clamped refuge_score in [0.0, 1.0], and breakdown components.
    """
    # 30°C is cool baseline in Phoenix summer, 48°C is extreme exposed asphalt ceiling
    norm_temp = clamp((float(corridor_mean_temp_c) - 30.0) / (48.0 - 30.0))
    canopy_frac = clamp(float(corridor_canopy_pct) / 100.0)
    shade_frac = clamp(float(street_shade_pct) / 100.0)
    detour_penalty = 0.20 * clamp(float(detour_distance_km) / 3.0)

    raw_score = (
        0.40 * (1.0 - norm_temp)
        + 0.35 * canopy_frac
        + 0.25 * shade_frac
        - detour_penalty
    )
    clamped_score = round(clamp(raw_score, 0.0, 1.0), 4)

    return {
        "raw_refuge_score": round(raw_score, 4),
        "refuge_score": clamped_score,
        "norm_corridor_temp": round(norm_temp, 4),
        "canopy_fraction": round(canopy_frac, 4),
        "shade_fraction": round(shade_frac, 4),
        "detour_penalty": round(detour_penalty, 4),
    }
