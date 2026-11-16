"""
Automated Integration Tests for DCRG Phase 8: Complete Dashboard & End-to-End Integration.
Validates the 14 mandated integration scenarios across the full pipeline:
VOICE + JOYSTICK -> SYNC -> FUSION (CRS) -> SAFETY GATE -> GATEWAY -> SIMULATOR
1. Voice + joystick synchronized command
2. Voice and joystick contradiction
3. UNKNOWN voice command
4. Missing joystick input
5. Missing voice input
6. Stale event
7. GREEN authorization
8. YELLOW confirmation
9. RED rejection
10. EMERGENCY stop
11. Simulation command execution
12. Duplicate command prevention
13. WebSocket disconnection and reconnection
14. Backend failure / safe degradation
Plus System Configuration validation and Audit Log export.
"""

import json
import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.system_config import system_config_manager
from app.database.audit_logger import audit_logger
from app.modules.actuator_engine.schemas import (
    CalibrationStatus,
    CommonJoystickEvent,
    ConnectionStatus,
    DataValidity,
    JoystickDirection,
    JoystickSource,
)
from app.modules.fusion_engine.schemas import (
    AnalyticalFinding,
    CRSStatus,
    FusionFactors,
    FusionResult,
)
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    ConfirmationAction,
    EmergencySource,
    SafetyDecision,
)
from app.modules.safety_engine.rules import generate_auth_token
from app.modules.safety_engine.gateway import simulated_gateway
from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.schemas import ExecutionResultType
from app.modules.simulation_engine.manager import simulation_manager
from app.modules.sync_engine.schemas import CorrelatedEvent, SynchronizationStatus
from app.modules.sync_engine.manager import sync_manager
from app.modules.voice_engine.schemas import CanonicalCommand, SemanticStatus, VoiceEvent


@pytest.fixture(autouse=True)
def clean_system_state():
    """Resets simulator, unlatches emergency stop, resets defaults and clears gateway before each test."""
    simulation_manager.reset_pose(0.0, 0.0, 0.0)
    simulated_gateway._used_tokens.clear()
    simulated_gateway._history.clear()
    system_config_manager.reset_defaults("TEST-CLEANUP")
    if safety_manager._is_emergency_latched:
        safety_manager.reset_emergency_stop("1234", "TEST-OP", "Test reset")
    yield
    system_config_manager.reset_defaults("TEST-CLEANUP")


# ============================================================================
# SCENARIOS 1 - 3: MULTI-MODAL SYNCHRONIZATION & CONTRADICTION
# ============================================================================

def test_integration_01_voice_joystick_synchronized_command():
    """Scenario 1: Voice + joystick synchronized command -> full pipeline -> movement."""
    now_ms = time.time() * 1000.0

    voice_ev = VoiceEvent(
        event_id="v-sync-01",
        timestamp=now_ms,
        transcript="forward",
        normalized_transcript="forward",
        recognized_command=CanonicalCommand.FORWARD,
        recognition_confidence=0.95,
        classification_confidence=0.95,
        confidence=0.95,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        pitch_f0=120.0,
        pitch_f0_std=10.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=0.10,
        is_stressed=False,
    )

    joy_ev = CommonJoystickEvent(
        event_id="j-sync-01",
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="virtual-stick-01",
        timestamp=now_ms + 15.0,  # 15 ms delta, well within 150ms window
        axis_x=0.0,
        axis_y=0.90,  # Positive Y is FORWARD
        direction=JoystickDirection.FORWARD,
        intensity=0.90,
        buttons=[False] * 12,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.CALIBRATED,
        data_validity=DataValidity.VALID,
        is_simulation=True,
    )

    # Ingest through synchronizer
    sync_manager.synchronizer.ingest_voice_event(voice_ev)
    correlated = sync_manager.synchronizer.ingest_joystick_event(joy_ev)
    assert correlated is not None
    assert correlated.synchronization_status == SynchronizationStatus.SYNCHRONIZED
    assert correlated.voice_available is True
    assert correlated.joystick_available is True

    # Ingest through fusion
    fusion = fusion_manager.process_correlated_event(correlated)
    assert fusion is not None
    assert fusion.CRS >= 85.0
    assert fusion.evidence_completeness == 1.0
    assert fusion.contradiction_detected is False

    # Ingest through safety
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "FORWARD"

    # Ingest through simulation
    simulation_manager.on_safety_decision(decision)
    for _ in range(10):
        simulation_manager.step(0.05)

    pose = simulation_manager.simulator.get_pose()
    assert pose.y > 0.0
    assert pose.linear_speed > 0.0


