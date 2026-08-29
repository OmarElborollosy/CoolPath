import asyncio
from app.schemas.common import Coordinates
from app.services.routing_service import CoolRoutingService

def main():
    routing = CoolRoutingService()
    coord = Coordinates(lat=33.44275, lng=-112.0555)
    best, all_options, tier = routing.find_cool_refuge_detour(coord, 40.0)
    
    print(f"R6 Coordinate: {coord}")
    print(f"Best: {best}")
    print(f"Tier: {tier}")
    print("Candidates:")
    for opt in all_options:
        print(opt)

if __name__ == "__main__":
    main()
