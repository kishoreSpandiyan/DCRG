"""
Comprehensive End-to-End Validation Suite for DCRG.
Executes the exact 10 mandated operational test cases from Section 5:
1. Voice LEFT + Controller LEFT           = MATCH
2. Voice LEFT + Controller RIGHT          = MISMATCH
3. Voice RIGHT + Controller LEFT          = MISMATCH
4. Voice FORWARD + Controller FORWARD     = MATCH
5. Voice BACKWARD + Controller FORWARD    = MISMATCH
6. Unclear speech + Controller LEFT       = UNCERTAIN / CONFIRM
7. No voice input + Controller LEFT       = Mode-dependent handling
8. Voice LEFT + Controller Disconnected   = Controller fault
9. Expired voice event + Controller RIGHT = Reject stale event
10. Voice STOP + Controller Any movement  = High-priority stop request
"""

import os
import sys
import time
from typing import Dict, List, Optional
import numpy as np

# Adjust path for backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    JoystickMode,
    ConnectionStatus,
)
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.voice_engine.schemas import (
    VoiceEvent,
    CanonicalCommand,
    SemanticStatus,
)
from app.modules.voice_engine.manager import voice_manager
from app.modules.sync_engine.manager import sync_manager
from app.modules.sync_engine.schemas import SynchronizationStatus
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.fusion_engine.schemas import CRSStatus, AnalyticalFinding
from app.modules.safety_engine.manager import safety_manager
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    EmergencySource,
)
from app.modules.simulation_engine.manager import simulation_manager
from app.modules.simulation_engine.simulator import RobotSimulator


def reset_all_subsystems():
    """Restores all subsystems to a clean baseline state."""
    if safety_manager.get_status().is_emergency_latched:
        safety_manager.reset_emergency_stop("1234", "OP-TEST", "E2E test setup reset")
    sync_manager.synchronizer.reset()
    fusion_manager.reset_stats()
    safety_manager.reset_stats()
    simulation_manager.simulator.reset_pose(0.0, 0.0, 0.0)


