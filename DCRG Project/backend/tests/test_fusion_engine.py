"""
Comprehensive Unit Tests for DCRG Phase 5 Fusion Engine & CRS Computation.
Validates:
- Semantic reliability component (S) and stress attenuation
- Motor agreement component (M), vector cosine similarity, and STOP handling
- Contextual consistency component (C) and obstacle/mode constraints
- Zero-override contradiction veto filter and 30.0 CRS ceiling
- Status determination (COMPLETE, PROVISIONAL, INCOMPLETE, INVALID)
- Configurable weights and parameter boundaries
"""

import math
import pytest
from typing import Optional

from app.modules.context_engine.schemas import ContextState, MissionMode
from app.modules.context_engine.service import context_service
from app.modules.sync_engine.schemas import (
    CorrelatedEvent,
    SynchronizationStatus,
)
from app.modules.voice_engine.schemas import (
    CanonicalCommand,
    SemanticStatus,
    VoiceEvent,
)
from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
)
from app.modules.fusion_engine.calculator import CRSCalculator
from app.modules.fusion_engine.manager import FusionManager
from app.modules.fusion_engine.schemas import (
    AnalyticalFinding,
    CRSStatus,
    FusionConfig,
)


@pytest.fixture(autouse=True)
def reset_context_and_stats():
    """Reset context state and fusion singleton before each test."""
    context_service.reset_defaults()
    yield
    context_service.reset_defaults()


def build_voice_event(
    command: CanonicalCommand,
    confidence: float = 0.90,
    stress_score: float = 0.0,
    is_uncertain: bool = False,
) -> VoiceEvent:
    return VoiceEvent(
        transcript=command.value.lower(),
        normalized_transcript=command.value.lower(),
        recognized_command=command,
        recognition_confidence=confidence,
        classification_confidence=confidence,
        composite_stress_score=stress_score,
        is_uncertain=is_uncertain,
        semantic_status=SemanticStatus.UNCERTAIN if is_uncertain else SemanticStatus.VALID,
    )


def build_joystick_event(
    direction: JoystickDirection,
    axis_x: float,
    axis_y: float,
    intensity: float,
) -> CommonJoystickEvent:
    return CommonJoystickEvent(
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="VIRT-TEST-001",
        axis_x=axis_x,
        axis_y=axis_y,
        direction=direction,
        intensity=intensity,
        is_simulation=True,
    )


def build_correlated_pair(
    v_event: Optional[VoiceEvent] = None,
    j_event: Optional[CommonJoystickEvent] = None,
    sync_status: SynchronizationStatus = SynchronizationStatus.SYNCHRONIZED,
    delta_ms: float = 10.0,
) -> CorrelatedEvent:
    return CorrelatedEvent(
        voice_event_id=v_event.event_id if v_event else None,
        joystick_event_id=j_event.event_id if j_event else None,
        voice_command=v_event.recognized_command.value if v_event else None,
        joystick_direction=j_event.direction.value if j_event else None,
        joystick_intensity=j_event.intensity if j_event else None,
        timestamp_difference_ms=delta_ms,
        synchronization_status=sync_status,
        voice_available=v_event is not None,
        joystick_available=j_event is not None,
        correlation_reason="Automated test pair",
        voice_event=v_event,
        joystick_event=j_event,
    )


# ============================================================================
# 1. SEMANTIC RELIABILITY TESTS
# ============================================================================

