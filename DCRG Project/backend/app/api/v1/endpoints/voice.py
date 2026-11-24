"""
FastAPI REST and WebSocket Endpoints for Voice Recognition and Prosody Subsystem (Phase 3).
"""

import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel, Field

from app.modules.voice_engine.schemas import (
    VoiceEvent,
    VoiceSystemStatus,
    MicrophoneStatus,
)
from app.modules.voice_engine.manager import voice_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice Recognition Subsystem"])


class SelectDeviceRequest(BaseModel):
    device_index: Optional[int] = Field(None, description="Audio input device index from /devices")


class MuteRequest(BaseModel):
    muted: bool = Field(..., description="Whether to mute the microphone")


class ProcessAudioRequest(BaseModel):
    audio_base64: Optional[str] = Field(None, description="Base64 encoded raw 16-bit PCM or 32-bit float audio")
    audio_samples: Optional[List[float]] = Field(None, description="Raw normalized float32 samples [-1.0, 1.0]")
    sample_rate: int = Field(16000, description="Audio sample rate (default 16000)")
    operator_id: Optional[str] = Field("OP-PRIMARY", description="Operator identity identifier")
    client_timestamp: Optional[float] = Field(None, description="Client timestamp in milliseconds")


class AudioUploadBase64Request(BaseModel):
    filename: str = Field(..., description="Uploaded audio filename")
    audio_base64: str = Field(..., description="Base64 encoded audio file bytes")
    operator_id: Optional[str] = Field("OP-PRIMARY", description="Operator identity identifier")


class PredefinedSampleItem(BaseModel):
    id: str
    filename: str
    command: str
    label: str
    description: str
    url: str


@router.get("/status", response_model=VoiceSystemStatus)
async def get_voice_status():
    """Returns the truthful status of the microphone, model, and voice engine."""
    return voice_manager.get_status()


@router.get("/devices")
async def get_audio_devices():
    """Lists physically discovered microphone and audio input devices."""
    return voice_manager.mic_service.get_available_devices()


@router.post("/start")
async def start_voice_capture():
    """Starts microphone audio capture and background STT/prosody inference."""
    success, message = voice_manager.start_microphone()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return {
        "status": "success",
        "microphone_status": voice_manager.mic_service.status,
        "message": message,
    }


@router.post("/stop")
async def stop_voice_capture():
    """Stops microphone audio capture."""
    success, message = voice_manager.stop_microphone()
    return {
        "status": "success",
        "microphone_status": voice_manager.mic_service.status,
        "message": message,
    }


@router.post("/mute")
async def set_microphone_mute(req: MuteRequest):
    """Sets or toggles microphone mute state."""
    is_muted = voice_manager.set_mute(req.muted)
    return {
        "status": "success",
        "is_muted": is_muted,
        "microphone_status": voice_manager.mic_service.status,
    }


@router.post("/select-device")
async def select_audio_device(req: SelectDeviceRequest):
    """Selects target microphone input device."""
    success, message = voice_manager.select_device(req.device_index)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    return {
        "status": "success",
        "selected_device_index": voice_manager.mic_service.device_index,
        "selected_device_name": voice_manager.mic_service.device_name,
        "message": message,
    }


@router.get("/latest", response_model=Optional[VoiceEvent])
async def get_latest_voice_event():
    """Returns the most recent VoiceEvent or null if none processed yet."""
    return voice_manager.last_event


@router.post("/process-audio", response_model=VoiceEvent)
async def process_audio_buffer(req: ProcessAudioRequest):
    """
    Ingests and processes a discrete audio chunk (samples or base64).
    Returns the assembled VoiceEvent with Prosody and Semantic classification.
    """
    target_sr = req.sample_rate
    if req.audio_samples is not None and len(req.audio_samples) > 0:
        audio_array = np.array(req.audio_samples, dtype=np.float32)
    elif req.audio_base64:
        try:
            raw_bytes = base64.b64decode(req.audio_base64)
            # Try soundfile decoding first (supports WAV/FLAC/OGG containers)
            try:
                import io
                import soundfile as sf
                data, file_sr = sf.read(io.BytesIO(raw_bytes))
                if data.ndim > 1:
                    data = data.mean(axis=1)
                audio_array = data.astype(np.float32)
                target_sr = file_sr
            except Exception:
                target_sr = req.sample_rate
                if len(raw_bytes) % 4 == 0:
                    audio_array = np.frombuffer(raw_bytes, dtype=np.float32)
                else:
                    int_data = np.frombuffer(raw_bytes, dtype=np.int16)
                    audio_array = int_data.astype(np.float32) / 32768.0
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to decode audio base64 payload: {str(e)}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either audio_samples or audio_base64",
        )

    event = voice_manager.process_audio_chunk(
        audio_data=audio_array,
        sample_rate=target_sr,
        operator_id=req.operator_id or "OP-PRIMARY",
        client_timestamp=req.client_timestamp,
    )
    return event


@router.post("/upload", response_model=VoiceEvent)
async def upload_audio_file(req: AudioUploadBase64Request):
    """
    Uploads and processes an entire recorded or predefined audio file (WAV, MP3, etc.).
    Extracts samples, runs speech-to-text, prosody, and semantic classification,
    and dispatches to the multimodal synchronizer and CRS fusion engine.
    """
    try:
        raw_bytes = base64.b64decode(req.audio_base64)
        import io
        import soundfile as sf
        import librosa

        data, sr = sf.read(io.BytesIO(raw_bytes))
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != 16000:
            data = librosa.resample(data.astype(np.float32), orig_sr=sr, target_sr=16000)
            sr = 16000
        audio_array = data.astype(np.float32)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to decode and parse audio file '{req.filename}': {str(e)}",
        )

    event = voice_manager.process_audio_chunk(
        audio_data=audio_array,
        sample_rate=sr,
        operator_id=req.operator_id or "OP-UPLOAD",
    )
    return event


