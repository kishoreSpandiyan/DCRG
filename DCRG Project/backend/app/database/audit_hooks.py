"""
Audit Hooks Subsystem for DCRG Phase 8.
Wires persistent audit logging into Voice, Joystick, Sync, Fusion, Safety, and Simulation streams.
"""

import logging
from typing import Optional

from app.database.audit_logger import audit_logger
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.actuator_engine.schemas import CommonJoystickEvent
from app.modules.voice_engine.manager import voice_manager
from app.modules.voice_engine.schemas import VoiceEvent
from app.modules.sync_engine.manager import sync_manager
from app.modules.sync_engine.schemas import CorrelatedEvent
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.fusion_engine.schemas import FusionResult
from app.modules.safety_engine.manager import safety_manager
from app.modules.safety_engine.schemas import SafetyDecision
from app.modules.simulation_engine.manager import simulation_manager

logger = logging.getLogger(__name__)

_hooks_installed = False


def install_audit_subscribers() -> None:
    """Connects all active subsystem event streams to persistent SQLite audit logging."""
    global _hooks_installed
    if _hooks_installed:
        return

    # 1. Voice Event Hook
    def on_voice_event(v: VoiceEvent) -> None:
        try:
            audit_logger.log_event(
                category="VOICE",
                command=v.recognized_command.value if hasattr(v.recognized_command, "value") else str(v.recognized_command),
                details={
                    "transcript": v.transcript,
                    "confidence": v.recognition_confidence,
                    "is_uncertain": v.is_uncertain,
                    "pitch_f0": v.pitch_f0,
                    "composite_stress_score": v.composite_stress_score,
                },
                event_id=v.event_id,
            )
        except Exception as e:
            logger.debug("Voice audit log error: %s", e)

    # 2. Joystick Event Hook (Filtered to active deflections or changes)
    last_logged_dir = [None]
    def on_joystick_event(j: CommonJoystickEvent) -> None:
        try:
            cur_dir = j.direction.value if hasattr(j.direction, "value") else str(j.direction)
            if cur_dir != last_logged_dir[0] and (cur_dir != "CENTER" or j.intensity > 0.1):
                last_logged_dir[0] = cur_dir
                audit_logger.log_event(
                    category="JOYSTICK",
                    command=cur_dir,
                    details={
                        "axis_x": j.axis_x,
                        "axis_y": j.axis_y,
                        "intensity": j.intensity,
                        "source": j.source.value if hasattr(j.source, "value") else str(j.source),
                        "buttons": j.buttons,
                    },
                    event_id=j.event_id,
                )
            elif cur_dir == "CENTER" and last_logged_dir[0] != "CENTER":
                last_logged_dir[0] = "CENTER"
                audit_logger.log_event(
                    category="JOYSTICK",
                    command="CENTER",
                    details={"intensity": 0.0, "source": str(j.source)},
                    event_id=j.event_id,
                )
        except Exception as e:
            logger.debug("Joystick audit log error: %s", e)

    # 3. Synchronizer Correlated Event Hook
    def on_sync_event(c: CorrelatedEvent) -> None:
        try:
            audit_logger.log_event(
                category="SYNC",
                command=c.voice_command,
                details={
                    "correlation_id": c.correlation_id,
                    "joystick_direction": c.joystick_direction,
                    "temporal_delta_ms": c.temporal_delta_ms,
                    "synchronization_status": c.synchronization_status.value if hasattr(c.synchronization_status, "value") else str(c.synchronization_status),
                    "evidence_completeness": c.evidence_completeness,
                },
                event_id=c.correlation_id,
            )
        except Exception as e:
            logger.debug("Sync audit log error: %s", e)

    # 4. Fusion Engine Event Hook
    def on_fusion_event(f: FusionResult) -> None:
        try:
            audit_logger.log_event(
                category="FUSION",
                command=f.voice_command,
                safety_state=f.recommended_state,
                crs=f.CRS,
                details={
                    "fusion_id": f.fusion_id,
                    "crs_status": f.CRS_status.value if hasattr(f.CRS_status, "value") else str(f.CRS_status),
                    "contradiction_detected": f.contradiction_detected,
                    "semantic_score": f.factors.semantic_score,
                    "motor_agreement": f.factors.motor_agreement,
                    "context_consistency": f.factors.context_consistency,
                },
                event_id=f.fusion_id,
            )
        except Exception as e:
            logger.debug("Fusion audit log error: %s", e)

    # 5. Safety Manager Event Hook
    def on_safety_event(s: SafetyDecision) -> None:
        try:
            audit_logger.log_event(
                category="SAFETY",
                command=s.authorized_command or s.requested_command,
                safety_state=s.authorization_state.value if hasattr(s.authorization_state, "value") else str(s.authorization_state),
                execution_result=s.authorization_decision.value if hasattr(s.authorization_decision, "value") else str(s.authorization_decision),
                crs=s.crs_score,
                details={
                    "decision_id": s.decision_id,
                    "reason": s.reason,
                    "is_latched": s.is_latched,
                    "is_confirmed": s.is_confirmed,
                },
                event_id=s.decision_id,
            )
        except Exception as e:
            logger.debug("Safety audit log error: %s", e)

    # Register listeners
    voice_manager.subscribe(on_voice_event)
    actuator_manager.subscribe(on_joystick_event)
    sync_manager.subscribe(on_sync_event)
    fusion_manager.subscribe(on_fusion_event)
    safety_manager.subscribe(on_safety_event)

    _hooks_installed = True
    logger.info("DCRG Audit Hooks successfully registered across all subsystems.")