class TestSemanticReliability:

    def test_clean_speech_unattenuated(self):
        """Speech with 0 stress should maintain full Whisper confidence."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.92, stress_score=0.0)
        pair = build_correlated_pair(v_event=v)
        s_score, exp = calc.calculate_semantic_factor(pair)
        assert s_score == pytest.approx(0.92, abs=1e-3)
        assert "Stress=0.00" in exp

    def test_stress_attenuation_formula(self):
        """S = C_whisper * (1 - 0.25 * S_stress)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.80, stress_score=0.60)
        pair = build_correlated_pair(v_event=v)
        s_score, _ = calc.calculate_semantic_factor(pair)
        # Expected: 0.80 * (1 - 0.25 * 0.60) = 0.80 * 0.85 = 0.68
        assert s_score == pytest.approx(0.68, abs=1e-3)

    def test_shouted_stressed_stop_preserved(self):
        """A shouted STOP under maximum stress (1.0) must never be rejected or zeroed."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.STOP, confidence=0.95, stress_score=1.0)
        pair = build_correlated_pair(v_event=v)
        s_score, _ = calc.calculate_semantic_factor(pair)
        # Expected: 0.95 * (1 - 0.25 * 1.0) = 0.95 * 0.75 = 0.7125
        assert s_score >= 0.70
        assert s_score == pytest.approx(0.7125, abs=1e-3)

    def test_unknown_command_yields_zero_semantic(self):
        """UNKNOWN command tokens strictly yield S = 0.0."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.UNKNOWN, confidence=0.99)
        pair = build_correlated_pair(v_event=v)
        s_score, exp = calc.calculate_semantic_factor(pair)
        assert s_score == 0.0
        assert "non-actionable" in exp

    def test_uncertain_command_yields_zero_semantic(self):
        """UNCERTAIN command tokens strictly yield S = 0.0."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.45, is_uncertain=True)
        pair = build_correlated_pair(v_event=v)
        s_score, _ = calc.calculate_semantic_factor(pair)
        assert s_score == 0.0

    def test_missing_prosody_no_false_stress(self):
        """Missing prosody metrics assumes stress=0.0 without penalizing."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.RIGHT, confidence=0.88)
        v.composite_stress_score = None
        pair = build_correlated_pair(v_event=v)
        s_score, _ = calc.calculate_semantic_factor(pair)
        assert s_score == pytest.approx(0.88, abs=1e-3)


# ============================================================================
# 2. MOTOR AGREEMENT TESTS
# ============================================================================

class TestMotorAgreement:

    def test_exact_directional_match(self):
        """Voice LEFT and Joystick LEFT yield cos(theta)=1.0 and high agreement."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.90)
        j = build_joystick_event(JoystickDirection.LEFT, axis_x=-0.85, axis_y=0.0, intensity=0.85)
        pair = build_correlated_pair(v_event=v, j_event=j, delta_ms=0.0)

        res = calc.evaluate(pair)
        assert res.factors.cosine_similarity == pytest.approx(1.0, abs=1e-2)
        assert res.factors.angular_delta_deg == pytest.approx(0.0, abs=1e-1)
        # M = 1.0 * sqrt(0.85) * 1.0 = 0.922
        assert res.motor_agreement == pytest.approx(0.922, abs=1e-2)
        assert res.analytical_finding == AnalyticalFinding.AGREEMENT

    def test_perpendicular_direction(self):
        """Voice FORWARD and Joystick RIGHT yield cos(theta)=0.0 (delta=90 deg)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.85)
        j = build_joystick_event(JoystickDirection.RIGHT, axis_x=0.80, axis_y=0.0, intensity=0.80)
        pair = build_correlated_pair(v_event=v, j_event=j, delta_ms=0.0)

        res = calc.evaluate(pair)
        assert res.factors.cosine_similarity == pytest.approx(0.0, abs=1e-2)
        assert res.factors.angular_delta_deg == pytest.approx(90.0, abs=1e-1)
        # M = ((1 + 0)/2) * sqrt(0.80) * 1.0 = 0.5 * 0.894 = 0.447
        assert res.motor_agreement == pytest.approx(0.447, abs=1e-2)

    def test_stop_command_neutral_joystick(self):
        """Voice STOP and neutral stick yield full motor agreement."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.STOP, confidence=0.90)
        j = build_joystick_event(JoystickDirection.CENTER, axis_x=0.0, axis_y=0.0, intensity=0.0)
        pair = build_correlated_pair(v_event=v, j_event=j, delta_ms=0.0)

        res = calc.evaluate(pair)
        assert res.motor_agreement == pytest.approx(1.0, abs=1e-2)
        assert res.analytical_finding == AnalyticalFinding.AGREEMENT
        assert not res.contradiction_detected

    def test_stop_command_active_joystick_contradiction(self):
        """Voice STOP while joystick is actively deflected is a contradiction (M=0)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.STOP, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.80, intensity=0.80)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        assert res.motor_agreement == 0.0
        assert res.contradiction_detected is True
        assert res.veto_asserted is True
        assert res.CRS <= 30.0
        assert res.analytical_finding == AnalyticalFinding.CONTRADICTION

    def test_directional_voice_with_neutral_joystick(self):
        """Spoken direction with stationary joystick yields M=0 (no confirmation)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.RIGHT, confidence=0.88)
        j = build_joystick_event(JoystickDirection.CENTER, axis_x=0.02, axis_y=0.01, intensity=0.02)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        assert res.motor_agreement == 0.0
        assert res.analytical_finding == AnalyticalFinding.NEUTRAL_JOYSTICK

    def test_temporal_alignment_decay(self):
        """Increasing time delta between inputs reduces Q_sync and M score."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.81, intensity=0.81)

        # Pair 1: 0ms delta -> Q_sync = 1.0
        p1 = build_correlated_pair(v, j, delta_ms=0.0)
        res1 = calc.evaluate(p1)

        # Pair 2: 75ms delta (half of 150ms window) -> Q_sync = 0.50
        p2 = build_correlated_pair(v, j, delta_ms=75.0)
        res2 = calc.evaluate(p2)

        assert res1.factors.sync_quality == pytest.approx(1.0, abs=1e-2)
        assert res2.factors.sync_quality == pytest.approx(0.5, abs=1e-2)
        assert res1.motor_agreement > res2.motor_agreement


