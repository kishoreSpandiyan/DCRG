"""
DCRG Phase 9 – Comprehensive Final Validation and Acceptance Test Suite.
Verifies hardware contracts, Tests A through H, Safety Authorization states,
fail-safe behavior, and simulation interlock.
"""

import time
import pytest
from app.core.system_config import system_config_manager
from app.modules.voice_engine.schemas import VoiceEvent, CanonicalCommand, SemanticStatus
from app.modules.actuator_engine.schemas import (
    CalibrationStatus,
    CommonJoystickEvent,
    ConnectionStatus,
    DataValidity,
    JoystickDirection,
    JoystickSource,
)
from app.modules.sync_engine.schemas import SynchronizationStatus, CorrelatedEvent
from app.modules.sync_engine.manager import sync_manager
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.fusion_engine.schemas import FusionResult
from app.modules.safety_engine.manager import safety_manager
from app.modules.safety_engine.rules import SafetyRuleEngine
from app.modules.safety_engine.schemas import (
    AuthorizationState,
    AuthorizationDecision,
    ConfirmationAction,
    EmergencySource,
    SafetyDecision,
)
from app.modules.safety_engine.gateway import simulated_gateway
from app.modules.simulation_engine.manager import simulation_manager
from app.modules.simulation_engine.simulator import RobotSimulator
from app.database.audit_logger import audit_logger


@pytest.fixture(autouse=True)
def clean_system_state():
    """Resets simulator, unlatches emergency stop, clears sync buffers, resets defaults and clears gateway before each test."""
    simulation_manager.reset_pose(0.0, 0.0, 0.0)
    simulated_gateway._used_tokens.clear()
    simulated_gateway._history.clear()
    system_config_manager.reset_defaults("TEST-CLEANUP")
    if safety_manager._is_emergency_latched:
        safety_manager.reset_emergency_stop("1234", "TEST-OP", "Test reset")
    with sync_manager.synchronizer._lock:
        sync_manager.synchronizer._voice_buffer.clear()
        sync_manager.synchronizer._joystick_buffer.clear()
        sync_manager.synchronizer._seen_event_ids.clear()
    yield
    system_config_manager.reset_defaults("TEST-CLEANUP")
    with sync_manager.synchronizer._lock:
        sync_manager.synchronizer._voice_buffer.clear()
        sync_manager.synchronizer._joystick_buffer.clear()
        sync_manager.synchronizer._seen_event_ids.clear()


def create_voice_event(
    command: CanonicalCommand,
    confidence: float = 0.95,
    timestamp_ms: float = None,
    stress_score: float = 0.10,
    prefix: str = "v",
) -> VoiceEvent:
    now_ms = timestamp_ms if timestamp_ms is not None else (time.time() * 1000.0)
    return VoiceEvent(
        event_id=f"{prefix}-{command.value.lower()}-{int(now_ms)}",
        timestamp=now_ms,
        transcript=f"MOVE {command.value}" if command != CanonicalCommand.STOP else "STOP",
        normalized_transcript=f"move {command.value.lower()}" if command != CanonicalCommand.STOP else "stop",
        recognized_command=command,
        classified_command=command.value,
        recognition_confidence=confidence,
        classification_confidence=0.98,
        confidence=confidence,
        semantic_status=SemanticStatus.VALID if command not in (CanonicalCommand.UNKNOWN, CanonicalCommand.UNCERTAIN) else SemanticStatus.UNKNOWN,
        is_uncertain=command in (CanonicalCommand.UNKNOWN, CanonicalCommand.UNCERTAIN),
        direction_vector={"x": -1.0 if command == CanonicalCommand.LEFT else (1.0 if command == CanonicalCommand.RIGHT else 0.0),
                          "y": 1.0 if command == CanonicalCommand.FORWARD else (-1.0 if command == CanonicalCommand.BACKWARD else 0.0)},
        pitch_f0=180.0,
        pitch_f0_std=12.0,
        jitter=0.01,
        shimmer=0.02,
        speech_rate=3.0,
        composite_stress_score=stress_score,
        is_stressed=stress_score > 0.5,
    )


def create_joystick_event(
    direction: JoystickDirection,
    axis_x: float,
    axis_y: float,
    timestamp_ms: float = None,
    is_simulation: bool = True,
    prefix: str = "j",
) -> CommonJoystickEvent:
    now_ms = timestamp_ms if timestamp_ms is not None else (time.time() * 1000.0)
    intensity = min(1.0, (axis_x**2 + axis_y**2)**0.5)
    return CommonJoystickEvent(
        event_id=f"{prefix}-{direction.value.lower()}-{int(now_ms)}",
        source=JoystickSource.VIRTUAL_SIMULATION if is_simulation else JoystickSource.REAL_HARDWARE,
        device_id="flight-stick-01",
        timestamp=now_ms,
        axis_x=axis_x,
        axis_y=axis_y,
        direction=direction,
        intensity=intensity,
        buttons=[False] * 12,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.CALIBRATED,
        data_validity=DataValidity.VALID,
        is_simulation=is_simulation,
    )


