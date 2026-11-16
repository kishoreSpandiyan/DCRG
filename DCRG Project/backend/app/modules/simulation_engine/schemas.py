"""
Robot Simulation and Command Execution Schemas for DCRG Phase 7.
Defines data structures for robot pose, kinematic state, obstacles,
simulation configurations, execution records, and control requests.
Compliant with DCRG-ARCH-005.
"""

from enum import Enum
from typing import List, Optional, Tuple
from uuid import uuid4
import time
from pydantic import BaseModel, Field


class ExecutionResultType(str, Enum):
    """Categorical outcome of command dispatch and simulation application."""
    AUTHORIZED = "AUTHORIZED"
    EXECUTED = "EXECUTED"
    HELD = "HELD"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class RobotPose(BaseModel):
    """Spatial 2D position, orientation, and kinematic velocity of the simulated robot."""
    x: float = Field(0.0, description="X coordinate in meters on 2D grid")
    y: float = Field(0.0, description="Y coordinate in meters on 2D grid")
    heading_deg: float = Field(0.0, description="Heading angle in degrees (0=North/+Y, 90=East/+X)")
    linear_speed: float = Field(0.0, ge=0.0, description="Current linear velocity in m/s")
    angular_speed: float = Field(0.0, ge=0.0, description="Current angular rotational velocity in deg/s")


class Obstacle(BaseModel):
    """Static circular collision obstacle within the simulation environment."""
    id: str = Field(..., description="Unique obstacle identifier")
    x: float = Field(..., description="Obstacle center X coordinate (m)")
    y: float = Field(..., description="Obstacle center Y coordinate (m)")
    radius: float = Field(..., ge=0.1, description="Collision radius (m)")
    label: str = Field("Static Barrier", description="Human-readable obstacle label")


class SimulationConfig(BaseModel):
    """Configurable boundaries, kinematic limits, and rates for the robot simulation."""
    boundary_min_x: float = Field(-50.0, description="West grid boundary (m)")
    boundary_max_x: float = Field(50.0, description="East grid boundary (m)")
    boundary_min_y: float = Field(-50.0, description="South grid boundary (m)")
    boundary_max_y: float = Field(50.0, description="North grid boundary (m)")
    base_speed: float = Field(3.0, ge=0.1, le=10.0, description="Max linear velocity (m/s)")
    turn_speed_deg: float = Field(120.0, ge=10.0, le=360.0, description="Max rotational velocity (deg/s)")
    tick_rate_hz: float = Field(20.0, ge=1.0, le=60.0, description="Physics loop update frequency (Hz)")
    robot_radius: float = Field(1.0, ge=0.2, le=5.0, description="Collision envelope radius of robot (m)")


class CommandExecutionRecord(BaseModel):
    """
    Immutable audit record for every command evaluated against the simulation engine.
    Ensures commands are strictly recorded as EXECUTED only after simulated actuation occurs.
    """
    command_id: str = Field(default_factory=lambda: str(uuid4()), description="Execution event UUID")
    decision_id: str = Field(..., description="Associated Phase 6 SafetyDecision UUID")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000.0, description="Execution timestamp UTC")
    requested_command: str = Field(..., description="Motion primitive requested")
    authorized_command: Optional[str] = Field(None, description="Command approved by Safety Gateway")
    crs: Optional[float] = Field(None, description="Command Reliability Score")
    authorization_state: str = Field(..., description="GREEN, YELLOW, RED, or EMERGENCY")
    execution_result: ExecutionResultType = Field(..., description="Execution outcome")
    rejection_reason: Optional[str] = Field(None, description="Failure or hold explanation")
    pose_before: RobotPose = Field(..., description="Robot pose immediately prior to command")
    pose_after: RobotPose = Field(..., description="Robot pose immediately following command step")


class SimulationState(BaseModel):
    """
    Authoritative real-time state of the robot simulation environment.
    Broadcasted over WebSockets to synchronize dashboard visualizers.
    """
    pose: RobotPose = Field(default_factory=RobotPose, description="Current robot spatial pose")
    active_command: str = Field("STOP", description="Active motion primitive being executed")
    authorization_state: str = Field("GREEN", description="Active safety authorization state")
    is_running: bool = Field(True, description="Whether simulation physics loop is active")
    is_paused: bool = Field(False, description="Whether simulation is currently paused")
    is_collision: bool = Field(False, description="Collision flag")
    collision_object: Optional[str] = Field(None, description="Identifier of collided obstacle")
    boundary_hit: bool = Field(False, description="Boundary limit reached flag")
    speed_multiplier: float = Field(1.0, ge=0.1, le=5.0, description="Simulation time/speed scale")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000.0, description="Snapshot timestamp")
    step_count: int = Field(0, description="Simulation physics ticks elapsed")
    trajectory: List[List[float]] = Field(default_factory=list, description="Historical breadcrumb trajectory [[x, y], ...]")
    obstacles: List[Obstacle] = Field(default_factory=list, description="Active environment obstacles")
    last_rejected_command: Optional[str] = Field(None, description="Most recent rejected command primitive")
    last_rejection_reason: Optional[str] = Field(None, description="Explanation for most recent rejection")
    voice_command: Optional[str] = Field(None, description="Latest recognized speech command")
    joystick_direction: Optional[str] = Field(None, description="Latest joystick direction")
    crs: Optional[float] = Field(None, description="Latest Command Reliability Score")


class SimulationControlRequest(BaseModel):
    """Request payload to control simulation physics or reset robot position."""
    action: str = Field(..., description="START, PAUSE, RESUME, RESET, or SET_SPEED")
    speed_multiplier: Optional[float] = Field(None, ge=0.1, le=5.0, description="Speed scaling factor")
    reset_x: Optional[float] = Field(0.0, description="Reset target X coordinate")
    reset_y: Optional[float] = Field(0.0, description="Reset target Y coordinate")

