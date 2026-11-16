"""
Common Joystick Event Contract and Actuator Engine Schemas.
Standardized data contracts for both physical hardware and virtual simulation.
"""

from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID, uuid4
import time
from pydantic import BaseModel, Field, field_validator, model_validator


class JoystickDirection(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    FORWARD_LEFT = "FORWARD_LEFT"
    FORWARD_RIGHT = "FORWARD_RIGHT"
    BACKWARD_LEFT = "BACKWARD_LEFT"
    BACKWARD_RIGHT = "BACKWARD_RIGHT"
    UNKNOWN = "UNKNOWN"


class JoystickSource(str, Enum):
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"
    VIRTUAL_SIMULATION = "VIRTUAL_SIMULATION"


class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    DEGRADED = "DEGRADED"


class CalibrationStatus(str, Enum):
    CALIBRATED = "CALIBRATED"
    UNCALIBRATED = "UNCALIBRATED"
    DEFAULT = "DEFAULT"


class DataValidity(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    CORRUPTED = "CORRUPTED"


class CommonJoystickEvent(BaseModel):
    """
    Standardized Joystick Event Contract consumed by the DCRG Actuator Engine.
    Enforces strict typing, range validation, temporal checks, and hardware isolation.
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event identifier (UUID)")
    source: JoystickSource = Field(..., description="Ingress origin (PHYSICAL_HARDWARE or VIRTUAL_SIMULATION)")
    device_id: str = Field(..., description="Device identifier (e.g., 'USB-046d-c215' or 'VIRT-SIM-001')")
    timestamp: float = Field(default_factory=lambda: time.time() * 1000.0, description="Unix timestamp in milliseconds")
    axis_x: float = Field(..., ge=-1.0, le=1.0, description="Normalized deflection on X axis (-1.0 Left to +1.0 Right)")
    axis_y: float = Field(..., ge=-1.0, le=1.0, description="Normalized deflection on Y axis (-1.0 Backward to +1.0 Forward)")
    direction: JoystickDirection = Field(..., description="Classified motion direction or state")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Normalized scalar magnitude of deflection")
    buttons: List[bool] = Field(default_factory=list, description="Digital state of joystick buttons")
    connection_status: ConnectionStatus = Field(ConnectionStatus.CONNECTED, description="Device connection health")
    calibration_status: CalibrationStatus = Field(CalibrationStatus.DEFAULT, description="Axis calibration state")
    data_validity: DataValidity = Field(DataValidity.VALID, description="Freshness and integrity flag")
    is_simulation: bool = Field(..., description="Strict boolean flag indicating simulated telemetry")

    @field_validator("axis_x", "axis_y")
    @classmethod
    def validate_axis_range(cls, v: float) -> float:
        if v < -1.0 or v > 1.0:
            raise ValueError(f"Axis value {v} outside normalized range [-1.0, +1.0]")
        return round(v, 4)

    @field_validator("intensity")
    @classmethod
    def validate_intensity_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"Intensity {v} outside range [0.0, 1.0]")
        return round(v, 4)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: float) -> float:
        # Prevent absurd historical or far-future timestamps (tolerance: must be > year 2024 and < +10 minutes)
        now_ms = time.time() * 1000.0
        if v < 1700000000000.0 or v > (now_ms + 600000.0):
            raise ValueError(f"Timestamp {v} is invalid or corrupted")
        return v

    @model_validator(mode="after")
    def enforce_simulation_isolation(self) -> "CommonJoystickEvent":
        # Rule: Source and is_simulation must never be contradictory
        if self.source == JoystickSource.VIRTUAL_SIMULATION and not self.is_simulation:
            raise ValueError("Virtual simulation events must have is_simulation=True")
        if self.source == JoystickSource.PHYSICAL_HARDWARE and self.is_simulation:
            raise ValueError("Physical hardware events cannot have is_simulation=True")
        
        # Rule: Disconnected or corrupted joystick must never be classified as CENTER
        if (self.connection_status == ConnectionStatus.DISCONNECTED or self.data_validity != DataValidity.VALID) and self.direction == JoystickDirection.CENTER:
            raise ValueError("Disconnected or corrupted joystick cannot be classified as CENTER")
        
        return self


class JoystickMode(str, Enum):
    VIRTUAL_SIMULATION = "VIRTUAL_SIMULATION"
    REAL_HARDWARE = "REAL_HARDWARE"


class JoystickSystemStatus(BaseModel):
    """System-level joystick subsystem health and discovery summary."""
    active_mode: JoystickMode = Field(default=JoystickMode.VIRTUAL_SIMULATION)
    physical_hardware_detected: bool = Field(default=False)
    connected_device_count: int = Field(default=0)
    primary_device_name: Optional[str] = None
    primary_device_id: Optional[str] = None
    connection_status: ConnectionStatus = Field(default=ConnectionStatus.DISCONNECTED)
    calibration_status: CalibrationStatus = Field(default=CalibrationStatus.DEFAULT)
    last_event: Optional[CommonJoystickEvent] = None
    error_message: Optional[str] = None

