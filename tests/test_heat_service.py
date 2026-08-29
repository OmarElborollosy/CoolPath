"""Tests for FortyGuard HeatService integration, async polling, and caching."""
from unittest.mock import MagicMock, patch
import pytest

from app.core.phoenix_aois import PHOENIX_AOIS, AOI_BASELINE_METRICS
from app.schemas.common import Coordinates
from app.services.cache import RuntimeCache
from app.services.heat_service import (
    HeatService,
    FortyGuardService,
    FortyGuardError,
    ActivityNotReadyError,
    TaskFailedError,
    TaskTimeoutError,
    get_global_heat_service,
    reset_global_heat_service,
)


@pytest.fixture
def clean_service():
    """Create a fresh HeatService with an isolated in-memory cache."""
    service = HeatService()
    service.cache = RuntimeCache()
    return service


def test_heat_service_synthesized_heatmap(clean_service):
    """Verify synthetic baseline generation for an AOI heatmap."""
    res = clean_service.fetch_aoi_heatmap("downtown_phoenix", analytic_type="tcm", force_refresh=True)
    assert res.aoi_id == "downtown_phoenix"
    assert res.is_synthesized is True
    assert len(res.tiles) == 25  # 5x5 grid
    assert res.stats.tile_count == 25
    assert res.stats.mean_c > 35.0

    # Ensure result is cached
    cached_res = clean_service.fetch_aoi_heatmap("downtown_phoenix", analytic_type="tcm")
    assert cached_res.activity_id == res.activity_id


def test_heat_service_synthesized_env_params(clean_service):
    """Verify point environmental parameter queries with synthesized baseline fallback."""
    coord = PHOENIX_AOIS["van_buren_corridor"].center
    res = clean_service.fetch_env_params(coord=coord, temperature_anchor_c=46.2)
    assert res.is_synthesized is True
    assert res.temperature_anchor_c == 46.2
    assert res.apparent_temperature_c > res.temperature_anchor_c
    assert res.wet_bulb_temperature_c == AOI_BASELINE_METRICS["van_buren_corridor"]["wet_bulb_c"]
    assert res.solar_irradiance_ghi == AOI_BASELINE_METRICS["van_buren_corridor"]["solar_ghi"]


def test_heat_service_synthesized_segmentation(clean_service):
    """Verify satellite and street view segmentation queries."""
    coord = PHOENIX_AOIS["encanto_park"].center
    sat = clean_service.fetch_satellite_segmentation(coord=coord)
    assert sat.is_synthesized is True
    assert sat.canopy_percentage == AOI_BASELINE_METRICS["encanto_park"]["canopy_percentage"]

    sv = clean_service.fetch_streetview_segmentation(coord=coord)
    assert sv.is_synthesized is True
    assert sv.street_shade_percentage == AOI_BASELINE_METRICS["encanto_park"]["street_shade_percentage"]


def test_async_task_polling_lifecycle(clean_service):
    """Verify wait_for_task handles ActivityNotReadyError, pending ticks, and terminal success."""
    mock_client = MagicMock()
    clean_service._client = mock_client

    # Simulate: 1st call -> 404 (ActivityNotReadyError), 2nd call -> pending, 3rd call -> succeeded
    mock_client.get_status.side_effect = [
        ActivityNotReadyError("act_123"),
        {"status": "pending", "progress": 30},
        {"status": "succeeded", "result": {"heatmap_tiles": [1, 2, 3]}},
    ]

    ticks = []
    def on_tick(status, data):
        ticks.append(status)

    result = clean_service.wait_for_task("act_123", poll_interval=0.01, timeout=2.0, on_tick=on_tick)
    assert result == {"heatmap_tiles": [1, 2, 3]}
    assert "not_ready" in ticks
    assert "pending" in ticks
    assert "succeeded" in ticks


def test_async_task_polling_failure_and_timeout(clean_service):
    """Verify wait_for_task raises TaskFailedError and TaskTimeoutError."""
    mock_client = MagicMock()
    clean_service._client = mock_client

    # Task failed
    mock_client.get_status.return_value = {"status": "failed", "message": "Out of memory in worker"}
    with pytest.raises(TaskFailedError) as exc_info:
        clean_service.wait_for_task("act_fail", poll_interval=0.01, timeout=0.5)
    assert "Out of memory" in str(exc_info.value)

    # Task timeout
    mock_client.get_status.return_value = {"status": "processing"}
    with pytest.raises(TaskTimeoutError):
        clean_service.wait_for_task("act_slow", poll_interval=0.01, timeout=0.05)


def test_live_heatmap_error_falls_back_to_synthesized(clean_service):
    """Verify live API error gracefully falls back to synthesized baseline rather than crashing."""
    mock_client = MagicMock()
    mock_client.create_heatmap.side_effect = TaskFailedError("AOI geometry invalid")
    clean_service._client = mock_client

    res = clean_service.fetch_aoi_heatmap("arcadia_residential", force_refresh=True, allow_live=True)
    assert res.is_synthesized is True
    assert res.aoi_id == "arcadia_residential"


def test_global_singleton_and_alias():
    """Verify HeatService and FortyGuardService are aliases and share singleton."""
    reset_global_heat_service()
    s1 = get_global_heat_service()
    assert isinstance(s1, HeatService)
    assert isinstance(s1, FortyGuardService)
