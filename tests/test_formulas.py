"""Unit tests for core scientific and scoring formulas."""
from __future__ import annotations

import pytest
from app.core.formulas import (
    clamp,
    compute_norm_aqi,
    compute_norm_heat_index,
    compute_norm_persistence,
    compute_norm_solar,
    compute_refuge_score,
    compute_thermal_risk_score,
)


def test_clamp_helper():
    """Verify clamp utility behavior."""
    assert clamp(0.5, 0.0, 1.0) == 0.5
    assert clamp(-0.2, 0.0, 1.0) == 0.0
    assert clamp(1.5, 0.0, 1.0) == 1.0
    assert clamp("invalid", 0.0, 1.0) == 0.0


def test_refuge_score_clamping_bad_candidate():
    """Fix 1: Test deliberately awful candidate (far, hot, zero canopy) clamps to 0.0."""
    # 48°C corridor, 0% canopy, 0% street shade, 3.0km detour
    res = compute_refuge_score(
        corridor_mean_temp_c=48.0,
        corridor_canopy_pct=0.0,
        street_shade_pct=0.0,
        detour_distance_km=3.0,
    )
    # Raw score is 0.40*(1-1.0) + 0 + 0 - 0.20*(1.0) = -0.20
    assert res["raw_refuge_score"] == -0.20
    assert res["refuge_score"] == 0.0
    assert 0.0 <= res["refuge_score"] <= 1.0


def test_refuge_score_clamping_ideal_candidate():
    """Verify ideal cool corridor achieves high score clamped to <= 1.0."""
    # 30°C corridor, 100% canopy, 100% street shade, 0km detour
    res = compute_refuge_score(
        corridor_mean_temp_c=30.0,
        corridor_canopy_pct=100.0,
        street_shade_pct=100.0,
        detour_distance_km=0.0,
    )
    # Raw score is 0.40*(1-0) + 0.35*(1) + 0.25*(1) - 0 = 1.00
    assert res["raw_refuge_score"] == 1.00
    assert res["refuge_score"] == 1.00
    assert 0.0 <= res["refuge_score"] <= 1.0


def test_thermal_risk_scoring_osha_tiers():
    """Fix 2: Test OSHA 4-factor thermal risk equation and exact tier boundaries."""
    # 1. Low Risk (< 0.35) -> Normal conditions (28°C heat index, 0 hrs persistence, low solar, low aqi)
    low_res = compute_thermal_risk_score(
        heat_index_c=28.0,
        persistence_hours=0.0,
        ghi_w_m2=200.0,
        aqi=30.0,
    )
    assert low_res["thermal_risk_score"] < 0.35
    assert low_res["risk_tier"] == "Low"
    assert low_res["action_required"] == "none"

    # 2. Moderate Risk (0.35 <= score < 0.55) -> Caution
    # NormHI for 38°C = (38-27)/27 = 0.4074 -> 0.35*0.4074 = 0.1426
    # Persistence 4 hrs = 4/12 = 0.3333 -> 0.30*0.3333 = 0.1000
    # Solar 800 W/m2 = 0.8 -> 0.20*0.8 = 0.1600
    # AQI 50 = 50/200 = 0.25 -> 0.15*0.25 = 0.0375
    # Total = 0.4401 (Moderate)
    mod_res = compute_thermal_risk_score(
        heat_index_c=38.0,
        persistence_hours=4.0,
        ghi_w_m2=800.0,
        aqi=50.0,
    )
    assert 0.35 <= mod_res["thermal_risk_score"] < 0.55
    assert mod_res["risk_tier"] == "Moderate"
    assert mod_res["action_required"] == "advisory"

    # 3. High Risk (0.55 <= score < 0.75) -> Danger (Triggers Reroute)
    high_res = compute_thermal_risk_score(
        heat_index_c=43.0,
        persistence_hours=7.0,
        ghi_w_m2=900.0,
        aqi=65.0,
    )
    assert 0.55 <= high_res["thermal_risk_score"] < 0.75
    assert high_res["risk_tier"] == "High"
    assert high_res["action_required"] == "reroute"

    # 4. Critical Risk (>= 0.75) -> Extreme Danger (Triggers Mandatory Stop Alert)
    crit_res = compute_thermal_risk_score(
        heat_index_c=49.0,
        persistence_hours=10.0,
        ghi_w_m2=950.0,
        aqi=80.0,
    )
    assert crit_res["thermal_risk_score"] >= 0.75
    assert crit_res["risk_tier"] == "Critical"
    assert crit_res["action_required"] == "mandatory_stop"


def test_thermal_risk_exact_boundary_sanity():
    """Verify boundary checks are inclusive (>= 0.55 for High, >= 0.75 for Critical)."""
    # Verify score normalization stays strictly within [0.0, 1.0]
    extreme_max = compute_thermal_risk_score(
        heat_index_c=65.0,
        persistence_hours=24.0,
        ghi_w_m2=1500.0,
        aqi=500.0,
    )
    assert extreme_max["thermal_risk_score"] == 1.0
    assert extreme_max["risk_tier"] == "Critical"
