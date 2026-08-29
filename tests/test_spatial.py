"""Unit tests for spatial geometry, Haversine distance, and corridor polyline sampling."""
from __future__ import annotations

import pytest
from app.core.spatial import (
    coord_distance_km,
    haversine_distance_km,
    point_in_polygon,
    sample_polyline_corridor,
)
from app.schemas.common import Coordinates


def test_haversine_distance():
    """Verify Haversine distance matches expected benchmark."""
    # Downtown Phoenix to Encanto Park (~2.7 km)
    downtown = Coordinates(lat=33.4484, lng=-112.0740)
    encanto = Coordinates(lat=33.4270, lng=-112.0870)
    dist = coord_distance_km(downtown, encanto)
    assert 2.5 <= dist <= 3.0

    # Same point distance is 0.0
    assert haversine_distance_km(33.4484, -112.0740, 33.4484, -112.0740) == 0.0


def test_point_in_polygon():
    """Verify ray-casting point-in-polygon logic."""
    poly = [
        [-112.08, 33.44],
        [-112.06, 33.44],
        [-112.06, 33.46],
        [-112.08, 33.46],
        [-112.08, 33.44],
    ]
    # Center is inside
    assert point_in_polygon(33.45, -112.07, poly) is True
    # Outside points
    assert point_in_polygon(33.48, -112.07, poly) is False
    assert point_in_polygon(33.45, -112.10, poly) is False


def test_sample_polyline_corridor_spacing():
    """Fix 3: Verify polyline is sampled every ~150-200m along the corridor.

    The algorithm guarantees interior consecutive sample pairs are spaced at
    exactly the requested interval (~175m). The final pair is a remainder gap:
    it spans the distance from the last regularly-placed sample to the polyline
    endpoint, which is always ≤ interval (not necessarily ≥ 150m). Enforcing
    150-200m on the last pair would require skipping the actual destination,
    which is wrong. We verify interior pairs only, then separately confirm the
    last element is exactly the destination endpoint.
    """
    p1 = Coordinates(lat=33.4484, lng=-112.0740)
    p2 = Coordinates(lat=33.4484, lng=-112.0632)  # ~1.0 km east
    polyline = [p1, p2]

    # Sample at 175m intervals
    samples = sample_polyline_corridor(polyline, interval_meters=175.0)

    # 1.0 km / 0.175 km ≈ 6-7 sample points
    assert len(samples) >= 6
    assert samples[0] == p1
    assert samples[-1] == p2  # terminal point is always the destination endpoint

    # Interior pairs: all must be within 150-200m
    interior_pairs = list(range(len(samples) - 2))  # exclude last pair (remainder)
    for i in interior_pairs:
        dist_m = coord_distance_km(samples[i], samples[i + 1]) * 1000.0
        assert 150.0 <= dist_m <= 200.0, (
            f"Interior pair {i}->{i+1} spacing {dist_m:.1f}m is outside [150, 200m]"
        )

    # Terminal remainder gap: must be > 0 and <= interval
    if len(samples) >= 2:
        last_gap_m = coord_distance_km(samples[-2], samples[-1]) * 1000.0
        assert 0 < last_gap_m <= 200.0, (
            f"Terminal remainder gap {last_gap_m:.1f}m must be in (0, 200m]"
        )

