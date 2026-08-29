"""FortyGuard service module (re-exports HeatService for backward compatibility)."""
from __future__ import annotations

from app.services.heat_service import (
    ActivityNotReadyError,
    FortyGuardError,
    FortyGuardService,
    HeatService,
    TaskFailedError,
    TaskTimeoutError,
    get_global_fortyguard_service,
    get_global_heat_service,
    reset_global_heat_service,
)

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
