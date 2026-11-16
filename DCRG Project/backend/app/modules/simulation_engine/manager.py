"""
Simulation Manager for DCRG Phase 7.
Coordinates the interactive 2D kinematic robot simulation, manages physics tick updates,
integrates with the Phase 6 Safety Authorization Engine and Simulated Command Gateway,
maintains the immutable command execution audit log, and broadcasts real-time telemetry.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
import time
from typing import Callable, List, Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.modules.safety_engine.manager import safety_manager
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    SafetyDecision,
)
from app.modules.safety_engine.gateway import simulated_gateway
from app.modules.simulation_engine.schemas import (
    CommandExecutionRecord,
    ExecutionResultType,
    RobotPose,
    SimulationConfig,
    SimulationState,
)
from app.modules.simulation_engine.simulator import RobotSimulator

logger = logging.getLogger(__name__)


class SimulationManager:
    """
    Central Controller for the Robot Simulation Subsystem.
    Listens to verified safety decisions, gates kinematic motion execution,
    maintains simulation timing, and logs all command lifecycle events.
    """

    def __init__(
        self,
        simulator: Optional[RobotSimulator] = None,
        autostart: bool = True,
    ):
        self._lock = threading.RLock()
        self.simulator = simulator or RobotSimulator()

        # Command Execution Audit Log (capped at 200 records)
        self._execution_logs: List[CommandExecutionRecord] = []
        self._max_logs = 200

        # State Telemetry Listeners
        self._subscribers: List[Callable[[SimulationState], None]] = []

        # Physics Loop Threading
        self._stop_event = threading.Event()
        self._physics_thread: Optional[threading.Thread] = None
        self._tick_rate_hz = self.simulator.config.tick_rate_hz

        # Subscribe directly to Phase 6 Safety Manager
        safety_manager.subscribe(self.on_safety_decision)

        if autostart:
            self.start()

    def start(self) -> None:
        """Starts background simulation physics update thread."""
        with self._lock:
            if self._physics_thread is not None and self._physics_thread.is_alive():
                return
            self._stop_event.clear()
            self._physics_thread = threading.Thread(
                target=self._physics_loop,
                name="SimulationPhysicsLoop",
                daemon=True,
            )
            self._physics_thread.start()
            logger.info("Simulation physics loop started at %.1f Hz.", self._tick_rate_hz)

    def stop(self) -> None:
        """Stops background simulation physics thread."""
        self._stop_event.set()
        if self._physics_thread is not None:
            self._physics_thread.join(timeout=1.0)
            self._physics_thread = None
            logger.info("Simulation physics loop stopped.")

    def _physics_loop(self) -> None:
        """Background physics execution loop running at tick_rate_hz."""
        dt = 1.0 / max(1.0, self._tick_rate_hz)
        next_tick = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()
            sleep_duration = next_tick - now
            if sleep_duration > 0:
                time.sleep(sleep_duration)

            next_tick += dt
            if next_tick < time.monotonic():
                next_tick = time.monotonic() + dt

            try:
                self.step(dt)
            except Exception as e:
                logger.error("Error in simulation physics step: %s", e)

    def step(self, dt: float) -> Tuple[RobotPose, bool]:
        """
        Advances the kinematic simulation forward by dt seconds.
        Dispatches state updates to all active listeners.
        """
        pose, has_moved = self.simulator.step(dt)
        state = self.simulator.get_state()
        self._broadcast(state)
        return pose, has_moved

    def subscribe(self, callback: Callable[[SimulationState], None]) -> None:
        """Registers a listener for real-time simulation state updates."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[SimulationState], None]) -> None:
        """Unregisters a previously registered listener."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _broadcast(self, state: SimulationState) -> None:
        """Dispatches state snapshot to subscribers."""
        with self._lock:
            listeners = list(self._subscribers)
        for cb in listeners:
            try:
                cb(state)
            except Exception as e:
                logger.error("Error dispatching simulation state to subscriber: %s", e)

    def _record_execution(
        self,
        decision_id: str,
        requested_command: str,
        authorized_command: Optional[str],
        crs: Optional[float],
        authorization_state: str,
        execution_result: ExecutionResultType,
        pose_before: RobotPose,
        pose_after: RobotPose,
        rejection_reason: Optional[str] = None,
    ) -> CommandExecutionRecord:
        """Appends an immutable audit log record for a command evaluation."""
        record = CommandExecutionRecord(
            command_id=str(uuid4()),
            decision_id=decision_id,
            timestamp_ms=time.time() * 1000.0,
            requested_command=requested_command,
            authorized_command=authorized_command,
            crs=crs,
            authorization_state=authorization_state,
            execution_result=execution_result,
            rejection_reason=rejection_reason,
            pose_before=pose_before,
            pose_after=pose_after,
        )
        with self._lock:
            self._execution_logs.append(record)
            if len(self._execution_logs) > self._max_logs:
                self._execution_logs.pop(0)
        return record

    def on_safety_decision(self, decision: SafetyDecision) -> None:
        """
        Safety Manager subscription listener.
        Processes verified safety decisions and translates them into simulation actuation.
        """
        pose_before = self.simulator.get_pose()
        auth_state = decision.authorization_state.value
        req_cmd = decision.requested_command or "UNKNOWN"
        crs_val = decision.crs_score

        # Case 1: EMERGENCY HALT
        if decision.authorization_state == AuthorizationState.EMERGENCY:
            self.simulator.halt_immediate("EMERGENCY")
            pose_after = self.simulator.get_pose()
            self._record_execution(
                decision_id=decision.decision_id,
                requested_command=req_cmd,
                authorized_command=None,
                crs=crs_val,
                authorization_state=auth_state,
                execution_result=ExecutionResultType.EMERGENCY_STOPPED,
                pose_before=pose_before,
                pose_after=pose_after,
                rejection_reason=decision.reason or "EMERGENCY STOP ENGAGED",
            )
            self.simulator.record_telemetry(
                rejected_command=req_cmd,
                rejection_reason=decision.reason,
                crs=crs_val,
            )
            logger.warning("Simulation halted by EMERGENCY decision: %s", decision.reason)
            return

        # Case 2: RED STATE (Contradiction, constraint violation, or low CRS)
        if decision.authorization_state == AuthorizationState.RED:
            self.simulator.halt_immediate("RED")
            pose_after = self.simulator.get_pose()
            self._record_execution(
                decision_id=decision.decision_id,
                requested_command=req_cmd,
                authorized_command=None,
                crs=crs_val,
                authorization_state=auth_state,
                execution_result=ExecutionResultType.REJECTED,
                pose_before=pose_before,
                pose_after=pose_after,
                rejection_reason=decision.reason or "Safety rule violation / Contradiction",
            )
            self.simulator.record_telemetry(
                rejected_command=req_cmd,
                rejection_reason=decision.reason,
                crs=crs_val,
            )
            logger.info("Simulation rejected RED command: %s (%s)", req_cmd, decision.reason)
            return

        # Case 3: YELLOW HOLD (Uncertain, human confirmation required)
        if decision.authorization_state == AuthorizationState.YELLOW:
            self.simulator.halt_immediate("YELLOW")
            pose_after = self.simulator.get_pose()
            self._record_execution(
                decision_id=decision.decision_id,
                requested_command=req_cmd,
                authorized_command=None,
                crs=crs_val,
                authorization_state=auth_state,
                execution_result=ExecutionResultType.HELD,
                pose_before=pose_before,
                pose_after=pose_after,
                rejection_reason=decision.reason or "YELLOW state: Pending operator confirmation",
            )
            self.simulator.record_telemetry(
                rejected_command=req_cmd,
                rejection_reason=decision.reason or "Pending confirmation",
                crs=crs_val,
            )
            logger.info("Simulation placed command on YELLOW HOLD: %s", req_cmd)
            return

        # Case 4: GREEN STATE (Fully authorized)
        if decision.authorization_state == AuthorizationState.GREEN:
            if (
                decision.authorization_decision == AuthorizationDecision.AUTHORIZED
                and decision.authorized_command
            ):
                cmd_to_run = decision.authorized_command.upper()
                self.simulator.apply_authorized_command(cmd_to_run, "GREEN")
                pose_after = self.simulator.get_pose()

                self._record_execution(
                    decision_id=decision.decision_id,
                    requested_command=req_cmd,
                    authorized_command=cmd_to_run,
                    crs=crs_val,
                    authorization_state=auth_state,
                    execution_result=ExecutionResultType.EXECUTED,
                    pose_before=pose_before,
                    pose_after=pose_after,
                )
                self.simulator.record_telemetry(
                    crs=crs_val,
                    rejected_command=None,
                    rejection_reason=None,
                )
                logger.info("Simulation applied authorized command: %s", cmd_to_run)
            else:
                # Green state but not authorized (e.g. unknown command primitive)
                self.simulator.halt_immediate("GREEN")
                pose_after = self.simulator.get_pose()
                self._record_execution(
                    decision_id=decision.decision_id,
                    requested_command=req_cmd,
                    authorized_command=None,
                    crs=crs_val,
                    authorization_state=auth_state,
                    execution_result=ExecutionResultType.REJECTED,
                    pose_before=pose_before,
                    pose_after=pose_after,
                    rejection_reason=decision.reason or "No authorized command primitive available",
                )

    def dispatch_gateway_command(
        self,
        decision: SafetyDecision,
        command: str,
        auth_token: Optional[str] = None,
    ) -> Tuple[bool, CommandExecutionRecord]:
        """
        Directly submits a command and decision through the Simulated Command Gateway.
        Enforces token replay protection, expiration TTL, and decision checks.
        Returns (is_executed, CommandExecutionRecord).
        """
        pose_before = self.simulator.get_pose()
        token = auth_token or decision.auth_token
        is_accepted, gw_record = simulated_gateway.dispatch(decision, command, token)

        if is_accepted:
            self.simulator.apply_authorized_command(command, "GREEN")
            pose_after = self.simulator.get_pose()
            record = self._record_execution(
                decision_id=decision.decision_id,
                requested_command=command,
                authorized_command=command,
                crs=decision.crs_score,
                authorization_state=decision.authorization_state.value,
                execution_result=ExecutionResultType.EXECUTED,
                pose_before=pose_before,
                pose_after=pose_after,
            )
            return True, record
        else:
            self.simulator.halt_immediate(decision.authorization_state.value)
            pose_after = self.simulator.get_pose()
            record = self._record_execution(
                decision_id=decision.decision_id,
                requested_command=command,
                authorized_command=None,
                crs=decision.crs_score,
                authorization_state=decision.authorization_state.value,
                execution_result=ExecutionResultType.REJECTED,
                pose_before=pose_before,
                pose_after=pose_after,
                rejection_reason=gw_record.reason,
            )
            return False, record

    # Simulator Controls
    def pause(self) -> bool:
        """Pauses simulation physics."""
        return self.simulator.set_paused(True)

    def resume(self) -> bool:
        """Resumes simulation physics."""
        return self.simulator.set_paused(False)

    def reset_pose(self, x: float = 0.0, y: float = 0.0, heading: float = 0.0) -> RobotPose:
        """Resets the robot to specified coordinates."""
        return self.simulator.reset_pose(x, y, heading)

    def set_speed_multiplier(self, multiplier: float) -> float:
        """Adjusts simulation speed scaling."""
        return self.simulator.set_speed_multiplier(multiplier)

    def get_state(self) -> SimulationState:
        """Retrieves comprehensive real-time simulation snapshot."""
        return self.simulator.get_state()

    def get_execution_logs(self, limit: int = 50) -> List[CommandExecutionRecord]:
        """Retrieves chronological execution audit logs (newest first)."""
        with self._lock:
            return list(reversed(self._execution_logs[-limit:]))


# Global Singleton Instance
simulation_manager = SimulationManager()

