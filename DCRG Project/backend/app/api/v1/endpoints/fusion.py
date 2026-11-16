"""
FastAPI REST and WebSocket Endpoints for DCRG Fusion Engine and CRS (Phase 5).
Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
"""

import asyncio
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.fusion_engine.schemas import (
    FusionConfig,
    FusionEngineStatus,
    FusionResult,
)
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.context_engine.schemas import ContextState
from app.modules.context_engine.service import context_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fusion", tags=["Fusion & CRS Subsystem"])


class ManualEvaluateRequest(BaseModel):
    voice_command: Optional[str] = Field(None, description="Spoken canonical command")
    voice_confidence: float = Field(0.85, ge=0.0, le=1.0, description="Speech recognition confidence")
    stress_score: float = Field(0.0, ge=0.0, le=1.0, description="Cognitive stress score")
    joystick_direction: Optional[str] = Field(None, description="Classified joystick direction")
    joystick_intensity: float = Field(0.80, ge=0.0, le=1.0, description="Joystick deflection magnitude")
    axis_x: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Raw X axis deflection")
    axis_y: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Raw Y axis deflection")
    sync_delta_ms: float = Field(10.0, ge=0.0, description="Temporal offset between inputs in ms")


@router.get("/status", response_model=FusionEngineStatus)
async def get_fusion_status():
    """Returns runtime telemetry metrics and statistics of the Fusion Engine."""
    return fusion_manager.get_status()


@router.get("/latest", response_model=Optional[FusionResult])
async def get_latest_fusion():
    """Returns the most recent multimodal fusion evaluation result or null."""
    return fusion_manager.get_latest()


@router.get("/crs")
async def get_current_crs():
    """Returns a lightweight summary of the latest Command Reliability Score."""
    latest = fusion_manager.get_latest()
    if not latest:
        return {
            "CRS": None,
            "CRS_status": "NO_EVALUATION",
            "contradiction_detected": False,
            "analytical_finding": "INSUFFICIENT_EVIDENCE",
            "recommended_state": "YELLOW",
        }
    return {
        "fusion_id": latest.fusion_id,
        "CRS": latest.CRS,
        "CRS_status": latest.CRS_status,
        "contradiction_detected": latest.contradiction_detected,
        "analytical_finding": latest.analytical_finding,
        "semantic_reliability": latest.semantic_reliability,
        "motor_agreement": latest.motor_agreement,
        "context_consistency": latest.context_consistency,
        "recommended_state": latest.recommended_state,
        "timestamp": latest.timestamp,
    }


@router.get("/history", response_model=List[FusionResult])
async def get_fusion_history(limit: int = 50):
    """Returns a chronological list of recent fusion evaluations, latest first."""
    return fusion_manager.get_history(limit=limit)


@router.get("/config", response_model=FusionConfig)
async def get_fusion_config():
    """Returns current scoring weights, thresholds, and damping parameters."""
    return fusion_manager.get_config()


@router.post("/config", response_model=FusionConfig)
async def update_fusion_config(new_config: FusionConfig):
    """Updates scoring weights and damping parameters dynamically."""
    success, msg = fusion_manager.update_config(new_config)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
    return fusion_manager.get_config()


@router.post("/evaluate", response_model=FusionResult)
async def evaluate_manual_pair(req: ManualEvaluateRequest):
    """Manually evaluates a synthetic or ad-hoc multimodal bundle."""
    return fusion_manager.evaluate_manual_bundle(
        voice_command=req.voice_command,
        voice_confidence=req.voice_confidence,
        stress_score=req.stress_score,
        joystick_direction=req.joystick_direction,
        joystick_intensity=req.joystick_intensity,
        axis_x=req.axis_x,
        axis_y=req.axis_y,
        sync_delta_ms=req.sync_delta_ms,
    )


@router.get("/context", response_model=ContextState)
async def get_context_state():
    """Returns current operational and environmental context state."""
    return context_service.get_state()


@router.post("/context", response_model=ContextState)
async def update_context_state(new_state: ContextState):
    """Updates operational and environmental context parameters."""
    return context_service.update_state(new_state)


@router.post("/context/reset", response_model=ContextState)
async def reset_context_state():
    """Resets environmental context to nominal baseline."""
    return context_service.reset_defaults()


@router.websocket("/stream")
async def websocket_fusion_stream(websocket: WebSocket):
    """
    WebSocket endpoint streaming live FusionResult events to connected clients.
    Also accepts inbound evaluation requests as JSON commands.
    """
    await websocket.accept()
    logger.info("Client connected to Fusion WebSocket stream.")

    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue[FusionResult] = asyncio.Queue()

    def sync_listener(result: FusionResult):
        loop.call_soon_threadsafe(event_queue.put_nowait, result)

    fusion_manager.subscribe(sync_listener)

    # Send initial status packet
    status_packet = {
        "type": "INITIAL_STATE",
        "status": fusion_manager.get_status().model_dump(),
        "latest": fusion_manager.get_latest().model_dump() if fusion_manager.get_latest() else None,
        "context": context_service.get_state().model_dump(),
    }
    await websocket.send_text(json.dumps(status_packet, default=str))

    async def sender():
        while True:
            result = await event_queue.get()
            payload = {
                "type": "FUSION_RESULT",
                "data": result.model_dump(),
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
                elif msg_type == "EVALUATE":
                    res = fusion_manager.evaluate_manual_bundle(
                        voice_command=data.get("voice_command"),
                        voice_confidence=float(data.get("voice_confidence", 0.85)),
                        stress_score=float(data.get("stress_score", 0.0)),
                        joystick_direction=data.get("joystick_direction"),
                        joystick_intensity=float(data.get("joystick_intensity", 0.80)),
                    )
                    await websocket.send_text(json.dumps({"type": "FUSION_RESULT", "data": res.model_dump()}, default=str))
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
        logger.info("Client disconnected from Fusion WebSocket stream.")
    finally:
        fusion_manager.unsubscribe(sync_listener)
        sender_task.cancel()
        receiver_task.cancel()

