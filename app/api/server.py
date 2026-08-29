"""FastAPI application factory for CoolPath with lifespan lifecycle management."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as http_router
from app.api.websocket import background_fleet_broadcast_loop, router as ws_router
from app.config import get_settings

logger = logging.getLogger("coolpath.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initialises services and starts background cache warm."""
    settings = get_settings()
    logger.info("Initializing %s v%s", settings.app_name, settings.app_version)

    # Initialize the shared FortyGuardService singleton
    from app.services.fortyguard_service import get_global_fortyguard_service
    loop = asyncio.get_event_loop()
    fg_service = await loop.run_in_executor(None, get_global_fortyguard_service)
    logger.info("FortyGuardService singleton ready.")

    # Build coordinator and simulator
    from app.agents.coordinator import DecisionCoordinatorAgent
    from app.simulation.fleet_simulator import FleetSimulator

    coordinator = DecisionCoordinatorAgent()
    simulator = FleetSimulator(coordinator=coordinator)

    # Attach to app.state
    app.state.fg_service = fg_service
    app.state.coordinator = coordinator
    app.state.simulator = simulator

    # Start background warm cycle
    from app.services.background_worker import MicroclimateBackgroundWorker
    worker = MicroclimateBackgroundWorker(fortyguard_service=fg_service)
    loop.run_in_executor(None, worker.warm_cache_for_all_aois)
    from app.core.phoenix_aois import PHOENIX_AOIS
    logger.info(
        "Cache pre-warm task started in background (%d AOIs). Server accepting requests.",
        len(PHOENIX_AOIS),
    )

    # Start the periodic 15-minute refresh scheduler
    worker.start()

    # Start the real-time WebSocket fleet broadcast loop
    broadcast_task = asyncio.create_task(background_fleet_broadcast_loop(app.state))

    yield

    # Shutdown
    broadcast_task.cancel()
    worker.shutdown()
    logger.info("CoolPath server shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Multi-Agent Microclimate Risk Intelligence & Shaded Corridor Routing for Fleets",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include REST HTTP and WebSocket routers
    app.include_router(http_router)
    app.include_router(ws_router)

    # Mount static assets
    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/")
        @app.get("/dashboard")
        async def serve_dashboard():
            return FileResponse(str(static_dir / "index.html"))

    return app


app = create_app()


__all__ = ["create_app", "app"]