# =========================================================================
# SECTION 4: COMPLETE DCRG FUSION TESTS (TEST A through TEST H)
# =========================================================================

def test_scenario_a_left_agreement():
    """TEST A – AGREEMENT: Voice: MOVE LEFT, Joystick: LEFT -> High agreement, CRS >= 85, GREEN."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.LEFT, confidence=0.95, timestamp_ms=now_ms, prefix="a-v")
    j_ev = create_joystick_event(JoystickDirection.LEFT, axis_x=-0.88, axis_y=0.0, timestamp_ms=now_ms + 10.0, prefix="a-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)
    assert corr is not None
    assert corr.synchronization_status == SynchronizationStatus.SYNCHRONIZED

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.contradiction_detected is False
    assert fusion.CRS >= 85.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorization_decision == AuthorizationDecision.AUTHORIZED
    assert decision.authorized_command == "LEFT"

    # Verify simulation execution
    simulation_manager.on_safety_decision(decision)
    for _ in range(5):
        simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.x < 0.0


def test_scenario_b_left_vs_right_contradiction():
    """TEST B – CONTRADICTION: Voice: MOVE LEFT, Joystick: RIGHT -> Contradiction veto, CRS <= 30.0, RED."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.LEFT, confidence=0.95, timestamp_ms=now_ms, prefix="b-v")
    j_ev = create_joystick_event(JoystickDirection.RIGHT, axis_x=0.88, axis_y=0.0, timestamp_ms=now_ms + 10.0, prefix="b-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)
    assert corr is not None

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.contradiction_detected is True
    assert fusion.CRS <= 30.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorization_decision == AuthorizationDecision.REJECTED
    assert decision.authorized_command is None

    # Simulation remains stationary
    simulation_manager.on_safety_decision(decision)
    simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.x == 0.0
    assert pose.y == 0.0


def test_scenario_c_forward_agreement():
    """TEST C – FORWARD AGREEMENT: Voice: MOVE FORWARD, Joystick: FORWARD -> Correct sync & fusion."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.FORWARD, confidence=0.95, timestamp_ms=now_ms, prefix="c-v")
    j_ev = create_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.90, timestamp_ms=now_ms + 10.0, prefix="c-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)
    assert corr is not None

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.contradiction_detected is False
    assert fusion.CRS >= 85.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "FORWARD"

    simulation_manager.on_safety_decision(decision)
    for _ in range(5):
        simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.y > 0.0


def test_scenario_d_uncertain_voice():
    """TEST D – UNCERTAIN VOICE: Voice: UNKNOWN, Joystick: RIGHT -> No automatic movement."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.UNKNOWN, confidence=0.20, timestamp_ms=now_ms, prefix="d-v")
    j_ev = create_joystick_event(JoystickDirection.RIGHT, axis_x=0.85, axis_y=0.0, timestamp_ms=now_ms + 10.0, prefix="d-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.CRS < 85.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state != AuthorizationState.GREEN
    assert decision.authorization_decision != AuthorizationDecision.AUTHORIZED

    # Gateway rejects autonomous dispatch
    simulation_manager.on_safety_decision(decision)
    simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.x == 0.0


def test_scenario_e_missing_joystick():
    """TEST E – MISSING JOYSTICK: Voice: MOVE LEFT, Joystick: Disconnected -> Incomplete evidence fail-safe."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.LEFT, confidence=0.92, timestamp_ms=now_ms, prefix="e-v")

    corr = sync_manager.synchronizer.correlate_manual_pair(v_ev, None)
    assert corr.joystick_available is False

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.evidence_completeness < 1.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state != AuthorizationState.GREEN


def test_scenario_f_missing_voice():
    """TEST F – MISSING VOICE: Voice: No command, Joystick: LEFT -> Incomplete evidence fail-safe."""
    now_ms = time.time() * 1000.0
    j_ev = create_joystick_event(JoystickDirection.LEFT, axis_x=-0.85, axis_y=0.0, timestamp_ms=now_ms, prefix="f-j")

    corr = sync_manager.synchronizer.correlate_manual_pair(None, j_ev)
    assert corr.voice_available is False

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.evidence_completeness < 1.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state != AuthorizationState.GREEN


def test_scenario_g_out_of_sync_events():
    """TEST G – OUT-OF-SYNC: Events arrive outside window (>150ms) -> No false agreement."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.LEFT, confidence=0.95, timestamp_ms=now_ms, prefix="g-v")
    j_ev = create_joystick_event(JoystickDirection.LEFT, axis_x=-0.88, axis_y=0.0, timestamp_ms=now_ms + 250.0, prefix="g-j")

    corr = sync_manager.synchronizer.correlate_manual_pair(v_ev, j_ev)
    assert corr is not None
    assert corr.synchronization_status == SynchronizationStatus.OUT_OF_WINDOW

    fusion = fusion_manager.process_correlated_event(corr)
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state != AuthorizationState.GREEN


def test_scenario_h_stop_command_priority():
    """TEST H – STOP COMMAND: Voice: STOP -> STOP takes priority and halts motion."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.STOP, confidence=0.99, timestamp_ms=now_ms, prefix="h-v")
    j_ev = create_joystick_event(JoystickDirection.CENTER, axis_x=0.0, axis_y=0.0, timestamp_ms=now_ms + 10.0, prefix="h-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)

    fusion = fusion_manager.process_correlated_event(corr)
    assert fusion.CRS >= 85.0

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "STOP"

    # Verify vehicle velocity is zero
    simulation_manager.on_safety_decision(decision)
    simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.linear_speed == 0.0


# =========================================================================
# SECTION 5 & 6: SAFETY AUTHORIZATION & FAIL-SAFE RECOVERY
# =========================================================================

def test_emergency_stop_overrides_everything():
    """Emergency stop latches, rejects all motion, and locks out simulation."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.FORWARD, confidence=0.99, timestamp_ms=now_ms, prefix="estop-v")
    j_ev = create_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.90, timestamp_ms=now_ms + 10.0, prefix="estop-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)
    fusion = fusion_manager.process_correlated_event(corr)

    # Trigger emergency stop latch
    safety_manager.trigger_emergency_stop(source=EmergencySource.HARDWARE_BUTTON, reason="Physical test trigger")
    assert safety_manager._is_emergency_latched is True

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.EMERGENCY
    assert decision.authorization_decision == AuthorizationDecision.EMERGENCY_HALT
    assert decision.authorized_command is None

    # Simulation halts completely
    simulation_manager.on_safety_decision(decision)
    simulation_manager.step(0.05)
    pose = simulation_manager.simulator.get_pose()
    assert pose.linear_speed == 0.0


def test_yellow_confirmation_workflow():
    """YELLOW held state requires explicit manual operator confirmation before execution."""
    now_ms = time.time() * 1000.0
    v_ev = create_voice_event(CanonicalCommand.FORWARD, confidence=0.65, timestamp_ms=now_ms, stress_score=0.35, prefix="yel-v")
    j_ev = create_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.75, timestamp_ms=now_ms + 10.0, prefix="yel-j")

    sync_manager.synchronizer.ingest_voice_event(v_ev)
    corr = sync_manager.synchronizer.ingest_joystick_event(j_ev)
    fusion = fusion_manager.process_correlated_event(corr)

    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.YELLOW
    assert decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION

    # Confirm via safety manager resolve_confirmation
    from app.modules.safety_engine.schemas import ConfirmationAction
    succ, confirmed_dec, msg = safety_manager.resolve_confirmation(
        decision_id=decision.decision_id,
        action=ConfirmationAction.CONFIRM,
        operator_id="OP-LEAD"
    )
    assert succ is True
    assert confirmed_dec is not None
    assert confirmed_dec.authorization_state == AuthorizationState.GREEN
    assert confirmed_dec.authorized_command == "FORWARD"


def test_replay_token_attack_prevention():
    """Replaying the same cryptographic authorization token is rejected by the gateway."""
    from app.modules.safety_engine.rules import generate_auth_token
    now_ms = time.time() * 1000.0
    token = generate_auth_token("dec-phase9-dup", "FORWARD", now_ms + 2000.0)
    decision = SafetyDecision(
        decision_id="dec-phase9-dup",
        timestamp_ms=now_ms,
        authorization_state=AuthorizationState.GREEN,
        authorization_decision=AuthorizationDecision.AUTHORIZED,
        requested_command="FORWARD",
        authorized_command="FORWARD",
        crs_score=92.0,
        crs_status="COMPLETE",
        evidence_completeness=1.0,
        contradiction_detected=False,
        reason="Phase 9 duplicate token validation",
        auth_token=token,
        expires_at_ms=now_ms + 2000.0,
        is_latched=False,
        is_simulation=True,
    )

    # First dispatch succeeds
    acc1, _ = simulation_manager.dispatch_gateway_command(decision, "FORWARD", token)
    assert acc1 is True

    # Replay fails
    acc2, rec2 = simulation_manager.dispatch_gateway_command(decision, "FORWARD", token)
    assert acc2 is False
    assert "replay" in rec2.rejection_reason.lower()
