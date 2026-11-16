"""
FastAPI REST and WebSocket Endpoints for Event Synchronization & Correlation (Phase 4).
"""

import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.sync_engine.schemas import (
    CorrelatedEvent,
    SyncEngineStatus,
    ConfigureSyncRequest,
)
from app.modules.voice_engine.schemas import VoiceEvent
from app.modules.actuator_engine.schemas import CommonJoystickEvent
from app.modules.sync_engine.manager import sync_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Synchronization Subsystem"])


class ManualCorrelateRequest(BaseModel):
    voice_event: Optional[VoiceEvent] = Field(None, description="VoiceEvent to correlate")
    joystick_event: Optional[CommonJoystickEvent] = Field(None, description="CommonJoystickEvent to correlate")


@router.get("/status", response_model=SyncEngineStatus)
async def get_sync_status():
    """Returns the truthful operational status of the event synchronization engine."""
    return sync_manager.get_status()


@router.get("/latest", response_model=Optional[CorrelatedEvent])
async def get_latest_correlated_event():
    """Returns the most recently evaluated CorrelatedEvent or null."""
    return sync_manager.synchronizer.last_correlation


@router.get("/history", response_model=List[CorrelatedEvent])
async def get_correlation_history(limit: int = 50):
    """Returns recent correlated events log."""
    return sync_manager.get_history(limit=limit)


@router.post("/configure", response_model=SyncEngineStatus)
async def configure_synchronization(req: ConfigureSyncRequest):
    """Dynamically adjusts synchronization matching window and staleness timeout."""
    success, msg = sync_manager.configure(
        sync_window_ms=req.sync_window_ms,
        max_event_age_ms=req.max_event_age_ms,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return sync_manager.get_status()


@router.post("/correlate", response_model=CorrelatedEvent)
async def correlate_manual_pair(req: ManualCorrelateRequest):
    """
    Deterministically evaluates a simulated or test pair of voice and joystick events.
    Enforces the synchronization window and returns the resulting CorrelatedEvent.
    """
    return sync_manager.correlate_manual_pair(req.voice_event, req.joystick_event)


class SyncConnectionManager:
    """Manages active WebSocket clients subscribed to /ws/sync/stream."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"Sync WebSocket client connected. Active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"Sync WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_event(self, event: CorrelatedEvent):
        """Broadcasts validated CorrelatedEvent to all connected clients."""
        payload = {
            "type": "CORRELATED_EVENT",
            "data": event.model_dump(),
        }
        dead_conns = []
        async with self._lock:
            for conn in self.active_connections:
                try:
                    await conn.send_json(payload)
                except Exception:
                    dead_conns.append(conn)

            for d in dead_conns:
                if d in self.active_connections:
                    self.active_connections.remove(d)


sync_ws_manager = SyncConnectionManager()


# Register async bridge for synchronizer events
def _broadcast_sync_to_ws(event: CorrelatedEvent):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(sync_ws_manager.broadcast_event(event), loop)
    except Exception:
        pass


sync_manager.subscribe(_broadcast_sync_to_ws)


@router.websocket("/stream")
async def websocket_sync_stream(websocket: WebSocket):
    """
    Bidirectional WebSocket endpoint for synchronized command streams and timeline telemetry.
    - Downstream: Broadcasts CorrelatedEvent frames and timeline states.
    - Upstream: Ingests configuration adjustments (CONFIGURE, PING).
    """
    await sync_ws_manager.connect(websocket)
    try:
        # Deliver initial status frame and recent history
        await websocket.send_json({
            "type": "INITIAL_STATUS",
            "status": sync_manager.get_status().model_dump(),
            "history": [ev.model_dump() for ev in sync_manager.get_history(limit=10)],
        })

        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type")

                if msg_type == "CONFIGURE":
                    w = msg.get("sync_window_ms")
                    a = msg.get("max_event_age_ms")
                    sync_manager.configure(sync_window_ms=w, max_event_age_ms=a)
                    await websocket.send_json({
                        "type": "CONFIG_UPDATED",
                        "status": sync_manager.get_status().model_dump(),
                    })
                elif msg_type == "PING":
                    await websocket.send_json({"type": "PONG", "timestamp": msg.get("timestamp")})

            except (json.JSONDecodeError, ValueError) as err:
                await websocket.send_json({
                    "type": "ERROR",
                    "detail": f"Malformed packet: {str(err)}",
                })

    except WebSocketDisconnect:
        await sync_ws_manager.disconnect(websocket)
        logger.info("Sync WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"Sync WebSocket unexpected error: {e}")
        await sync_ws_manager.disconnect(websocket)

