"""
Automated integration tests for Synchronization REST API and WebSocket endpoints (Phase 4).
"""

import json
import time
import pytest
from fastapi.testclient import TestClient


def test_sync_status_endpoint(client: TestClient):
    """Verifies GET /api/v1/sync/status returns valid synchronization state."""
    response = client.get("/api/v1/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert "sync_window_ms" in data
    assert "max_event_age_ms" in data
    assert data["sync_window_ms"] == 150.0
    assert "total_synchronized_count" in data


def test_sync_configure_endpoint(client: TestClient):
    """Verifies POST /api/v1/sync/configure adjusts matching parameters."""
    response = client.post(
        "/api/v1/sync/configure",
        json={"sync_window_ms": 175.0, "max_event_age_ms": 400.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sync_window_ms"] == 175.0
    assert data["max_event_age_ms"] == 400.0

    # Reset back to 150ms default
    client.post("/api/v1/sync/configure", json={"sync_window_ms": 150.0, "max_event_age_ms": 350.0})


def test_sync_correlate_manual_endpoint(client: TestClient):
    """Verifies POST /api/v1/sync/correlate pairs simulated voice and joystick events."""
    now_ms = time.time() * 1000.0
    voice_payload = {
        "timestamp": now_ms,
        "transcript": "LEFT",
        "normalized_transcript": "left",
        "recognized_command": "LEFT",
        "recognition_confidence": 0.95,
        "classification_confidence": 0.98,
        "semantic_status": "VALID",
    }
    joystick_payload = {
        "source": "VIRTUAL_SIMULATION",
        "device_id": "TEST-JOY-01",
        "timestamp": now_ms + 40.0,
        "axis_x": -0.80,
        "axis_y": 0.0,
        "direction": "LEFT",
        "intensity": 0.80,
        "is_simulation": True,
    }

    response = client.post(
        "/api/v1/sync/correlate",
        json={
            "voice_event": voice_payload,
            "joystick_event": joystick_payload,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["synchronization_status"] == "SYNCHRONIZED"
    assert data["voice_command"] == "LEFT"
    assert data["joystick_direction"] == "LEFT"
    assert data["timestamp_difference_ms"] == 40.0


def test_sync_websocket_connection(client: TestClient):
    """Verifies WebSocket /ws/sync/stream handshakes and delivers initial status frame."""
    with client.websocket_connect("/ws/sync/stream") as websocket:
        init_frame = websocket.receive_json()
        assert init_frame["type"] == "INITIAL_STATUS"
        assert "status" in init_frame
        assert init_frame["status"]["sync_window_ms"] == 150.0

        # Send PING
        websocket.send_json({"type": "PING", "timestamp": 67890})
        pong_frame = websocket.receive_json()
        assert pong_frame["type"] == "PONG"
        assert pong_frame["timestamp"] == 67890

        # Send CONFIGURE
        websocket.send_json({"type": "CONFIGURE", "sync_window_ms": 180.0})
        cfg_frame = websocket.receive_json()
        assert cfg_frame["type"] == "CONFIG_UPDATED"
        assert cfg_frame["status"]["sync_window_ms"] == 180.0

        # Reset
        websocket.send_json({"type": "CONFIGURE", "sync_window_ms": 150.0})

