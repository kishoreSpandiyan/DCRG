"""
Safety Manager for DCRG Phase 6.
Coordinates tiered safety evaluations, manages the software emergency-stop latch,
tracks pending human confirmations, and interfaces with the simulated gateway.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.fusion_engine.schemas import FusionResult
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    ConfirmationAction,
    EmergencyResetRequest,
    EmergencySource,
    EmergencyStopRequest,
    SafetyDecision,
    SafetyEngineStatus,
)
from app.modules.safety_engine.rules import SafetyRuleEngine
from app.modules.safety_engine.gateway import simulated_gateway

logger = logging.getLogger(__name__)


class SafetyManager:
    """
    Central Coordinator for the Tiered Safety Authorization Engine.
    Subscribes directly to Phase 5 FusionResult events and governs command admissibility.
    """

    def __init__(self, rule_engine: Optional[SafetyRuleEngine] = None):
        self.rule_engine = rule_engine or SafetyRuleEngine()
        self._lock = threading.RLock()
        
        # History & Pending Buffers
        self._history: List[SafetyDecision] = []
        self._max_history = 100
        self._pending_confirmations: Dict[str, SafetyDecision] = {}
        self._subscribers: List[Callable[[SafetyDecision], None]] = []
        self._is_active = True

        # Emergency Stop Latch State
        self._is_emergency_latched: bool = False
        self._emergency_source: Optional[EmergencySource] = None
        self._emergency_timestamp_ms: Optional[float] = None
        self._emergency_reason: Optional[str] = None

        # Cumulative Metrics
        self._total_decisions = 0
        self._total_green = 0
        self._total_yellow = 0
        self._total_red = 0
        self._total_emergency = 0

        # Hook directly into Phase 5 Fusion Engine
        fusion_manager.subscribe(self.process_fusion_result)

    def start(self) -> Tuple[bool, str]:
        """Starts safety authorization monitoring."""
        with self._lock:
            self._is_active = True
            msg = "Safety Authorization Engine active."
            logger.info(msg)
            return True, msg

    def stop(self) -> Tuple[bool, str]:
        """Pauses safety authorization monitoring."""
        with self._lock:
            self._is_active = False
            msg = "Safety Authorization Engine stopped."
            logger.info(msg)
            return True, msg

    def subscribe(self, callback: Callable[[SafetyDecision], None]) -> None:
        """Registers a listener callback for emitted SafetyDecisions."""
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[SafetyDecision], None]) -> None:
        """Unregisters a previously registered listener."""
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def _dispatch(self, decision: SafetyDecision) -> None:
        """Safely dispatches decision to all registered listeners."""
        with self._lock:
            listeners = list(self._subscribers)
        for cb in listeners:
            try:
                cb(decision)
            except Exception as e:
                logger.error("Error in safety subscriber callback: %s", e)

    def process_fusion_result(self, fusion_result: FusionResult) -> Optional[SafetyDecision]:
        """
        Evaluates an inbound FusionResult against the deterministic safety rules.
        """
        if not self._is_active:
            return None

        with self._lock:
            is_latched = self._is_emergency_latched
            source_str = self._emergency_source.value if self._emergency_source else None

        decision = self.rule_engine.evaluate(
            fusion_result=fusion_result,
            is_emergency_latched=is_latched,
            emergency_source=source_str,
        )

        with self._lock:
            # Check for YELLOW hold to stage for human confirmation
            if decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION:
                self._pending_confirmations[decision.decision_id] = decision
                self._total_yellow += 1
            elif decision.authorization_state == AuthorizationState.GREEN:
                self._total_green += 1
                # Forward automatically authorized GREEN decision to simulated gateway
                if decision.authorized_command and decision.auth_token:
                    simulated_gateway.dispatch(decision, decision.authorized_command, decision.auth_token)
            elif decision.authorization_state == AuthorizationState.RED:
                self._total_red += 1
            elif decision.authorization_state == AuthorizationState.EMERGENCY:
                self._total_emergency += 1

            self._total_decisions += 1
            self._history.append(decision)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        self._dispatch(decision)
        return decision

    def trigger_emergency_stop(
        self,
        source: EmergencySource = EmergencySource.SOFTWARE_UI,
        reason: str = "Manual emergency stop triggered",
        operator_id: str = "OP-PRIMARY",
    ) -> SafetyDecision:
        """
        Engages the Emergency Stop Latch.
        Immediately cancels all pending commands, locks out motion, and dispatches E-STOP halt.
        """
        now_ms = time.time() * 1000.0
        source_str = source.value if hasattr(source, "value") else str(source)

        with self._lock:
            self._is_emergency_latched = True
            self._emergency_source = source
            self._emergency_timestamp_ms = now_ms
            self._emergency_reason = reason
            self._total_emergency += 1

            # Immediately cancel any commands on YELLOW hold
            for dec in list(self._pending_confirmations.values()):
                dec.authorization_state = AuthorizationState.EMERGENCY
                dec.authorization_decision = AuthorizationDecision.EMERGENCY_HALT
                dec.is_confirmed = False
                dec.is_latched = True
                dec.reason = f"Cancelled by EMERGENCY STOP ({source_str})"
            self._pending_confirmations.clear()

            estop_decision = SafetyDecision(
                decision_id=str(uuid4()),
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.EMERGENCY,
                authorization_decision=AuthorizationDecision.EMERGENCY_HALT,
                requested_command="STOP",
                authorized_command=None,
                crs_score=0.0,
                crs_status="EMERGENCY",
                evidence_completeness=1.0,
                contradiction_detected=False,
                reason=f"EMERGENCY STOP ACTIVATED by {operator_id} via {source_str}: {reason}",
                auth_token=None,
                expires_at_ms=None,
                is_latched=True,
                is_simulation=True,
            )

            self._total_decisions += 1
            self._history.append(estop_decision)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        logger.warning("EMERGENCY STOP ACTIVATED (%s): %s", source_str, reason)
        self._dispatch(estop_decision)
        return estop_decision

    def reset_emergency_stop(
        self,
        reset_pin: str,
        operator_id: str = "OP-PRIMARY",
        reason: str = "Operator safety reset",
    ) -> Tuple[bool, str]:
        """
        Authorized Emergency Stop Reset Workflow.
        Verifies credentials before unlatching emergency lockout.
        """
        with self._lock:
            if not self._is_emergency_latched:
                return True, "Emergency stop is not currently engaged."

            # Verify authorization pin
            if reset_pin != settings.SAFETY_EMERGENCY_RESET_PIN:
                logger.warning("Unauthorized emergency reset attempt by %s with invalid PIN.", operator_id)
                return False, "Invalid emergency reset authorization PIN."

            self._is_emergency_latched = False
            self._emergency_source = None
            self._emergency_timestamp_ms = None
            self._emergency_reason = None

            reset_event = SafetyDecision(
                decision_id=str(uuid4()),
                timestamp_ms=time.time() * 1000.0,
                authorization_state=AuthorizationState.YELLOW,
                authorization_decision=AuthorizationDecision.HOLD_PENDING_CONFIRMATION,
                requested_command="STOP",
                authorized_command=None,
                crs_score=50.0,
                crs_status="RESET",
                evidence_completeness=1.0,
                contradiction_detected=False,
                reason=f"Emergency Stop UNLATCHED by operator {operator_id}: {reason}. System entering safe hold.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )
            self._history.append(reset_event)

        logger.info("Emergency Stop unlatched successfully by %s.", operator_id)
        self._dispatch(reset_event)
        return True, "Emergency Stop unlatched successfully. System returned to operational monitoring."

    def resolve_confirmation(
        self,
        decision_id: str,
        action: ConfirmationAction,
        operator_id: str = "OP-PRIMARY",
        reason: Optional[str] = None,
    ) -> Tuple[bool, Optional[SafetyDecision], str]:
        """
        Handles operator confirmation or rejection of a pending YELLOW decision.
        """
        with self._lock:
            if decision_id not in self._pending_confirmations:
                # Check if it was already processed in history to report specific error
                for hist_dec in reversed(self._history):
                    if hist_dec.decision_id == decision_id:
                        if hist_dec.is_confirmed is not None:
                            return False, hist_dec, "Decision has already been resolved (Duplicate confirmation rejected)."
                        if hist_dec.expires_at_ms and time.time() * 1000.0 > hist_dec.expires_at_ms:
                            return False, hist_dec, "Confirmation expired due to timeout."

                return False, None, f"No pending confirmation found for decision ID {decision_id}."

            pending_decision = self._pending_confirmations[decision_id]
            is_confirm = (action == ConfirmationAction.CONFIRM)
            is_latched = self._is_emergency_latched

            success, updated_decision, msg = self.rule_engine.evaluate_confirmation(
                pending_decision=pending_decision,
                action_confirm=is_confirm,
                operator_id=operator_id,
                is_emergency_latched=is_latched,
            )

            # Remove from pending queue
            del self._pending_confirmations[decision_id]

            if success and updated_decision.authorization_decision == AuthorizationDecision.AUTHORIZED:
                # Forward newly confirmed command to simulated gateway
                if updated_decision.authorized_command and updated_decision.auth_token:
                    simulated_gateway.dispatch(
                        updated_decision,
                        updated_decision.authorized_command,
                        updated_decision.auth_token,
                    )

            # Update history record
            for i, h in enumerate(self._history):
                if h.decision_id == decision_id:
                    self._history[i] = updated_decision
                    break

        self._dispatch(updated_decision)
        return success, updated_decision, msg

    def get_status(self) -> SafetyEngineStatus:
        """Returns the current operational status and metrics."""
        with self._lock:
            # Determine current state
            if self._is_emergency_latched:
                active_state = AuthorizationState.EMERGENCY
            elif self._pending_confirmations:
                active_state = AuthorizationState.YELLOW
            elif self._history:
                active_state = self._history[-1].authorization_state
            else:
                active_state = AuthorizationState.GREEN

            last_dec = self._history[-1] if self._history else None

            return SafetyEngineStatus(
                active_state=active_state,
                is_emergency_latched=self._is_emergency_latched,
                emergency_source=self._emergency_source,
                emergency_timestamp_ms=self._emergency_timestamp_ms,
                pending_confirmations_count=len(self._pending_confirmations),
                total_decisions=self._total_decisions,
                total_green=self._total_green,
                total_yellow=self._total_yellow,
                total_red=self._total_red,
                total_emergency=self._total_emergency,
                green_threshold=self.rule_engine.green_threshold,
                yellow_threshold=self.rule_engine.yellow_threshold,
                last_decision=last_dec,
            )

    def get_latest(self) -> Optional[SafetyDecision]:
        """Returns the most recent safety decision."""
        with self._lock:
            return self._history[-1] if self._history else None

    def get_history(self, limit: int = 50) -> List[SafetyDecision]:
        """Returns chronological list of safety decisions, latest first."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_pending_confirmations(self) -> List[SafetyDecision]:
        """Returns all decisions currently awaiting human confirmation."""
        with self._lock:
            now_ms = time.time() * 1000.0
            # Clean up expired holds
            expired_ids = [
                d_id for d_id, dec in self._pending_confirmations.items()
                if dec.expires_at_ms and now_ms > dec.expires_at_ms
            ]
            for d_id in expired_ids:
                dec = self._pending_confirmations.pop(d_id)
                dec.authorization_state = AuthorizationState.RED
                dec.authorization_decision = AuthorizationDecision.REJECTED
                dec.is_confirmed = False
                dec.reason = "Confirmation TIMEOUT expired. Rejected."

            return list(self._pending_confirmations.values())

    def reset_stats(self) -> None:
        """Resets history, buffers, and counters (for testing)."""
        with self._lock:
            self._history.clear()
            self._pending_confirmations.clear()
            self._is_emergency_latched = False
            self._emergency_source = None
            self._emergency_timestamp_ms = None
            self._emergency_reason = None
            self._total_decisions = 0
            self._total_green = 0
            self._total_yellow = 0
            self._total_red = 0
            self._total_emergency = 0
            simulated_gateway.reset()


# Global singleton instance of SafetyManager
safety_manager = SafetyManager()

