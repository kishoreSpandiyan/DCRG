"""
Automated Unit and Integration Tests for DCRG Phase 7 Robot Simulation Subsystem.
Validates the 17 mandated safety, kinematic, boundary, and execution scenarios:
1. Voice LEFT + stick LEFT -> authorized movement
2. Voice RIGHT + stick RIGHT -> authorized movement
3. Voice LEFT + stick RIGHT -> contradiction, no movement
4. Voice FORWARD + stick FORWARD -> authorized movement
5. Voice STOP + neutral stick -> stop
6. Voice UNKNOWN -> no movement
7. Voice UNCERTAIN -> hold
8. YELLOW -> confirmation required
9. RED -> command rejected
10. EMERGENCY -> immediate stop and lockout
11. Joystick disconnect -> fail-safe hold
12. Microphone disconnect -> fail-safe hold
13. Robot boundary reached -> stop
14. Obstacle collision -> stop
15. Duplicate command -> reject duplicate execution (Replay attack defense)
16. Expired authorization -> reject execution
17. Invalid command -> reject execution
"""

import math
import time
from unittest.mock import patch
import pytest

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
from app.modules.safety_engine.rules import generate_auth_token
from app.modules.safety_engine.gateway import simulated_gateway
from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.schemas import (
    ExecutionResultType,
    RobotPose,
)
from app.modules.simulation_engine.simulator import RobotSimulator
from app.modules.simulation_engine.manager import SimulationManager


def make_mock_fusion_result(
    crs: float = 90.0,
    command: str = "FORWARD",
    crs_status: CRSStatus = CRSStatus.COMPLETE,
    evidence_completeness: float = 1.0,
    contradiction: bool = False,
    analytical_finding: AnalyticalFinding = AnalyticalFinding.AGREEMENT,
    sync_status: str = "SYNCHRONIZED",
) -> FusionResult:
    """Helper creating a test FusionResult payload."""
    return FusionResult(
        fusion_id=f"fus-{command}-{int(crs)}",
        correlation_id=f"corr-{command}",
        timestamp=time.time() * 1000.0,
        voice_command=command,
        joystick_direction=command if not contradiction else "RIGHT",
        joystick_intensity=0.85,
        semantic_reliability=0.90,
        motor_agreement=0.90 if not contradiction else 0.0,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.90,
            motor_agreement=0.90 if not contradiction else 0.0,
            context_consistency=1.00,
            angular_delta_deg=0.0 if not contradiction else 180.0,
            cosine_similarity=1.0 if not contradiction else -1.0,
            sync_quality=1.0,
        ),
        CRS=crs,
        CRS_status=crs_status,
        contradiction_detected=contradiction,
        veto_asserted=contradiction,
        contradiction_reason="Opposing directions" if contradiction else None,
        synchronization_status=sync_status,
        temporal_delta_ms=12.0,
        evidence_completeness=evidence_completeness,
        missing_components=[] if evidence_completeness == 1.0 else ["JOYSTICK"],
        scoring_config_version="v1.0-test",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Test scenario evaluation",
        analytical_finding=analytical_finding,
        recommended_state="GREEN" if crs >= 85.0 and not contradiction else ("RED" if contradiction or crs < 50.0 else "YELLOW"),
    )


@pytest.fixture
def test_sim_mgr():
    """Provides an isolated SimulationManager with background thread disabled for deterministic testing."""
    sim = RobotSimulator()
    sim.reset_pose(0.0, 0.0, 0.0)
    mgr = SimulationManager(simulator=sim, autostart=False)
    # Ensure gateway is clean
    simulated_gateway._used_tokens.clear()
    simulated_gateway._history.clear()
    # Ensure safety manager unlatched
    if safety_manager._is_emergency_latched:
        safety_manager.reset_emergency_stop("1234", "TEST-OP", "Test reset")
    return mgr


# ============================================================================
# SCENARIOS 1 - 5: CARDINAL MOVEMENTS & STOP
# ============================================================================

def test_scenario_01_voice_left_stick_left_authorized_movement(test_sim_mgr):
    """Scenario 1: Voice LEFT + stick LEFT -> authorized movement."""
    fusion = make_mock_fusion_result(crs=92.0, command="LEFT")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "LEFT"

    test_sim_mgr.on_safety_decision(decision)

    # Step simulation physics forward (0.5s)
    pose_before = test_sim_mgr.simulator.get_pose()
    for _ in range(10):
        test_sim_mgr.step(0.05)
    pose_after = test_sim_mgr.simulator.get_pose()

    # Robot moved in negative X direction
    assert pose_after.x < pose_before.x
    assert pose_after.linear_speed > 0.0
    # Heading rotated toward 270 deg
    assert abs(pose_after.heading_deg - 270.0) < 5.0 or pose_after.heading_deg > 250.0

    logs = test_sim_mgr.get_execution_logs()
    assert len(logs) > 0
    assert logs[0].execution_result == ExecutionResultType.EXECUTED
    assert logs[0].authorized_command == "LEFT"


