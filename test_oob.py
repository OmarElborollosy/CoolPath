import asyncio
from app.schemas.common import Coordinates
from app.core.phoenix_aois import get_aoi_for_coordinate

def main():
    coord = Coordinates(lat=33.44275, lng=-112.0555)
    aoi = get_aoi_for_coordinate(coord)
    print(f"AOI for {coord}: {aoi.aoi_id if aoi else 'None'}")

if __name__ == "__main__":
    main()
