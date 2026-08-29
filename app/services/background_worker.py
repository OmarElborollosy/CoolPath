"""Slow-path background worker (APScheduler) for FortyGuard microclimate layer refresh."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.core.phoenix_aois import PHOENIX_AOIS
from app.services.fortyguard_service import FortyGuardService, get_global_fortyguard_service

logger = logging.getLogger("coolpath.worker")


# ---------------------------------------------------------------------------
# WarmCycleState — single source of truth for cache readiness.
# Exposed via /health so callers are never silently served degraded data.
# ---------------------------------------------------------------------------

@dataclass
class WarmCycleState:
    """Tracks the progress of the active (or most-recent) warm cycle."""
    status: Literal["idle", "warming", "ready"] = "idle"
    anchors_warmed: int = 0
    anchors_total: int = 0
    cycle_started_at: datetime | None = None
    cycle_completed_at: datetime | None = None
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "cache_status": self.status,
            "anchors_warmed": self.anchors_warmed,
            "anchors_total": self.anchors_total,
            "progress": (
                f"{self.anchors_warmed}/{self.anchors_total} anchors warmed"
                if self.anchors_total > 0
                else "not started"
            ),
            "cycle_started_at": self.cycle_started_at.isoformat() if self.cycle_started_at else None,
            "cycle_completed_at": self.cycle_completed_at.isoformat() if self.cycle_completed_at else None,
            "last_error": self.last_error,
        }


# Global singleton — imported by routes.py for /health
warm_cycle_state = WarmCycleState()


class MicroclimateBackgroundWorker:
    """Manages slow-path background caching of FortyGuard thermal and spatial layers."""

    def __init__(self, fortyguard_service: FortyGuardService | None = None) -> None:
        self.fg_service = fortyguard_service or get_global_fortyguard_service()
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()

    def warm_cache_for_all_aois(self) -> None:
        """Fetch and cache FortyGuard layers for Phoenix AOIs with Nearest-Anchor subsampling.

        Runs entirely in the background (launched via run_in_executor in server.py).
        Updates warm_cycle_state continuously so /health reflects real progress.
        """
        # We need haversine_distance_km for the nearest-anchor lookup calculation
        from app.core.spatial import haversine_distance_km

        # --- Count total anchors upfront so progress is accurate from the start ---
        anchor_counts: dict[str, int] = {}
        for aoi_id in PHOENIX_AOIS:
            if aoi_id == "downtown_phoenix":
                anchor_counts[aoi_id] = 25
            elif aoi_id == "van_buren_corridor":
                anchor_counts[aoi_id] = 15
            else:
                anchor_counts[aoi_id] = 10
        total_anchors = sum(anchor_counts.values())

        warm_cycle_state.status = "warming"
        warm_cycle_state.anchors_warmed = 0
        warm_cycle_state.anchors_total = total_anchors
        warm_cycle_state.cycle_started_at = datetime.now(timezone.utc)
        warm_cycle_state.cycle_completed_at = None
        warm_cycle_state.last_error = None

        logger.info(
            "Starting FortyGuard cache pre-warm for date=%s across %d AOIs (%d total anchors)",
            self.settings.study_date,
            len(PHOENIX_AOIS),
            total_anchors,
        )
        start_time = datetime.now(timezone.utc)
        total_live_calls = 0

        for aoi_id, aoi in PHOENIX_AOIS.items():
            try:
                # 1. Thermal snapshot (tcm)
                hm = self.fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="tcm", date=self.settings.study_date)
                # 2. Persistence (longest continuous heat streak)
                self.fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="persistence", date=self.settings.study_date)
                # 3. Exceedance (hours past threshold)
                self.fg_service.fetch_aoi_heatmap(aoi_id, analytic_type="exceedance", date=self.settings.study_date)

                # Sub-sample anchor tiles
                tiles = hm.tiles
                total_tiles = len(tiles)
                target_anchors = anchor_counts.get(aoi_id, 10)

                step = max(1, total_tiles // target_anchors)
                anchor_tiles = tiles[::step][:target_anchors]

                # Pre-warm env_params, satellite, and streetview for anchor centroids
                for anchor in anchor_tiles:
                    if anchor.centroid:
                        self.fg_service.fetch_env_params(
                            coord=anchor.centroid,
                            temperature_anchor_c=anchor.temperature_c,
                            date=self.settings.study_date
                        )
                        self.fg_service.fetch_satellite_segmentation(anchor.centroid, date=self.settings.study_date)
                        self.fg_service.fetch_streetview_segmentation(anchor.centroid)
                        total_live_calls += 3

                    # Update progress counter after each anchor regardless of centroid presence
                    warm_cycle_state.anchors_warmed += 1

                # Precompute tile_id -> nearest_anchor lookup table.
                # Selection rule: Haversine distance from the raw tile centroid to each anchor tile's
                # centroid; minimum distance wins; first-anchor-index wins on exact ties.
                lookup_table = {}
                snap_distances = []

                for tile in tiles:
                    if not tile.centroid:
                        continue

                    min_dist = float('inf')
                    best_anchor = None
                    for anchor in anchor_tiles:
                        if not anchor.centroid:
                            continue
                        dist = haversine_distance_km(
                            tile.centroid.lat, tile.centroid.lng,
                            anchor.centroid.lat, anchor.centroid.lng,
                        )
                        if dist < min_dist:
                            min_dist = dist
                            best_anchor = anchor

                    if best_anchor and best_anchor.centroid:
                        lookup_table[tile.tile_id] = {
                            "lat": best_anchor.centroid.lat,
                            "lng": best_anchor.centroid.lng,
                        }
                        snap_distances.append(min_dist)

                # Save lookup table in cache
                self.fg_service.cache.set(f"anchor_lookup:{aoi_id}", lookup_table, ttl_seconds=86400)

                # Log snap distances
                if snap_distances:
                    avg_snap = sum(snap_distances) / len(snap_distances)
                    max_snap = max(snap_distances)
                    logger.info(
                        "AOI %s: Warmed %d anchors (from %d tiles). Snap dist: avg=%.0fm, max=%.0fm. "
                        "Progress: %d/%d anchors total.",
                        aoi_id, len(anchor_tiles), total_tiles,
                        avg_snap * 1000, max_snap * 1000,
                        warm_cycle_state.anchors_warmed, warm_cycle_state.anchors_total,
                    )

            except Exception as exc:
                warm_cycle_state.last_error = f"{aoi_id}: {exc}"
                logger.error("Error pre-warming cache for AOI %s: %s", aoi_id, exc)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        warm_cycle_state.status = "ready"
        warm_cycle_state.cycle_completed_at = datetime.now(timezone.utc)

        logger.info(
            "FortyGuard cache pre-warm complete in %.2f seconds. Total live calls made: %d. "
            "Final progress: %d/%d anchors.",
            elapsed, total_live_calls,
            warm_cycle_state.anchors_warmed, warm_cycle_state.anchors_total,
        )

    def start(self) -> None:
        """Start the background periodic refresh scheduler."""
        if not self.scheduler.running:
            # Refresh every 15 minutes
            self.scheduler.add_job(
                self.warm_cache_for_all_aois,
                trigger=IntervalTrigger(minutes=15),
                id="fortyguard_cache_refresh",
                replace_existing=True,
            )
            self.scheduler.start()
            logger.info("Microclimate background worker started (15 min interval).")

    def shutdown(self) -> None:
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Microclimate background worker stopped.")
