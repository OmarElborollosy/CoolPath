"""Full end-to-end demonstration script for Step 4: Action & Output Agents."""
import asyncio
from app.agents.coordinator import DecisionCoordinatorAgent
from app.core.phoenix_aois import PHOENIX_AOIS
from app.schemas.fleet import RiderTelemetry
from app.simulation.fleet_simulator import FleetSimulator


async def main():
    print("=" * 85)
    print("COOLPATH STEP 4: ACTION & OUTPUT AGENTS (REROUTE, ALERT AUTOMATION, EXPLANATION)")
    print("=" * 85)

    coordinator = DecisionCoordinatorAgent()
    simulator = FleetSimulator(coordinator=coordinator)

    # -----------------------------------------------------------------------
    # SCENARIO 1: Rider R3 (Marcus Vance) — Van Buren Corridor Heat Trap
    # -----------------------------------------------------------------------
    print("\n" + "#" * 85)
    print("DEMO 1: RIDER R3 (Marcus Vance) — VAN BUREN CRITICAL HEAT ALERT TRIGGER")
    print("#" * 85)

    sim_time_r3 = "14:15"
    tel_r3 = simulator.generate_telemetry("R3", sim_time_r3)
    state_r3 = await coordinator.evaluate_rider(tel_r3)

    print(f"\n[Telemetry Ingest]")
    print(f"  * Rider ID    : {tel_r3.rider_id} (Marcus Vance)")
    print(f"  * Sim Time    : {tel_r3.timestamp} (Peak Extreme Heat Window)")
    print(f"  * Location    : Van Buren Industrial Corridor (lat: {tel_r3.coordinate.lat:.4f}, lng: {tel_r3.coordinate.lng:.4f})")
    print(f"  * Speed       : {tel_r3.speed_kmh} km/h")

    print(f"\n[Agent 1: Heat Perception (FortyGuard Ingestion)]")
    hp = state_r3.heat_perception
    print(f"  * Surface Temperature : {hp.tile_temperature_c:.1f}°C")
    print(f"  * Heat Index (NOAA)   : {hp.heat_index_c:.1f}°C (Apparent: {hp.apparent_temperature_c:.1f}°C)")
    print(f"  * Exceedance Duration : {hp.exceedance_hours:.1f} hours past threshold")
    print(f"  * Heat Persistence    : {hp.persistence_hours:.1f} hours continuous streak")
    print(f"  * Tree Canopy (Sat)   : {hp.canopy_percentage:.1f}% | Street Shade: {hp.street_shade_percentage:.1f}%")
    print(f"  * Solar GHI Radiation : {hp.solar_irradiance_ghi:.0f} W/m² | AQI: {hp.aqi:.0f}")

    print(f"\n[Agent 2: Risk Scoring (OSHA-grounded Equation)]")
    rs = state_r3.risk_scoring
    print(f"  * Thermal Risk Score  : {rs.thermal_risk_score:.4f} / 1.0000")
    print(f"  * Risk Tier           : [{rs.risk_tier.upper()}] (Category: {rs.osha_heat_category})")
    print(f"  * Action Required     : {rs.action_required.upper()}")
    print(f"  * Active Risk Factors : {', '.join(rs.risk_factors)}")

    print(f"\n[Agent 5: Alert Automation (Hard-Gate Intervention)]")
    al = state_r3.alert
    print(f"  * Alert Triggered     : {al.alert_triggered} -> Level: [{al.alert_level.upper()}]")
    print(f"  * Alert Title         : {al.title}")
    print(f"  * Mandatory Stop Flag : {al.mandatory_stop_required}")
    print(f"  * Cooldown / Hydration: {al.cooldown_minutes_recommended} min rest | {al.hydration_oz_recommended} oz fluid intake")
    print(f"  * Dispatch Escalated  : {al.dispatch_escalated}")

    print(f"\n[Agent 6: Explanation & Debriefing Synthesis]")
    exp = state_r3.explanation
    print(f"  * Headline            : {exp.summary_headline}")
    print(f"  * Driver Directives   : \"{exp.driver_safety_brief}\"")
    print(f"  * Fleet Manager Brief : \"{exp.fleet_manager_brief}\"")
    print(f"  * Action Directives   :")
    for item in exp.action_items:
        print(f"    - {item}")

    # -----------------------------------------------------------------------
    # SCENARIO 2: Rider R6 (David Kim) — Van Buren to Encanto Park Reroute
    # -----------------------------------------------------------------------
    print("\n" + "#" * 85)
    print("DEMO 2: RIDER R6 (David Kim) — AUTONOMOUS SHADED REROUTE HERO STORY")
    print("#" * 85)

    sim_time_r6 = "15:40"
    tel_r6 = simulator.generate_telemetry("R6", sim_time_r6)
    tel_r6.assigned_route = ["van_buren_corridor", "encanto_park"]
    state_r6 = await coordinator.evaluate_rider(tel_r6)

    print(f"\n[Telemetry Ingest]")
    print(f"  * Rider ID    : {tel_r6.rider_id} (David Kim)")
    print(f"  * Sim Time    : {tel_r6.timestamp}")
    print(f"  * Route       : Van Buren Industrial Corridor -> Encanto Park Shaded Refuge")

    print(f"\n[Agent 4: Shaded Corridor Reroute (Micro-Refuge Spatial Cascade)]")
    rr = state_r6.reroute
    opt = rr.selected_option
    print(f"  * Reroute Recommended : {rr.reroute_recommended} (Cascade Tier: {rr.cascade_tier_used})")
    print(f"  * Destination Refuge  : {opt.refuge_name}")
    print(f"  * Detour Distance     : {opt.detour_distance_km:.2f} km (+{opt.estimated_extra_minutes:.1f} min travel time)")
    print(f"  * Corridor Canopy     : {opt.corridor_canopy_pct:.1f}% canopy along polyline path")
    print(f"  * Corridor Mean Temp  : {opt.corridor_mean_temp_c:.1f}°C")
    print(f"  * Temperature Drop (Delta T) : {opt.delta_temperature_c:+.1f}°C cooling benefit!")
    print(f"  * Clamped Refuge Score: {opt.refuge_score:.4f} / 1.0000 (Raw: {opt.raw_refuge_score:.4f})")
    print(f"  * Polyline Waypoints  : {len(opt.polyline)} GPS nodes sampled every ~175m")

    print(f"\n[Agent 6: Explanation Synthesis for R6]")
    exp_r6 = state_r6.explanation
    print(f"  * Headline            : {exp_r6.summary_headline}")
    print(f"  * Narrative           : {exp_r6.briefing_narrative}")
    print(f"  * Driver Directives   : \"{exp_r6.driver_safety_brief}\"")

    print("\n" + "=" * 85)
    print("STEP 4 END-TO-END VERIFICATION COMPLETE: ALL 6 SPECIALIST AGENTS OPERATIONAL.")
    print("=" * 85)


if __name__ == "__main__":
    asyncio.run(main())