# ============================================================================
# 3. ZERO-OVERRIDE CONTRADICTION VETO TESTS
# ============================================================================

class TestContradictionVetoFilter:

    def test_direct_opposing_directions_trigger_veto(self):
        """Voice LEFT and physical joystick RIGHT must trigger contradiction veto."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.95)
        j = build_joystick_event(JoystickDirection.RIGHT, axis_x=0.90, axis_y=0.0, intensity=0.90)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        assert res.contradiction_detected is True
        assert res.veto_asserted is True
        assert res.factors.cosine_similarity == pytest.approx(-1.0, abs=1e-2)
        assert res.CRS <= 30.0
        assert res.analytical_finding == AnalyticalFinding.CONTRADICTION
        assert "VETO ASSERTED" in res.explanation

    def test_forward_vs_backward_veto(self):
        """Voice FORWARD and joystick BACKWARD triggers veto and ceiling."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.BACKWARD, axis_x=0.0, axis_y=-0.85, intensity=0.85)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        assert res.contradiction_detected is True
        assert res.CRS <= 30.0

    def test_low_confidence_voice_does_not_falsely_veto(self):
        """Low confidence voice (conf < 0.70) is ambiguous, not a confirmed veto."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.55)  # below 0.70 threshold
        j = build_joystick_event(JoystickDirection.RIGHT, axis_x=0.85, axis_y=0.0, intensity=0.85)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        # Even though opposing, confidence is too low to prove operator contradiction
        assert res.contradiction_detected is False

    def test_low_joystick_deflection_does_not_trigger_veto(self):
        """Very low joystick deflection (I < 0.30) does not trigger contradiction."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.95)
        j = build_joystick_event(JoystickDirection.BACKWARD, axis_x=0.0, axis_y=-0.20, intensity=0.20)
        pair = build_correlated_pair(v_event=v, j_event=j)

        res = calc.evaluate(pair)
        assert res.contradiction_detected is False


# ============================================================================
# 4. CONTEXTUAL CONSISTENCY TESTS
# ============================================================================

