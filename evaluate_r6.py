import asyncio
from app.simulation.fleet_simulator import FleetSimulator
from app.services.routing_service import CoolRoutingService
from app.config import get_settings

async def main():
    simulator = FleetSimulator()
    frame = await simulator.step_simulation("15:45")
    r6 = frame.riders["R6"]
    print(f"R6 Coordinate: {r6.current_coordinate}")
    print(f"Current AOI: {r6.current_aoi_id}")
    
    routing = CoolRoutingService()
    best, all_options, tier = routing.find_cool_refuge_detour(r6.current_coordinate, 40.0)
    print(f"Best: {best}")
    print(f"Tier: {tier}")
    print("Candidates:")
    for opt in all_options:
        print(opt)

if __name__ == "__main__":
    asyncio.run(main())
