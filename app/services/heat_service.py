"""Resilient FortyGuard Heat Service with caching, async task polling, and failover.

Handles live communication with the FortyGuard tOS Enterprise API, layered caching
(Redis + in-memory fallback), async task polling lifecycle (ActivityNotReadyError retry,
TaskTimeoutError, TaskFailedError), and high-fidelity Phoenix baseline synthesis.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings
from app.core.phoenix_aois import AOI_BASELINE_METRICS, PHOENIX_AOIS, get_aoi_for_coordinate
from app.schemas.common import Coordinates
from app.schemas.fortyguard import (
    EnvParamsResult,
    HeatmapResult,
    HeatmapStats,
    HeatmapTile,
    SatelliteSegmentationResult,
    StreetViewSegmentationResult,
    TaskPollingStatus,
)
from app.services.cache import get_global_cache

logger = logging.getLogger("coolpath.heat_service")


# ---------------------------------------------------------------------------
# Exception Hierarchy (mirrored from FortyGuard SDK)
# ---------------------------------------------------------------------------

class FortyGuardError(Exception):
    """Base exception for any error returned by FortyGuard API or client."""


class TaskFailedError(FortyGuardError):
    """The async FortyGuard task finished with status=failed or error."""


class TaskTimeoutError(FortyGuardError):
    """The async FortyGuard task did not finish within the polling timeout budget."""


class ActivityNotReadyError(FortyGuardError):
    """The status endpoint returned 404 — the activity is not visible yet (eventual consistency)."""

    def __init__(self, activity_id: str) -> None:
        self.activity_id = activity_id
        super().__init__(f"Activity {activity_id} is not visible yet (status endpoint 404).")


# ---------------------------------------------------------------------------
# FortyGuard Client Loader
# ---------------------------------------------------------------------------

def _load_fortyguard_client_class() -> type | None:
    """Dynamically discover and import FortyGuardClient from path or package."""
    try:
        from fortyguard import FortyGuardClient
        return FortyGuardClient
    except ImportError:
        pass

    # Try quickstart directory relative to project root
    quickstart_dirs = [
        Path(__file__).resolve().parent.parent.parent.parent / "temperature-api-quickstart",
        Path.cwd() / "temperature-api-quickstart",
        Path.cwd().parent / "temperature-api-quickstart",
    ]
    for qs_dir in quickstart_dirs:
        if qs_dir.is_dir() and str(qs_dir) not in sys.path:
            sys.path.insert(0, str(qs_dir))
            try:
                from fortyguard import FortyGuardClient
                return FortyGuardClient
            except ImportError:
                continue

    return None


FortyGuardSDKClient = _load_fortyguard_client_class()


# ---------------------------------------------------------------------------
# HeatService Implementation
# ---------------------------------------------------------------------------

class HeatService:
    """Manages thermal and microclimate intelligence queries with caching and polling."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.fortyguard_api_key
        self.base_url = (base_url or settings.fortyguard_base_url).rstrip("/")
        self.timeout = timeout or settings.fortyguard_timeout_seconds
        self.cache = get_global_cache()
        self._client: Any = None

        if self.api_key and FortyGuardSDKClient is not None:
            try:
                self._client = FortyGuardSDKClient(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
                logger.info("FortyGuardClient successfully initialized (base_url=%s).", self.base_url)
            except Exception as exc:
                logger.warning("Could not initialize FortyGuardClient (%s); fallback ready.", exc)
        else:
            logger.info("HeatService operating in synthetic baseline mode (no live API key).")

    @property
    def is_live_client_ready(self) -> bool:
        """Return True if live FortyGuard client is initialized and available."""
        return self._client is not None

    # -----------------------------------------------------------------------
    # Task Status & Polling Engine
    # -----------------------------------------------------------------------

    def get_task_status(self, activity_id: str) -> TaskPollingStatus:
        """Check status of an async activity ID directly via the client."""
        if not self._client:
            return TaskPollingStatus(
                activity_id=activity_id,
                status="succeeded",
                progress_pct=100.0,
                message="Synthetic baseline immediate completion",
                result={},
            )

        try:
            data = self._client.get_status(activity_id)
            status_str = str(data.get("status", "unknown")).lower()
            return TaskPollingStatus(
                activity_id=activity_id,
                status=status_str,
                progress_pct=100.0 if status_str in ("succeeded", "completed") else 50.0,
                message=data.get("message", ""),
                result=data.get("result", data),
            )
        except Exception as exc:
            if "not visible yet" in str(exc) or "404" in str(exc) or type(exc).__name__ == "ActivityNotReadyError":
                return TaskPollingStatus(
                    activity_id=activity_id,
                    status="not_ready",
                    progress_pct=10.0,
                    message="Activity not visible in status endpoint yet",
                )
            logger.warning("get_task_status exception for %s: %s", activity_id, exc)
            return TaskPollingStatus(
                activity_id=activity_id,
                status="error",
                message=str(exc),
            )

    def wait_for_task(
        self,
        activity_id: str,
        poll_interval: float = 2.0,
        timeout: float = 60.0,
        on_tick: Callable[[str, dict], None] | None = None,
    ) -> dict[str, Any]:
        """Poll an async activity until terminal completion with error handling."""
        if not self._client:
            return {"activity_id": activity_id, "status": "succeeded", "result": {}}

        deadline = time.monotonic() + timeout
        current_interval = poll_interval

        while True:
            try:
                data = self._client.get_status(activity_id)
            except Exception as exc:
                if "not visible yet" in str(exc) or "404" in str(exc) or type(exc).__name__ == "ActivityNotReadyError":
                    if on_tick:
                        on_tick("not_ready", {})
                    if time.monotonic() >= deadline:
                        raise TaskTimeoutError(
                            f"Activity {activity_id} never became queryable within {timeout:.1f}s"
                        )
                    time.sleep(current_interval)
                    current_interval = min(current_interval * 1.25, 5.0)
                    continue
                raise FortyGuardError(f"Status query error on {activity_id}: {exc}") from exc

            status = str(data.get("status", "")).lower()
            if on_tick:
                on_tick(status, data)

            if status in ("succeeded", "completed"):
                return data.get("result", data)
            if status in ("failed", "error"):
                raise TaskFailedError(f"Activity {activity_id} failed: {data.get('message') or data}")

            if time.monotonic() >= deadline:
                raise TaskTimeoutError(f"Activity {activity_id} still '{status}' after {timeout:.1f}s")

            time.sleep(current_interval)

    # -----------------------------------------------------------------------
    # Heatmap Query (Fast-Path Cache + Async Polling Live Path + Synthetic)
    # -----------------------------------------------------------------------

    def fetch_aoi_heatmap(
        self,
        aoi_id: str,
        analytic_type: str = "tcm",
        date: str | None = None,
        hour: str = "14:00",
        force_refresh: bool = False,
        allow_live: bool = True,
    ) -> HeatmapResult:
        """Fetch or retrieve cached heatmap for a Phoenix AOI."""
        settings = get_settings()
        study_date = date or settings.study_date
        cache_key = f"heatmap:{aoi_id}:{analytic_type}:{study_date}:{hour}"

        if not force_refresh:
            cached = self.cache.get(cache_key)
            if cached:
                return HeatmapResult.model_validate(cached)

        aoi = PHOENIX_AOIS.get(aoi_id)
        if not aoi:
            raise ValueError(f"Unknown Phoenix AOI ID: {aoi_id}")

        result: HeatmapResult | None = None

        # 1. Attempt Live API if client is available and allowed
        if allow_live and self._client:
            try:
                logger.info("Calling FortyGuard API create_heatmap for %s (%s)", aoi_id, analytic_type)
                extra_args: dict[str, Any] = {}
                if analytic_type in ("exceedance", "persistence"):
                    extra_args["threshold"] = 38.0  # Celsius threshold for Phoenix extreme heat
                    extra_args["direction"] = "above"

                raw = self._client.create_heatmap(
                    polygon_aoi=aoi.geojson,
                    start_date=study_date,
                    start_time=hour,
                    filter_type=1,
                    granularity=100,
                    analytic_type=analytic_type,
                    wait=True,
                    timeout=self.timeout,
                    verbose=False,
                    **extra_args,
                )
                result = self._parse_live_heatmap_response(aoi_id, analytic_type, study_date, hour, raw)
            except (TaskFailedError, TaskTimeoutError, ActivityNotReadyError, FortyGuardError, Exception) as exc:
                logger.warning(
                    "Live heatmap call failed for %s (%s: %s); utilizing synthesized baseline.",
                    aoi_id, type(exc).__name__, exc,
                )

        # 2. Synthetic Baseline if live API is unavailable, fails, or offline
        if not result:
            result = self._generate_baseline_heatmap(aoi_id, analytic_type, study_date, hour)

        # Cache result
        self.cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=settings.heatmap_cache_ttl_seconds)
        return result

    def _parse_live_heatmap_response(
        self, aoi_id: str, analytic_type: str, date: str, hour: str, raw_response: dict
    ) -> HeatmapResult:
        activity_id = raw_response.get("activity_id", "live_activity")
        res = raw_response.get("result", {})
        stats_data = res.get("stats_data", {})
        map_data = res.get("map_data", {})

        tiles: list[HeatmapTile] = []
        temps: list[float] = []

        for feat in map_data.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [[]])[0]

            val = props.get("temperature", props.get("value", 40.0))
            tile_id = str(props.get("tile_id", f"tile_{len(tiles)}"))

            # Calculate centroid
            centroid = None
            if coords:
                c_lng = sum(pt[0] for pt in coords) / len(coords)
                c_lat = sum(pt[1] for pt in coords) / len(coords)
                centroid = Coordinates(lat=c_lat, lng=c_lng)

            tile = HeatmapTile(
                tile_id=tile_id,
                temperature_c=float(val),
                persistence_hours=float(val) if analytic_type == "persistence" else None,
                exceedance_hours=float(val) if analytic_type == "exceedance" else None,
                geometry_polygon=coords,
                centroid=centroid,
            )
            tiles.append(tile)
            temps.append(float(val))

        temp_stats = stats_data.get("Temperature_stats", {})
        stats = HeatmapStats(
            min_c=float(temp_stats.get("min", min(temps) if temps else 35.0)),
            max_c=float(temp_stats.get("max", max(temps) if temps else 45.0)),
            mean_c=float(temp_stats.get("mean", sum(temps) / len(temps) if temps else 40.0)),
            std_c=float(temp_stats.get("std", 2.0)),
            tile_count=len(tiles),
            temperature_distribution=temps,
        )

        return HeatmapResult(
            activity_id=activity_id,
            aoi_id=aoi_id,
            analytic_type=analytic_type,
            date=date,
            hour=hour,
            stats=stats,
            tiles=tiles,
            raw_geojson=map_data,
            is_synthesized=False,
        )

    def _generate_baseline_heatmap(self, aoi_id: str, analytic_type: str, date: str, hour: str) -> HeatmapResult:
        """High-fidelity synthetic FortyGuard GeoJSON grid for Phoenix AOI."""
        aoi = PHOENIX_AOIS[aoi_id]
        base_meta = AOI_BASELINE_METRICS[aoi_id]

        target_val = (
            base_meta["persistence_hours"] if analytic_type == "persistence"
            else base_meta["exceedance_hours"] if analytic_type == "exceedance"
            else base_meta["surface_temp_c"]
        )

        tiles: list[HeatmapTile] = []
        temps: list[float] = []
        features: list[dict] = []

        # Generate a 5x5 grid of 100m cells across the AOI bbox
        bbox = aoi.bbox
        lat_step = (bbox.max_lat - bbox.min_lat) / 5.0
        lng_step = (bbox.max_lng - bbox.min_lng) / 5.0

        for r in range(5):
            for c in range(5):
                min_lat = bbox.min_lat + r * lat_step
                max_lat = min_lat + lat_step
                min_lng = bbox.min_lng + c * lng_step
                max_lng = min_lng + lng_step

                # Small spatial gradient variation (+/-0.8C)
                variation = ((r * 0.3) - (c * 0.2))
                val = round(target_val + variation, 2)
                temps.append(val)

                poly = [
                    [min_lng, min_lat],
                    [max_lng, min_lat],
                    [max_lng, max_lat],
                    [min_lng, max_lat],
                    [min_lng, min_lat],
                ]
                tile_id = f"{aoi_id}_tile_{r}_{c}"
                centroid = Coordinates(lat=min_lat + lat_step / 2.0, lng=min_lng + lng_step / 2.0)

                tile = HeatmapTile(
                    tile_id=tile_id,
                    temperature_c=val if analytic_type == "tcm" else base_meta["surface_temp_c"],
                    persistence_hours=val if analytic_type == "persistence" else base_meta["persistence_hours"],
                    exceedance_hours=val if analytic_type == "exceedance" else base_meta["exceedance_hours"],
                    geometry_polygon=poly,
                    centroid=centroid,
                )
                tiles.append(tile)

                features.append({
                    "type": "Feature",
                    "properties": {
                        "tile_id": tile_id,
                        "temperature": val if analytic_type == "tcm" else base_meta["surface_temp_c"],
                        "value": val,
                    },
                    "geometry": {"type": "Polygon", "coordinates": [poly]},
                })

        stats = HeatmapStats(
            min_c=min(temps),
            max_c=max(temps),
            mean_c=round(sum(temps) / len(temps), 2),
            std_c=0.85,
            tile_count=len(tiles),
            temperature_distribution=temps,
        )

        return HeatmapResult(
            activity_id=f"syn_{aoi_id}_{analytic_type}",
            aoi_id=aoi_id,
            analytic_type=analytic_type,
            date=date,
            hour=hour,
            stats=stats,
            tiles=tiles,
            raw_geojson={"type": "FeatureCollection", "features": features},
            is_synthesized=True,
        )

    # -----------------------------------------------------------------------
    # Environmental Parameters Query
    # -----------------------------------------------------------------------

    def fetch_env_params(
        self,
        coord: Coordinates,
        temperature_anchor_c: float,
        date: str | None = None,
        allow_live: bool = True,
    ) -> EnvParamsResult:
        """Query point environmental parameters from POST /v1/env_params."""
        settings = get_settings()
        study_date = date or settings.study_date
        cache_key = f"env_params:{round(coord.lat, 4)}:{round(coord.lng, 4)}:{round(temperature_anchor_c, 1)}"

        cached = self.cache.get(cache_key)
        if cached:
            return EnvParamsResult.model_validate(cached)

        result: EnvParamsResult | None = None

        # 1. Attempt live API
        if allow_live and self._client:
            try:
                logger.info(
                    "Calling FortyGuard API environmental_parameters for (%.4f, %.4f)",
                    coord.lat, coord.lng,
                )
                raw = self._client.environmental_parameters(
                    latitude=coord.lat,
                    longitude=coord.lng,
                    temperature=temperature_anchor_c,
                    start_date=study_date,
                    start_time="14:00",
                    filter_type=1,
                    analysis=[
                        "heat_index_celsius",
                        "apparent_temperature_celsius",
                        "wet_bulb_temperature_celsius",
                        "relative_humidity_percent",
                        "cloud_cover_octas",
                        "air_quality:idx",
                        "air_quality_o3:idx",
                        "air_quality_pm2p5:idx",
                        "solar_irradiance",
                    ],
                    wait=True,
                    timeout=self.timeout,
                    verbose=False,
                )
                activity_id = raw.get("activity_id", "live_env_params")
                res = raw.get("result", {})
                location = (res.get("locations") or [{}])[0]
                params = location.get("parameters", {})
                solar = location.get("solar_irradiance", {}).get("clear_sky", {})
                meta = res.get("metadata", {})
                timestamps = meta.get("timestamps", [])

                def _scalar(val: object, default: float = 0.0) -> float:
                    if isinstance(val, list):
                        return float(val[0]) if val else default
                    return float(val) if val is not None else default

                result = EnvParamsResult(
                    activity_id=activity_id,
                    coordinate=coord,
                    temperature_anchor_c=temperature_anchor_c,
                    heat_index_c=_scalar(params.get("heat_index_celsius"), temperature_anchor_c + 1.8),
                    apparent_temperature_c=_scalar(params.get("apparent_temperature_celsius"), temperature_anchor_c + 0.4),
                    wet_bulb_temperature_c=_scalar(params.get("wet_bulb_temperature_celsius"), 22.0),
                    relative_humidity_pct=_scalar(params.get("relative_humidity_percent"), 20.0),
                    solar_irradiance_ghi=_scalar(solar.get("ghi"), 850.0),
                    solar_irradiance_dni=_scalar(solar.get("dni"), 750.0),
                    solar_irradiance_dhi=_scalar(solar.get("dhi"), 100.0),
                    aqi_idx=_scalar(params.get("air_quality:idx"), 55.0),
                    aqi_pm25=_scalar(params.get("air_quality_pm2p5:idx")) or None,
                    aqi_o3=_scalar(params.get("air_quality_o3:idx")) or None,
                    cloud_cover_octas=_scalar(params.get("cloud_cover_octas"), 0.0),
                    timestamps=timestamps if isinstance(timestamps, list) else [],
                    is_synthesized=False,
                )
            except Exception as exc:
                logger.warning(
                    "Live env_params call failed for (%.4f, %.4f) (%s); using synthesized baseline.",
                    coord.lat, coord.lng, exc,
                )

        # 2. Synthesized fallback
        if not result:
            aoi = get_aoi_for_coordinate(coord)
            base = AOI_BASELINE_METRICS.get(
                aoi.aoi_id if aoi else "downtown_phoenix",
                AOI_BASELINE_METRICS["downtown_phoenix"],
            )
            result = EnvParamsResult(
                activity_id="synthesized_env_params",
                coordinate=coord,
                temperature_anchor_c=temperature_anchor_c,
                heat_index_c=round(temperature_anchor_c + 1.8, 1),
                apparent_temperature_c=round(temperature_anchor_c + 0.4, 1),
                wet_bulb_temperature_c=base["wet_bulb_c"],
                relative_humidity_pct=base["humidity_pct"],
                solar_irradiance_ghi=base["solar_ghi"],
                solar_irradiance_dni=base["solar_ghi"] * 0.85,
                solar_irradiance_dhi=base["solar_ghi"] * 0.15,
                aqi_idx=base["aqi"],
                is_synthesized=True,
            )

        self.cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=settings.cache_default_ttl_seconds)
        return result

    # -----------------------------------------------------------------------
    # Premium Satellite & Street View Segmentation
    # -----------------------------------------------------------------------

    def fetch_satellite_segmentation(
        self,
        coord: Coordinates,
        date: str | None = None,
        allow_live: bool = True,
    ) -> SatelliteSegmentationResult:
        """Land-cover segmentation from POST /v1/satellite."""
        settings = get_settings()
        study_date = date or settings.study_date
        cache_key = f"sat_seg:{round(coord.lat, 4)}:{round(coord.lng, 4)}"
        cached = self.cache.get(cache_key)
        if cached:
            return SatelliteSegmentationResult.model_validate(cached)

        result: SatelliteSegmentationResult | None = None

        if allow_live and self._client:
            try:
                logger.info("Calling FortyGuard API satellite_segmentation for (%.4f, %.4f)", coord.lat, coord.lng)
                raw = None
                for attempt in range(3):
                    try:
                        raw = self._client.satellite_segmentation(
                            latitude=coord.lat,
                            longitude=coord.lng,
                            start_date=study_date,
                            filter_type=3,
                            granularity=100,
                            wait=True,
                            timeout=self.timeout,
                            verbose=False,
                        )
                        break
                    except Exception as e:
                        if attempt < 2:
                            delay = 2 * (attempt + 1)
                            logger.warning("satellite_segmentation failed, retrying in %ds: %s", delay, e)
                            time.sleep(delay)
                        else:
                            raise e

                activity_id = raw.get("activity_id", "live_satellite")
                seg = raw.get("result", {}).get("segmentation", {})
                segments: dict = seg.get("segments", {})

                def _sum_classes(*keywords: str) -> float:
                    total = 0.0
                    for cls, pct in segments.items():
                        cls_lower = cls.lower()
                        if any(kw in cls_lower for kw in keywords):
                            total += float(pct or 0.0)
                    return min(total, 100.0)

                canopy_pct = _sum_classes("tree", "tall veg", "forest", "canopy")
                vegetation_pct = _sum_classes("low veg", "grass", "shrub", "vegetation")
                impervious_pct = _sum_classes("impervious", "asphalt", "concrete", "road", "pavement", "building", "roof")
                water_pct = _sum_classes("water", "lake", "river", "pool")
                bare_pct = _sum_classes("bare", "soil", "sand", "dirt")

                result = SatelliteSegmentationResult(
                    coordinate=coord,
                    canopy_percentage=round(canopy_pct, 1),
                    vegetation_percentage=round(vegetation_pct, 1),
                    impervious_percentage=round(impervious_pct, 1),
                    water_percentage=round(water_pct, 1),
                    bare_soil_percentage=round(bare_pct, 1),
                    is_synthesized=False,
                )
            except Exception as exc:
                logger.warning(
                    "Live satellite_segmentation call failed for (%.4f, %.4f) (%s); using synthesized baseline.",
                    coord.lat, coord.lng, exc,
                )

        if not result:
            aoi = get_aoi_for_coordinate(coord)
            base = AOI_BASELINE_METRICS.get(
                aoi.aoi_id if aoi else "downtown_phoenix",
                AOI_BASELINE_METRICS["downtown_phoenix"],
            )
            result = SatelliteSegmentationResult(
                coordinate=coord,
                canopy_percentage=base["canopy_percentage"],
                vegetation_percentage=base["canopy_percentage"] * 0.5,
                impervious_percentage=100.0 - base["canopy_percentage"] * 1.5,
                water_percentage=5.0 if aoi and aoi.aoi_id == "encanto_park" else 0.0,
                is_synthesized=True,
            )

        self.cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=86400)
        return result

    def fetch_streetview_segmentation(
        self,
        coord: Coordinates,
        allow_live: bool = True,
    ) -> StreetViewSegmentationResult:
        """Ground-level shade segmentation from POST /v1/streetview."""
        cache_key = f"streetview_seg:{round(coord.lat, 4)}:{round(coord.lng, 4)}"
        cached = self.cache.get(cache_key)
        if cached:
            return StreetViewSegmentationResult.model_validate(cached)

        result: StreetViewSegmentationResult | None = None

        if allow_live and self._client:
            try:
                logger.info("Calling FortyGuard API street_view_segmentation for (%.4f, %.4f)", coord.lat, coord.lng)
                raw = None
                for attempt in range(3):
                    try:
                        raw = self._client.street_view_segmentation(
                            latitude=coord.lat,
                            longitude=coord.lng,
                            vertical_angle=5.0,
                            horizontal_angle=0.0,
                            back_view=False,
                            wait=True,
                            timeout=self.timeout,
                            verbose=False,
                        )
                        break
                    except Exception as e:
                        if attempt < 2:
                            delay = 2 * (attempt + 1)
                            logger.warning("street_view_segmentation failed, retrying in %ds: %s", delay, e)
                            time.sleep(delay)
                        else:
                            raise e

                activity_id = raw.get("activity_id", "live_streetview")
                front = raw.get("result", {}).get("front", {})
                segments: dict = front.get("segments", {})

                def _class_pct(*keywords: str) -> float:
                    total = 0.0
                    for cls, pct in segments.items():
                        if any(kw in cls.lower() for kw in keywords):
                            total += float(pct or 0.0)
                    return min(total, 100.0)

                sky_pct = _class_pct("sky")
                building_pct = _class_pct("building", "wall", "fence")
                tree_pct = _class_pct("tree", "vegetation", "plant", "foliage")
                shade_pct = max(0.0, 100.0 - sky_pct)
                sky_view_factor = round(sky_pct / 100.0, 3)

                result = StreetViewSegmentationResult(
                    coordinate=coord,
                    street_shade_percentage=round(shade_pct, 1),
                    sky_view_factor=sky_view_factor,
                    building_obstruction_pct=round(building_pct, 1),
                    tree_obstruction_pct=round(tree_pct, 1),
                    is_synthesized=False,
                )
            except Exception as exc:
                logger.warning(
                    "Live street_view_segmentation call failed for (%.4f, %.4f) (%s); using synthesized baseline.",
                    coord.lat, coord.lng, exc,
                )

        if not result:
            aoi = get_aoi_for_coordinate(coord)
            base = AOI_BASELINE_METRICS.get(
                aoi.aoi_id if aoi else "downtown_phoenix",
                AOI_BASELINE_METRICS["downtown_phoenix"],
            )
            result = StreetViewSegmentationResult(
                coordinate=coord,
                street_shade_percentage=base["street_shade_percentage"],
                sky_view_factor=0.4 if base["street_shade_percentage"] > 30 else 0.85,
                is_synthesized=True,
            )

        self.cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=86400)
        return result


# ---------------------------------------------------------------------------
# Aliasing & Global Singleton
# ---------------------------------------------------------------------------

FortyGuardService = HeatService

_global_heat_service_instance: HeatService | None = None


def get_global_heat_service() -> HeatService:
    """Return the shared global HeatService instance."""
    global _global_heat_service_instance
    if _global_heat_service_instance is None:
        _global_heat_service_instance = HeatService()
    return _global_heat_service_instance


def get_global_fortyguard_service() -> HeatService:
    """Backward-compatible alias for get_global_heat_service."""
    return get_global_heat_service()


def reset_global_heat_service() -> None:
    """Reset the singleton instance for testing isolation."""
    global _global_heat_service_instance
    _global_heat_service_instance = None


__all__ = [
    "HeatService",
    "FortyGuardService",
    "FortyGuardError",
    "TaskFailedError",
    "TaskTimeoutError",
    "ActivityNotReadyError",
    "get_global_heat_service",
    "get_global_fortyguard_service",
    "reset_global_heat_service",
]
