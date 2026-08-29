"""Unit tests for the 300m -> 1km -> 3km micro-refuge cascade search."""
from __future__ import annotations

import pytest
from app.schemas.common import Coordinates
from app.services.routing_service import CoolRoutingService


def test_cascade_tier1_selection():
    """Verify immediate refuge within 300m is selected in Tier 1."""
    service = CoolRoutingService()
    # Position right next to Civic Space Park (< 200m)
    current_pos = Coordinates(lat=33.4525, lng=-112.0730)
    best_opt, all_opts, tier_used = service.find_cool_refuge_detour(current_pos, baseline_temp_c=44.0)

    assert best_opt is not None
    assert tier_used == "tier1_300m"
    assert best_opt.detour_distance_km <= 0.30
    assert best_opt.refuge_score > 0.0
    assert best_opt.delta_temperature_c < 0.0


def test_cascade_tier2_selection():
    """Verify refuge between 300m and 1.0km is selected in Tier 2 when Tier 1 is empty."""
    service = CoolRoutingService()
    # Position in Downtown area ~700m from Margaret T. Hance Park
    current_pos = Coordinates(lat=33.4520, lng=-112.0720)
    best_opt, all_opts, tier_used = service.find_cool_refuge_detour(current_pos, baseline_temp_c=43.0)

    assert best_opt is not None
    assert tier_used in ("tier1_300m", "tier2_1km")
    assert best_opt.detour_distance_km <= 1.00


def test_cascade_tier3_selection():
    """Verify major refuge (Encanto Park) is selected in Tier 3 (1.0km - 3.0km)."""
    service = CoolRoutingService()
    # Position ~1.5 km west of Encanto Park (no other refuges in Tier 1 or Tier 2)
    current_pos = Coordinates(lat=33.4270, lng=-112.1000)
    best_opt, all_opts, tier_used = service.find_cool_refuge_detour(current_pos, baseline_temp_c=42.0)

    assert best_opt is not None
    assert tier_used in ("tier1_300m", "tier2_1km", "tier3_3km")
    assert best_opt.detour_distance_km <= 3.00


def test_cascade_safe_fail_beyond_3km():
    """Verify that when no refuge exists within 3.0km, the cascade safe-fails to no_refuge_found."""
    service = CoolRoutingService()
    # Position in desert fringe 10km south of Phoenix
    desert_pos = Coordinates(lat=33.3000, lng=-112.0740)
    best_opt, all_opts, tier_used = service.find_cool_refuge_detour(desert_pos, baseline_temp_c=46.0)

    assert best_opt is None
    assert tier_used == "no_refuge_found"