def test_integration_02_voice_joystick_contradiction_rejected():
    """Scenario 2: Voice LEFT + Joystick RIGHT -> contradiction veto -> RED -> no movement."""
    now_ms = time.time() * 1000.0

    voice_ev = VoiceEvent(
        event_id="v-contra-01",
        timestamp=now_ms,
        transcript="left",
        normalized_transcript="left",
        recognized_command=CanonicalCommand.LEFT,
        recognition_confidence=0.92,
        classification_confidence=0.92,
        confidence=0.92,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        pitch_f0=120.0,
        pitch_f0_std=10.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=0.10,
        is_stressed=False,
    )

    joy_ev = CommonJoystickEvent(
        event_id="j-contra-01",
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="virtual-stick-01",
        timestamp=now_ms + 10.0,
        axis_x=0.88,  # Moving RIGHT
        axis_y=0.0,
        direction=JoystickDirection.RIGHT,
        intensity=0.88,
        buttons=[False] * 12,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.CALIBRATED,
        data_validity=DataValidity.VALID,
        is_simulation=True,
    )

    sync_manager.synchronizer.ingest_voice_event(voice_ev)
    correlated = sync_manager.synchronizer.ingest_joystick_event(joy_ev)
    assert correlated is not None

    fusion = fusion_manager.process_correlated_event(correlated)
    assert fusion.contradiction_detected is True
    assert fusion.CRS <= 30.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.RED

    simulation_manager.on_safety_decision(decision)
    for _ in range(5):
        simulation_manager.step(0.05)

    pose = simulation_manager.simulator.get_pose()
    assert pose.x == 0.0
    assert pose.y == 0.0
    assert pose.linear_speed == 0.0


def test_integration_03_unknown_voice_command_rejected():
    """Scenario 3: UNKNOWN voice command -> RED -> robot stationary."""
    now_ms = time.time() * 1000.0
    voice_ev = VoiceEvent(
        event_id="v-unk-01",
        timestamp=now_ms,
        transcript="gibberish waffle",
        normalized_transcript="gibberish waffle",
        recognized_command=CanonicalCommand.UNKNOWN,
        recognition_confidence=0.20,
        classification_confidence=0.10,
        confidence=0.20,
        semantic_status=SemanticStatus.UNKNOWN,
        is_uncertain=False,
        pitch_f0=120.0,
        pitch_f0_std=10.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=0.10,
        is_stressed=False,
    )
    joy_ev = CommonJoystickEvent(
        event_id="j-unk-01",
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="virtual-stick-01",
        timestamp=now_ms,
        axis_x=0.0,
        axis_y=0.0,
        direction=JoystickDirection.CENTER,
        intensity=0.0,
        buttons=[False] * 12,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.CALIBRATED,
        data_validity=DataValidity.VALID,
        is_simulation=True,
    )

    correlated = sync_manager.synchronizer.correlate_manual_pair(voice_ev, joy_ev)
    assert correlated is not None

    fusion = fusion_manager.process_correlated_event(correlated)
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.RED

    simulation_manager.on_safety_decision(decision)
    assert simulation_manager.simulator.get_pose().linear_speed == 0.0


# ============================================================================
# SCENARIOS 4 - 6: MISSING & STALE MODALITY INPUTS
# ============================================================================

def test_integration_04_missing_joystick_input_fails_safe():
    """Scenario 4: Missing joystick input -> never grants automatic GREEN."""
    now_ms = time.time() * 1000.0
    voice_ev = VoiceEvent(
        event_id="v-nojy-01",
        timestamp=now_ms,
        transcript="forward",
        normalized_transcript="forward",
        recognized_command=CanonicalCommand.FORWARD,
        recognition_confidence=0.95,
        classification_confidence=0.95,
        confidence=0.95,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        pitch_f0=120.0,
        pitch_f0_std=10.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=0.10,
        is_stressed=False,
    )

    correlated = sync_manager.synchronizer.correlate_manual_pair(voice_ev, None)
    assert correlated.voice_available is True
    assert correlated.joystick_available is False

    fusion = fusion_manager.process_correlated_event(correlated)
    assert fusion.evidence_completeness < 1.0
    decision = safety_manager.process_fusion_result(fusion)
    # Must never be GREEN with missing joystick
    assert decision.authorization_state in (AuthorizationState.YELLOW, AuthorizationState.RED)


