"""
API and WebSocket Endpoint Tests for DCRG Phase 7 Robot Simulation Subsystem.
"""

import json
import pytest
from fastapi.testclient import TestClient


def test_simulation_state_endpoint(client: TestClient):
    """Test GET /api/v1/simulation/state returns authoritative simulation state."""
    response = client.get("/api/v1/simulation/state")
    assert response.status_code == 200
    data = response.json()
    assert "pose" in data
    assert "active_command" in data
    assert "authorization_state" in data
    assert "trajectory" in data
    assert "obstacles" in data
    assert len(data["obstacles"]) == 3


def test_simulation_logs_endpoint(client: TestClient):
    """Test GET /api/v1/simulation/logs returns chronological execution history."""
    response = client.get("/api/v1/simulation/logs?limit=10")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)


def test_simulation_control_pause_resume(client: TestClient):
    """Test POST /api/v1/simulation/control with PAUSE and RESUME."""
    # Pause
    res_pause = client.post("/api/v1/simulation/control", json={"action": "PAUSE"})
    assert res_pause.status_code == 200
    assert res_pause.json()["is_paused"] is True

    # Resume
    res_resume = client.post("/api/v1/simulation/control", json={"action": "RESUME"})
    assert res_resume.status_code == 200
    assert res_resume.json()["is_paused"] is False


def test_simulation_control_set_speed(client: TestClient):
    """Test POST /api/v1/simulation/control with SET_SPEED."""
    res = client.post(
        "/api/v1/simulation/control",
        json={"action": "SET_SPEED", "speed_multiplier": 2.0},
    )
    assert res.status_code == 200
    assert res.json()["speed_multiplier"] == 2.0


def test_simulation_reset_endpoint(client: TestClient):
    """Test POST /api/v1/simulation/reset zeroes vehicle coordinates."""
    res = client.post(
        "/api/v1/simulation/reset",
        json={"x": 5.0, "y": 10.0, "heading": 90.0},
    )
    assert res.status_code == 200
    pose = res.json()
    assert pose["x"] == 5.0
    assert pose["y"] == 10.0
    assert pose["heading_deg"] == 90.0
    assert pose["linear_speed"] == 0.0


def test_simulation_websocket_connection(client: TestClient):
    """Test WebSocket connection to /ws/simulation/stream."""
    with client.websocket_connect("/ws/simulation/stream") as websocket:
        init_data = websocket.receive_text()
        payload = json.loads(init_data)
        assert payload["type"] == "SIMULATION_INIT"
        assert "state" in payload
        assert "pose" in payload["state"]

        # Send PING
        websocket.send_text(json.dumps({"type": "PING", "timestamp": 12345}))
        pong_data = websocket.receive_text()
        pong_payload = json.loads(pong_data)
        assert pong_payload["type"] == "PONG"
        assert pong_payload["timestamp"] == 12345

