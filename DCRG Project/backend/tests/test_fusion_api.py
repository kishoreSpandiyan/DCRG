"""
Integration and API tests for DCRG Phase 5 Fusion REST & WebSocket endpoints.
"""

import pytest
from fastapi.testclient import TestClient


def test_get_fusion_status(client: TestClient):
    """Verifies the /api/v1/fusion/status endpoint reports telemetry."""
    response = client.get("/api/v1/fusion/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_active" in data
    assert data["is_active"] is True
    assert "total_evaluations" in data
    assert "scoring_config_version" in data
    assert "weights" in data
    assert "semantic" in data["weights"]
    assert "motor" in data["weights"]
    assert "context" in data["weights"]


def test_get_fusion_config(client: TestClient):
    """Verifies getting scoring configuration parameters."""
    response = client.get("/api/v1/fusion/config")
    assert response.status_code == 200
    data = response.json()
    assert data["weight_semantic"] == pytest.approx(0.35)
    assert data["weight_motor"] == pytest.approx(0.50)
    assert data["weight_context"] == pytest.approx(0.15)
    assert data["contradiction_cap"] == 30.0


def test_post_fusion_config_update(client: TestClient):
    """Verifies updating scoring weights."""
    update_payload = {
        "weight_semantic": 0.40,
        "weight_motor": 0.40,
        "weight_context": 0.20,
        "stress_damping": 0.30,
        "contradiction_cap": 25.0,
        "contradiction_whisper_min": 0.70,
        "contradiction_joystick_min": 0.30,
        "joystick_deadzone": 0.10,
        "scoring_config_version": "v1.1-test",
    }
    response = client.post("/api/v1/fusion/config", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["weight_semantic"] == pytest.approx(0.40)
    assert data["contradiction_cap"] == 25.0

    # Reset back to prototype defaults
    client.post(
        "/api/v1/fusion/config",
        json={
            "weight_semantic": 0.35,
            "weight_motor": 0.50,
            "weight_context": 0.15,
            "stress_damping": 0.25,
            "contradiction_cap": 30.0,
            "contradiction_whisper_min": 0.70,
            "contradiction_joystick_min": 0.30,
            "joystick_deadzone": 0.08,
            "scoring_config_version": "v1.0-prototype",
        },
    )


def test_post_fusion_config_invalid_sum_rejected(client: TestClient):
    """Weights that do not sum to 1.0 must be rejected with 422."""
    bad_payload = {
        "weight_semantic": 0.50,
        "weight_motor": 0.50,
        "weight_context": 0.50,  # Sum = 1.5
    }
    response = client.post("/api/v1/fusion/config", json=bad_payload)
    assert response.status_code == 422


def test_manual_evaluate_agreement(client: TestClient):
    """Tests manual evaluation of agreeing multimodal pair."""
    payload = {
        "voice_command": "FORWARD",
        "voice_confidence": 0.95,
        "stress_score": 0.10,
        "joystick_direction": "FORWARD",
        "joystick_intensity": 0.85,
        "sync_delta_ms": 12.0,
    }
    response = client.post("/api/v1/fusion/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["CRS"] > 85.0
    assert data["contradiction_detected"] is False
    assert data["analytical_finding"] == "AGREEMENT"
    assert data["CRS_status"] == "COMPLETE"


def test_manual_evaluate_contradiction_capped(client: TestClient):
    """Tests manual evaluation of opposing voice/joystick commands."""
    payload = {
        "voice_command": "FORWARD",
        "voice_confidence": 0.95,
        "joystick_direction": "BACKWARD",
        "joystick_intensity": 0.85,
    }
    response = client.post("/api/v1/fusion/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["contradiction_detected"] is True
    assert data["veto_asserted"] is True
    assert data["CRS"] <= 30.0
    assert data["analytical_finding"] == "CONTRADICTION"


def test_get_crs_endpoint(client: TestClient):
    """Tests the lightweight /crs summary endpoint."""
    response = client.get("/api/v1/fusion/crs")
    assert response.status_code == 200
    data = response.json()
    assert "CRS" in data
    assert "CRS_status" in data
    assert "contradiction_detected" in data


def test_get_fusion_history(client: TestClient):
    """Tests the history retrieval endpoint."""
    response = client.get("/api/v1/fusion/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_context_endpoints(client: TestClient):
    """Tests GET, POST, and reset for operational context."""
    # GET initial state
    res = client.get("/api/v1/fusion/context")
    assert res.status_code == 200
    state = res.json()
    assert state["operating_mode"] == "NORMAL"

    # POST update
    state["operating_mode"] = "PRECISION"
    state["nearest_obstacle_distance_m"] = 3.2
    post_res = client.post("/api/v1/fusion/context", json=state)
    assert post_res.status_code == 200
    assert post_res.json()["operating_mode"] == "PRECISION"

    # Reset
    reset_res = client.post("/api/v1/fusion/context/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["operating_mode"] == "NORMAL"


def test_fusion_websocket_connection(client: TestClient):
    """Tests WebSocket connectivity and streaming on /ws/fusion/stream."""
    with client.websocket_connect("/ws/fusion/stream") as ws:
        # First packet is INITIAL_STATE
        init_raw = ws.receive_text()
        assert "INITIAL_STATE" in init_raw

        # Send PING
        ws.send_text('{"type": "PING", "timestamp": 12345}')
        pong_raw = ws.receive_text()
        assert "PONG" in pong_raw

        # Trigger manual evaluation over WebSocket
        eval_payload = {
            "type": "EVALUATE",
            "voice_command": "RIGHT",
            "voice_confidence": 0.90,
            "joystick_direction": "RIGHT",
            "joystick_intensity": 0.80,
        }
        ws.send_text('{"type": "EVALUATE", "voice_command": "RIGHT", "voice_confidence": 0.90, "joystick_direction": "RIGHT", "joystick_intensity": 0.80}')
        res_raw = ws.receive_text()
        assert "FUSION_RESULT" in res_raw
        assert "RIGHT" in res_raw

