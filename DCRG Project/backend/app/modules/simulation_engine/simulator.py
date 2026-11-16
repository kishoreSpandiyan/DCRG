"""
Interactive 2D Robot Kinematic Simulator for DCRG Phase 7.
Simulates smooth motion, rotational heading transitions, boundary constraints,
obstacle collision detection, and breadcrumb trajectory tracking.
Compliant with DCRG-ARCH-005.
"""

import math
import logging
import threading
import time
from typing import List, Optional, Tuple

from app.core.config import settings
from app.modules.simulation_engine.schemas import (
    Obstacle,
    RobotPose,
    SimulationConfig,
    SimulationState,
)

logger = logging.getLogger(__name__)

# Heading mapping for motion primitives (0=North, 90=East, 180=South, 270=West)
TARGET_HEADINGS = {
    "FORWARD": 0.0,
    "RIGHT": 90.0,
    "BACKWARD": 180.0,
    "LEFT": 270.0,
    "STOP": None,
}


class RobotSimulator:
    """
    2D Kinematic Robot Simulator.
    Calculates differential time-stepped position updates, angular orientation alignment,
    environment boundary checks, and circular obstacle collisions.
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        self._lock = threading.RLock()
        self.config = config or SimulationConfig(
            boundary_min_x=settings.SIMULATION_BOUNDARY_MIN_X,
            boundary_max_x=settings.SIMULATION_BOUNDARY_MAX_X,
            boundary_min_y=settings.SIMULATION_BOUNDARY_MIN_Y,
            boundary_max_y=settings.SIMULATION_BOUNDARY_MAX_Y,
            base_speed=settings.SIMULATION_BASE_SPEED,
            turn_speed_deg=settings.SIMULATION_TURN_SPEED_DEG,
            tick_rate_hz=settings.SIMULATION_TICK_RATE_HZ,
            robot_radius=settings.SIMULATION_ROBOT_RADIUS,
        )

        # Pose & Motion States
        self._x: float = 0.0
        self._y: float = 0.0
        self._heading_deg: float = 0.0  # 0.0 = Facing North (+Y)
        self._linear_speed: float = 0.0
        self._angular_speed: float = 0.0
        self._active_command: str = "STOP"
        self._authorization_state: str = "GREEN"

        # Flags & Diagnostics
        self._is_paused: bool = False
        self._is_collision: bool = False
        self._collision_object: Optional[str] = None
        self._boundary_hit: bool = False
        self._speed_multiplier: float = 1.0
        self._step_count: int = 0
        self._trajectory: List[List[float]] = [[0.0, 0.0]]
        self._max_trajectory_points = 100

        # Telemetry Cache from latest evaluation
        self._last_rejected_command: Optional[str] = None
        self._last_rejection_reason: Optional[str] = None
        self._voice_command: Optional[str] = None
        self._joystick_direction: Optional[str] = None
        self._crs: Optional[float] = None

        # Environment Obstacles (3 static pylons/barriers)
        self._obstacles: List[Obstacle] = [
            Obstacle(id="obs-alpha", x=15.0, y=15.0, radius=3.5, label="Barrier Alpha"),
            Obstacle(id="obs-beta", x=-20.0, y=12.0, radius=4.0, label="Pylon Beta"),
            Obstacle(id="obs-gamma", x=0.0, y=-25.0, radius=3.0, label="Cylinder Gamma"),
        ]

    def get_pose(self) -> RobotPose:
        """Returns snapshot of current robot spatial pose."""
        with self._lock:
            return RobotPose(
                x=round(self._x, 3),
                y=round(self._y, 3),
                heading_deg=round(self._heading_deg, 1),
                linear_speed=round(self._linear_speed, 2),
                angular_speed=round(self._angular_speed, 2),
            )

    def apply_authorized_command(self, command: str, auth_state: str = "GREEN") -> bool:
        """
        Applies a newly verified authorized command to the robot kinematic state.
        Only called by the SimulationManager upon valid gateway approval.
        """
        cmd_clean = command.upper().strip()
        with self._lock:
            self._active_command = cmd_clean
            self._authorization_state = auth_state

            if cmd_clean == "STOP":
                self._linear_speed = 0.0
                self._angular_speed = 0.0
            else:
                self._is_collision = False
                self._boundary_hit = False

            logger.debug("Simulator applied command: %s (State: %s)", cmd_clean, auth_state)
            return True

    def halt_immediate(self, reason_state: str = "EMERGENCY") -> None:
        """Instantly zeroes velocities and arrests robot motion."""
        with self._lock:
            self._active_command = "STOP"
            self._linear_speed = 0.0
            self._angular_speed = 0.0
            self._authorization_state = reason_state

    def step(self, dt: float) -> Tuple[RobotPose, bool]:
        """
        Advances the kinematic simulation forward by time delta dt (seconds).
        Implements smooth rotational alignment, velocity ramp, boundary clamps,
        and obstacle collision detection.

        Returns (new_pose, has_moved).
        """
        with self._lock:
            if self._is_paused:
                return self.get_pose(), False

            self._step_count += 1
            cmd = self._active_command
            target_heading = TARGET_HEADINGS.get(cmd)

            # 1. Smooth Angular Heading Rotation
            if target_heading is not None:
                # Shortest angular distance across 0/360 wrap
                diff = (target_heading - self._heading_deg + 180.0) % 360.0 - 180.0
                max_turn = self.config.turn_speed_deg * self._speed_multiplier * dt
                if abs(diff) > 1e-2:
                    turn_step = math.copysign(min(abs(diff), max_turn), diff)
                    self._heading_deg = (self._heading_deg + turn_step) % 360.0
                    self._angular_speed = abs(turn_step) / max(dt, 0.001)
                else:
                    self._heading_deg = target_heading
                    self._angular_speed = 0.0
            else:
                self._angular_speed = 0.0

            # 2. Linear Velocity & Translation Step
            target_speed = (
                self.config.base_speed * self._speed_multiplier
                if cmd in ("FORWARD", "BACKWARD", "LEFT", "RIGHT")
                else 0.0
            )

            # Smooth speed acceleration / deceleration
            accel = 8.0 * dt  # Ramp rate
            if self._linear_speed < target_speed:
                self._linear_speed = min(target_speed, self._linear_speed + accel)
            elif self._linear_speed > target_speed:
                self._linear_speed = max(target_speed, self._linear_speed - accel)

            old_x, old_y = self._x, self._y

            if self._linear_speed > 0.0:
                dist = self._linear_speed * dt
                if cmd == "FORWARD":
                    self._y += dist
                elif cmd == "BACKWARD":
                    self._y -= dist
                elif cmd == "LEFT":
                    self._x -= dist
                elif cmd == "RIGHT":
                    self._x += dist

            # 3. Boundary Limits Collision Check
            r = self.config.robot_radius
            if self._x < (self.config.boundary_min_x + r):
                self._x = self.config.boundary_min_x + r
                self._linear_speed = 0.0
                self._boundary_hit = True
                self._active_command = "STOP"
            elif self._x > (self.config.boundary_max_x - r):
                self._x = self.config.boundary_max_x - r
                self._linear_speed = 0.0
                self._boundary_hit = True
                self._active_command = "STOP"

            if self._y < (self.config.boundary_min_y + r):
                self._y = self.config.boundary_min_y + r
                self._linear_speed = 0.0
                self._boundary_hit = True
                self._active_command = "STOP"
            elif self._y > (self.config.boundary_max_y - r):
                self._y = self.config.boundary_max_y - r
                self._linear_speed = 0.0
                self._boundary_hit = True
                self._active_command = "STOP"

            # 4. Obstacle Collision Detection
            for obs in self._obstacles:
                dx = self._x - obs.x
                dy = self._y - obs.y
                center_dist = math.sqrt(dx * dx + dy * dy)
                min_safe_dist = r + obs.radius

                if center_dist <= min_safe_dist:
                    self._is_collision = True
                    self._collision_object = obs.id
                    self._linear_speed = 0.0
                    self._active_command = "STOP"

                    # Push back outward along collision normal
                    if center_dist > 1e-4:
                        overlap = min_safe_dist - center_dist
                        self._x += (dx / center_dist) * overlap
                        self._y += (dy / center_dist) * overlap
                    break

            has_moved = (abs(self._x - old_x) > 1e-4) or (abs(self._y - old_y) > 1e-4)

            # 5. Record Trajectory Breadcrumb
            if has_moved and self._trajectory:
                last_pt = self._trajectory[-1]
                traj_dist = math.sqrt((self._x - last_pt[0])**2 + (self._y - last_pt[1])**2)
                if traj_dist >= 0.5:
                    self._trajectory.append([round(self._x, 2), round(self._y, 2)])
                    if len(self._trajectory) > self._max_trajectory_points:
                        self._trajectory.pop(0)

            return self.get_pose(), has_moved

    def reset_pose(self, x: float = 0.0, y: float = 0.0, heading: float = 0.0) -> RobotPose:
        """Resets the robot to starting coordinates and clears collision flags."""
        with self._lock:
            self._x = x
            self._y = y
            self._heading_deg = heading
            self._linear_speed = 0.0
            self._angular_speed = 0.0
            self._active_command = "STOP"
            self._is_collision = False
            self._collision_object = None
            self._boundary_hit = False
            self._trajectory = [[round(x, 2), round(y, 2)]]
            return self.get_pose()

    def set_speed_multiplier(self, multiplier: float) -> float:
        """Scales simulation execution speed (0.1x to 5.0x)."""
        with self._lock:
            self._speed_multiplier = max(0.1, min(5.0, multiplier))
            return self._speed_multiplier

    def set_paused(self, paused: bool) -> bool:
        """Pauses or resumes simulation physics updates."""
        with self._lock:
            self._is_paused = paused
            return self._is_paused

    def record_telemetry(
        self,
        voice_command: Optional[str] = None,
        joystick_direction: Optional[str] = None,
        crs: Optional[float] = None,
        rejected_command: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> None:
        """Updates display cache with latest multi-modal evaluation metadata."""
        with self._lock:
            if voice_command is not None:
                self._voice_command = voice_command
            if joystick_direction is not None:
                self._joystick_direction = joystick_direction
            if crs is not None:
                self._crs = crs
            if rejected_command is not None:
                self._last_rejected_command = rejected_command
            if rejection_reason is not None:
                self._last_rejection_reason = rejection_reason

    def get_state(self) -> SimulationState:
        """Generates comprehensive snapshot of the simulation environment."""
        with self._lock:
            return SimulationState(
                pose=self.get_pose(),
                active_command=self._active_command,
                authorization_state=self._authorization_state,
                is_running=True,
                is_paused=self._is_paused,
                is_collision=self._is_collision,
                collision_object=self._collision_object,
                boundary_hit=self._boundary_hit,
                speed_multiplier=self._speed_multiplier,
                timestamp_ms=time.time() * 1000.0,
                step_count=self._step_count,
                trajectory=list(self._trajectory),
                obstacles=list(self._obstacles),
                last_rejected_command=self._last_rejected_command,
                last_rejection_reason=self._last_rejection_reason,
                voice_command=self._voice_command,
                joystick_direction=self._joystick_direction,
                crs=self._crs,
            )

