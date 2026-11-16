"""
Actuator Engine Package.
Ingests, normalizes, calibrates, and classifies physical and virtual joystick inputs.
"""

from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
    JoystickMode,
    JoystickSystemStatus,
)
from app.modules.actuator_engine.calibration import (
    JoystickProfile,
    JoystickProfileRegistry,
    apply_radial_deadzone,
    calibrate_axis,
)
from app.modules.actuator_engine.classifier import classify_joystick_vector

__all__ = [
    "CommonJoystickEvent",
    "JoystickDirection",
    "JoystickSource",
    "ConnectionStatus",
    "CalibrationStatus",
    "DataValidity",
    "JoystickMode",
    "JoystickSystemStatus",
    "JoystickProfile",
    "JoystickProfileRegistry",
    "apply_radial_deadzone",
    "calibrate_axis",
    "classify_joystick_vector",
]
