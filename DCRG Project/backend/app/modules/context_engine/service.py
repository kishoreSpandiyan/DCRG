"""
Mission Context Engine Service for DCRG Phase 5.
Maintains operational context, environmental safety boundaries, and constraint validation.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
from typing import Optional, Tuple
import time

from app.modules.context_engine.schemas import ContextState, MissionMode

logger = logging.getLogger(__name__)


class ContextService:
    """
    Thread-safe Mission Context Service.
    Evaluates environmental and operational constraints against commanded directions.
    """

    def __init__(self, initial_state: Optional[ContextState] = None):
        self._lock = threading.RLock()
        self._state: ContextState = initial_state or ContextState()

    def get_state(self) -> ContextState:
        """Returns the current snapshot of operational context."""
        with self._lock:
            return self._state.model_copy()

    def update_state(self, new_state: ContextState) -> ContextState:
        """Atomically replaces the operational context state."""
        with self._lock:
            new_state.timestamp_ms = time.time() * 1000.0
            self._state = new_state
            logger.debug("Context state updated: mode=%s, obstacle_dist=%.1f",
                         self._state.operating_mode, self._state.nearest_obstacle_distance_m)
            return self._state.model_copy()

    def patch_state(self, **kwargs) -> ContextState:
        """Selectively updates fields of the operational context state."""
        with self._lock:
            state_dict = self._state.model_dump()
            for key, val in kwargs.items():
                if key in state_dict and val is not None:
                    state_dict[key] = val
            state_dict["timestamp_ms"] = time.time() * 1000.0
            self._state = ContextState(**state_dict)
            return self._state.model_copy()

    def reset_defaults(self) -> ContextState:
        """Resets the context engine to nominal default baseline state."""
        with self._lock:
            self._state = ContextState()
            return self._state.model_copy()

    def evaluate_contextual_consistency(
        self,
        direction: Optional[str],
        intensity: Optional[float] = 1.0,
    ) -> Tuple[float, bool, str]:
        """
        Calculates the contextual consistency factor C in [0.0, 1.0].
        
        Returns:
            Tuple of:
            - factor_score (float in [0.0, 1.0])
            - is_admissible (bool: whether movement is physically permissible)
            - explanation (str: human-readable rationale)
        """
        with self._lock:
            state = self._state

            # Rule 1: Missing / unavailable context must never be fabricated as 1.0
            if not state.is_available:
                return (
                    0.5,
                    True,
                    "Context telemetry unavailable; provisional neutral factor applied without fabrication.",
                )

            # Rule 2: Non-directional or neutral command handling
            dir_norm = direction.upper().strip() if direction else ""
            if not dir_norm or dir_norm in ("CENTER", "NONE"):
                return 1.0, True, "Neutral position; no environmental hazard."

            if dir_norm == "STOP":
                return 1.0, True, "STOP command is always contextually admissible."

            if dir_norm in ("UNKNOWN", "UNCERTAIN"):
                return 0.5, True, "Command direction ambiguous; neutral context evaluation."

            # Rule 3: Operating mode restrictions
            if state.operating_mode == MissionMode.EMERGENCY_STOP:
                return 0.0, False, "Robot is in EMERGENCY_STOP mode; all movement strictly forbidden."

            if state.operating_mode == MissionMode.DOCKED:
                return 0.0, False, "Robot is DOCKED; motion disengaged until undock sequence."

            score = 1.0

            # Rule 4: Directional permissibility
            if dir_norm not in state.permitted_directions:
                return (
                    0.0,
                    False,
                    f"Direction '{dir_norm}' is not permitted in current mission profile (permitted: {state.permitted_directions}).",
                )

            # Rule 5: Active dynamic constraints
            for constraint in state.active_constraints:
                if not constraint.is_active:
                    continue
                forbidden = [d.upper() for d in constraint.forbidden_directions]
                if dir_norm in forbidden:
                    return (
                        0.0,
                        False,
                        f"Active constraint '{constraint.constraint_id}' blocks direction '{dir_norm}': {constraint.description}",
                    )
                if intensity is not None and intensity > constraint.max_intensity:
                    speed_penalty = constraint.max_intensity / max(intensity, 0.01)
                    score = min(score, speed_penalty)

            # Rule 6: Obstacle proximity and stopping distance
            if state.obstacle_direction and state.obstacle_direction.upper() == dir_norm:
                d_obs = state.nearest_obstacle_distance_m
                d_stop = state.stopping_distance_threshold_m

                if d_obs <= d_stop:
                    return (
                        0.0,
                        False,
                        f"Obstacle in direction '{dir_norm}' at {d_obs:.2f}m is within critical stopping threshold ({d_stop:.2f}m).",
                    )
                elif d_obs < (2.0 * d_stop):
                    # Proximity penalty buffer
                    ratio = (d_obs - d_stop) / d_stop
                    score = min(score, max(0.1, 0.2 + 0.6 * ratio))
                    return (
                        round(score * state.context_confidence, 3),
                        True,
                        f"Proximity caution: Obstacle detected '{dir_norm}' at {d_obs:.2f}m (stopping buffer: {d_stop:.2f}m).",
                    )

            # Rule 7: Scale with sensor/context confidence
            score = round(min(1.0, max(0.0, score * state.context_confidence)), 3)
            return score, True, "Trajectory satisfies all operational and environmental constraints."


# Global singleton instance for backend context evaluation
context_service = ContextService()
