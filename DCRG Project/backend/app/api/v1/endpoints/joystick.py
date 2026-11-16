"""
FastAPI REST and WebSocket Endpoints for Joystick Input Subsystem.
"""

import asyncio
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickMode,
    JoystickSystemStatus,
    ConnectionStatus,
)
from app.modules.actuator_engine.manager import actuator_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/joystick", tags=["Joystick Subsystem"])


class VirtualInputRequest(BaseModel):
    axis_x: float = Field(..., ge=-1.0, le=1.0, description="Virtual X deflection")
    axis_y: float = Field(..., ge=-1.0, le=1.0, description="Virtual Y deflection")
    buttons: Optional[List[bool]] = Field(default_factory=list, description="Digital button states")
    device_id: Optional[str] = Field("VIRT-REACT-CANVAS", description="Client identifier")
    client_timestamp: Optional[float] = Field(None, description="Client clock in ms")


class SetModeRequest(BaseModel):
    mode: JoystickMode = Field(..., description="Target mode (REAL_HARDWARE or VIRTUAL_SIMULATION)")
    force: Optional[bool] = Field(False, description="Allow hardware mode engagement")


class HardwareInputRequest(BaseModel):
    axis_x: float = Field(..., ge=-1.0, le=1.0, description="Hardware X deflection")
    axis_y: float = Field(..., ge=-1.0, le=1.0, description="Hardware Y deflection")
    buttons: Optional[List[bool]] = Field(default_factory=list, description="Digital button states")
    device_id: Optional[str] = Field("USB-PHYSICAL-CONTROLLER", description="Device identifier")
    client_timestamp: Optional[float] = Field(None, description="Client clock in ms")


@router.get("/status", response_model=JoystickSystemStatus)
async def get_joystick_status():
    """Returns the truthful system and connection status of joystick inputs."""
    return actuator_manager.get_status()


@router.get("/devices")
async def get_detected_devices():
    """Lists physically discovered USB and Bluetooth controllers."""
    return actuator_manager.physical_service.get_connected_devices()


@router.post("/rescan")
async def rescan_joystick_devices():
    """Forces Pygame SDL2 to re-scan for newly plugged USB flight sticks / gamepads."""
    devices = actuator_manager.physical_service.rescan()
    return {
        "status": "success",
        "device_count": len(devices),
        "devices": devices
    }


@router.post("/mode")
async def set_joystick_mode(req: SetModeRequest):
    """
    Safely switches between REAL_HARDWARE and VIRTUAL_SIMULATION modes.
    """
    success, message = actuator_manager.set_mode(req.mode, force=bool(req.force))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    return {
        "status": "success",
        "active_mode": actuator_manager.active_mode,
        "message": message
    }


@router.post("/hardware", response_model=CommonJoystickEvent)
async def post_hardware_input(req: HardwareInputRequest):
    """
    Ingests a single hardware joystick frame over HTTP REST.
    Returns the validated, classified CommonJoystickEvent with is_simulation=False.
    """
    try:
        event = actuator_manager.ingest_hardware_input(
            raw_x=req.axis_x,
            raw_y=req.axis_y,
            buttons=req.buttons,
            device_id=req.device_id or "USB-PHYSICAL-CONTROLLER",
            client_timestamp=req.client_timestamp
        )
        return event
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/virtual", response_model=CommonJoystickEvent)
async def post_virtual_input(req: VirtualInputRequest):
    """
    Ingests a single virtual joystick frame over HTTP REST.
    Returns the validated, classified CommonJoystickEvent.
    """
    try:
        event = actuator_manager.ingest_virtual_input(
            raw_x=req.axis_x,
            raw_y=req.axis_y,
            buttons=req.buttons,
            device_id=req.device_id or "VIRT-REACT-CANVAS",
            client_timestamp=req.client_timestamp
        )
        return event
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


class JoystickConnectionManager:
    """Manages active WebSocket connections to /ws/joystick/stream."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_event(self, event: CommonJoystickEvent):
        """Broadcasts validated joystick event to all connected web clients."""
        payload = {
            "type": "JOYSTICK_EVENT",
            "data": event.model_dump()
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


ws_manager = JoystickConnectionManager()


# Register async bridge for actuator manager events
def _broadcast_to_ws(event: CommonJoystickEvent):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast_event(event), loop)
    except Exception:
        pass

actuator_manager.subscribe(_broadcast_to_ws)


@router.websocket("/stream")
async def websocket_joystick_stream(websocket: WebSocket):
    """
    Bidirectional WebSocket endpoint for joystick events.
    - Upstream: Ingests virtual joystick input frames from React frontend.
    - Downstream: Streams validated CommonJoystickEvents and telemetry status.
    """
    await ws_manager.connect(websocket)
    try:
        # Send initial status frame upon connection
        await websocket.send_json({
            "type": "INITIAL_STATUS",
            "status": actuator_manager.get_status().model_dump()
        })

        while True:
            # Await incoming message from client
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type")

                if msg_type == "VIRTUAL_INPUT":
                    axis_x = float(msg.get("axis_x", 0.0))
                    axis_y = float(msg.get("axis_y", 0.0))
                    buttons = msg.get("buttons", [])
                    client_ts = msg.get("client_timestamp")

                    actuator_manager.ingest_virtual_input(
                        raw_x=axis_x,
                        raw_y=axis_y,
                        buttons=buttons,
                        client_timestamp=client_ts
                    )
                elif msg_type in ("HARDWARE_INPUT", "PHYSICAL_INPUT"):
                    axis_x = float(msg.get("axis_x", 0.0))
                    axis_y = float(msg.get("axis_y", 0.0))
                    buttons = msg.get("buttons", [])
                    device_id = msg.get("device_id", "USB-PHYSICAL-CONTROLLER")
                    client_ts = msg.get("client_timestamp")

                    actuator_manager.ingest_hardware_input(
                        raw_x=axis_x,
                        raw_y=axis_y,
                        buttons=buttons,
                        device_id=device_id,
                        client_timestamp=client_ts
                    )
                elif msg_type == "SET_MODE":
                    target_mode = JoystickMode(msg.get("mode"))
                    force = msg.get("force", True)
                    success, text = actuator_manager.set_mode(target_mode, force=force)
                    await websocket.send_json({
                        "type": "MODE_CHANGE_RESULT",
                        "success": success,
                        "message": text,
                        "active_mode": actuator_manager.active_mode
                    })
                elif msg_type == "PING":
                    await websocket.send_json({"type": "PONG", "timestamp": msg.get("timestamp")})

            except (json.JSONDecodeError, ValueError) as err:
                await websocket.send_json({
                    "type": "ERROR",
                    "detail": f"Malformed packet: {str(err)}"
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
        logger.info("Joystick WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"WebSocket unexpected error: {e}")
        await ws_manager.disconnect(websocket)

