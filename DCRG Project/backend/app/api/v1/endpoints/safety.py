"""
FastAPI REST and WebSocket Endpoints for Tiered Safety Authorization (Phase 6).
Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
"""

import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.safety_engine.schemas import (
    ConfirmationAction,
    ConfirmationRequest,
    EmergencyResetRequest,
    EmergencySource,
    EmergencyStopRequest,
    GatewayExecutionRecord,
    SafetyDecision,
    SafetyEngineStatus,
)
from app.modules.safety_engine.manager import safety_manager
from app.modules.safety_engine.gateway import simulated_gateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["Safety Authorization Subsystem"])


class GatewayExecuteRequest(BaseModel):
    decision_id: str = Field(..., description="UUID of the safety decision")
    command: str = Field(..., description="Motion command attempted")
    auth_token: Optional[str] = Field(None, description="Cryptographic execution signature")


@router.get("/status", response_model=SafetyEngineStatus)
async def get_safety_status():
    """Returns runtime telemetry, active state, and E-Stop latch status."""
    return safety_manager.get_status()


@router.get("/latest", response_model=Optional[SafetyDecision])
async def get_latest_safety_decision():
    """Returns the most recent authoritative SafetyDecision or null."""
    return safety_manager.get_latest()


@router.get("/history", response_model=List[SafetyDecision])
async def get_safety_history(limit: int = 50):
    """Returns chronological audit trail of safety authorization decisions."""
    return safety_manager.get_history(limit=limit)


@router.get("/pending", response_model=List[SafetyDecision])
async def get_pending_confirmations():
    """Returns all commands currently on YELLOW hold awaiting operator confirmation."""
    return safety_manager.get_pending_confirmations()


@router.post("/confirm", response_model=SafetyDecision)
async def confirm_or_reject_decision(req: ConfirmationRequest):
    """Processes operator confirmation or rejection for a YELLOW command hold."""
    success, updated_dec, msg = safety_manager.resolve_confirmation(
        decision_id=req.decision_id,
        action=req.action,
        operator_id=req.operator_id,
        reason=req.reason,
    )
    if not updated_dec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=msg,
        )
    if not success and req.action == ConfirmationAction.CONFIRM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return updated_dec


@router.post("/estop", response_model=SafetyDecision)
async def activate_emergency_stop(req: EmergencyStopRequest):
    """Activates immediate software emergency stop latch and command lockout."""
    return safety_manager.trigger_emergency_stop(
        source=req.source,
        reason=req.reason,
        operator_id=req.operator_id,
    )


@router.post("/reset")
async def reset_emergency_stop(req: EmergencyResetRequest):
    """Authorizes unlatching of an active Emergency Stop."""
    success, msg = safety_manager.reset_emergency_stop(
        reset_pin=req.reset_pin,
        operator_id=req.operator_id,
        reason=req.reason,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=msg,
        )
    return {"status": "unlatched", "message": msg}


@router.post("/gateway/execute", response_model=GatewayExecutionRecord)
async def execute_simulated_command(req: GatewayExecuteRequest):
    """
    Submits an authorized command to the Simulated Command Gateway.
    Verifies decision ID, command matching, auth token signature, and expiration TTL.
    """
    # Lookup decision in safety manager history
    decision = None
    for dec in reversed(safety_manager.get_history(limit=100)):
        if dec.decision_id == req.decision_id:
            decision = dec
            break

    if not decision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Decision ID {req.decision_id} not found in authorization records.",
        )

    accepted, record = simulated_gateway.dispatch(
        decision=decision,
        command_attempted=req.command,
        auth_token=req.auth_token,
    )

    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=record.reason,
        )

    return record


@router.get("/gateway/history", response_model=List[GatewayExecutionRecord])
async def get_gateway_execution_history(limit: int = 50):
    """Returns audit trail of commands dispatched to the simulated gateway."""
    return simulated_gateway.get_history(limit=limit)


@router.websocket("/stream")
async def websocket_safety_stream(websocket: WebSocket):
    """
    WebSocket endpoint streaming live SafetyDecision events, E-Stop changes,
    and pending confirmation states to connected clients.
    """
    await websocket.accept()
    logger.info("Client connected to Safety WebSocket stream.")

    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[SafetyDecision] = asyncio.Queue()

    def safety_listener(decision: SafetyDecision):
        loop.call_soon_threadsafe(event_queue.put_nowait, decision)

    safety_manager.subscribe(safety_listener)

    # Initial snapshot packet
    init_packet = {
        "type": "INITIAL_SAFETY_STATE",
        "status": safety_manager.get_status().model_dump(),
        "latest": safety_manager.get_latest().model_dump() if safety_manager.get_latest() else None,
        "pending": [d.model_dump() for d in safety_manager.get_pending_confirmations()],
        "gateway_history": [r.model_dump() for r in simulated_gateway.get_history(limit=10)],
    }
    await websocket.send_text(json.dumps(init_packet, default=str))

    async def sender():
        while True:
            decision = await event_queue.get()
            payload = {
                "type": "SAFETY_DECISION",
                "data": decision.model_dump(),
                "status": safety_manager.get_status().model_dump(),
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
                elif msg_type == "CONFIRM":
                    action = ConfirmationAction.CONFIRM if data.get("action") == "CONFIRM" else ConfirmationAction.REJECT
                    safety_manager.resolve_confirmation(
                        decision_id=data.get("decision_id"),
                        action=action,
                        operator_id=data.get("operator_id", "OP-WS"),
                    )
                elif msg_type == "ESTOP":
                    safety_manager.trigger_emergency_stop(
                        source=EmergencySource.SOFTWARE_UI,
                        reason=data.get("reason", "WebSocket emergency stop"),
                        operator_id=data.get("operator_id", "OP-WS"),
                    )
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
        logger.info("Client disconnected from Safety WebSocket stream.")
    finally:
        safety_manager.unsubscribe(safety_listener)
        sender_task.cancel()
        receiver_task.cancel()