@router.get("/samples", response_model=List[PredefinedSampleItem])
async def list_predefined_samples():
    """Returns a catalogue of curated predefined audio command files available on the server."""
    return [
        PredefinedSampleItem(
            id="forward",
            filename="forward.wav",
            command="FORWARD",
            label="Move Forward",
            description="Clear spoken command: 'Drone move forward'",
            url="/static/samples/forward.wav",
        ),
        PredefinedSampleItem(
            id="backward",
            filename="backward.wav",
            command="BACKWARD",
            label="Move Backward",
            description="Clear spoken command: 'Drone move backward'",
            url="/static/samples/backward.wav",
        ),
        PredefinedSampleItem(
            id="left",
            filename="left.wav",
            command="LEFT",
            label="Move Left",
            description="Clear spoken command: 'Drone move left'",
            url="/static/samples/left.wav",
        ),
        PredefinedSampleItem(
            id="right",
            filename="right.wav",
            command="RIGHT",
            label="Turn Right",
            description="Clear spoken command: 'Drone turn right'",
            url="/static/samples/right.wav",
        ),
        PredefinedSampleItem(
            id="stop",
            filename="stop.wav",
            command="STOP",
            label="Stop Drone",
            description="Clear emergency halt command: 'Drone stop'",
            url="/static/samples/stop.wav",
        ),
        PredefinedSampleItem(
            id="emergency_stop",
            filename="emergency_stop.wav",
            command="EMERGENCY_STOP",
            label="Emergency Stop",
            description="Critical safety shutdown command: 'Emergency stop'",
            url="/static/samples/emergency_stop.wav",
        ),
    ]


@router.post("/samples/{sample_id}/play", response_model=VoiceEvent)
async def play_predefined_sample(sample_id: str):
    """
    Loads and executes a predefined audio command from the curated sample library.
    Immediately feeds it into the voice engine, updating the CRS score in real-time.
    """
    import os
    import soundfile as sf
    import librosa

    clean_id = sample_id.lower().strip()
    filename = f"{clean_id}.wav"
    sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static/samples"))
    file_path = os.path.join(sample_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Predefined sample '{sample_id}' not found at {file_path}",
        )

    try:
        data, sr = sf.read(file_path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != 16000:
            data = librosa.resample(data.astype(np.float32), orig_sr=sr, target_sr=16000)
            sr = 16000
        audio_array = data.astype(np.float32)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read sample '{filename}': {str(e)}",
        )

    event = voice_manager.process_audio_chunk(
        audio_data=audio_array,
        sample_rate=sr,
        operator_id=f"OP-PREDEFINED-{clean_id.upper()}",
    )
    return event


class VoiceConnectionManager:
    """Manages active WebSocket connections to /ws/voice/stream."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"Voice WebSocket client connected. Active: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"Voice WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_event(self, event: VoiceEvent):
        """Broadcasts validated VoiceEvent to all connected clients."""
        payload = {
            "type": "VOICE_EVENT",
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


voice_ws_manager = VoiceConnectionManager()


# Register async bridge for voice manager events
def _broadcast_voice_to_ws(event: VoiceEvent):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(voice_ws_manager.broadcast_event(event), loop)
    except Exception:
        pass


voice_manager.subscribe(_broadcast_voice_to_ws)


@router.websocket("/stream")
async def websocket_voice_stream(websocket: WebSocket):
    """
    Bidirectional WebSocket endpoint for live voice recognition telemetry.
    - Downstream: Streams real-time VoiceEvents, transcripts, prosody, and mic health.
    - Upstream: Receives control commands (START_MIC, STOP_MIC, SET_MUTE, PING).
    """
    await voice_ws_manager.connect(websocket)
    try:
        # Initial status frame
        await websocket.send_json({
            "type": "INITIAL_STATUS",
            "status": voice_manager.get_status().model_dump(),
        })

        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
                msg_type = msg.get("type")

                if msg_type == "START_MIC":
                    success, text = voice_manager.start_microphone()
                    await websocket.send_json({
                        "type": "MIC_CONTROL_RESULT",
                        "action": "START",
                        "success": success,
                        "message": text,
                        "status": voice_manager.get_status().model_dump(),
                    })
                elif msg_type == "STOP_MIC":
                    success, text = voice_manager.stop_microphone()
                    await websocket.send_json({
                        "type": "MIC_CONTROL_RESULT",
                        "action": "STOP",
                        "success": success,
                        "message": text,
                        "status": voice_manager.get_status().model_dump(),
                    })
                elif msg_type == "SET_MUTE":
                    muted = bool(msg.get("muted", False))
                    is_muted = voice_manager.set_mute(muted)
                    await websocket.send_json({
                        "type": "MIC_CONTROL_RESULT",
                        "action": "MUTE",
                        "is_muted": is_muted,
                        "status": voice_manager.get_status().model_dump(),
                    })
                elif msg_type == "PING":
                    await websocket.send_json({"type": "PONG", "timestamp": msg.get("timestamp")})

            except (json.JSONDecodeError, ValueError) as err:
                await websocket.send_json({
                    "type": "ERROR",
                    "detail": f"Malformed packet: {str(err)}",
                })

    except WebSocketDisconnect:
        await voice_ws_manager.disconnect(websocket)
        logger.info("Voice WebSocket connection closed by client.")
    except Exception as e:
        logger.error(f"Voice WebSocket unexpected error: {e}")
        await voice_ws_manager.disconnect(websocket)