def test_integration_05_missing_voice_input_fails_safe():
    """Scenario 5: Missing voice input -> single joystick deflection -> withholds GREEN."""
    now_ms = time.time() * 1000.0
    joy_ev = CommonJoystickEvent(
        event_id="j-novc-01",
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="virtual-stick-01",
        timestamp=now_ms,
        axis_x=0.0,
        axis_y=-0.80,
        direction=JoystickDirection.FORWARD,
        intensity=0.80,
        buttons=[False] * 12,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.CALIBRATED,
        data_validity=DataValidity.VALID,
        is_simulation=True,
    )

    correlated = sync_manager.synchronizer.correlate_manual_pair(None, joy_ev)
    assert correlated.voice_available is False
    assert correlated.joystick_available is True

    fusion = fusion_manager.process_correlated_event(correlated)
    assert fusion.evidence_completeness < 1.0
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state in (AuthorizationState.YELLOW, AuthorizationState.RED)


def test_integration_06_stale_event_fails_safe():
    """Scenario 6: Stale/corrupted timestamp rejected fails safe."""
    voice_ev = VoiceEvent(
        event_id="v-stale-01",
        timestamp=time.time() * 1000.0,
        transcript="forward",
        normalized_transcript="forward",
        recognized_command=CanonicalCommand.FORWARD,
        recognition_confidence=0.95,
        classification_confidence=0.95,
        confidence=0.95,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        pitch_f0=120.0,
        pitch_f0_std=10.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=0.10,
        is_stressed=False,
    )

    # Mutate to absurdly ancient timestamp
    object.__setattr__(voice_ev, "timestamp", 1000.0)
    corr = sync_manager.synchronizer.ingest_voice_event(voice_ev)
    assert corr is not None
    assert corr.synchronization_status == SynchronizationStatus.INVALID_TIMESTAMP


# ============================================================================
# SCENARIOS 7 - 10: TIERED STATES & EMERGENCY PRIORITY
# ============================================================================

def test_integration_07_green_authorization_executes_movement():
    """Scenario 7: GREEN authorization -> dispatches to simulation -> moves."""
    fusion = FusionResult(
        fusion_id="fus-green-01",
        correlation_id="corr-green-01",
        timestamp=time.time() * 1000.0,
        voice_command="RIGHT",
        joystick_direction="RIGHT",
        joystick_intensity=0.90,
        semantic_reliability=0.95,
        motor_agreement=0.95,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.95,
            motor_agreement=0.95,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=93.0,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        contradiction_reason=None,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=10.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Green agreement",
        analytical_finding=AnalyticalFinding.AGREEMENT,
        recommended_state="GREEN",
    )

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "RIGHT"

    simulation_manager.on_safety_decision(decision)
    for _ in range(15):
        simulation_manager.step(0.05)

    assert simulation_manager.simulator.get_pose().x > 0.0


def test_integration_08_yellow_confirmation_workflow():
    """Scenario 8: YELLOW -> HOLD -> human confirm -> execute."""
    fusion = FusionResult(
        fusion_id="fus-yellow-01",
        correlation_id="corr-yellow-01",
        timestamp=time.time() * 1000.0,
        voice_command="LEFT",
        joystick_direction="LEFT",
        joystick_intensity=0.70,
        semantic_reliability=0.75,
        motor_agreement=0.75,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.75,
            motor_agreement=0.75,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=74.0,  # Yellow range
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        contradiction_reason=None,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=12.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Yellow hold",
        analytical_finding=AnalyticalFinding.AGREEMENT,
        recommended_state="YELLOW",
    )

    dec = safety_manager.process_fusion_result(fusion)
    assert dec.authorization_state == AuthorizationState.YELLOW
    assert dec.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION

    # Vehicle stationary on hold
    simulation_manager.on_safety_decision(dec)
    assert simulation_manager.simulator.get_pose().linear_speed == 0.0

    # Human operator confirms
    ok, confirmed_dec, _ = safety_manager.resolve_confirmation(
        decision_id=dec.decision_id,
        action=ConfirmationAction.CONFIRM,
        operator_id="OP-SUPERVISOR",
    )
    assert ok is True
    assert confirmed_dec.authorization_state == AuthorizationState.GREEN
    assert confirmed_dec.authorized_command == "LEFT"

    # Step simulation
    for _ in range(10):
        simulation_manager.step(0.05)
    assert simulation_manager.simulator.get_pose().x < 0.0


