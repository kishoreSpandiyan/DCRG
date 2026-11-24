"""
DCRG Fusion Calculator.
Implements mathematical formulations for Semantic Reliability (S),
Motor Agreement (M), Contextual Consistency (C), Contradiction Veto Filter,
and the composite Command Reliability Score (CRS).
Compliant with DCRG-ARCH-005.
"""

import math
from typing import Dict, List, Optional, Tuple
import logging

from app.core.config import settings
from app.modules.context_engine.service import context_service
from app.modules.sync_engine.schemas import CorrelatedEvent, SynchronizationStatus
from app.modules.fusion_engine.schemas import (
    AnalyticalFinding,
    CRSStatus,
    FusionConfig,
    FusionFactors,
    FusionResult,
)

logger = logging.getLogger(__name__)

# Direction Vectors for canonical voice commands
VOICE_DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "FORWARD": (0.0, 1.0),
    "BACKWARD": (0.0, -1.0),
    "LEFT": (-1.0, 0.0),
    "RIGHT": (1.0, 0.0),
    "STOP": (0.0, 0.0),
    "UNKNOWN": (0.0, 0.0),
    "UNCERTAIN": (0.0, 0.0),
}

# Diagonal and cardinal joystick direction mapping
JOYSTICK_DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "FORWARD": (0.0, 1.0),
    "BACKWARD": (0.0, -1.0),
    "LEFT": (-1.0, 0.0),
    "RIGHT": (1.0, 0.0),
    "FORWARD_LEFT": (-0.7071, 0.7071),
    "FORWARD_RIGHT": (0.7071, 0.7071),
    "BACKWARD_LEFT": (-0.7071, -0.7071),
    "BACKWARD_RIGHT": (0.7071, -0.7071),
    "CENTER": (0.0, 0.0),
    "UNKNOWN": (0.0, 0.0),
}


