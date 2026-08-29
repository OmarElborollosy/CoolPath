"""Cool corridor routing service with micro-refuge cascade and polyline shade sampling.

Implements:
1. Micro-refuge cascade search: Tier 1 (<=300m), Tier 2 (<=1.0km), Tier 3 (<=3.0km / regional <=5.0km).
2. Corridor polyline shade & temperature sampling at 150-200m intervals.
3. Clamped [0.0, 1.0] Refuge Score evaluation and delta T calculation.
"""
from __future__ import annotations

import logging
from typing import Sequence

from app.config import get_settings
from app.core.formulas import compute_refuge_score
from app.core.phoenix_aois import PHOENIX_AOIS
from app.core.spatial import coord_distance_km, interpolate_coordinates, sample_polyline_corridor
from app.schemas.assessments import RerouteOption
from app.schemas.common import Coordinates
from app.services.heat_service import HeatService, get_global_heat_service

logger = logging.getLogger("coolpath.routing")


class CoolRoutingService:
    """Evaluates and generates cool corridor detour options for riders."""

    def __init__(self, heat_service: HeatService | None = None) -> None:
        self.heat_service = heat_service or get_global_heat_service()
        self.settings = get_settings()

    def find_cool_refuge_detour(
        self,
        current_coord: Coordinates,
        destination_coord: Coordinates | None = None,
        baseline_temp_c: float = 45.0,
    ) -> tuple[RerouteOption | None, list[RerouteOption], str]:
        """Execute the 300m -> 1km -> 3km cascade to find the optimal cool corridor detour.

        Returns:
            - best_option: RerouteOption or None (if no refuge is within range)
            - all_evaluated_options: list of evaluated candidate routes
            - cascade_tier_used: 'tier1_300m', 'tier2_1km', 'tier3_3km', or 'no_refuge_found'
        """
        candidate_destinations = self._get_candidate_refuges(current_coord)
        if destination_coord:
            candidate_destinations.append(("Designated Destination Refuge", destination_coord))

        all_options: list[RerouteOption] = []

        # Sort candidates into cascade tiers
        tier1_candidates = []
        tier2_candidates = []
        tier3_candidates = []

        for name, target_coord in candidate_destinations:
            dist_km = coord_distance_km(current_coord, target_coord)
            if dist_km <= self.settings.refuge_radius_tier1_km:  # <= 0.30 km
                tier1_candidates.append((name, target_coord, dist_km, "tier1_300m"))
            elif dist_km <= self.settings.refuge_radius_tier2_km:  # <= 1.00 km
                tier2_candidates.append((name, target_coord, dist_km, "tier2_1km"))
            elif dist_km <= 5.00:  # <= 5.00 km regional ceiling
                tier3_candidates.append((name, target_coord, dist_km, "tier3_3km"))

        # Cascade evaluation order: Tier 1 -> Tier 2 -> Tier 3
        tier_used = "no_refuge_found"
        evaluated_tier: list[tuple[str, Coordinates, float, str]] = []

        if tier1_candidates:
            evaluated_tier = tier1_candidates
            tier_used = "tier1_300m"
        elif tier2_candidates:
            evaluated_tier = tier2_candidates
            tier_used = "tier2_1km"
        elif tier3_candidates:
            evaluated_tier = tier3_candidates
            tier_used = "tier3_3km"

        for name, target_coord, dist_km, tier_label in evaluated_tier:
            option = self._evaluate_candidate_route(
                current_coord=current_coord,
                refuge_name=name,
                refuge_coord=target_coord,
                detour_dist_km=dist_km,
                tier_label=tier_label,
                baseline_temp_c=baseline_temp_c,
            )
            all_options.append(option)

        if not all_options:
            return None, [], "no_refuge_found"

        # Pick the highest scoring refuge option (or greatest cooling delta)
        all_options.sort(key=lambda opt: (opt.refuge_score, -opt.delta_temperature_c, -opt.detour_distance_km), reverse=True)
        best_option = all_options[0]

        # Ensure option provides tangible cooling or refuge score
        if best_option.refuge_score <= 0.0 and best_option.delta_temperature_c >= 0.0:
            return None, all_options, "no_refuge_found"

        return best_option, all_options, tier_used

    def _evaluate_candidate_route(
        self,
        current_coord: Coordinates,
        refuge_name: str,
        refuge_coord: Coordinates,
        detour_dist_km: float,
        tier_label: str,
        baseline_temp_c: float,
    ) -> RerouteOption:
        """Sample FortyGuard canopy and temperature along the path polyline."""
        # Synthesize path waypoints with an intermediate shaded corridor bend
        midpoint = interpolate_coordinates(current_coord, refuge_coord, 0.5)
        # Clean slight street offset without stray spikes
        polyline = [current_coord, midpoint, refuge_coord]

        # Polyline Corridor Sampling (s_1, ..., s_k every ~175m)
        samples = sample_polyline_corridor(polyline, interval_meters=self.settings.corridor_sample_interval_m)

        sample_temps: list[float] = []
        sample_canopies: list[float] = []

        for sample_pt in samples:
            # Look up satellite segmentation along the path
            sat = self.heat_service.fetch_satellite_segmentation(sample_pt, allow_live=False)
            sample_canopies.append(sat.canopy_percentage)

            # Temp along path is modulated by canopy (dense canopy lowers ambient surface temp)
            corridor_pt_temp = baseline_temp_c - (sat.canopy_percentage * 0.22)
            sample_temps.append(corridor_pt_temp)

        corridor_mean_temp = sum(sample_temps) / len(sample_temps) if sample_temps else baseline_temp_c
        corridor_canopy = sum(sample_canopies) / len(sample_canopies) if sample_canopies else 0.0

        # Destination ground-level street shade
        street_view = self.heat_service.fetch_streetview_segmentation(refuge_coord, allow_live=False)
        street_shade = street_view.street_shade_percentage

        # Destination canopy boost if refuge is a known park
        if "encanto" in refuge_name.lower() or "park" in refuge_name.lower():
            corridor_canopy = max(corridor_canopy, 35.0)
            street_shade = max(street_shade, 45.0)
            corridor_mean_temp = min(corridor_mean_temp, 35.5)

        # Compute Clamped [0.0, 1.0] Refuge Score
        score_dict = compute_refuge_score(
            corridor_mean_temp_c=corridor_mean_temp,
            corridor_canopy_pct=corridor_canopy,
            street_shade_pct=street_shade,
            detour_distance_km=detour_dist_km,
        )

        delta_temp = round(corridor_mean_temp - baseline_temp_c, 1)  # Expected to be negative

        # Estimated extra travel time at 15 km/h
        extra_minutes = round((detour_dist_km / 15.0) * 60.0, 1)

        return RerouteOption(
            option_id=f"reroute_{refuge_name.lower().replace(' ', '_')}_{round(detour_dist_km*1000)}m",
            refuge_name=refuge_name,
            refuge_coordinate=refuge_coord,
            detour_distance_km=round(detour_dist_km, 2),
            estimated_extra_minutes=extra_minutes,
            corridor_mean_temp_c=round(corridor_mean_temp, 1),
            corridor_canopy_pct=round(corridor_canopy, 1),
            street_shade_pct=round(street_shade, 1),
            delta_temperature_c=delta_temp,
            raw_refuge_score=score_dict["raw_refuge_score"],
            refuge_score=score_dict["refuge_score"],
            polyline=polyline,
            tier_level=tier_label,
        )

    def _get_candidate_refuges(self, current_coord: Coordinates) -> list[tuple[str, Coordinates]]:
        """List of candidate Phoenix cooling refuges and shaded stops."""
        candidates = [
            ("Encanto Park Canopy Refuge", PHOENIX_AOIS["encanto_park"].center),
            (
                "Civic Space Park Shaded Ramada",
                Coordinates(lat=33.4530, lng=-112.0735),
            ),
            (
                "Margaret T. Hance Park Tree Alley",
                Coordinates(lat=33.4580, lng=-112.0720),
            ),
            (
                "Arcadia Grove Shaded Misting Station",
                Coordinates(lat=33.5010, lng=-112.0010),
            ),
            (
                "Coronado Park Green Space",
                Coordinates(lat=33.4680, lng=-112.0520),
            ),
            (
                "Eastlake Shaded Plaza",
                Coordinates(lat=33.4450, lng=-112.0580),
            ),
            (
                "University Park Shaded Ramada",
                Coordinates(lat=33.4380, lng=-112.0680),
            ),
        ]
        return candidates


__all__ = ["CoolRoutingService"]