def test_integration_09_red_rejection():
    """Scenario 9: RED rejection -> command blocked, audit logged."""
    fusion = FusionResult(
        fusion_id="fus-red-01",
        correlation_id="corr-red-01",
        timestamp=time.time() * 1000.0,
        voice_command="FORWARD",
        joystick_direction="FORWARD",
        joystick_intensity=0.40,
        semantic_reliability=0.30,
        motor_agreement=0.40,
        context_consistency=0.50,
        factors=FusionFactors(
            semantic_score=0.30,
            motor_agreement=0.40,
            context_consistency=0.50,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=0.5,
        ),
        CRS=38.0,  # RED
        CRS_status=CRSStatus.INCOMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        contradiction_reason=None,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=25.0,
        evidence_completeness=0.7,
        missing_components=["CONTEXT"],
        scoring_config_version="v1.0",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Red low reliability",
        analytical_finding=AnalyticalFinding.INSUFFICIENT_EVIDENCE,
        recommended_state="RED",
    )

    dec = safety_manager.process_fusion_result(fusion)
    assert dec.authorization_state == AuthorizationState.RED

    simulation_manager.on_safety_decision(dec)
    assert simulation_manager.simulator.get_pose().linear_speed == 0.0


def test_integration_10_emergency_stop_priority_and_lockout():
    """Scenario 10: EMERGENCY stop cancels pending, stops vehicle, locks out."""
    # Start vehicle moving
    simulation_manager.simulator.apply_authorized_command("FORWARD", "GREEN")
    for _ in range(5):
        simulation_manager.step(0.05)
    assert simulation_manager.simulator.get_pose().linear_speed > 0.0

    # Fire E-STOP
    estop_dec = safety_manager.trigger_emergency_stop(
        source=EmergencySource.SOFTWARE_UI,
        reason="Obstacle detected",
        operator_id="OP-EMERGENCY",
    )
    simulation_manager.on_safety_decision(estop_dec)

    # Robot instantly halted
    assert simulation_manager.simulator.get_pose().linear_speed == 0.0
    assert simulation_manager.simulator.get_state().active_command == "STOP"

    # Subsequent movement command rejected
    fusion = FusionResult(
        fusion_id="fus-e-lock",
        correlation_id="corr-e-lock",
        timestamp=time.time() * 1000.0,
        voice_command="FORWARD",
        joystick_direction="FORWARD",
        joystick_intensity=0.90,
        semantic_reliability=0.95,
        motor_agreement=0.95,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.95,
            motor_agreement=0.95,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=95.0,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        contradiction_reason=None,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=5.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Attempted during estop",
        analytical_finding=AnalyticalFinding.AGREEMENT,
        recommended_state="GREEN",
    )
    locked_dec = safety_manager.process_fusion_result(fusion)
    assert locked_dec.authorization_state == AuthorizationState.EMERGENCY


# ============================================================================
# SCENARIOS 11 - 14: EXECUTION, DEFENSES, WEBSOCKETS & FAIL-SAFE
# ============================================================================

def test_integration_11_simulation_command_execution_audit():
    """Scenario 11: Command is logged as EXECUTED only after simulated actuation."""
    simulation_manager.reset_pose(0.0, 0.0, 0.0)
    decision = SafetyDecision(
        decision_id="dec-audit-01",
        timestamp_ms=time.time() * 1000.0,
        authorization_state=AuthorizationState.GREEN,
        authorization_decision=AuthorizationDecision.AUTHORIZED,
        requested_command="FORWARD",
        authorized_command="FORWARD",
        crs_score=92.0,
        crs_status="COMPLETE",
        evidence_completeness=1.0,
        contradiction_detected=False,
        reason="Test execution",
        auth_token=generate_auth_token("dec-audit-01", "FORWARD", time.time() * 1000.0 + 2000.0),
        expires_at_ms=time.time() * 1000.0 + 2000.0,
        is_latched=False,
        is_simulation=True,
    )

    simulation_manager.on_safety_decision(decision)
    logs = simulation_manager.get_execution_logs(1)
    assert len(logs) > 0
    assert logs[0].execution_result == ExecutionResultType.EXECUTED
    assert logs[0].authorized_command == "FORWARD"