class CRSCalculator:
    """
    Mathematical computation engine for multimodal command fusion.
    Stateless evaluator operating on CorrelatedEvent contracts.
    """

    def __init__(self, config: Optional[FusionConfig] = None):
        self.config = config or FusionConfig(
            weight_semantic=settings.CRS_WEIGHT_SEMANTIC,
            weight_motor=settings.CRS_WEIGHT_MOTOR,
            weight_context=settings.CRS_WEIGHT_CONTEXT,
            stress_damping=settings.CRS_STRESS_DAMPING,
            contradiction_cap=settings.CRS_CONTRADICTION_CAP,
            contradiction_whisper_min=settings.CRS_CONTRADICTION_WHISPER_MIN,
            contradiction_joystick_min=settings.CRS_CONTRADICTION_JOYSTICK_MIN,
            joystick_deadzone=settings.CRS_JOYSTICK_DEADZONE,
            scoring_config_version=settings.CRS_SCORING_CONFIG_VERSION,
        )

    def normalize_joystick(
        self,
        event: CorrelatedEvent,
    ) -> Tuple[Tuple[float, float], float, bool]:
        """
        Extracts and normalizes the joystick direction vector (x, y) and intensity.
        Handles radial deadzones, diagonal movements, and neutral positions.

        Returns:
            Tuple of:
            - unit_vector: (x, y) normalized to unit length or (0.0, 0.0)
            - intensity: scalar magnitude in [0.0, 1.0]
            - is_neutral: boolean indicating stick is within deadzone
        """
        deadzone = self.config.joystick_deadzone
        intensity = 0.0
        vec = (0.0, 0.0)

        # Priority 1: Raw axis values from CommonJoystickEvent if present
        if event.joystick_event is not None:
            raw_x = event.joystick_event.axis_x
            raw_y = event.joystick_event.axis_y
            mag = math.sqrt(raw_x * raw_x + raw_y * raw_y)

            if mag < deadzone:
                return (0.0, 0.0), 0.0, True

            intensity = min(1.0, max(0.0, mag))
            vec = (raw_x / mag, raw_y / mag)
            return vec, intensity, False

        # Priority 2: Use joystick_direction and joystick_intensity from CorrelatedEvent
        if event.joystick_direction:
            dir_str = event.joystick_direction.upper().strip()
            intensity = min(1.0, max(0.0, event.joystick_intensity or 0.0))

            if dir_str in ("CENTER", "UNKNOWN") or intensity < deadzone:
                return (0.0, 0.0), 0.0, True

            base_vec = JOYSTICK_DIRECTION_VECTORS.get(dir_str, (0.0, 0.0))
            return base_vec, intensity, False

        # No joystick data
        return (0.0, 0.0), 0.0, True

    def calculate_semantic_factor(self, event: CorrelatedEvent) -> Tuple[float, str]:
        """
        Computes Semantic Factor S in [0.0, 1.0]:
        S = C_whisper * (1.0 - beta * S_stress)

        Defensive clamps:
        - UNKNOWN or UNCERTAIN tokens strictly yield S = 0.0
        - Missing prosody data assumes S_stress = 0.0 (no false stress penalization)
        - Values clamped to [0.0, 1.0]
        """
        if not event.voice_available or not event.voice_command:
            return 0.0, "Voice modality unpartnered or absent."

        cmd = event.voice_command.upper().strip()
        if cmd in ("UNKNOWN", "UNCERTAIN"):
            return 0.0, f"Spoken command is non-actionable: {cmd}"

        # Whisper recognition confidence
        c_whisper = 0.0
        if event.voice_event is not None:
            c_whisper = event.voice_event.recognition_confidence
            if event.voice_event.is_uncertain or event.voice_event.semantic_status.value == "UNCERTAIN":
                return 0.0, "Voice classifier marked command as UNCERTAIN."
        else:
            c_whisper = 0.80  # Default nominal confidence if unbundled

        c_whisper = min(1.0, max(0.0, c_whisper))

        # Prosody cognitive stress
        s_stress = 0.0
        if event.voice_event is not None and event.voice_event.composite_stress_score is not None:
            s_stress = min(1.0, max(0.0, event.voice_event.composite_stress_score))

        beta = self.config.stress_damping
        attenuation = max(0.0, 1.0 - (beta * s_stress))
        score = min(1.0, max(0.0, c_whisper * attenuation))

        explanation = (
            f"Semantic S={score:.3f} (Whisper conf={c_whisper:.2f}, "
            f"Stress={s_stress:.2f}, Attenuation={attenuation:.2f})"
        )
        return round(score, 4), explanation

    def calculate_sync_quality(self, event: CorrelatedEvent) -> float:
        """
        Computes temporal synchrony factor Q_sync in [0.0, 1.0]:
        Q_sync = max(0.0, 1.0 - (Delta_t / tau_sync))
        """
        status = event.synchronization_status

        if status == SynchronizationStatus.SYNCHRONIZED:
            delta_t = event.timestamp_difference_ms if event.timestamp_difference_ms is not None else 0.0
            tau_sync = max(1.0, settings.SYNC_WINDOW_MS)
            if delta_t <= tau_sync:
                decay = max(0.0, 1.0 - (abs(delta_t) / tau_sync))
            else:
                # Active multimodal deflection beyond strict boundary decays smoothly over max_event_age
                max_age = max(1.0, getattr(settings, "SYNC_MAX_EVENT_AGE_MS", 2500.0))
                decay = max(0.20, 0.70 * (1.0 - (abs(delta_t) / max_age)))
            return round(min(1.0, max(0.0, decay)), 4)
        elif status in (SynchronizationStatus.VOICE_ONLY, SynchronizationStatus.JOYSTICK_ONLY):
            return 0.5
        elif status in (SynchronizationStatus.OUT_OF_WINDOW, SynchronizationStatus.DELAYED, SynchronizationStatus.STALE):
            return 0.1
        else:
            # DUPLICATE or INVALID_TIMESTAMP
            return 0.0

    def calculate_motor_agreement(
        self,
        event: CorrelatedEvent,
        joy_vec: Tuple[float, float],
        joy_intensity: float,
        joy_is_neutral: bool,
        q_sync: float,
    ) -> Tuple[float, Optional[float], Optional[float], str]:
        """
        Computes Motor Agreement Factor M in [0.0, 1.0]:
        M = ((1 + cos(Delta theta)) / 2) * sqrt(I_joy) * Q_sync

        Handles special non-directional commands:
        - STOP spoken + Neutral joystick => Agreement (M = 1.0 * Q_sync)
        - STOP spoken + Active joystick (I >= 0.30) => Contradiction (M = 0.0)
        - UNKNOWN/UNCERTAIN spoken => M = 0.0
        """
        if not event.voice_available or not event.voice_command:
            # Joystick-only input
            if joy_is_neutral:
                return 0.0, None, None, "Joystick in neutral position; no voice command."
            # Unpartnered active joystick gives fractional motor evidence
            m_score = min(1.0, math.sqrt(joy_intensity) * q_sync)
            return round(m_score, 4), None, None, f"Unpartnered joystick movement (intensity={joy_intensity:.2f})."

        cmd = event.voice_command.upper().strip()

        # Edge case: Spoken STOP
        if cmd == "STOP":
            if joy_is_neutral or joy_intensity < 0.10:
                m_score = min(1.0, 1.0 * q_sync)
                return round(m_score, 4), 1.0, 0.0, "Voice STOP and Neutral joystick in agreement."
            elif joy_intensity >= self.config.contradiction_joystick_min:
                return 0.0, -1.0, 180.0, "Voice STOP contradicts active joystick movement."
            else:
                # Transitional deflection
                taper = max(0.0, 1.0 - ((joy_intensity - 0.10) / 0.20))
                m_score = min(1.0, taper * q_sync)
                return round(m_score, 4), 0.0, 90.0, "Voice STOP with slight joystick residual deflection."

        if cmd in ("UNKNOWN", "UNCERTAIN"):
            return 0.0, None, None, f"Voice command {cmd} cannot establish motor agreement."

        if not event.joystick_available or joy_is_neutral:
            return 0.0, None, None, "Voice command active but joystick is centered/neutral (no physical motion)."

        # Directional Voice vs Joystick Vector Cosine Similarity
        v_vec = VOICE_DIRECTION_VECTORS.get(cmd, (0.0, 0.0))
        v_mag = math.sqrt(v_vec[0] * v_vec[0] + v_vec[1] * v_vec[1])
        j_mag = math.sqrt(joy_vec[0] * joy_vec[0] + joy_vec[1] * joy_vec[1])

        if v_mag < 1e-4 or j_mag < 1e-4:
            return 0.0, None, None, "Zero vector encountered during directional comparison."

        # Dot product
        dot = (v_vec[0] * joy_vec[0]) + (v_vec[1] * joy_vec[1])
        cos_sim = max(-1.0, min(1.0, dot / (v_mag * j_mag)))
        ang_deg = math.degrees(math.acos(cos_sim))

        alignment_factor = (1.0 + cos_sim) / 2.0
        intensity_factor = math.sqrt(joy_intensity)
        m_score = min(1.0, max(0.0, alignment_factor * intensity_factor * q_sync))

        explanation = (
            f"Motor M={m_score:.3f} (cos_sim={cos_sim:.2f}, ang={ang_deg:.1f}deg, "
            f"joy_int={joy_intensity:.2f}, Q_sync={q_sync:.2f})"
        )
        return round(m_score, 4), round(cos_sim, 4), round(ang_deg, 2), explanation

    def check_contradiction(
        self,
        event: CorrelatedEvent,
        cos_sim: Optional[float],
        joy_intensity: float,
        joy_is_neutral: bool,
    ) -> Tuple[bool, Optional[str]]:
        """
        The Zero-Override Contradiction Veto Filter:
        Asserts contradiction if:
        1. Directional contradiction: cos(Delta theta) <= 0.0 AND C_whisper >= 0.70 AND I_joy >= 0.30
        2. Spoken STOP contradiction: Voice STOP with C_whisper >= 0.70 AND I_joy >= 0.30
        """
        if not event.voice_available or not event.voice_command:
            return False, None

        cmd = event.voice_command.upper().strip()
        c_whisper = event.voice_event.recognition_confidence if event.voice_event else 0.80

        min_whisper = self.config.contradiction_whisper_min
        min_joy = self.config.contradiction_joystick_min

        # Check 1: Spoken STOP vs Active Joystick
        if cmd == "STOP":
            if c_whisper >= min_whisper and joy_intensity >= min_joy:
                reason = (
                    f"Direct Contradiction: Spoken 'STOP' (conf={c_whisper:.2f}) "
                    f"opposed by active joystick deflection ({joy_intensity:.2f} >= {min_joy})."
                )
                return True, reason
            return False, None

        # Check 2: Directional Contradiction (Opposing or Perpendicular directions)
        if cos_sim is not None and cos_sim <= 0.0:
            if c_whisper >= min_whisper and joy_intensity >= min_joy:
                j_dir = event.joystick_direction or "DEFLECTED"
                reason = (
                    f"Direct Contradiction: Spoken '{cmd}' (conf={c_whisper:.2f}) "
                    f"opposed by physical joystick '{j_dir}' (intensity={joy_intensity:.2f}, cos_sim={cos_sim:.2f})."
                )
                return True, reason

        return False, None

    def evaluate(self, event: CorrelatedEvent) -> FusionResult:
        """
        Executes complete DCRG fusion evaluation on a CorrelatedEvent.
        Computes S, M, C, detects contradictions, applies veto clamping,
        and constructs a fully-specified FusionResult.
        """
        # 1. Inspect input completeness & data hygiene
        missing_components: List[str] = []
        if not event.voice_available:
            missing_components.append("VOICE")
        if not event.joystick_available:
            missing_components.append("JOYSTICK")

        # Context completeness check
        ctx_state = context_service.get_state()
        if not ctx_state.is_available:
            missing_components.append("CONTEXT")

        evidence_completeness = 1.0 - (0.35 * len(missing_components))
        evidence_completeness = round(max(0.0, min(1.0, evidence_completeness)), 2)

        # 2. Check for invalid or duplicate events
        if event.synchronization_status in (
            SynchronizationStatus.INVALID_TIMESTAMP,
            SynchronizationStatus.DUPLICATE,
        ):
            return FusionResult(
                correlation_id=event.correlation_id,
                timestamp=event.correlation_timestamp,
                voice_command=event.voice_command,
                joystick_direction=event.joystick_direction,
                joystick_intensity=event.joystick_intensity,
                semantic_reliability=0.0,
                motor_agreement=0.0,
                context_consistency=0.0,
                factors=FusionFactors(
                    semantic_score=0.0,
                    motor_agreement=0.0,
                    context_consistency=0.0,
                    angular_delta_deg=None,
                    cosine_similarity=None,
                    sync_quality=0.0,
                ),
                CRS=0.0,
                CRS_status=CRSStatus.INVALID,
                contradiction_detected=False,
                contradiction_reason=f"Event rejected due to status: {event.synchronization_status.value}",
                synchronization_status=event.synchronization_status.value,
                temporal_delta_ms=event.timestamp_difference_ms,
                evidence_completeness=0.0,
                missing_components=missing_components,
                scoring_config_version=self.config.scoring_config_version,
                weights={
                    "semantic": self.config.weight_semantic,
                    "motor": self.config.weight_motor,
                    "context": self.config.weight_context,
                },
                explanation=f"Evaluation aborted: Synchronization status is {event.synchronization_status.value}.",
                analytical_finding=AnalyticalFinding.INSUFFICIENT_EVIDENCE,
                recommended_state="RED",
            )

        # 3. Joystick Normalization
        joy_vec, joy_intensity, joy_is_neutral = self.normalize_joystick(event)

        # 4. Temporal Alignment Quality Q_sync
        q_sync = self.calculate_sync_quality(event)

        # 5. Component Scoring
        # A. Semantic Reliability S
        s_score, s_exp = self.calculate_semantic_factor(event)

        # B. Motor Agreement M
        m_score, cos_sim, ang_deg, m_exp = self.calculate_motor_agreement(
            event, joy_vec, joy_intensity, joy_is_neutral, q_sync
        )

        # C. Contextual Consistency C
        target_dir = event.voice_command or event.joystick_direction
        c_score, is_admissible, c_reason = context_service.evaluate_contextual_consistency(
            target_dir, joy_intensity
        )

        # 6. Contradiction Veto Filter
        contradiction_detected, contradiction_reason = self.check_contradiction(
            event, cos_sim, joy_intensity, joy_is_neutral
        )

        # 7. Raw Composite CRS Calculation
        ws = self.config.weight_semantic
        wm = self.config.weight_motor
        wc = self.config.weight_context

        raw_crs = 100.0 * ((ws * s_score) + (wm * m_score) + (wc * c_score))

        # 8. Contradiction Clamping
        final_crs = raw_crs
        if contradiction_detected:
            final_crs = min(raw_crs, self.config.contradiction_cap)

        final_crs = round(max(0.0, min(100.0, final_crs)), 1)

        # 9. Determine Analytical Finding
        if contradiction_detected:
            finding = AnalyticalFinding.CONTRADICTION
        elif not is_admissible:
            finding = AnalyticalFinding.CONTEXT_VIOLATION
        elif event.voice_command in ("UNKNOWN",):
            finding = AnalyticalFinding.UNKNOWN_COMMAND
        elif event.voice_command in ("UNCERTAIN",):
            finding = AnalyticalFinding.UNCERTAIN_COMMAND
        elif event.voice_available and joy_is_neutral and event.voice_command != "STOP":
            finding = AnalyticalFinding.NEUTRAL_JOYSTICK
        elif s_score > 0.60 and m_score > 0.60:
            finding = AnalyticalFinding.AGREEMENT
        elif not ctx_state.is_available:
            finding = AnalyticalFinding.CONTEXT_UNAVAILABLE
        else:
            finding = AnalyticalFinding.INSUFFICIENT_EVIDENCE

        # 10. Determine CRS Status Category
        if evidence_completeness >= 1.0 and event.synchronization_status == SynchronizationStatus.SYNCHRONIZED:
            crs_status = CRSStatus.COMPLETE
        elif event.voice_available or event.joystick_available:
            crs_status = CRSStatus.PROVISIONAL
        else:
            crs_status = CRSStatus.INCOMPLETE

        # 11. Informative Explanation String
        voice_desc = f"{event.voice_command or 'NONE'}"
        if event.voice_event:
            voice_desc += f" (conf={event.voice_event.recognition_confidence:.2f})"
        joy_desc = f"{event.joystick_direction or 'NONE'}"
        if joy_intensity > 0.0:
            joy_desc += f" (intensity={joy_intensity:.2f})"

        explanation = (
            f"Evaluated multimodal pair [Voice: {voice_desc} | Joystick: {joy_desc}]. "
            f"Factors: Semantic={s_score:.2f}, Motor={m_score:.2f}, Context={c_score:.2f}. "
            f"Weights: [Ws={ws:.2f}, Wm={wm:.2f}, Wc={wc:.2f}]. "
            f"Raw CRS: {raw_crs:.1f} -> Final CRS: {final_crs:.1f}/100 ({crs_status.value}). "
            f"Finding: {finding.value}."
        )
        if contradiction_detected:
            explanation = f"VETO ASSERTED: {contradiction_reason} CRS capped at {self.config.contradiction_cap:.1f}. " + explanation

        # Recommended state indicator (transitional guidance for Phase 6)
        recommended_state = "GREEN" if (final_crs >= 85.0 and not contradiction_detected and is_admissible) else ("YELLOW" if final_crs >= 50.0 and not contradiction_detected else "RED")

        return FusionResult(
            correlation_id=event.correlation_id,
            timestamp=event.correlation_timestamp,
            voice_command=event.voice_command,
            joystick_direction=event.joystick_direction,
            joystick_intensity=joy_intensity,
            semantic_reliability=s_score,
            motor_agreement=m_score,
            context_consistency=c_score,
            factors=FusionFactors(
                semantic_score=s_score,
                motor_agreement=m_score,
                context_consistency=c_score,
                angular_delta_deg=ang_deg,
                cosine_similarity=cos_sim,
                sync_quality=q_sync,
            ),
            CRS=final_crs,
            CRS_status=crs_status,
            contradiction_detected=contradiction_detected,
            veto_asserted=contradiction_detected,
            contradiction_reason=contradiction_reason,
            synchronization_status=event.synchronization_status.value,
            temporal_delta_ms=event.timestamp_difference_ms,
            evidence_completeness=evidence_completeness,
            missing_components=missing_components,
            scoring_config_version=self.config.scoring_config_version,
            weights={"semantic": ws, "motor": wm, "context": wc},
            explanation=explanation,
            analytical_finding=finding,
            recommended_state=recommended_state,
        )

