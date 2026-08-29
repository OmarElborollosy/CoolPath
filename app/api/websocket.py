"""WebSocket real-time streaming endpoint for fleet simulation and telemetry."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("coolpath.websocket")

router = APIRouter()


class WebSocketManager:
    """Manages active WebSocket client connections and simulation broadcast."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self.is_streaming: bool = False
        self.current_sim_time_minutes: int = 13 * 60  # 13:00 start (1 PM)
        self.end_sim_time_minutes: int = 16 * 60 + 40  # 16:40 end (4:40 PM)
        self.sim_step_minutes: int = 5
        self.stream_interval_seconds: float = 2.0
        self._background_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info("WebSocket client connected (total active: %d)", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected (total active: %d)", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast JSON message to all connected clients."""
        payload = json.dumps(message)
        dead_connections = []
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                if dead in self.active_connections:
                    self.active_connections.remove(dead)

    def format_sim_time(self) -> str:
        h = self.current_sim_time_minutes // 60
        m = self.current_sim_time_minutes % 60
        return f"{h:02d}:{m:02d}"

    def step_time(self) -> str:
        self.current_sim_time_minutes += self.sim_step_minutes
        if self.current_sim_time_minutes > self.end_sim_time_minutes:
            self.current_sim_time_minutes = 13 * 60  # Loop back to 13:00
        return self.format_sim_time()

    def set_sim_time(self, time_str: str) -> None:
        try:
            parts = time_str.split(":")
            self.current_sim_time_minutes = int(parts[0]) * 60 + int(parts[1])
        except Exception:
            pass


ws_manager = WebSocketManager()


@router.websocket("/ws/fleet")
async def fleet_websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket connection streaming fleet states, risk scores, and autonomous alerts."""
    await ws_manager.connect(websocket)
    simulator = websocket.app.state.simulator

    try:
        # 1. Send immediate initial state
        initial_sim_time = ws_manager.format_sim_time()
        initial_frame = await simulator.step_simulation(initial_sim_time)
        await websocket.send_json({
            "type": "fleet_update",
            "simulation_time": initial_sim_time,
            "data": initial_frame.model_dump(mode="json"),
        })

        # 2. Listen for client interactive commands
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                cmd = msg.get("command")

                if cmd == "set_time":
                    new_time = msg.get("time", "14:15")
                    ws_manager.set_sim_time(new_time)
                    frame = await simulator.step_simulation(new_time)
                    await ws_manager.broadcast({
                        "type": "fleet_update",
                        "simulation_time": new_time,
                        "data": frame.model_dump(mode="json"),
                    })

                elif cmd == "step":
                    sim_time = ws_manager.step_time()
                    frame = await simulator.step_simulation(sim_time)
                    await ws_manager.broadcast({
                        "type": "fleet_update",
                        "simulation_time": sim_time,
                        "data": frame.model_dump(mode="json"),
                    })

                elif cmd == "play":
                    ws_manager.is_streaming = True
                    await ws_manager.broadcast({"type": "playback_status", "is_streaming": True})

                elif cmd == "pause":
                    ws_manager.is_streaming = False
                    await ws_manager.broadcast({"type": "playback_status", "is_streaming": False})

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket error (%s); disconnecting client.", exc)
        await ws_manager.disconnect(websocket)


async def background_fleet_broadcast_loop(app_state: Any) -> None:
    """Periodic background runner stepping simulation and broadcasting updates when active."""
    while True:
        try:
            if ws_manager.is_streaming and ws_manager.active_connections:
                sim_time = ws_manager.step_time()
                simulator = getattr(app_state, "simulator", None)
                if simulator:
                    frame = await simulator.step_simulation(sim_time)
                    await ws_manager.broadcast({
                        "type": "fleet_update",
                        "simulation_time": sim_time,
                        "data": frame.model_dump(mode="json"),
                    })
        except Exception as exc:
            logger.error("Error in background fleet broadcast loop: %s", exc)

        await asyncio.sleep(ws_manager.stream_interval_seconds)


__all__ = ["router", "ws_manager", "background_fleet_broadcast_loop"]
