"""
Centralized Dynamic System Configuration Manager for DCRG Phase 8.
Governs parameters across Sync, Joystick, Voice, Fusion, Safety, and Simulation subsystems.
Enforces strict range validation, weight sum invariants, audit logging of modifications,
and explicit labeling of experimental parameters.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.database.audit_logger import audit_logger
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.manager import simulation_manager
from app.modules.sync_engine.manager import sync_manager

logger = logging.getLogger(__name__)


class SystemConfigModel(BaseModel):
    """Authoritative DCRG system parameter schema with strict range invariants."""
    sync_window_ms: float = Field(150.0, ge=50.0, le=500.0, description="Temporal correlation matching window (ms)")
    joystick_deadzone: float = Field(0.08, ge=0.01, le=0.40, description="Radial deadzone threshold")
    voice_confidence_threshold: float = Field(0.60, ge=0.10, le=1.00, description="Whisper confidence threshold")
    crs_weight_semantic: float = Field(0.35, ge=0.0, le=1.0, description="CRS semantic weight Ws")
    crs_weight_motor: float = Field(0.50, ge=0.0, le=1.0, description="CRS motor agreement weight Wm")
    crs_weight_context: float = Field(0.15, ge=0.0, le=1.0, description="CRS context consistency weight Wc")
    safety_green_threshold: float = Field(85.0, ge=50.0, le=100.0, description="CRS required for automatic GREEN authorization")
    safety_yellow_threshold: float = Field(50.0, ge=10.0, le=80.0, description="CRS floor for YELLOW hold")
    simulation_speed: float = Field(1.0, ge=0.1, le=5.0, description="Simulation physics time multiplier")
    prosody_stress_damping: float = Field(0.25, ge=0.0, le=1.0, description="Beta coefficient for stress attenuation (Experimental)")

    @model_validator(mode="after")
    def validate_invariants(self) -> "SystemConfigModel":
        # Invariant 1: CRS weights must sum to 1.0 (± 0.005)
        weight_sum = self.crs_weight_semantic + self.crs_weight_motor + self.crs_weight_context
        if abs(weight_sum - 1.0) > 0.005:
            raise ValueError(f"CRS weights must sum to 1.00. Current sum is {weight_sum:.3f}.")

        # Invariant 2: Yellow threshold must be strictly less than green threshold
        if self.safety_yellow_threshold >= self.safety_green_threshold:
            raise ValueError(
                f"Safety yellow threshold ({self.safety_yellow_threshold}) must be strictly less than green threshold ({self.safety_green_threshold})."
            )
        return self


class SystemConfigManager:
    """Central Controller managing dynamic runtime parameters and forensic audits."""

    def __init__(self):
        self._lock = threading.RLock()
        self._current_config = SystemConfigModel(
            sync_window_ms=settings.SYNC_WINDOW_MS,
            joystick_deadzone=settings.CRS_JOYSTICK_DEADZONE,
            voice_confidence_threshold=settings.VOICE_RECOGNITION_CONFIDENCE_THRESHOLD,
            crs_weight_semantic=settings.CRS_WEIGHT_SEMANTIC,
            crs_weight_motor=settings.CRS_WEIGHT_MOTOR,
            crs_weight_context=settings.CRS_WEIGHT_CONTEXT,
            safety_green_threshold=settings.SAFETY_GREEN_THRESHOLD,
            safety_yellow_threshold=settings.SAFETY_YELLOW_THRESHOLD,
            simulation_speed=1.0,
            prosody_stress_damping=settings.CRS_STRESS_DAMPING,
        )

        self._metadata = {
            "sync_window_ms": {
                "label": "Synchronization Window",
                "unit": "ms",
                "default": 150.0,
                "is_experimental": False,
                "description": "Maximum timestamp delta between voice and joystick events for multi-modal binding.",
            },
            "joystick_deadzone": {
                "label": "Joystick Radial Deadzone",
                "unit": "ratio",
                "default": 0.08,
                "is_experimental": False,
                "description": "Deflection filter below which joystick input is classified as neutral center.",
            },
            "voice_confidence_threshold": {
                "label": "Voice Confidence Floor",
                "unit": "ratio",
                "default": 0.60,
                "is_experimental": False,
                "description": "Minimum Whisper acoustic model confidence required for clear speech classification.",
            },
            "crs_weight_semantic": {
                "label": "CRS Semantic Weight (Ws)",
                "unit": "weight",
                "default": 0.35,
                "is_experimental": False,
                "description": "Weight of speech recognition and stress factor in final CRS evaluation.",
            },
            "crs_weight_motor": {
                "label": "CRS Motor Weight (Wm)",
                "unit": "weight",
                "default": 0.50,
                "is_experimental": False,
                "description": "Weight of directional joystick vector agreement in final CRS evaluation.",
            },
            "crs_weight_context": {
                "label": "CRS Context Weight (Wc)",
                "unit": "weight",
                "default": 0.15,
                "is_experimental": False,
                "description": "Weight of mission context and environmental constraints in final CRS evaluation.",
            },
            "safety_green_threshold": {
                "label": "Safety GREEN Threshold",
                "unit": "score",
                "default": 85.0,
                "is_experimental": False,
                "description": "Minimum CRS required for automatic simulation command authorization.",
            },
            "safety_yellow_threshold": {
                "label": "Safety YELLOW Threshold",
                "unit": "score",
                "default": 50.0,
                "is_experimental": False,
                "description": "CRS score threshold below which commands are rejected outright to RED.",
            },
            "simulation_speed": {
                "label": "Simulation Time Scaling",
                "unit": "multiplier",
                "default": 1.0,
                "is_experimental": False,
                "description": "Kinematic physics update time scale factor (0.1x to 5.0x).",
            },
            "prosody_stress_damping": {
                "label": "Prosody Stress Damping (Beta)",
                "unit": "coefficient",
                "default": 0.25,
                "is_experimental": True,
                "description": "Acoustic stress penalty coefficient. Marked EXPERIMENTAL pending clinical prosody validation.",
            },
        }

    def get_config(self) -> Dict[str, Any]:
        """Returns snapshot of active configuration along with metadata."""
        with self._lock:
            return {
                "parameters": self._current_config.model_dump(),
                "metadata": self._metadata,
            }

    def update_config(
        self,
        updates: Dict[str, Any],
        operator_id: str = "OP-PRIMARY",
        reason: Optional[str] = None,
    ) -> Tuple[bool, SystemConfigModel, str]:
        """
        Validates and applies configuration mutations, logging each field change to SQLite.
        Propagates new values directly into running subsystems.
        """
        with self._lock:
            current_dict = self._current_config.model_dump()
            merged_dict = {**current_dict, **updates}

            try:
                new_model = SystemConfigModel(**merged_dict)
            except Exception as e:
                err_msg = f"Validation failed: {e}"
                logger.warning("Configuration update rejected: %s", err_msg)
                return False, self._current_config, err_msg

            # Log forensic audit for each modified parameter
            for key, new_val in updates.items():
                if key in current_dict and current_dict[key] != new_val:
                    old_val = current_dict[key]
                    audit_logger.log_config_change(
                        parameter_name=key,
                        old_value=old_val,
                        new_value=new_val,
                        operator_id=operator_id,
                        reason=reason or "System settings update",
                    )
                    audit_logger.log_event(
                        category="CONFIG",
                        command=key,
                        details={
                            "operator_id": operator_id,
                            "parameter": key,
                            "old_value": old_val,
                            "new_value": new_val,
                            "reason": reason,
                        },
                    )

            # Apply runtime updates to live subsystems
            try:
                # Sync window
                if "sync_window_ms" in updates:
                    sync_manager.synchronizer.sync_window_ms = new_model.sync_window_ms

                # Actuator deadzone
                if "joystick_deadzone" in updates:
                    actuator_manager.radial_deadzone = new_model.joystick_deadzone

                # Fusion weights
                cfg = fusion_manager.get_config()
                cfg.weight_semantic = new_model.crs_weight_semantic
                cfg.weight_motor = new_model.crs_weight_motor
                cfg.weight_context = new_model.crs_weight_context
                fusion_manager.update_config(cfg)

                # Safety thresholds
                safety_manager.rule_engine.green_threshold = new_model.safety_green_threshold
                safety_manager.rule_engine.yellow_threshold = new_model.safety_yellow_threshold

                # Simulation speed
                if "simulation_speed" in updates:
                    simulation_manager.set_speed_multiplier(new_model.simulation_speed)

                self._current_config = new_model
                msg = "Configuration successfully updated and propagated to live subsystems."
                logger.info(msg)
                return True, self._current_config, msg
            except Exception as e:
                err_msg = f"Error applying configuration to active subsystems: {e}"
                logger.error(err_msg)
                return False, self._current_config, err_msg

    def reset_defaults(self, operator_id: str = "OP-PRIMARY") -> SystemConfigModel:
        """Resets all settings to system factory defaults and audits the reset."""
        defaults = {
            "sync_window_ms": 150.0,
            "joystick_deadzone": 0.08,
            "voice_confidence_threshold": 0.60,
            "crs_weight_semantic": 0.35,
            "crs_weight_motor": 0.50,
            "crs_weight_context": 0.15,
            "safety_green_threshold": 85.0,
            "safety_yellow_threshold": 50.0,
            "simulation_speed": 1.0,
            "prosody_stress_damping": 0.25,
        }
        _, updated_model, _ = self.update_config(defaults, operator_id=operator_id, reason="Reset to defaults")
        return updated_model


# Global Singleton Instance
system_config_manager = SystemConfigManager()
