"""
Mission Context Engine Schemas for DCRG Phase 5.
Defines environmental constraints, operating modes, and situational context.
Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
"""

from enum import Enum
from typing import Dict, List, Optional
import time
from pydantic import BaseModel, Field, field_validator


class MissionMode(str, Enum):
    NORMAL = "NORMAL"
    RESTRICTED = "RESTRICTED"
    PRECISION = "PRECISION"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    DOCKED = "DOCKED"
    MAINTENANCE = "MAINTENANCE"


class MovementConstraint(BaseModel):
    """Specific environmental or mission constraint applied to movement commands."""
    constraint_id: str = Field(..., description="Unique constraint identifier")
    description: str = Field(..., description="Human-readable description of constraint")
    forbidden_directions: List[str] = Field(default_factory=list, description="Directions blocked by constraint")
    max_intensity: float = Field(1.0, ge=0.0, le=1.0, description="Speed/intensity ceiling")
    is_active: bool = Field(True, description="Whether constraint is currently enforced")


class ContextState(BaseModel):
    """
    Operational Context State consumed by the DCRG Fusion Engine.
    Represents the robot's physical situation, obstacles, and mission parameters.
    """
    operating_mode: MissionMode = Field(MissionMode.NORMAL, description="Current mission operational mode")
    permitted_directions: List[str] = Field(
        default_factory=lambda: ["FORWARD", "BACKWARD", "LEFT", "RIGHT", "STOP"],
        description="Directions permissible under current mission state"
    )
    nearest_obstacle_distance_m: float = Field(5.0, ge=0.0, description="Distance to closest obstacle in meters")
    obstacle_direction: Optional[str] = Field(None, description="Cardinal direction where nearest obstacle is detected")
    stopping_distance_threshold_m: float = Field(1.0, ge=0.0, description="Minimum safe stopping buffer")
    max_admissible_linear_velocity: float = Field(1.5, ge=0.0, description="Admissible linear velocity in m/s")
    current_linear_velocity: float = Field(0.0, ge=0.0, description="Current robot velocity in m/s")
    context_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Sensor/context reliability confidence")
    is_available: bool = Field(True, description="Whether real context telemetry is present")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000.0, description="UTC timestamp in ms")
    context_source: str = Field("SIMULATED_ENVIRONMENT", description="Origin of context telemetry")
    active_constraints: List[MovementConstraint] = Field(
        default_factory=list, description="Active movement constraint rules"
    )

    @field_validator("permitted_directions")
    @classmethod
    def normalize_directions(cls, dirs: List[str]) -> List[str]:
        return [d.upper().strip() for d in dirs]
