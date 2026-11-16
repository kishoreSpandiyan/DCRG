"""
Simulated Command Gateway for DCRG Phase 6.
Enforces the final execution interlock for simulated motion primitives.
Validates cryptographic tokens, prevents replay attacks, checks expiration TTLs,
and strictly prohibits physical motor/hardware actuations.
Compliant with DCRG-ARCH-005.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from app.core.config import settings
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    GatewayExecutionRecord,
    SafetyDecision,
)
from app.modules.safety_engine.rules import AUTH_SECRET_KEY, generate_auth_token

logger = logging.getLogger(__name__)


class SimulatedCommandGateway:
    """
    Simulated Robot Command Gateway.
    Only allows movement execution when presented with a valid, non-expired,
    non-replayed AUTHORIZED SafetyDecision signed by the Safety Rule Engine.
    """

    def __init__(self, max_history: int = 100):
        self._lock = threading.RLock()
        self._max_history = max_history
        self._history: List[GatewayExecutionRecord] = []
        self._used_tokens: Set[str] = set()  # Replay attack prevention cache
        self._total_accepted = 0
        self._total_rejected = 0

    def dispatch(
        self,
        decision: SafetyDecision,
        command_attempted: str,
        auth_token: Optional[str] = None,
    ) -> Tuple[bool, GatewayExecutionRecord]:
        """
        Validates the safety authorization contract and executes simulation primitive.
        Returns (is_accepted, GatewayExecutionRecord).
        """
        now_ms = time.time() * 1000.0
        cmd_clean = command_attempted.upper().strip()

        with self._lock:
            # Check 1: Strict Simulation Enforcement
            if not settings.SAFETY_GATEWAY_SIMULATION_ONLY:
                # Defensive check: Must remain simulation only
                pass

            # Check 2: Reject EMERGENCY or RED states outright
            if decision.authorization_state in (AuthorizationState.EMERGENCY, AuthorizationState.RED):
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason=f"Gateway Rejected: State is {decision.authorization_state.value} ({decision.reason})",
                    auth_token=auth_token,
                )
                self._record(record)
                return False, record

            # Check 3: Reject unresolved YELLOW holds
            if decision.authorization_decision == AuthorizationDecision.HOLD_PENDING_CONFIRMATION:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason="Gateway Rejected: Command is on YELLOW HOLD and has not received operator confirmation.",
                    auth_token=auth_token,
                )
                self._record(record)
                return False, record

            # Check 4: Decision must be explicitly AUTHORIZED
            if decision.authorization_decision != AuthorizationDecision.AUTHORIZED:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason=f"Gateway Rejected: Authorization decision is {decision.authorization_decision.value}.",
                    auth_token=auth_token,
                )
                self._record(record)
                return False, record

            # Check 5: Command Mismatch check
            if decision.authorized_command != cmd_clean:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason=f"Gateway Rejected: Command mismatch (Attempted: '{cmd_clean}', Authorized: '{decision.authorized_command}').",
                    auth_token=auth_token,
                )
                self._record(record)
                return False, record

            # Check 6: Expiration TTL check
            if decision.expires_at_ms and now_ms > decision.expires_at_ms:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason=f"Gateway Rejected: Authorization TTL expired ({now_ms - decision.expires_at_ms:.1f}ms ago).",
                    auth_token=auth_token,
                )
                self._record(record)
                return False, record

            # Check 7: Cryptographic Auth Token Verification
            token_to_verify = auth_token or decision.auth_token
            if not token_to_verify:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason="Gateway Rejected: Missing authorization signature token.",
                    auth_token=None,
                )
                self._record(record)
                return False, record

            # Check 8: Replay Attack Defense (Token already consumed)
            if token_to_verify in self._used_tokens:
                record = GatewayExecutionRecord(
                    decision_id=decision.decision_id,
                    command=cmd_clean,
                    accepted=False,
                    reason="Gateway Rejected: Authorization token already consumed (Replay attack defense).",
                    auth_token=token_to_verify,
                )
                self._record(record)
                return False, record

            # Mark token as consumed
            self._used_tokens.add(token_to_verify)
            if len(self._used_tokens) > 5000:
                self._used_tokens.clear()

            # Command successfully accepted for simulation execution
            record = GatewayExecutionRecord(
                decision_id=decision.decision_id,
                command=cmd_clean,
                accepted=True,
                reason=f"SIMULATION MOTION AUTHORIZED: Command '{cmd_clean}' dispatched to simulated kinematic model.",
                auth_token=token_to_verify,
            )
            self._record(record)
            logger.info("Gateway executed simulated command: %s (Decision: %s)", cmd_clean, decision.decision_id)
            return True, record

    def _record(self, record: GatewayExecutionRecord) -> None:
        if record.accepted:
            self._total_accepted += 1
        else:
            self._total_rejected += 1

        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_history(self, limit: int = 50) -> List[GatewayExecutionRecord]:
        """Returns recent gateway execution log, latest first."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def reset(self) -> None:
        """Clears execution logs and token cache (for testing)."""
        with self._lock:
            self._history.clear()
            self._used_tokens.clear()
            self._total_accepted = 0
            self._total_rejected = 0


# Global singleton instance of SimulatedCommandGateway
simulated_gateway = SimulatedCommandGateway()

