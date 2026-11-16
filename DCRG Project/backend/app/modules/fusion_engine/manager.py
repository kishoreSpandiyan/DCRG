"""
Fusion Manager for DCRG Phase 5.
Subscribes to Phase 4 Synchronization Engine events, coordinates CRS evaluation,
maintains history, and dispatches FusionResults to listeners and WebSockets.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
from typing import Callable, List, Optional, Tuple

from app.core.config import settings
from app.modules.sync_engine.schemas import CorrelatedEvent, SynchronizationStatus
from app.modules.sync_engine.manager import sync_manager
from app.modules.voice_engine.schemas import VoiceEvent, CanonicalCommand
from app.modules.actuator_engine.schemas import CommonJoystickEvent, JoystickDirection, JoystickSource
from app.modules.fusion_engine.schemas import (
    CRSStatus,
    FusionConfig,
    FusionEngineStatus,
    FusionResult,
)
from app.modules.fusion_engine.calculator import CRSCalculator

logger = logging.getLogger(__name__)


class FusionManager:
    """
    Central Coordinator for the DCRG Fusion Engine.
    Subscribes to synchronized multimodal streams and produces verified CRS metrics.
    """

    def __init__(self, calculator: Optional[CRSCalculator] = None):
        self.calculator = calculator or CRSCalculator()
        self._lock = threading.RLock()
        self._history: List[FusionResult] = []
        self._max_history = 100
        self._subscribers: List[Callable[[FusionResult], None]] = []
        self._is_active = True

        # Aggregate runtime counters
        self._total_evaluations = 0
        self._total_agreements = 0
        self._total_contradictions = 0
        self._crs_sum = 0.0

        # Subscribe directly to Phase 4 Event Synchronization stream
        sync_manager.subscribe(self.process_correlated_event)

    def start(self) -> Tuple[bool, str]:
        """Activates fusion engine processing."""
        with self._lock:
            self._is_active = True
            msg = "Fusion Engine started successfully."
            logger.info(msg)
            return True, msg

    def stop(self) -> Tuple[bool, str]:
        """Deactivates fusion engine processing."""
        with self._lock:
            self._is_active = False
            msg = "Fusion Engine paused."
            logger.info(msg)
            return True, msg

    def subscribe(self, callback: Callable[[FusionResult], None]) -> None:
        """Registers a listener callback for newly produced FusionResults."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[FusionResult], None]) -> None:
        """Unregisters a previously registered listener."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _dispatch(self, result: FusionResult) -> None:
        """Dispatches result to all registered listeners safely."""
        with self._lock:
            listeners = list(self._subscribers)
        for cb in listeners:
            try:
                cb(result)
            except Exception as e:
                logger.error("Error in fusion subscriber callback: %s", e)

    def process_correlated_event(self, event: CorrelatedEvent) -> Optional[FusionResult]:
        """
        Callback invoked whenever Phase 4 sync engine produces a CorrelatedEvent.
        Computes CRS and records result into history.
        """
        if not self._is_active:
            return None

        result = self.calculator.evaluate(event)

        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history.pop(0)

            self._total_evaluations += 1
            self._crs_sum += result.CRS
            if result.analytical_finding.value == "AGREEMENT":
                self._total_agreements += 1
            if result.contradiction_detected:
                self._total_contradictions += 1

        self._dispatch(result)
        return result

    def evaluate_manual_bundle(
        self,
        voice_command: Optional[str] = None,
        voice_confidence: float = 0.85,
        stress_score: float = 0.0,
        joystick_direction: Optional[str] = None,
        joystick_intensity: float = 0.80,
        axis_x: Optional[float] = None,
        axis_y: Optional[float] = None,
        sync_delta_ms: float = 10.0,
    ) -> FusionResult:
        """
        Manual evaluation utility for explicit pair testing or API evaluation calls.
        """
        v_event: Optional[VoiceEvent] = None
        j_event: Optional[CommonJoystickEvent] = None

        if voice_command:
            try:
                canon_cmd = CanonicalCommand(voice_command.upper().strip())
            except ValueError:
                canon_cmd = CanonicalCommand.UNKNOWN

            v_event = VoiceEvent(
                transcript=voice_command.lower(),
                normalized_transcript=voice_command.lower(),
                recognized_command=canon_cmd,
                recognition_confidence=voice_confidence,
                classification_confidence=voice_confidence,
                composite_stress_score=stress_score,
            )

        if joystick_direction:
            try:
                joy_dir = JoystickDirection(joystick_direction.upper().strip())
            except ValueError:
                joy_dir = JoystickDirection.UNKNOWN

            # Default axes if not explicitly provided
            if axis_x is None or axis_y is None:
                if joy_dir == JoystickDirection.FORWARD:
                    axis_x, axis_y = 0.0, joystick_intensity
                elif joy_dir == JoystickDirection.BACKWARD:
                    axis_x, axis_y = 0.0, -joystick_intensity
                elif joy_dir == JoystickDirection.LEFT:
                    axis_x, axis_y = -joystick_intensity, 0.0
                elif joy_dir == JoystickDirection.RIGHT:
                    axis_x, axis_y = joystick_intensity, 0.0
                else:
                    axis_x, axis_y = 0.0, 0.0

            j_event = CommonJoystickEvent(
                source=JoystickSource.VIRTUAL_SIMULATION,
                device_id="VIRT-EVAL-001",
                axis_x=axis_x,
                axis_y=axis_y,
                direction=joy_dir,
                intensity=joystick_intensity,
                is_simulation=True,
            )

        correlated = CorrelatedEvent(
            voice_event_id=v_event.event_id if v_event else None,
            joystick_event_id=j_event.event_id if j_event else None,
            voice_command=voice_command.upper().strip() if voice_command else None,
            joystick_direction=joystick_direction.upper().strip() if joystick_direction else None,
            joystick_intensity=joystick_intensity if joystick_direction else None,
            timestamp_difference_ms=sync_delta_ms,
            synchronization_status=(
                SynchronizationStatus.SYNCHRONIZED
                if (voice_command and joystick_direction)
                else (SynchronizationStatus.VOICE_ONLY if voice_command else SynchronizationStatus.JOYSTICK_ONLY)
            ),
            voice_available=voice_command is not None,
            joystick_available=joystick_direction is not None,
            correlation_reason="Manual test bundle evaluation",
            voice_event=v_event,
            joystick_event=j_event,
        )

        return self.process_correlated_event(correlated)

    def get_latest(self) -> Optional[FusionResult]:
        """Returns the most recent fusion evaluation result."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_history(self, limit: int = 50) -> List[FusionResult]:
        """Returns a list of recent fusion results, most recent first."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_config(self) -> FusionConfig:
        """Returns the active FusionConfig parameters."""
        with self._lock:
            return self.calculator.config.model_copy()

    def update_config(self, new_config: FusionConfig) -> Tuple[bool, str]:
        """Updates scoring weights and thresholds dynamically."""
        with self._lock:
            self.calculator.config = new_config
            msg = f"Fusion configuration updated: Ws={new_config.weight_semantic}, Wm={new_config.weight_motor}, Wc={new_config.weight_context}"
            logger.info(msg)
            return True, msg

    def get_status(self) -> FusionEngineStatus:
        """Returns telemetry status metrics."""
        with self._lock:
            avg_crs = (self._crs_sum / self._total_evaluations) if self._total_evaluations > 0 else 0.0
            last_res = self._history[-1] if self._history else None
            return FusionEngineStatus(
                is_active=self._is_active,
                total_evaluations=self._total_evaluations,
                total_agreements=self._total_agreements,
                total_contradictions=self._total_contradictions,
                average_crs=round(avg_crs, 1),
                last_crs=last_res.CRS if last_res else None,
                last_status=last_res.CRS_status if last_res else None,
                scoring_config_version=self.calculator.config.scoring_config_version,
                weights={
                    "semantic": self.calculator.config.weight_semantic,
                    "motor": self.calculator.config.weight_motor,
                    "context": self.calculator.config.weight_context,
                },
            )

    def reset_stats(self) -> None:
        """Clears history and performance counters (primarily for test isolation)."""
        with self._lock:
            self._history.clear()
            self._total_evaluations = 0
            self._total_agreements = 0
            self._total_contradictions = 0
            self._crs_sum = 0.0


# Global singleton instance of FusionManager
fusion_manager = FusionManager()

