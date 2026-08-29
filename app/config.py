"""CoolPath application configuration."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for CoolPath."""
    model_config = SettingsConfigDict(
        env_file=(".env", "../temperature-api-quickstart/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CoolPath Microclimate Intelligence"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # FortyGuard API
    fortyguard_api_key: str = Field(default="", alias="FORTYGUARD_API_KEY")
    fortyguard_base_url: str = Field(default="https://api.fortyguard.com", alias="FORTYGUARD_BASE_URL")
    fortyguard_timeout_seconds: float = 120.0

    # Locked Study Date for Phoenix extreme heat simulation
    study_date: str = "2026-08-03"

    # Redis & Caching
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_default_ttl_seconds: int = 1800  # 30 min
    heatmap_cache_ttl_seconds: int = 7200  # 2 hours

    # Micro-Refuge Spatial Cascade (km)
    refuge_radius_tier1_km: float = 0.30  # 300m
    refuge_radius_tier2_km: float = 1.00  # 1km
    refuge_radius_tier3_km: float = 3.00  # 3km ceiling
    corridor_sample_interval_m: float = 175.0

    # Risk Scoring Thresholds (OSHA-aligned)
    risk_threshold_moderate: float = 0.35
    risk_threshold_high: float = 0.55       # >= 0.55 triggers Reroute Agent
    risk_threshold_critical: float = 0.75   # >= 0.75 triggers Alert Automation Agent


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached singleton settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
