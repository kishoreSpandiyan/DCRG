"""
Integration Tests for Joystick REST and WebSocket Endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app


def test_get_joystick_status():
    """Verify joystick status endpoint returns accurate truthful status."""
    client = TestClient(app)
    response = client.get("/api/v1/joystick/status")
    assert response.status_code == 200
    data = response.json()
    assert "active_mode" in data
    assert data["active_mode"] == "VIRTUAL_SIMULATION"
    assert "physical_hardware_detected" in data
    assert "connected_device_count" in data


def test_get_joystick_devices():
    """Verify physical devices discovery endpoint returns a list."""
    client = TestClient(app)
    response = client.get("/api/v1/joystick/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_post_virtual_joystick_valid():
    """Verify posting a valid virtual joystick input frame."""
    client = TestClient(app)
    payload = {
        "axis_x": 0.0,
        "axis_y": 0.85,
        "buttons": [True, False],
        "device_id": "TEST-CLIENT-01",
    }
    response = client.post("/api/v1/joystick/virtual", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "VIRTUAL_SIMULATION"
    assert data["is_simulation"] is True
    assert data["direction"] == "FORWARD"
    assert data["intensity"] > 0.8


def test_post_virtual_joystick_invalid_axis():
    """Verify rejection of out-of-range axis values via REST."""
    client = TestClient(app)
    payload = {
        "axis_x": 2.5,  # Exceeds max 1.0
        "axis_y": 0.0,
    }
    response = client.post("/api/v1/joystick/virtual", json=payload)
    assert response.status_code == 422  # Pydantic validation error


def test_mode_switch_rejection_without_hardware():
    """Verify that switching to REAL_HARDWARE is rejected if no device is connected."""
    client = TestClient(app)
    payload = {"mode": "REAL_HARDWARE"}
    response = client.post("/api/v1/joystick/mode", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "No physical" in data["detail"]


def test_websocket_joystick_stream():
    """Verify bidirectional WebSocket streaming for virtual joystick frames."""
    client = TestClient(app)
    with client.websocket_connect("/ws/joystick/stream") as websocket:
        # Initial greeting status frame
        init_data = websocket.receive_json()
        assert init_data["type"] == "INITIAL_STATUS"
        assert init_data["status"]["active_mode"] == "VIRTUAL_SIMULATION"

        # Send virtual input packet
        websocket.send_json({
            "type": "VIRTUAL_INPUT",
            "axis_x": -0.8,
            "axis_y": 0.0,
            "buttons": [False, True],
        })

        # Receive streamed CommonJoystickEvent frame
        event_data = websocket.receive_json()
        assert event_data["type"] == "JOYSTICK_EVENT"
        joy_event = event_data["data"]
        assert joy_event["is_simulation"] is True
        assert joy_event["source"] == "VIRTUAL_SIMULATION"
        assert joy_event["direction"] == "LEFT"
        assert joy_event["intensity"] > 0.7