def test_scenario_02_voice_right_stick_right_authorized_movement(test_sim_mgr):
    """Scenario 2: Voice RIGHT + stick RIGHT -> authorized movement."""
    fusion = make_mock_fusion_result(crs=91.0, command="RIGHT")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "RIGHT"

    test_sim_mgr.on_safety_decision(decision)

    pose_before = test_sim_mgr.simulator.get_pose()
    for _ in range(20):
        test_sim_mgr.step(0.05)
    pose_after = test_sim_mgr.simulator.get_pose()

    # Robot moved in positive X direction
    assert pose_after.x > pose_before.x
    assert pose_after.linear_speed > 0.0
    assert abs(pose_after.heading_deg - 90.0) < 1e-2


def test_scenario_03_voice_left_stick_right_contradiction_no_movement(test_sim_mgr):
    """Scenario 3: Voice LEFT + stick RIGHT -> contradiction, no movement."""
    fusion = make_mock_fusion_result(
        crs=40.0,
        command="LEFT",
        contradiction=True,
        analytical_finding=AnalyticalFinding.CONTRADICTION,
    )
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.RED
    assert decision.authorized_command is None

    test_sim_mgr.on_safety_decision(decision)

    pose_before = test_sim_mgr.simulator.get_pose()
    for _ in range(10):
        test_sim_mgr.step(0.05)
    pose_after = test_sim_mgr.simulator.get_pose()

    # Robot did not move
    assert pose_after.x == pose_before.x
    assert pose_after.y == pose_before.y
    assert pose_after.linear_speed == 0.0

    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.REJECTED
    assert "CONTRADICTION" in (logs[0].rejection_reason or "").upper()


def test_scenario_04_voice_forward_stick_forward_authorized_movement(test_sim_mgr):
    """Scenario 4: Voice FORWARD + stick FORWARD -> authorized movement."""
    fusion = make_mock_fusion_result(crs=94.0, command="FORWARD")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "FORWARD"

    test_sim_mgr.on_safety_decision(decision)

    pose_before = test_sim_mgr.simulator.get_pose()
    for _ in range(10):
        test_sim_mgr.step(0.05)
    pose_after = test_sim_mgr.simulator.get_pose()

    # Robot moved in positive Y direction
    assert pose_after.y > pose_before.y
    assert pose_after.linear_speed > 0.0


