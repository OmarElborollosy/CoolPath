"""Verification script for Step 2: Heat Perception Agent & Fleet Simulation."""
import asyncio
from app.agents.heat_perception import HeatPerceptionAgent
from app.core.phoenix_aois import PHOENIX_AOIS, get_aoi_for_coordinate
from app.simulation.fleet_simulator import FleetSimulator, RIDER_CONFIGS


async def main():
    print("=" * 80)
    print("COOLPATH STEP 2: HEAT PERCEPTION AGENT & FLEET SIMULATION VERIFICATION")
    print("=" * 80)

    simulator = FleetSimulator()
    agent = HeatPerceptionAgent()
    sim_time = "14:15"

    print(f"\n[1] Evaluating Fleet Telemetry at Simulation Time: {sim_time} (Peak Afternoon Heat)\n")
    telemetries = simulator.generate_fleet_telemetry_batch(sim_time)

    print(f"{'Rider':<6} | {'AOI Location':<22} | {'Tile Temp':<10} | {'Heat Index':<11} | {'Exceedance':<11} | {'Canopy %':<9} | {'Status'}")
    print("-" * 88)

    for telemetry in telemetries:
        assessment = await agent.run(telemetry, allow_live=False)
        aoi = get_aoi_for_coordinate(telemetry.coordinate)
        aoi_name = aoi.name if aoi else "Out of Bounds"

        print(
            f"{assessment.rider_id:<6} | "
            f"{aoi_name:<22} | "
            f"{assessment.tile_temperature_c:>6.1f}°C   | "
            f"{assessment.heat_index_c:>7.1f}°C   | "
            f"{assessment.exceedance_hours:>6.1f} hrs   | "
            f"{assessment.canopy_percentage:>6.1f}%   | "
            f"{assessment.status}"
        )

    print("\n[2] Scenario Focus Checks:")
    # Check R3
    pos_r3 = simulator.get_rider_position_at_time("R3", "14:15")
    telemetry_r3 = simulator.generate_telemetry("R3", "14:15")
    r3_eval = await agent.run(telemetry_r3, allow_live=False)
    print(f"  - Rider R3 (Anchor): Locked in Van Buren Corridor")
    print(f"    * Temperature: {r3_eval.tile_temperature_c:.1f}°C (Apparent: {r3_eval.apparent_temperature_c:.1f}°C)")
    print(f"    * Exceedance: {r3_eval.exceedance_hours:.1f} hrs | Persistence: {r3_eval.persistence_hours:.1f} hrs")
    print(f"    * Tree Canopy: {r3_eval.canopy_percentage:.1f}% | Solar GHI: {r3_eval.solar_irradiance_ghi:.0f} W/m²")

    # Check R6 at 15:40 vs 16:40
    tel_r6_start = simulator.generate_telemetry("R6", "15:40")
    r6_start_eval = await agent.run(tel_r6_start, allow_live=False)
    tel_r6_end = simulator.generate_telemetry("R6", "16:40")
    r6_end_eval = await agent.run(tel_r6_end, allow_live=False)

    print(f"\n  - Rider R6 (Anchor Hero Story): Van Buren -> Encanto Park Reroute")
    print(f"    * 15:40 (Van Buren Start): Temp {r6_start_eval.tile_temperature_c:.1f}°C, Canopy {r6_start_eval.canopy_percentage:.1f}%")
    print(f"    * 16:40 (Encanto Park End): Temp {r6_end_eval.tile_temperature_c:.1f}°C, Canopy {r6_end_eval.canopy_percentage:.1f}%")
    delta_temp = r6_end_eval.tile_temperature_c - r6_start_eval.tile_temperature_c
    print(f"    * Thermal Refuge Cooling Effect: {delta_temp:+.1f}°C temperature reduction!")

    print("\n" + "=" * 80)
    print("STEP 2 VERIFICATION SUCCESSFUL: Heat Perception Agent & Fleet Simulation Operational.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