class TestContextualConsistency:

    def test_nominal_context_satisfies_constraints(self):
        """Nominal operational state yields C=1.0."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.8, intensity=0.8)
        pair = build_correlated_pair(v, j)

        res = calc.evaluate(pair)
        assert res.context_consistency == 1.0

    def test_forbidden_direction_blocks_action(self):
        """Commanding a direction excluded from permitted_directions yields C=0.0."""
        calc = CRSCalculator()
        context_service.patch_state(permitted_directions=["FORWARD", "STOP"])

        v = build_voice_event(CanonicalCommand.LEFT, confidence=0.90)
        j = build_joystick_event(JoystickDirection.LEFT, axis_x=-0.8, axis_y=0.0, intensity=0.8)
        pair = build_correlated_pair(v, j)

        res = calc.evaluate(pair)
        assert res.context_consistency == 0.0
        assert res.analytical_finding == AnalyticalFinding.CONTEXT_VIOLATION

    def test_emergency_stop_mode_forbids_motion(self):
        """In EMERGENCY_STOP mode, directional commands receive C=0.0."""
        calc = CRSCalculator()
        context_service.patch_state(operating_mode=MissionMode.EMERGENCY_STOP)

        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.8, intensity=0.8)
        pair = build_correlated_pair(v, j)

        res = calc.evaluate(pair)
        assert res.context_consistency == 0.0

    def test_obstacle_within_stopping_threshold_penalized(self):
        """Obstacle directly ahead at distance <= stopping distance zeroes C."""
        calc = CRSCalculator()
        context_service.patch_state(
            nearest_obstacle_distance_m=0.8,
            obstacle_direction="FORWARD",
            stopping_distance_threshold_m=1.0,
        )

        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.8, intensity=0.8)
        pair = build_correlated_pair(v, j)

        res = calc.evaluate(pair)
        assert res.context_consistency == 0.0

    def test_unavailable_context_never_fabricated(self):
        """When context telemetry is unavailable, C is neutral (0.5) and status is PROVISIONAL."""
        calc = CRSCalculator()
        context_service.patch_state(is_available=False)

        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.8, intensity=0.8)
        pair = build_correlated_pair(v, j)

        res = calc.evaluate(pair)
        assert res.context_consistency == 0.5
        assert "CONTEXT" in res.missing_components
        assert res.CRS_status == CRSStatus.PROVISIONAL


# ============================================================================
# 5. COMPOSITE CRS AND CONFIGURATION TESTS
# ============================================================================

class TestCompositeCRS:

    def test_formula_weights_application(self):
        """CRS = 100 * (0.35 * S + 0.50 * M + 0.15 * C)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=1.0, stress_score=0.0)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=1.0, intensity=1.0)
        pair = build_correlated_pair(v, j, delta_ms=0.0)

        res = calc.evaluate(pair)
        # S = 1.0, M = 1.0, C = 1.0
        # CRS = 100 * (0.35*1.0 + 0.50*1.0 + 0.15*1.0) = 100.0
        assert res.CRS == 100.0
        assert res.CRS_status == CRSStatus.COMPLETE

    def test_deadzone_filtering(self):
        """Joystick deflection within deadzone (0.05 < 0.08) is treated as neutral."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.05, intensity=0.05)
        pair = build_correlated_pair(v, j)

        vec, intensity, is_neutral = calc.normalize_joystick(pair)
        assert is_neutral is True
        assert intensity == 0.0
        assert vec == (0.0, 0.0)

    def test_diagonal_joystick_cosine_similarity(self):
        """Voice FORWARD compared to Joystick FORWARD_LEFT yields cos=0.707 (45 deg)."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD, confidence=0.90)
        # FORWARD_LEFT: (-0.7071, 0.7071)
        j = build_joystick_event(
            JoystickDirection.FORWARD_LEFT,
            axis_x=-0.7071,
            axis_y=0.7071,
            intensity=1.0,
        )
        pair = build_correlated_pair(v, j, delta_ms=0.0)

        res = calc.evaluate(pair)
        assert res.factors.cosine_similarity == pytest.approx(0.7071, abs=1e-2)
        assert res.factors.angular_delta_deg == pytest.approx(45.0, abs=1e-1)
        # M = ((1 + 0.7071)/2) * 1.0 * 1.0 = 0.8535
        assert res.motor_agreement == pytest.approx(0.854, abs=1e-2)

    def test_invalid_weights_sum_rejected(self):
        """Weights not summing to 1.0 must raise a validation error."""
        with pytest.raises(ValueError, match="Scoring weights must sum to 1.0"):
            FusionConfig(weight_semantic=0.5, weight_motor=0.5, weight_context=0.2)

    def test_invalid_timestamp_marks_crs_invalid(self):
        """Invalid timestamp sync status results in CRSStatus.INVALID and 0 CRS."""
        calc = CRSCalculator()
        v = build_voice_event(CanonicalCommand.FORWARD)
        j = build_joystick_event(JoystickDirection.FORWARD, axis_x=0.0, axis_y=0.8, intensity=0.8)
        pair = build_correlated_pair(v, j, sync_status=SynchronizationStatus.INVALID_TIMESTAMP)

        res = calc.evaluate(pair)
        assert res.CRS_status == CRSStatus.INVALID
        assert res.CRS == 0.0


# ============================================================================
# 6. FUSION MANAGER INTEGRATION TESTS
# ============================================================================

class TestFusionManager:

    def test_manager_evaluates_and_records_history(self):
        mgr = FusionManager()
        mgr.reset_stats()

        res = mgr.evaluate_manual_bundle(
            voice_command="LEFT",
            voice_confidence=0.90,
            joystick_direction="LEFT",
            joystick_intensity=0.85,
        )
        assert res.CRS > 80.0
        assert mgr.get_latest().fusion_id == res.fusion_id
        history = mgr.get_history(limit=10)
        assert len(history) == 1
        assert history[0].voice_command == "LEFT"

    def test_manager_status_aggregates(self):
        mgr = FusionManager()
        mgr.reset_stats()

        # Agreement
        mgr.evaluate_manual_bundle(voice_command="FORWARD", joystick_direction="FORWARD")
        # Contradiction
        mgr.evaluate_manual_bundle(voice_command="FORWARD", joystick_direction="BACKWARD")

        status = mgr.get_status()
        assert status.total_evaluations == 2
        assert status.total_agreements >= 1
        assert status.total_contradictions == 1
        assert status.average_crs > 0.0