def test_scenario_05_voice_stop_neutral_stick_stops_robot(test_sim_mgr):
    """Scenario 5: Voice STOP + neutral stick -> stop."""
    # First get robot moving
    test_sim_mgr.simulator.apply_authorized_command("FORWARD", "GREEN")
    for _ in range(5):
        test_sim_mgr.step(0.05)
    assert test_sim_mgr.simulator.get_pose().linear_speed > 0.0

    # Command STOP
    fusion = make_mock_fusion_result(crs=96.0, command="STOP")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.GREEN
    assert decision.authorized_command == "STOP"

    test_sim_mgr.on_safety_decision(decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0
    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.EXECUTED
    assert logs[0].authorized_command == "STOP"


# ============================================================================
# SCENARIOS 6 - 10: EDGE STATES, UNCERTAINTY, CONFIRMATION & E-STOP
# ============================================================================

def test_scenario_06_voice_unknown_no_movement(test_sim_mgr):
    """Scenario 6: Voice UNKNOWN -> no movement."""
    fusion = make_mock_fusion_result(
        crs=0.0,
        command="UNKNOWN",
        crs_status=CRSStatus.INVALID,
        evidence_completeness=0.5,
    )
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.RED

    test_sim_mgr.on_safety_decision(decision)
    for _ in range(5):
        test_sim_mgr.step(0.05)

    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0
    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.REJECTED


def test_scenario_07_voice_uncertain_hold(test_sim_mgr):
    """Scenario 7: Voice UNCERTAIN -> hold."""
    fusion = make_mock_fusion_result(
        crs=60.0,
        command="UNCERTAIN",
        crs_status=CRSStatus.INCOMPLETE,
        evidence_completeness=0.6,
    )
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    assert decision.authorization_state == AuthorizationState.YELLOW
    assert decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION

    test_sim_mgr.on_safety_decision(decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0
    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.HELD


def test_scenario_08_yellow_confirmation_required_and_resolved(test_sim_mgr):
    """Scenario 8: YELLOW -> confirmation required before movement."""
    fusion = make_mock_fusion_result(
        crs=72.0,
        command="FORWARD",
        crs_status=CRSStatus.COMPLETE,
        evidence_completeness=1.0,
    )
    # Stage through safety manager
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.YELLOW

    # Verify simulation holds stationary
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0

    # Operator confirms the command
    success, confirmed_dec, _ = safety_manager.resolve_confirmation(
        decision_id=decision.decision_id,
        action=ConfirmationAction.CONFIRM,
        operator_id="OP-TESTER",
    )
    assert success is True
    assert confirmed_dec.authorization_state == AuthorizationState.GREEN
    assert confirmed_dec.authorized_command == "FORWARD"

    # Verify confirmed decision was applied to simulator
    for _ in range(10):
        test_sim_mgr.step(0.05)
    assert test_sim_mgr.simulator.get_pose().linear_speed > 0.0
    assert test_sim_mgr.simulator.get_pose().y > 0.0


def test_scenario_09_red_command_rejected(test_sim_mgr):
    """Scenario 9: RED -> command rejected, robot stationary, reason logged."""
    fusion = make_mock_fusion_result(crs=35.0, command="FORWARD")
    decision = safety_manager.process_fusion_result(fusion)
    assert decision.authorization_state == AuthorizationState.RED

    test_sim_mgr.on_safety_decision(decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0
    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.REJECTED
    assert logs[0].rejection_reason is not None


def test_scenario_10_emergency_immediate_stop_and_lockout(test_sim_mgr):
    """Scenario 10: EMERGENCY -> immediate zero-velocity halt and command lockout."""
    # Start robot moving FORWARD
    test_sim_mgr.simulator.apply_authorized_command("FORWARD", "GREEN")
    for _ in range(5):
        test_sim_mgr.step(0.05)
    assert test_sim_mgr.simulator.get_pose().linear_speed > 0.0

    # Fire Emergency Stop
    estop_decision = safety_manager.trigger_emergency_stop(
        source=EmergencySource.SOFTWARE_UI,
        reason="Obstacle in path",
        operator_id="OP-SAFETY",
    )
    test_sim_mgr.on_safety_decision(estop_decision)

    # Robot instantly halted
    pose = test_sim_mgr.simulator.get_pose()
    assert pose.linear_speed == 0.0
    assert test_sim_mgr.simulator.get_state().active_command == "STOP"

    # Attempting new movement while latched must be rejected
    fusion = make_mock_fusion_result(crs=95.0, command="RIGHT")
    latched_decision = safety_manager.process_fusion_result(fusion)
    assert latched_decision.authorization_state == AuthorizationState.EMERGENCY

    test_sim_mgr.on_safety_decision(latched_decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0


# ============================================================================
# SCENARIOS 11 - 14: DISCONNECTS, BOUNDARIES & OBSTACLE COLLISIONS
# ============================================================================

def test_scenario_11_joystick_disconnect_failsafe_hold(test_sim_mgr):
    """Scenario 11: Joystick disconnect -> fail-safe hold."""
    fusion = make_mock_fusion_result(crs=88.0, command="FORWARD")

    with patch("app.modules.safety_engine.rules.actuator_manager.get_status") as mock_joy:
        mock_joy.return_value.active_mode.value = "REAL_HARDWARE"
        mock_joy.return_value.connection_status.value = "DISCONNECTED"
        decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
        assert decision.authorization_state == AuthorizationState.RED

    test_sim_mgr.on_safety_decision(decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0
    logs = test_sim_mgr.get_execution_logs()
    assert logs[0].execution_result == ExecutionResultType.REJECTED


def test_scenario_12_microphone_disconnect_failsafe_hold(test_sim_mgr):
    """Scenario 12: Microphone disconnect / error -> fail-safe hold."""
    fusion = make_mock_fusion_result(crs=88.0, command="FORWARD")

    with patch("app.modules.safety_engine.rules.voice_manager.get_status") as mock_voice:
        mock_voice.return_value.microphone_status.value = "ERROR"
        decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
        assert decision.authorization_state == AuthorizationState.RED

    test_sim_mgr.on_safety_decision(decision)
    assert test_sim_mgr.simulator.get_pose().linear_speed == 0.0


def test_scenario_13_robot_boundary_reached_stops_vehicle(test_sim_mgr):
    """Scenario 13: Robot boundary reached -> stop and clamp coordinates."""
    # Place robot close to max X boundary (48.0m, boundary is 50.0m, radius is 1.0m, limit = 49.0m)
    test_sim_mgr.simulator.reset_pose(48.5, 0.0, 90.0)
    test_sim_mgr.simulator.apply_authorized_command("RIGHT", "GREEN")

    # Step physics repeatedly toward boundary
    for _ in range(30):
        test_sim_mgr.step(0.05)

    pose = test_sim_mgr.simulator.get_pose()
    state = test_sim_mgr.simulator.get_state()

    # Robot must not exceed max_x - radius = 49.0m
    assert pose.x <= 49.0
    assert pose.linear_speed == 0.0
    assert state.boundary_hit is True
    assert state.active_command == "STOP"


def test_scenario_14_obstacle_collision_stops_vehicle(test_sim_mgr):
    """Scenario 14: Obstacle collision -> stop and push back to safe perimeter."""
    # Obstacle Alpha is at (15.0, 15.0, r=3.5). Place robot at (15.0, 10.0), command FORWARD (+Y)
    test_sim_mgr.simulator.reset_pose(15.0, 10.0, 0.0)
    test_sim_mgr.simulator.apply_authorized_command("FORWARD", "GREEN")

    for _ in range(40):
        test_sim_mgr.step(0.05)

    state = test_sim_mgr.simulator.get_state()
    pose = test_sim_mgr.simulator.get_pose()

    assert state.is_collision is True
    assert state.collision_object == "obs-alpha"
    assert pose.linear_speed == 0.0
    assert state.active_command == "STOP"

    # Verify robot is not penetrating inside obstacle (dist >= obstacle.radius + robot.radius)
    dx = pose.x - 15.0
    dy = pose.y - 15.0
    dist = math.sqrt(dx * dx + dy * dy)
    assert dist >= (3.5 + 1.0) - 0.01


# ============================================================================
# SCENARIOS 15 - 17: GATEWAY DEFENSES (DUPLICATE, EXPIRED, MISMATCH)
# ============================================================================

def test_scenario_15_duplicate_command_rejected(test_sim_mgr):
    """Scenario 15: Duplicate command submission rejected by gateway (Replay defense)."""
    fusion = make_mock_fusion_result(crs=92.0, command="FORWARD")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)
    token = decision.auth_token
    assert token is not None

    # First dispatch -> Accepted
    ok1, rec1 = test_sim_mgr.dispatch_gateway_command(decision, "FORWARD", token)
    assert ok1 is True
    assert rec1.execution_result == ExecutionResultType.EXECUTED

    # Second dispatch with identical consumed token -> Rejected
    ok2, rec2 = test_sim_mgr.dispatch_gateway_command(decision, "FORWARD", token)
    assert ok2 is False
    assert rec2.execution_result == ExecutionResultType.REJECTED
    assert "already consumed" in (rec2.rejection_reason or "")


def test_scenario_16_expired_authorization_rejected(test_sim_mgr):
    """Scenario 16: Expired authorization TTL rejected by gateway."""
    now_ms = time.time() * 1000.0
    expired_decision = SafetyDecision(
        decision_id="dec-expired-001",
        timestamp_ms=now_ms - 2000.0,
        authorization_state=AuthorizationState.GREEN,
        authorization_decision=AuthorizationDecision.AUTHORIZED,
        requested_command="LEFT",
        authorized_command="LEFT",
        crs_score=90.0,
        crs_status="COMPLETE",
        evidence_completeness=1.0,
        contradiction_detected=False,
        reason="Pre-expired token test",
        auth_token=generate_auth_token("dec-expired-001", "LEFT", now_ms - 1000.0),
        expires_at_ms=now_ms - 1000.0,  # Expired 1 second ago
        is_latched=False,
        is_simulation=True,
    )

    ok, rec = test_sim_mgr.dispatch_gateway_command(expired_decision, "LEFT")
    assert ok is False
    assert rec.execution_result == ExecutionResultType.REJECTED
    assert "expired" in (rec.rejection_reason or "").lower()


def test_scenario_17_invalid_command_rejected(test_sim_mgr):
    """Scenario 17: Command mismatch or invalid primitive rejected by gateway."""
    fusion = make_mock_fusion_result(crs=92.0, command="FORWARD")
    decision = safety_manager.rule_engine.evaluate(fusion, is_emergency_latched=False)

    # Authorized for FORWARD, but attempting BACKWARD
    ok, rec = test_sim_mgr.dispatch_gateway_command(decision, "BACKWARD")
    assert ok is False
    assert rec.execution_result == ExecutionResultType.REJECTED
    assert "mismatch" in (rec.rejection_reason or "").lower()
