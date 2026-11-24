"""
FastAPI REST and WebSocket Endpoints for Robot Simulation (Phase 7).
Provides real-time kinematic telemetry, command execution audit logs,
simulation environment controls, and high-frequency WebSocket streaming.
Compliant with DCRG-ARCH-005.
"""

import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.schemas import (
    CommandExecutionRecord,
    RobotPose,
    SimulationControlRequest,
    SimulationState,
)
from app.modules.simulation_engine.manager import simulation_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation Subsystem"])


class ResetPoseRequest(BaseModel):
    """Payload to reset the simulated vehicle spatial coordinates."""
    x: float = Field(0.0, description="Target X coordinate (meters)")
    y: float = Field(0.0, description="Target Y coordinate (meters)")
    heading: float = Field(0.0, description="Target heading (degrees)")


class GatewayExecuteRequest(BaseModel):
    """Payload to dispatch a command through the simulated gateway."""
    decision_id: str = Field(..., description="UUID of the safety decision")
    command: str = Field(..., description="Motion command attempted")
    auth_token: Optional[str] = Field(None, description="Cryptographic execution signature")


@router.get("/state", response_model=SimulationState)
async def get_simulation_state():
    """Returns the current real-time state of the robot simulation environment."""
    return simulation_manager.get_state()


@router.get("/logs", response_model=List[CommandExecutionRecord])
async def get_execution_logs(limit: int = 50):
    """Returns chronological audit trail of command execution events."""
    return simulation_manager.get_execution_logs(limit=limit)


@router.post("/control", response_model=SimulationState)
async def control_simulation(req: SimulationControlRequest):
    """
    Executes simulation environment control actions:
    START, PAUSE, RESUME, RESET, or SET_SPEED.
    """
    action = req.action.upper().strip()
    if action == "START":
        simulation_manager.start()
    elif action == "PAUSE":
        simulation_manager.pause()
    elif action == "RESUME":
        simulation_manager.resume()
    elif action == "RESET":
        simulation_manager.reset_pose(req.reset_x or 0.0, req.reset_y or 0.0)
    elif action == "SET_SPEED":
        if req.speed_multiplier is not None:
            simulation_manager.set_speed_multiplier(req.speed_multiplier)
    elif action in ("FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"):
        simulation_manager.simulator.apply_authorized_command(action, "GREEN")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown simulation action '{action}'. Valid actions: START, PAUSE, RESUME, RESET, SET_SPEED, FORWARD, BACKWARD, LEFT, RIGHT, STOP.",
        )
    return simulation_manager.get_state()


@router.post("/reset", response_model=RobotPose)
async def reset_robot_pose(req: Optional[ResetPoseRequest] = None):
    """Resets robot position, zeroing velocity and clearing collision flags."""
    x = req.x if req else 0.0
    y = req.y if req else 0.0
    heading = req.heading if req else 0.0
    return simulation_manager.reset_pose(x, y, heading)


@router.post("/dispatch")
async def dispatch_gateway_command(req: GatewayExecuteRequest):
    """Dispatches a command through the simulated gateway for simulation execution."""
    # Look up decision from safety manager history
    history = safety_manager.get_history(limit=100)
    decision = next((d for d in history if d.decision_id == req.decision_id), None)
    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Safety decision '{req.decision_id}' not found in authorization history.",
        )

    is_executed, log_record = simulation_manager.dispatch_gateway_command(
        decision=decision,
        command=req.command,
        auth_token=req.auth_token,
    )
    return {
        "is_executed": is_executed,
        "record": log_record.model_dump(),
        "state": simulation_manager.get_state().model_dump(),
    }


@router.websocket("/stream")
async def simulation_stream_endpoint(websocket: WebSocket):
    """
    High-frequency WebSocket stream broadcasting real-time robot simulation telemetry.
    Accepts incoming control commands (PING, PAUSE, RESUME, RESET, SET_SPEED).
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def state_listener(state: SimulationState):
        loop.call_soon_threadsafe(event_queue.put_nowait, state)

    simulation_manager.subscribe(state_listener)

    # Initial snapshot
    init_state = simulation_manager.get_state()
    await websocket.send_text(json.dumps({
        "type": "SIMULATION_INIT",
        "state": init_state.model_dump(),
        "recent_logs": [l.model_dump() for l in simulation_manager.get_execution_logs(limit=10)],
    }, default=str))

    async def sender():
        while True:
            state = await event_queue.get()
            payload = {
                "type": "SIMULATION_UPDATE",
                "state": state.model_dump(),
            }
            await websocket.send_text(json.dumps(payload, default=str))

    async def receiver():
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg_type = data.get("type", "")
                if msg_type == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": data.get("timestamp")}))
                elif msg_type == "PAUSE":
                    simulation_manager.pause()
                elif msg_type == "RESUME":
                    simulation_manager.resume()
                elif msg_type == "RESET":
                    simulation_manager.reset_pose(
                        data.get("x", 0.0),
                        data.get("y", 0.0),
                        data.get("heading", 0.0),
                    )
                elif msg_type == "SET_SPEED":
                    mult = data.get("speed_multiplier", 1.0)
                    simulation_manager.set_speed_multiplier(mult)
                elif msg_type == "COMMAND":
                    cmd = data.get("command", "STOP").upper().strip()
                    simulation_manager.simulator.apply_authorized_command(cmd, "GREEN")
            except json.JSONDecodeError:
                pass

    sender_task = asyncio.create_task(sender())
    receiver_task = asyncio.create_task(receiver())

    try:
        done, pending = await asyncio.wait(
            [sender_task, receiver_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        logger.info("Client disconnected from Simulation WebSocket stream.")
    finally:
        simulation_manager.unsubscribe(state_listener)
        sender_task.cancel()
        receiver_task.cancel()