def test_integration_12_duplicate_command_prevention():
    """Scenario 12: Replay attack prevention rejects duplicate token submission."""
    now_ms = time.time() * 1000.0
    token = generate_auth_token("dec-dup-01", "LEFT", now_ms + 2000.0)
    decision = SafetyDecision(
        decision_id="dec-dup-01",
        timestamp_ms=now_ms,
        authorization_state=AuthorizationState.GREEN,
        authorization_decision=AuthorizationDecision.AUTHORIZED,
        requested_command="LEFT",
        authorized_command="LEFT",
        crs_score=90.0,
        crs_status="COMPLETE",
        evidence_completeness=1.0,
        contradiction_detected=False,
        reason="Duplicate token test",
        auth_token=token,
        expires_at_ms=now_ms + 2000.0,
        is_latched=False,
        is_simulation=True,
    )

    # First dispatch succeeds
    ok1, _ = simulation_manager.dispatch_gateway_command(decision, "LEFT", token)
    assert ok1 is True

    # Second dispatch with identical token fails
    ok2, rec2 = simulation_manager.dispatch_gateway_command(decision, "LEFT", token)
    assert ok2 is False
    assert rec2.execution_result == ExecutionResultType.REJECTED
    assert "already consumed" in (rec2.rejection_reason or "")


def test_integration_13_websocket_disconnection_and_reconnection(client: TestClient):
    """Scenario 13: WebSocket connect, disconnect, and clean reconnect."""
    # First connection
    with client.websocket_connect("/ws/simulation/stream") as ws1:
        data = ws1.receive_text()
        assert "SIMULATION_INIT" in data

    # Clean reconnection
    with client.websocket_connect("/ws/simulation/stream") as ws2:
        data2 = ws2.receive_text()
        assert "SIMULATION_INIT" in data2
        ws2.send_text(json.dumps({"type": "PING", "timestamp": 1234}))
        pong = ws2.receive_text()
        assert "PONG" in pong


def test_integration_14_backend_failure_safe_degradation():
    """Scenario 14: Corrupted payload / invalid structure fails safe."""
    corrupted_fusion = None
    dec = safety_manager.rule_engine.evaluate(corrupted_fusion, is_emergency_latched=False)
    # Default fail-safe state is RED or HOLD
    assert dec.authorization_state in (AuthorizationState.RED, AuthorizationState.YELLOW)
    assert dec.authorized_command is None


# ============================================================================
# CONFIGURATION & AUDIT LOG PERSISTENCE TESTS
# ============================================================================

def test_system_config_validation_and_audit():
    """Validates configuration bounds, weight sum invariants, and audit logging."""
    # Invariant failure: Weights not summing to 1.0
    bad_weights = {"crs_weight_semantic": 0.50, "crs_weight_motor": 0.50, "crs_weight_context": 0.50}
    ok, _, msg = system_config_manager.update_config(bad_weights, operator_id="TEST-OP")
    assert ok is False
    assert "sum to 1.00" in msg

    # Invariant failure: Yellow threshold >= Green threshold
    bad_thresholds = {"safety_green_threshold": 60.0, "safety_yellow_threshold": 70.0}
    ok2, _, msg2 = system_config_manager.update_config(bad_thresholds, operator_id="TEST-OP")
    assert ok2 is False
    assert "less than green" in msg2

    # Valid update
    valid_update = {"sync_window_ms": 180.0, "simulation_speed": 1.5}
    ok3, model, _ = system_config_manager.update_config(valid_update, operator_id="TEST-OP")
    assert ok3 is True
    assert model.sync_window_ms == 180.0
    assert model.simulation_speed == 1.5

    # Always reset to defaults
    system_config_manager.reset_defaults("TEST-CLEANUP")


def test_system_audit_log_query_and_export(client: TestClient):
    """Tests querying persistent logs and downloading JSON/CSV exports."""
    # Write test audit event
    eid = audit_logger.log_event(
        category="SAFETY",
        command="TEST_CMD",
        safety_state="GREEN",
        execution_result="EXECUTED",
        crs=99.0,
        details={"test_key": "test_val"},
    )
    assert eid is not None

    # Query logs API
    res = client.get("/api/v1/system/logs?category=SAFETY&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert "logs" in data
    assert any(l["command"] == "TEST_CMD" for l in data["logs"])

    # Export JSON
    res_json = client.get("/api/v1/system/logs/export?format=json&limit=10")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]

    # Export CSV
    res_csv = client.get("/api/v1/system/logs/export?format=csv&limit=10")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "event_id" in res_csv.text
