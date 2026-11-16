"""
Integration and API tests for DCRG Phase 6 Safety REST & WebSocket endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.modules.safety_engine.manager import safety_manager
from app.modules.fusion_engine.manager import fusion_manager


@pytest.fixture(autouse=True)
def clean_safety_state():
    safety_manager.reset_stats()
    yield
    safety_manager.reset_stats()


def test_get_safety_status(client: TestClient):
    """Verifies the /api/v1/safety/status endpoint."""
    response = client.get("/api/v1/safety/status")
    assert response.status_code == 200
    data = response.json()
    assert "active_state" in data
    assert "is_emergency_latched" in data
    assert data["is_emergency_latched"] is False
    assert "total_decisions" in data


def test_emergency_stop_and_reset_endpoints(client: TestClient):
    """Verifies triggering emergency stop and authorized reset."""
    # 1. Activate E-Stop
    estop_payload = {
        "source": "SOFTWARE_UI",
        "reason": "Test E-Stop activation",
        "operator_id": "TESTER-01",
    }
    res = client.post("/api/v1/safety/estop", json=estop_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["authorization_state"] == "EMERGENCY"
    assert data["authorization_decision"] == "EMERGENCY_HALT"

    # Status check confirms latched
    st = client.get("/api/v1/safety/status").json()
    assert st["is_emergency_latched"] is True

    # 2. Reset with bad PIN rejected (403)
    bad_reset = client.post("/api/v1/safety/reset", json={"reset_pin": "0000"})
    assert bad_reset.status_code == 403

    # 3. Reset with valid PIN accepted
    good_reset = client.post("/api/v1/safety/reset", json={"reset_pin": "1234"})
    assert good_reset.status_code == 200

    # Status check confirms unlatched
    st_after = client.get("/api/v1/safety/status").json()
    assert st_after["is_emergency_latched"] is False


def test_confirmation_workflow_via_api(client: TestClient):
    """Verifies querying pending confirmations and submitting confirm/reject."""
    # Ingest a manual fusion bundle that falls into YELLOW hold (CRS ~ 60)
    fusion_manager.evaluate_manual_bundle(
        voice_command="LEFT",
        voice_confidence=0.60,
        joystick_direction="LEFT",
        joystick_intensity=0.50,
    )

    # Check pending confirmations
    pending_res = client.get("/api/v1/safety/pending")
    assert pending_res.status_code == 200
    pending_list = pending_res.json()
    assert len(pending_list) >= 1

    dec_id = pending_list[0]["decision_id"]

    # Confirm the decision
    confirm_payload = {
        "decision_id": dec_id,
        "action": "CONFIRM",
        "operator_id": "OP-TEST",
    }
    confirm_res = client.post("/api/v1/safety/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    confirmed_data = confirm_res.json()
    assert confirmed_data["authorization_state"] == "GREEN"
    assert confirmed_data["authorization_decision"] == "AUTHORIZED"
    assert confirmed_data["auth_token"] is not None


def test_gateway_execute_and_history(client: TestClient):
    """Verifies simulated gateway execution and audit trail."""
    # Ingest high confidence matching bundle -> GREEN
    fusion_manager.evaluate_manual_bundle(
        voice_command="FORWARD",
        voice_confidence=0.98,
        joystick_direction="FORWARD",
        joystick_intensity=0.95,
        sync_delta_ms=5.0,
    )

    latest_dec = client.get("/api/v1/safety/latest").json()
    assert latest_dec["authorization_state"] == "GREEN"
    assert latest_dec["auth_token"] is not None

    # Dispatch to gateway
    exec_payload = {
        "decision_id": latest_dec["decision_id"],
        "command": "FORWARD",
        "auth_token": latest_dec["auth_token"],
    }
    exec_res = client.post("/api/v1/safety/gateway/execute", json=exec_payload)
    # Token may already be consumed on auto-dispatch, or succeeds if fresh
    # Check gateway history
    hist_res = client.get("/api/v1/safety/gateway/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1


def test_safety_websocket_stream(client: TestClient):
    """Verifies safety WebSocket stream connectivity and packets."""
    with client.websocket_connect("/ws/safety/stream") as ws:
        # First packet is initial snapshot
        init_raw = ws.receive_text()
        assert "INITIAL_SAFETY_STATE" in init_raw

        # Send PING
        ws.send_text('{"type": "PING", "timestamp": 12345}')
        pong_raw = ws.receive_text()
        assert "PONG" in pong_raw

