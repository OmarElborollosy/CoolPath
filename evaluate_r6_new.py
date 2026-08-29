import asyncio
from app.schemas.common import Coordinates
from app.services.routing_service import CoolRoutingService

def main():
    routing = CoolRoutingService()
    coord = Coordinates(lat=33.44625, lng=-112.0485)
    best, all_options, tier = routing.find_cool_refuge_detour(coord, 46.2)
    
    print(f"R6 Coordinate: {coord}")
    print(f"Best: {best}")
    print(f"Tier: {tier}")
    print("Candidates:")
    for opt in all_options:
        print(opt)

if __name__ == "__main__":
    main()