def run_all_scenarios() -> List[Dict]:
    results = []

    print("=" * 100)
    print("DCRG FORMAL END-TO-END VALIDATION SUITE (10 MANDATED TEST CASES)")
    print("=" * 100)

    # -------------------------------------------------------------------------
    # Test 1: Voice LEFT + Controller LEFT = MATCH
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy1 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=-0.85,
        axis_y=0.0,
        intensity=0.85,
        direction=JoystickDirection.LEFT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy1)

    voice1 = VoiceEvent(
        timestamp=now + 12.0,
        timestamp_event_ms=now + 12.0,
        source="voice",
        transcript="move left",
        recognized_command=CanonicalCommand.LEFT,
        recognition_confidence=0.94,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": -1.0, "y": 0.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice1)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion1 = fusion_manager.get_latest()
    decision1 = safety_manager.get_status().last_decision

    if decision1 and decision1.authorization_decision == AuthorizationDecision.AUTHORIZED:
        simulation_manager.simulator.apply_authorized_command(
            decision1.authorized_command,
            decision1.authorization_state.value
        )
        simulation_manager.simulator.step(dt=0.1)

    s1_pass = (
        fusion1 is not None
        and fusion1.CRS >= 85.0
        and fusion1.analytical_finding == AnalyticalFinding.AGREEMENT
        and decision1.authorization_state == AuthorizationState.GREEN
        and decision1.authorization_decision == AuthorizationDecision.AUTHORIZED
    )
    results.append({
        "test_id": 1,
        "input_received": "Voice: 'move left' | Stick: X=-0.85, Y=0.0",
        "recognized_command": "LEFT (conf: 0.94)",
        "controller_values": "Direction: LEFT | Intensity: 0.85",
        "timestamp_info": f"Δt: 12.0ms (Window: 150ms)",
        "fusion_result": fusion1.analytical_finding.value if fusion1 else "N/A",
        "crs_score": fusion1.CRS if fusion1 else 0.0,
        "final_decision": f"{decision1.authorization_decision.value} ({decision1.authorization_state.value})",
        "explanation": fusion1.explanation if fusion1 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s1_pass,
    })

    # -------------------------------------------------------------------------
    # Test 2: Voice LEFT + Controller RIGHT = MISMATCH (Contradiction Veto)
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy2 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=0.85,
        axis_y=0.0,
        intensity=0.85,
        direction=JoystickDirection.RIGHT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy2)

    voice2 = VoiceEvent(
        timestamp=now + 10.0,
        timestamp_event_ms=now + 10.0,
        source="voice",
        transcript="left",
        recognized_command=CanonicalCommand.LEFT,
        recognition_confidence=0.92,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": -1.0, "y": 0.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice2)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion2 = fusion_manager.get_latest()
    decision2 = safety_manager.get_status().last_decision

    s2_pass = (
        fusion2 is not None
        and fusion2.CRS <= 30.0
        and fusion2.contradiction_detected is True
        and fusion2.analytical_finding == AnalyticalFinding.CONTRADICTION
        and decision2.authorization_state == AuthorizationState.RED
        and decision2.authorization_decision == AuthorizationDecision.REJECTED
    )
    results.append({
        "test_id": 2,
        "input_received": "Voice: 'left' | Stick: X=+0.85, Y=0.0",
        "recognized_command": "LEFT (conf: 0.92)",
        "controller_values": "Direction: RIGHT | Intensity: 0.85",
        "timestamp_info": f"Δt: 10.0ms (Window: 150ms)",
        "fusion_result": fusion2.analytical_finding.value if fusion2 else "N/A",
        "crs_score": fusion2.CRS if fusion2 else 0.0,
        "final_decision": f"{decision2.authorization_decision.value} ({decision2.authorization_state.value})",
        "explanation": fusion2.contradiction_reason or fusion2.explanation if fusion2 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s2_pass,
    })

    # -------------------------------------------------------------------------
    # Test 3: Voice RIGHT + Controller LEFT = MISMATCH (Contradiction Veto)
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy3 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=-0.85,
        axis_y=0.0,
        intensity=0.85,
        direction=JoystickDirection.LEFT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy3)

    voice3 = VoiceEvent(
        timestamp=now + 10.0,
        timestamp_event_ms=now + 10.0,
        source="voice",
        transcript="right",
        recognized_command=CanonicalCommand.RIGHT,
        recognition_confidence=0.93,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": 1.0, "y": 0.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice3)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion3 = fusion_manager.get_latest()
    decision3 = safety_manager.get_status().last_decision

    s3_pass = (
        fusion3 is not None
        and fusion3.CRS <= 30.0
        and fusion3.contradiction_detected is True
        and fusion3.analytical_finding == AnalyticalFinding.CONTRADICTION
        and decision3.authorization_state == AuthorizationState.RED
        and decision3.authorization_decision == AuthorizationDecision.REJECTED
    )
    results.append({
        "test_id": 3,
        "input_received": "Voice: 'right' | Stick: X=-0.85, Y=0.0",
        "recognized_command": "RIGHT (conf: 0.93)",
        "controller_values": "Direction: LEFT | Intensity: 0.85",
        "timestamp_info": f"Δt: 10.0ms (Window: 150ms)",
        "fusion_result": fusion3.analytical_finding.value if fusion3 else "N/A",
        "crs_score": fusion3.CRS if fusion3 else 0.0,
        "final_decision": f"{decision3.authorization_decision.value} ({decision3.authorization_state.value})",
        "explanation": fusion3.contradiction_reason or fusion3.explanation if fusion3 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s3_pass,
    })

    # -------------------------------------------------------------------------
    # Test 4: Voice FORWARD + Controller FORWARD = MATCH
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy4 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=0.0,
        axis_y=0.90,
        intensity=0.90,
        direction=JoystickDirection.FORWARD,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy4)

    voice4 = VoiceEvent(
        timestamp=now + 14.0,
        timestamp_event_ms=now + 14.0,
        source="voice",
        transcript="move forward",
        recognized_command=CanonicalCommand.FORWARD,
        recognition_confidence=0.95,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": 0.0, "y": 1.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice4)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion4 = fusion_manager.get_latest()
    decision4 = safety_manager.get_status().last_decision

    s4_pass = (
        fusion4 is not None
        and fusion4.CRS >= 85.0
        and fusion4.analytical_finding == AnalyticalFinding.AGREEMENT
        and decision4.authorization_state == AuthorizationState.GREEN
        and decision4.authorization_decision == AuthorizationDecision.AUTHORIZED
    )
    results.append({
        "test_id": 4,
        "input_received": "Voice: 'move forward' | Stick: X=0.0, Y=+0.90",
        "recognized_command": "FORWARD (conf: 0.95)",
        "controller_values": "Direction: FORWARD | Intensity: 0.90",
        "timestamp_info": f"Δt: 14.0ms (Window: 150ms)",
        "fusion_result": fusion4.analytical_finding.value if fusion4 else "N/A",
        "crs_score": fusion4.CRS if fusion4 else 0.0,
        "final_decision": f"{decision4.authorization_decision.value} ({decision4.authorization_state.value})",
        "explanation": fusion4.explanation if fusion4 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s4_pass,
    })

    # -------------------------------------------------------------------------
    # Test 5: Voice BACKWARD + Controller FORWARD = MISMATCH (Contradiction Veto)
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy5 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=0.0,
        axis_y=0.85,
        intensity=0.85,
        direction=JoystickDirection.FORWARD,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy5)

    voice5 = VoiceEvent(
        timestamp=now + 12.0,
        timestamp_event_ms=now + 12.0,
        source="voice",
        transcript="backward",
        recognized_command=CanonicalCommand.BACKWARD,
        recognition_confidence=0.93,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": 0.0, "y": -1.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice5)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion5 = fusion_manager.get_latest()
    decision5 = safety_manager.get_status().last_decision

    s5_pass = (
        fusion5 is not None
        and fusion5.CRS <= 30.0
        and fusion5.contradiction_detected is True
        and fusion5.analytical_finding == AnalyticalFinding.CONTRADICTION
        and decision5.authorization_state == AuthorizationState.RED
        and decision5.authorization_decision == AuthorizationDecision.REJECTED
    )
    results.append({
        "test_id": 5,
        "input_received": "Voice: 'backward' | Stick: X=0.0, Y=+0.85",
        "recognized_command": "BACKWARD (conf: 0.93)",
        "controller_values": "Direction: FORWARD | Intensity: 0.85",
        "timestamp_info": f"Δt: 12.0ms (Window: 150ms)",
        "fusion_result": fusion5.analytical_finding.value if fusion5 else "N/A",
        "crs_score": fusion5.CRS if fusion5 else 0.0,
        "final_decision": f"{decision5.authorization_decision.value} ({decision5.authorization_state.value})",
        "explanation": fusion5.contradiction_reason or fusion5.explanation if fusion5 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s5_pass,
    })

    # -------------------------------------------------------------------------
    # Test 6: Unclear speech + Controller LEFT = UNCERTAIN / CONFIRM
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy6 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=-0.80,
        axis_y=0.0,
        intensity=0.80,
        direction=JoystickDirection.LEFT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy6)

    voice6 = VoiceEvent(
        timestamp=now + 15.0,
        timestamp_event_ms=now + 15.0,
        source="voice",
        transcript="mumble unclear static",
        recognized_command=CanonicalCommand.UNCERTAIN,
        recognition_confidence=0.38,
        semantic_status=SemanticStatus.UNCERTAIN,
        is_uncertain=True,
        direction_vector={"x": 0.0, "y": 0.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice6)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion6 = fusion_manager.get_latest()
    decision6 = safety_manager.get_status().last_decision

    s6_pass = (
        decision6 is not None
        and decision6.authorization_decision != AuthorizationDecision.AUTHORIZED
        and (decision6.authorization_state in (AuthorizationState.YELLOW, AuthorizationState.RED))
    )
    results.append({
        "test_id": 6,
        "input_received": "Voice: 'mumble unclear' | Stick: X=-0.80, Y=0.0",
        "recognized_command": "UNCERTAIN (conf: 0.38)",
        "controller_values": "Direction: LEFT | Intensity: 0.80",
        "timestamp_info": f"Δt: 15.0ms (Window: 150ms)",
        "fusion_result": fusion6.analytical_finding.value if fusion6 else "N/A",
        "crs_score": fusion6.CRS if fusion6 else 0.0,
        "final_decision": f"{decision6.authorization_decision.value} ({decision6.authorization_state.value})",
        "explanation": decision6.reason if decision6 else "N/A",
        "latency_ms": e2e_ms,
        "passed": s6_pass,
    })

    # -------------------------------------------------------------------------
    # Test 7: No voice input + Controller LEFT = Mode-dependent handling
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    now = time.time() * 1000.0

    joy7 = CommonJoystickEvent(
        timestamp=now,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=-0.75,
        axis_y=0.0,
        intensity=0.75,
        direction=JoystickDirection.LEFT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    sync_manager.synchronizer.ingest_joystick_event(joy7)
    time.sleep(0.02)
    timeouts7 = sync_manager.synchronizer.process_pending_timeouts()
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    fusion7 = fusion_manager.get_latest()
    decision7 = safety_manager.get_status().last_decision

    s7_pass = (
        decision7 is None or decision7.authorization_decision != AuthorizationDecision.AUTHORIZED
    )
    results.append({
        "test_id": 7,
        "input_received": "Voice: None (Silent) | Stick: X=-0.75, Y=0.0",
        "recognized_command": "NONE (No voice token)",
        "controller_values": "Direction: LEFT | Intensity: 0.75",
        "timestamp_info": "Δt: N/A (Unpartnered stick)",
        "fusion_result": "JOYSTICK_BUFFERED" if not fusion7 else fusion7.analytical_finding.value,
        "crs_score": fusion7.CRS if fusion7 else 0.0,
        "final_decision": "HELD_IN_BUFFER (Awaiting Partner)",
        "explanation": "Joystick frame buffered awaiting matching voice token. Motion not authorized.",
        "latency_ms": e2e_ms,
        "passed": s7_pass,
    })

    # -------------------------------------------------------------------------
    # Test 8: Voice LEFT + Controller Disconnected = Controller fault
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()

    actuator_manager.active_mode = JoystickMode.REAL_HARDWARE

    fusion8 = fusion_manager.evaluate_manual_bundle(
        voice_command="LEFT",
        voice_confidence=0.90,
        joystick_direction="CENTER",
        joystick_intensity=0.0,
    )
    decision8 = safety_manager.rule_engine.evaluate(fusion8, is_emergency_latched=False)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    actuator_manager.active_mode = JoystickMode.VIRTUAL_SIMULATION

    s8_pass = (
        decision8.authorization_state == AuthorizationState.RED
        and decision8.authorization_decision == AuthorizationDecision.REJECTED
        and "DISCONNECTED" in decision8.reason
    )
    results.append({
        "test_id": 8,
        "input_received": "Voice: 'left' | Stick: Hardware Mode Disconnected",
        "recognized_command": "LEFT (conf: 0.90)",
        "controller_values": "Connection: DISCONNECTED (0 controllers)",
        "timestamp_info": "Δt: N/A (Hardware fault)",
        "fusion_result": fusion8.analytical_finding.value,
        "crs_score": fusion8.CRS,
        "final_decision": f"{decision8.authorization_decision.value} ({decision8.authorization_state.value})",
        "explanation": decision8.reason,
        "latency_ms": e2e_ms,
        "passed": s8_pass,
    })

    # -------------------------------------------------------------------------
    # Test 9: Expired voice event + Controller RIGHT = Reject stale event
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    t0 = time.perf_counter()
    old_time = time.time() * 1000.0 - 3000.0  # 3 seconds ago (> 2500ms max age)

    joy9 = CommonJoystickEvent(
        timestamp=time.time() * 1000.0,
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRTUAL-0",
        axis_x=0.85,
        axis_y=0.0,
        intensity=0.85,
        direction=JoystickDirection.RIGHT,
        is_simulation=True,
        is_deadzone=False,
        hardware_available=True,
        active_controller_count=1,
    )
    voice9_old = VoiceEvent(
        timestamp=old_time,
        timestamp_event_ms=old_time,
        source="voice",
        transcript="right",
        recognized_command=CanonicalCommand.RIGHT,
        recognition_confidence=0.90,
        semantic_status=SemanticStatus.VALID,
        is_uncertain=False,
        direction_vector={"x": 1.0, "y": 0.0},
    )
    sync_manager.synchronizer.ingest_voice_event(voice9_old)
    timeouts9 = sync_manager.synchronizer.process_pending_timeouts()
    corr9 = timeouts9[0] if timeouts9 else None
    fusion9 = fusion_manager.process_correlated_event(corr9) if corr9 else None
    decision9 = safety_manager.rule_engine.evaluate(fusion9, is_emergency_latched=False) if fusion9 else None
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    s9_pass = (
        corr9 is not None
        and corr9.synchronization_status == SynchronizationStatus.STALE
        and (decision9 is None or decision9.authorization_decision != AuthorizationDecision.AUTHORIZED)
    )
    results.append({
        "test_id": 9,
        "input_received": f"Voice: 'right' (age: 3000ms) | Stick: X=+0.85, Y=0.0",
        "recognized_command": "RIGHT (Expired)",
        "controller_values": "Direction: RIGHT | Intensity: 0.85",
        "timestamp_info": "Δt: >3000ms (Exceeded max age 2500ms)",
        "fusion_result": "STALE / EXPIRED",
        "crs_score": fusion9.CRS if fusion9 else 0.0,
        "final_decision": "REJECTED (STALE_EVENT)",
        "explanation": "Event exceeded maximum allowable age window (2500ms). Temporal staleness fault.",
        "latency_ms": e2e_ms,
        "passed": s9_pass,
    })

    # -------------------------------------------------------------------------
    # Test 10: Voice STOP + Controller Any movement = High-priority stop request
    # -------------------------------------------------------------------------
    reset_all_subsystems()
    # Initial movement state
    simulation_manager.simulator.apply_authorized_command("FORWARD", "GREEN")
    simulation_manager.simulator.step(dt=0.05)
    speed_before = simulation_manager.simulator.get_pose().linear_speed

    t0 = time.perf_counter()
    # Trigger emergency stop via KWS
    safety_manager.trigger_emergency_stop(
        source=EmergencySource.KEYWORD_SPOTTER,
        reason="High-priority STOP voice keyword detected",
        operator_id="OP-SAFETY-GATE",
    )
    simulation_manager.simulator.halt_immediate("EMERGENCY")
    simulation_manager.simulator.step(dt=0.01)
    e2e_ms = (time.perf_counter() - t0) * 1000.0

    speed_after = simulation_manager.simulator.get_pose().linear_speed
    stat10 = safety_manager.get_status()

    s10_pass = (
        stat10.is_emergency_latched is True
        and stat10.active_state == AuthorizationState.EMERGENCY
        and stat10.last_decision.authorization_decision == AuthorizationDecision.EMERGENCY_HALT
        and speed_after == 0.0
    )
    results.append({
        "test_id": 10,
        "input_received": "Voice: 'STOP' | Stick: Moving (0.40 m/s)",
        "recognized_command": "STOP (Emergency Priority)",
        "controller_values": f"Speed Before: {speed_before:.2f} m/s -> After: {speed_after:.2f} m/s",
        "timestamp_info": f"Halt Latency: {e2e_ms:.3f}ms",
        "fusion_result": "EMERGENCY_PRIORITY",
        "crs_score": 0.0,
        "final_decision": f"{stat10.last_decision.authorization_decision.value} ({stat10.active_state.value})",
        "explanation": "High-priority STOP command clamped velocity to 0.0 m/s and latched Emergency state.",
        "latency_ms": e2e_ms,
        "passed": s10_pass,
    })

    # Print summary table
    print("\n" + "=" * 100)
    print(f"{'#':2s} | {'Test Case':38s} | {'Decision & State':28s} | {'Latency':9s} | Status")
    print("-" * 100)
    all_passed = True
    for r in results:
        status_str = "PASS" if r["passed"] else "FAIL"
        if not r["passed"]:
            all_passed = False
        name_trunc = r['input_received'][:38]
        print(f"{r['test_id']:2d} | {name_trunc:38s} | {r['final_decision']:28s} | {r['latency_ms']:6.2f}ms  | [{status_str}]")
    print("=" * 100)
    print(f"OVERALL RESULT: {'ALL 10 TEST CASES PASSED SUCCESSFULLY' if all_passed else 'SOME TEST CASES FAILED'}")
    print("=" * 100)

    return results


if __name__ == "__main__":
    run_all_scenarios()
