"""
Comprehensive Automated Unit and Integration Tests for DCRG Phase 6 Safety Authorization Engine.
Validates the 20 critical safety scenarios:
1. CRS 90 with complete matching evidence -> GREEN (Authorized for simulation)
2. CRS 80 requiring confirmation -> YELLOW HOLD
3. CRS 40 rejected -> RED
4. Contradiction with high CRS -> RED (Zero-override law)
5. Incomplete evidence with high CRS -> YELLOW HOLD (Never GREEN)
6. UNKNOWN voice command -> RED
7. UNCERTAIN voice command -> YELLOW HOLD
8. Disconnected joystick -> RED
9. Disconnected microphone -> RED
10. Stale events / invalid timestamps -> RED
11. Invalid authorization decision -> Rejected by gateway
12. Confirmation timeout -> Expired, rejected
13. Duplicate confirmation -> Rejected (Replay defense)
14. Emergency-stop priority -> Overrides everything, immediate halt
15. Emergency lockout -> Blocks subsequent commands
16. Unauthorized emergency reset -> Rejected
17. Expired authorization TTL -> Gateway rejects
18. Duplicate command submission -> Gateway rejects
19. Command mismatch -> Gateway rejects
20. Backend failure / missing CRS -> Fail-safe default (HOLD / REJECT)
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.modules.fusion_engine.schemas import (
    AnalyticalFinding,
    CRSStatus,
    FusionFactors,
    FusionResult,
)
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    ConfirmationAction,
    EmergencySource,
    SafetyDecision,
)
from app.modules.safety_engine.rules import SafetyRuleEngine, generate_auth_token
from app.modules.safety_engine.gateway import SimulatedCommandGateway
from app.modules.safety_engine.manager import SafetyManager


def create_mock_fusion_result(
    crs: float = 90.0,
    command: str = "FORWARD",
    crs_status: CRSStatus = CRSStatus.COMPLETE,
    evidence_completeness: float = 1.0,
    contradiction: bool = False,
    analytical_finding: AnalyticalFinding = AnalyticalFinding.AGREEMENT,
    sync_status: str = "SYNCHRONIZED",
) -> FusionResult:
    return FusionResult(
        fusion_id="test-fusion-uuid-001",
        correlation_id="test-corr-uuid-001",
        timestamp=time.time() * 1000.0,
        voice_command=command,
        joystick_direction=command,
        joystick_intensity=0.85,
        semantic_reliability=0.90,
        motor_agreement=0.90,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.90,
            motor_agreement=0.90,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=crs,
        CRS_status=crs_status,
        contradiction_detected=contradiction,
        veto_asserted=contradiction,
        contradiction_reason="Contradiction asserted" if contradiction else None,
        synchronization_status=sync_status,
        temporal_delta_ms=10.0,
        evidence_completeness=evidence_completeness,
        missing_components=[] if evidence_completeness == 1.0 else ["JOYSTICK"],
        scoring_config_version="v1.0-prototype",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Test explanation",
        analytical_finding=analytical_finding,
        recommended_state="GREEN" if crs >= 85.0 else ("YELLOW" if crs >= 50.0 else "RED"),
    )


@pytest.fixture
def rule_engine():
    return SafetyRuleEngine(
        green_threshold=85.0,
        yellow_threshold=50.0,
        confirmation_timeout_ms=500.0,  # Short timeout for testing
        auth_token_ttl_ms=500.0,
    )


@pytest.fixture
def gateway():
    gw = SimulatedCommandGateway()
    gw.reset()
    return gw


@pytest.fixture
def safety_mgr(rule_engine):
    mgr = SafetyManager(rule_engine=rule_engine)
    mgr.reset_stats()
    return mgr


# ============================================================================
# TESTS 1 - 5: CORE TIERED SCORING AND EVIDENCE
# ============================================================================

def test_1_crs_90_complete_evidence_grants_green(rule_engine):
    """Scenario 1: CRS 90 with complete matching evidence -> GREEN (Authorized)."""
    fusion = create_mock_fusion_result(crs=90.0, command="FORWARD")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorization_decision == AuthorizationDecision.AUTHORIZED
    assert decision.authorized_command == "FORWARD"
    assert decision.auth_token is not None
    assert decision.expires_at_ms is not None
    assert decision.is_simulation is True


def test_2_crs_80_requires_yellow_confirmation(rule_engine):
    """Scenario 2: CRS 80 requires human confirmation -> YELLOW (HOLD)."""
    fusion = create_mock_fusion_result(crs=80.0, command="FORWARD")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.YELLOW
    assert decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION
    assert decision.authorized_command is None
    assert decision.auth_token is None
    assert decision.confirmation_id is not None
    assert decision.expires_at_ms is not None


def test_3_crs_40_rejected(rule_engine):
    """Scenario 3: CRS 40 is below minimum safety threshold (50.0) -> RED."""
    fusion = create_mock_fusion_result(crs=40.0, command="LEFT")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorization_decision == AuthorizationDecision.REJECTED
    assert decision.authorized_command is None
    assert "below actionable minimum" in decision.reason


def test_4_contradiction_with_high_crs_rejected(rule_engine):
    """Scenario 4: Contradiction with high CRS -> RED (Zero-Override Law)."""
    fusion = create_mock_fusion_result(crs=88.0, command="LEFT", contradiction=True)
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorization_decision == AuthorizationDecision.REJECTED
    assert decision.contradiction_detected is True
    assert "CONTRADICTION VETO" in decision.reason


def test_5_incomplete_evidence_never_green(rule_engine):
    """Scenario 5: Incomplete evidence with high CRS (e.g. 95) -> YELLOW (Never GREEN!)."""
    fusion = create_mock_fusion_result(
        crs=95.0,
        command="RIGHT",
        crs_status=CRSStatus.PROVISIONAL,
        evidence_completeness=0.65,
    )
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state != AuthorizationState.GREEN
    assert decision.authorization_state == AuthorizationState.YELLOW
    assert decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION


# ============================================================================
# TESTS 6 - 10: SPEECH AMBIGUITY, DISCONNECTS, AND INTEGRITY
# ============================================================================

def test_6_unknown_voice_command_rejected(rule_engine):
    """Scenario 6: UNKNOWN voice command -> RED."""
    fusion = create_mock_fusion_result(crs=0.0, command="UNKNOWN")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorization_decision == AuthorizationDecision.REJECTED
    assert "UNKNOWN" in decision.reason


def test_7_uncertain_voice_command_held_on_yellow(rule_engine):
    """Scenario 7: UNCERTAIN voice command -> YELLOW."""
    fusion = create_mock_fusion_result(
        crs=60.0,
        command="UNCERTAIN",
        analytical_finding=AnalyticalFinding.UNCERTAIN_COMMAND,
    )
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.YELLOW
    assert decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION


def test_8_disconnected_joystick_rejects(rule_engine):
    """Scenario 8: Disconnected joystick fails safe -> RED."""
    fusion = create_mock_fusion_result(crs=85.0, command="FORWARD")
    with patch("app.modules.safety_engine.rules.actuator_manager.get_status") as mock_joy:
        mock_joy.return_value.active_mode.value = "REAL_HARDWARE"
        mock_joy.return_value.connection_status.value = "DISCONNECTED"
        decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

        assert decision.authorization_state == AuthorizationState.RED
        assert "joystick" in decision.reason.lower()


def test_9_disconnected_microphone_rejects(rule_engine):
    """Scenario 9: Disconnected microphone fails safe -> RED."""
    fusion = create_mock_fusion_result(crs=85.0, command="FORWARD")
    with patch("app.modules.safety_engine.rules.voice_manager.get_status") as mock_voice:
        mock_voice.return_value.microphone_status.value = "ERROR"
        decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

        assert decision.authorization_state == AuthorizationState.RED
        assert "microphone" in decision.reason.lower()


def test_10_stale_or_invalid_event_rejects(rule_engine):
    """Scenario 10: Invalid timestamps or corrupted sync -> RED."""
    fusion = create_mock_fusion_result(
        crs=0.0,
        command="FORWARD",
        crs_status=CRSStatus.INVALID,
        sync_status="INVALID_TIMESTAMP",
    )
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.RED
    assert "Data integrity fault" in decision.reason


# ============================================================================
# TESTS 11 - 13: CONFIRMATION WORKFLOW, TIMEOUT, AND REPLAY DEFENSE
# ============================================================================

def test_11_invalid_decision_rejected_by_gateway(gateway):
    """Scenario 11: Invalid/unauthorized decision rejected by simulated gateway."""
    unauthorized_dec = SafetyDecision(
        authorization_state=AuthorizationState.RED,
        authorization_decision=AuthorizationDecision.REJECTED,
        requested_command="FORWARD",
        reason="Rejected test decision",
    )
    accepted, record = gateway.dispatch(unauthorized_dec, "FORWARD")
    assert accepted is False
    assert "Gateway Rejected" in record.reason


def test_12_confirmation_timeout_rejects(rule_engine, safety_mgr):
    """Scenario 12: Confirmation expires after timeout -> REJECTED."""
    fusion = create_mock_fusion_result(crs=75.0, command="FORWARD")
    dec = safety_mgr.process_fusion_result(fusion)
    assert dec.authorization_state == AuthorizationState.YELLOW

    # Simulate clock advance beyond confirmation timeout
    dec.expires_at_ms = time.time() * 1000.0 - 100.0  # Expired in past

    success, updated, msg = safety_mgr.resolve_confirmation(
        decision_id=dec.decision_id,
        action=ConfirmationAction.CONFIRM,
    )
    assert success is False
    assert updated.authorization_decision == AuthorizationDecision.REJECTED
    assert "TIMEOUT" in updated.reason


def test_13_duplicate_confirmation_rejected(rule_engine, safety_mgr):
    """Scenario 13: Duplicate confirmation submission is rejected."""
    fusion = create_mock_fusion_result(crs=75.0, command="BACKWARD")
    dec = safety_mgr.process_fusion_result(fusion)

    # First confirmation succeeds
    success1, updated1, _ = safety_mgr.resolve_confirmation(
        decision_id=dec.decision_id,
        action=ConfirmationAction.CONFIRM,
    )
    assert success1 is True
    assert updated1.authorization_state == AuthorizationState.GREEN

    # Second confirmation on the same decision ID is rejected
    success2, updated2, msg2 = safety_mgr.resolve_confirmation(
        decision_id=dec.decision_id,
        action=ConfirmationAction.CONFIRM,
    )
    assert success2 is False
    assert "already been resolved" in msg2 or "No pending confirmation found" in msg2


# ============================================================================
# TESTS 14 - 16: EMERGENCY STOP, LOCKOUT, AND AUTHORIZED RESET
# ============================================================================

def test_14_emergency_stop_priority_overrides_everything(safety_mgr):
    """Scenario 14: Emergency stop overrides high CRS and cancels holds."""
    # Create a pending yellow hold
    fusion = create_mock_fusion_result(crs=70.0, command="RIGHT")
    safety_mgr.process_fusion_result(fusion)
    assert len(safety_mgr.get_pending_confirmations()) == 1

    # Trigger emergency stop
    estop_dec = safety_mgr.trigger_emergency_stop(
        source=EmergencySource.SOFTWARE_UI,
        reason="Manual E-STOP triggered",
    )
    assert estop_dec.authorization_state == AuthorizationState.EMERGENCY
    assert estop_dec.authorization_decision == AuthorizationDecision.EMERGENCY_HALT

    # Verify pending holds were wiped
    assert len(safety_mgr.get_pending_confirmations()) == 0


def test_15_emergency_lockout_blocks_subsequent_commands(safety_mgr):
    """Scenario 15: Emergency lockout blocks all subsequent commands."""
    safety_mgr.trigger_emergency_stop()

    # Inbound perfect 100 CRS command during lockout
    perfect_fusion = create_mock_fusion_result(crs=100.0, command="FORWARD")
    dec = safety_mgr.process_fusion_result(perfect_fusion)

    assert dec.authorization_state == AuthorizationState.EMERGENCY
    assert dec.authorization_decision == AuthorizationDecision.EMERGENCY_HALT
    assert dec.authorized_command is None
    assert dec.is_latched is True


def test_16_unauthorized_emergency_reset_rejected(safety_mgr):
    """Scenario 16: Unauthorized emergency reset with invalid PIN is rejected."""
    safety_mgr.trigger_emergency_stop()

    # Wrong PIN
    success, msg = safety_mgr.reset_emergency_stop(reset_pin="WRONG_PIN")
    assert success is False
    assert "Invalid emergency reset authorization PIN" in msg
    assert safety_mgr.get_status().is_emergency_latched is True

    # Correct PIN ("1234")
    success_valid, msg_valid = safety_mgr.reset_emergency_stop(reset_pin="1234")
    assert success_valid is True
    assert safety_mgr.get_status().is_emergency_latched is False


# ============================================================================
# TESTS 17 - 20: GATEWAY EXECUTION, TTL EXPIRATION, MISMATCH, AND FAIL-SAFE
# ============================================================================

def test_17_expired_authorization_rejected_by_gateway(gateway, rule_engine):
    """Scenario 17: Expired authorization token is rejected by the gateway."""
    fusion = create_mock_fusion_result(crs=90.0, command="FORWARD")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    # Force expiration into the past
    decision.expires_at_ms = time.time() * 1000.0 - 50.0

    accepted, record = gateway.dispatch(decision, "FORWARD")
    assert accepted is False
    assert "expired" in record.reason


def test_18_duplicate_command_submission_rejected(gateway, rule_engine):
    """Scenario 18: Replaying the same auth token twice is rejected (Replay defense)."""
    fusion = create_mock_fusion_result(crs=90.0, command="FORWARD")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    # First execution succeeds
    accepted1, record1 = gateway.dispatch(decision, "FORWARD")
    assert accepted1 is True

    # Duplicate execution attempt with same token is rejected
    accepted2, record2 = gateway.dispatch(decision, "FORWARD")
    assert accepted2 is False
    assert "already consumed" in record2.reason


def test_19_command_mismatch_rejected(gateway, rule_engine):
    """Scenario 19: Attempting a command different from the authorized one is rejected."""
    fusion = create_mock_fusion_result(crs=90.0, command="LEFT")
    decision = rule_engine.evaluate(fusion, is_emergency_latched=False)

    # Authorized for LEFT, but attempted RIGHT
    accepted, record = gateway.dispatch(decision, "RIGHT")
    assert accepted is False
    assert "Command mismatch" in record.reason


def test_20_backend_failure_missing_crs_fails_safe(rule_engine):
    """Scenario 20: Backend failure or null FusionResult defaults to safe rejection."""
    decision = rule_engine.evaluate(None, is_emergency_latched=False)

    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorization_decision == AuthorizationDecision.REJECTED
    assert decision.authorized_command is None
    assert "Fail-safe rejection" in decision.reason
