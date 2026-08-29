"""Step 2 Test Suite: Heat Perception Agent & Fleet Simulation Verification."""
import pytest
from app.agents.heat_perception import HeatPerceptionAgent
from app.core.phoenix_aois import PHOENIX_AOIS, AOI_BASELINE_METRICS, get_aoi_for_coordinate
from app.schemas.common import Coordinates
from app.schemas.fleet import RiderTelemetry
from app.services.background_worker import MicroclimateBackgroundWorker, warm_cycle_state
from app.services.heat_service import HeatService, get_global_heat_service
from app.simulation.fleet_simulator import FleetSimulator, RIDER_CONFIGS


@pytest.fixture
def heat_agent():
    """Create a HeatPerceptionAgent instance with isolated cache."""
    service = HeatService()
    return HeatPerceptionAgent(heat_service=service)


@pytest.fixture
def simulator():
    """Create FleetSimulator instance."""
    return FleetSimulator()


def test_6_riders_configuration():
    """Verify exactly 6 riders are configured with correct route AOIs and 13:00 - 16:40 time windows."""
    rider_ids = [cfg["rider_id"] for cfg in RIDER_CONFIGS]
    assert rider_ids == ["R1", "R2", "R3", "R4", "R5", "R6"]

    r3 = next(c for c in RIDER_CONFIGS if c["rider_id"] == "R3")
    assert r3["route_aois"] == ["van_buren_corridor"]

    r6 = next(c for c in RIDER_CONFIGS if c["rider_id"] == "R6")
    assert r6["route_aois"] == ["van_buren_corridor", "encanto_park"]


def test_fleet_positions_at_key_simulation_times(simulator):
    """Verify fleet GPS positions across simulation hours."""
    # 13:00 - R1 starts at Downtown Phoenix
    pos_r1_start = simulator.get_rider_position_at_time("R1", "13:00")
    aoi_r1 = get_aoi_for_coordinate(pos_r1_start)
    assert aoi_r1 is not None and aoi_r1.aoi_id == "downtown_phoenix"

    # 14:15 - R3 is in Van Buren Corridor (worst heat zone)
    pos_r3 = simulator.get_rider_position_at_time("R3", "14:15")
    aoi_r3 = get_aoi_for_coordinate(pos_r3)
    assert aoi_r3 is not None and aoi_r3.aoi_id == "van_buren_corridor"

    # 15:40 - R6 starts at Van Buren
    pos_r6_start = simulator.get_rider_position_at_time("R6", "15:40")
    aoi_r6_start = get_aoi_for_coordinate(pos_r6_start)
    assert aoi_r6_start is not None and aoi_r6_start.aoi_id == "van_buren_corridor"

    # 16:40 - R6 arrives at Encanto Park refuge
    pos_r6_end = simulator.get_rider_position_at_time("R6", "16:40")
    aoi_r6_end = get_aoi_for_coordinate(pos_r6_end)
    assert aoi_r6_end is not None and aoi_r6_end.aoi_id == "encanto_park"


@pytest.mark.asyncio
async def test_heat_perception_agent_all_6_riders(heat_agent, simulator):
    """Verify HeatPerceptionAgent processes all 6 riders and extracts accurate thermal metrics."""
    telemetries = simulator.generate_fleet_telemetry_batch("14:15")
    assert len(telemetries) == 6

    assessments = []
    for telemetry in telemetries:
        assessment = await heat_agent.run(telemetry, allow_live=False)
        assessments.append(assessment)

        assert assessment.rider_id == telemetry.rider_id
        assert assessment.tile_temperature_c > 30.0
        assert assessment.heat_index_c > 30.0
        assert assessment.apparent_temperature_c > 30.0
        assert assessment.wet_bulb_c > 15.0
        assert assessment.solar_irradiance_ghi > 600.0
        assert assessment.aqi > 30.0
        assert assessment.status == "success"
        assert assessment.confidence == 1.0

    # Specific check: R3 in Van Buren has high temperature (>45°C) and highest exceedance/persistence
    r3_assessment = next(a for a in assessments if a.rider_id == "R3")
    assert r3_assessment.tile_temperature_c >= 45.0
    assert r3_assessment.persistence_hours >= 8.0
    assert r3_assessment.exceedance_hours >= 10.0
    assert r3_assessment.canopy_percentage <= 5.0  # minimal canopy in Van Buren industrial


@pytest.mark.asyncio
async def test_heat_perception_encanto_park_refuge_contrast(heat_agent):
    """Verify thermal contrast when rider is in Encanto Park shaded refuge."""
    encanto_coord = PHOENIX_AOIS["encanto_park"].center
    telemetry = RiderTelemetry(
        rider_id="R_PARK",
        timestamp="14:15",
        coordinate=encanto_coord,
        speed_kmh=15.0,
        current_aoi_id="encanto_park",
    )

    assessment = await heat_agent.run(telemetry, allow_live=False)
    assert assessment.tile_temperature_c < 36.0
    assert assessment.canopy_percentage > 40.0
    assert assessment.street_shade_percentage > 50.0


def test_background_worker_cache_warm():
    """Verify MicroclimateBackgroundWorker warms cache across all 4 AOIs."""
    worker = MicroclimateBackgroundWorker()
    worker.warm_cache_for_all_aois()

    assert warm_cycle_state.status == "ready"
    assert warm_cycle_state.anchors_warmed == warm_cycle_state.anchors_total
    assert warm_cycle_state.anchors_total > 0

    # Verify anchor lookup tables exist in cache
    for aoi_id in PHOENIX_AOIS:
        lookup = worker.fg_service.cache.get(f"anchor_lookup:{aoi_id}")
        assert lookup is not None
        assert len(lookup) > 0
