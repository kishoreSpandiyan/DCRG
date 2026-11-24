"""
Automated integration tests for Voice REST API and WebSocket endpoints (Phase 3).
"""

import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.modules.voice_engine.schemas import CanonicalCommand


def test_voice_status_endpoint(client: TestClient):
    """Verifies GET /api/v1/voice/status returns valid voice subsystem status."""
    response = client.get("/api/v1/voice/status")
    assert response.status_code == 200
    data = response.json()
    assert "microphone_status" in data
    assert "is_capturing" in data
    assert "is_muted" in data
    assert "model_name" in data
    assert "sample_rate" in data
    assert data["sample_rate"] == 16000


def test_voice_devices_endpoint(client: TestClient):
    """Verifies GET /api/v1/voice/devices returns list of input devices."""
    response = client.get("/api/v1/voice/devices")
    assert response.status_code == 200
    devices = response.json()
    assert isinstance(devices, list)


def test_voice_mute_endpoint(client: TestClient):
    """Verifies POST /api/v1/voice/mute toggles mute state."""
    response = client.post("/api/v1/voice/mute", json={"muted": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_muted"] is True

    # Unmute
    response2 = client.post("/api/v1/voice/mute", json={"muted": False})
    assert response2.status_code == 200
    assert response2.json()["is_muted"] is False


def test_voice_select_device_invalid(client: TestClient):
    """Verifies POST /api/v1/voice/select-device with invalid index returns 400."""
    response = client.post("/api/v1/voice/select-device", json={"device_index": 99999})
    assert response.status_code == 400


def test_process_audio_endpoint_synthetic(client: TestClient):
    """
    Verifies POST /api/v1/voice/process-audio processes synthetic float audio,
    extracts prosody, transcribes, and returns a valid VoiceEvent.
    """
    sr = 16000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    # Generate 150 Hz tone
    audio_samples = (0.5 * np.sin(2 * np.pi * 150.0 * t)).tolist()

    response = client.post(
        "/api/v1/voice/process-audio",
        json={
            "audio_samples": audio_samples,
            "sample_rate": 16000,
            "operator_id": "TEST-OP",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "voice"
    assert "event_id" in data
    assert "pitch_f0" in data
    assert "intensity" in data
    assert "recognized_command" in data
    assert "direction_vector" in data


def test_voice_websocket_connection(client: TestClient):
    """Verifies WebSocket /ws/voice/stream handshakes and delivers initial status frame."""
    with client.websocket_connect("/ws/voice/stream") as websocket:
        init_frame = websocket.receive_json()
        assert init_frame["type"] == "INITIAL_STATUS"
        assert "status" in init_frame
        assert init_frame["status"]["sample_rate"] == 16000

        # Send PING
        websocket.send_json({"type": "PING", "timestamp": 12345})
        pong_frame = websocket.receive_json()
        assert pong_frame["type"] == "PONG"
        assert pong_frame["timestamp"] == 12345


def test_list_predefined_samples(client: TestClient):
    """Verifies GET /api/v1/voice/samples returns curated list of audio commands."""
    response = client.get("/api/v1/voice/samples")
    assert response.status_code == 200
    samples = response.json()
    assert len(samples) >= 6
    ids = [s["id"] for s in samples]
    assert "forward" in ids
    assert "backward" in ids
    assert "left" in ids
    assert "right" in ids
    assert "stop" in ids


def test_play_predefined_sample_forward(client: TestClient):
    """Verifies POST /api/v1/voice/samples/forward/play executes the sample into the engine."""
    response = client.post("/api/v1/voice/samples/forward/play")
    assert response.status_code == 200
    data = response.json()
    assert data["recognized_command"] == "FORWARD"
    assert data["recognition_confidence"] > 0.50


def test_upload_base64_audio_sample(client: TestClient):
    """Verifies POST /api/v1/voice/upload accepts base64 audio and returns VoiceEvent."""
    import base64
    import os
    sample_path = os.path.join(os.path.dirname(__file__), "../app/static/samples/left.wav")
    assert os.path.exists(sample_path)
    with open(sample_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    response = client.post(
        "/api/v1/voice/upload",
        json={
            "filename": "left.wav",
            "audio_base64": b64,
            "operator_id": "TEST-UPLOAD",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recognized_command"] == "LEFT"

