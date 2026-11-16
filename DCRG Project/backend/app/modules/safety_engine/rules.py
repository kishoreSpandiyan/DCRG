"""
Tiered Safety Authorization Rule Engine for DCRG Phase 6.
Enforces deterministic priority order:
1. EMERGENCY (Hardware & Software E-Stop latch)
2. RED (Contradictions, low CRS < 50, disconnects, constraint violations, UNKNOWN)
3. YELLOW (CRS 50-84.9, provisional/unpartnered evidence, UNCERTAIN, requires human confirmation)
4. GREEN (CRS >= 85, complete synchronized evidence, no contradictions, authorized for simulation)
Compliant with DCRG-ARCH-005.
"""

import hashlib
import hmac
import logging
import time
from typing import Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.modules.fusion_engine.schemas import CRSStatus, FusionResult
from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    SafetyDecision,
)
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.voice_engine.manager import voice_manager
from app.modules.context_engine.service import context_service

logger = logging.getLogger(__name__)

# Secret key for generating simulation execution authorization tokens
AUTH_SECRET_KEY = b"DCRG-PHASE6-SAFETY-GATEWAY-SECRET-TOKEN-2026"


def generate_auth_token(decision_id: str, command: str, timestamp_ms: float) -> str:
    """Generates an HMAC-SHA256 signature for authorized simulation commands."""
    payload = f"{decision_id}:{command}:{timestamp_ms:.0f}".encode("utf-8")
    return hmac.new(AUTH_SECRET_KEY, payload, hashlib.sha256).hexdigest()


class SafetyRuleEngine:
    """
    Deterministic safety evaluator enforcing the tiered hierarchy of safety constraints.
    Frontend inputs are never trusted to make authorization decisions.
    """

    def __init__(
        self,
        green_threshold: float = settings.SAFETY_GREEN_THRESHOLD,
        yellow_threshold: float = settings.SAFETY_YELLOW_THRESHOLD,
        confirmation_timeout_ms: float = settings.SAFETY_CONFIRMATION_TIMEOUT_MS,
        auth_token_ttl_ms: float = settings.SAFETY_AUTH_TOKEN_TTL_MS,
    ):
        self.green_threshold = green_threshold
        self.yellow_threshold = yellow_threshold
        self.confirmation_timeout_ms = confirmation_timeout_ms
        self.auth_token_ttl_ms = auth_token_ttl_ms

    def evaluate(
        self,
        fusion_result: Optional[FusionResult],
        is_emergency_latched: bool,
        emergency_source: Optional[str] = None,
    ) -> SafetyDecision:
        """
        Evaluates system evidence against the 4-tier safety state machine.
        Strict Priority: EMERGENCY -> RED -> YELLOW -> GREEN.
        """
        now_ms = time.time() * 1000.0
        decision_id = str(uuid4())

        # ====================================================================
        # PRIORITY 1: EMERGENCY (Immediate lockout & latch)
        # ====================================================================
        if is_emergency_latched:
            src = emergency_source or "SOFTWARE_UI"
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id if fusion_result else None,
                correlation_id=fusion_result.correlation_id if fusion_result else None,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.EMERGENCY,
                authorization_decision=AuthorizationDecision.EMERGENCY_HALT,
                requested_command=fusion_result.voice_command or fusion_result.joystick_direction if fusion_result else None,
                authorized_command=None,
                crs_score=fusion_result.CRS if fusion_result else 0.0,
                crs_status=fusion_result.CRS_status.value if fusion_result else None,
                evidence_completeness=fusion_result.evidence_completeness if fusion_result else 0.0,
                contradiction_detected=fusion_result.contradiction_detected if fusion_result else False,
                reason=f"EMERGENCY STOP ACTIVE ({src}): All motion strictly locked out. Emergency reset required.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=True,
                is_simulation=True,
            )

        # Fail-safe check: Missing fusion evaluation
        if fusion_result is None:
            return SafetyDecision(
                decision_id=decision_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=None,
                authorized_command=None,
                crs_score=0.0,
                crs_status="MISSING",
                evidence_completeness=0.0,
                contradiction_detected=False,
                reason="Fail-safe rejection: No multimodal fusion result available to verify safety.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        requested_cmd = (
            fusion_result.voice_command
            or fusion_result.joystick_direction
            or "STOP"
        ).upper().strip()

        # Check subsystem hardware health
        joy_status = actuator_manager.get_status()
        voice_status = voice_manager.get_status()

        # ====================================================================
        # PRIORITY 2: RED (Rejection due to hazard, contradiction, low CRS, or failure)
        # ====================================================================

        # Rule 2A: Contradiction Veto Filter Interlock (Zero-Override Law)
        if fusion_result.contradiction_detected or fusion_result.veto_asserted:
            reason = fusion_result.contradiction_reason or "Direct contradiction between voice intent and manual control."
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=True,
                reason=f"CONTRADICTION VETO: {reason} Movement prohibited.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # Rule 2B: Unrecognized Voice Command (UNKNOWN)
        if fusion_result.voice_command == "UNKNOWN":
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command="UNKNOWN",
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason="Voice recognition token is UNKNOWN. Unverified command rejected.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # Rule 2C: Hardware Disconnection Fail-Safe
        # Physical hardware disconnected when in hardware mode
        if (
            joy_status.active_mode.value == "REAL_HARDWARE"
            and joy_status.connection_status.value == "DISCONNECTED"
        ):
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason="Fail-safe rejection: Physical joystick device is DISCONNECTED.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        if voice_status.microphone_status.value == "ERROR":
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason=f"Fail-safe rejection: Microphone is in ERROR state.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # Rule 2D: Invalid, Corrupted, or Stale Timestamps
        if fusion_result.CRS_status == CRSStatus.INVALID:
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=0.0,
                contradiction_detected=False,
                reason=f"Data integrity fault: Event synchronization status is {fusion_result.synchronization_status}. Rejected.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # Rule 2E: Operating Context Violation (Obstacle proximity or Mode lock)
        if fusion_result.analytical_finding.value == "CONTEXT_VIOLATION":
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason="Environmental safety boundary violation: Command breaches obstacle buffer or mission mode constraints.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # Rule 2F: Insufficient Overall Reliability (CRS < 50.0)
        if fusion_result.CRS < self.yellow_threshold:
            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.RED,
                authorization_decision=AuthorizationDecision.REJECTED,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason=f"CRS {fusion_result.CRS:.1f} is below actionable minimum safety threshold ({self.yellow_threshold:.1f}). Command rejected.",
                auth_token=None,
                expires_at_ms=None,
                is_latched=False,
                is_simulation=True,
            )

        # ====================================================================
        # PRIORITY 3: YELLOW (Hold pending operator confirmation)
        # ====================================================================
        # Enforced if:
        # 1. CRS between 50.0 and 84.9
        # 2. Evidence is incomplete or provisional (unpartnered voice or joystick, context unverified)
        # 3. Command is marked UNCERTAIN
        is_yellow = (
            fusion_result.CRS < self.green_threshold
            or fusion_result.CRS_status != CRSStatus.COMPLETE
            or fusion_result.evidence_completeness < 1.0
            or fusion_result.voice_command == "UNCERTAIN"
            or fusion_result.analytical_finding.value in ("UNCERTAIN_COMMAND", "NEUTRAL_JOYSTICK", "CONTEXT_UNAVAILABLE")
        )

        if is_yellow:
            conf_id = str(uuid4())
            expires_at = now_ms + self.confirmation_timeout_ms
            reasons = []
            if fusion_result.CRS < self.green_threshold:
                reasons.append(f"CRS {fusion_result.CRS:.1f} requires confirmation (< {self.green_threshold:.1f})")
            if fusion_result.CRS_status != CRSStatus.COMPLETE:
                reasons.append(f"Evidence status is {fusion_result.CRS_status.value}")
            if fusion_result.voice_command == "UNCERTAIN":
                reasons.append("Speech token classified as UNCERTAIN")
            if fusion_result.analytical_finding.value == "NEUTRAL_JOYSTICK":
                reasons.append("Voice commanded movement while joystick remained centered")

            rationale = "; ".join(reasons) if reasons else "Elevated risk profile"

            return SafetyDecision(
                decision_id=decision_id,
                fusion_id=fusion_result.fusion_id,
                correlation_id=fusion_result.correlation_id,
                timestamp_ms=now_ms,
                authorization_state=AuthorizationState.YELLOW,
                authorization_decision=AuthorizationDecision.HOLD_PENDING_CONFIRMATION,
                requested_command=requested_cmd,
                authorized_command=None,
                crs_score=fusion_result.CRS,
                crs_status=fusion_result.CRS_status.value,
                evidence_completeness=fusion_result.evidence_completeness,
                contradiction_detected=False,
                reason=f"COMMAND ON HOLD: {rationale}. Operator confirmation required within {self.confirmation_timeout_ms/1000.0:.0f}s.",
                auth_token=None,
                expires_at_ms=expires_at,
                confirmation_id=conf_id,
                confirmation_timeout_ms=self.confirmation_timeout_ms,
                is_confirmed=None,
                is_latched=False,
                is_simulation=True,
            )

        # ====================================================================
        # PRIORITY 4: GREEN (Fully verified, authorized for simulation)
        # ====================================================================
        # All safety conditions met: CRS >= 85, COMPLETE evidence, synchronized, clear context.
        auth_token = generate_auth_token(decision_id, requested_cmd, now_ms)
        expires_at = now_ms + self.auth_token_ttl_ms

        return SafetyDecision(
            decision_id=decision_id,
            fusion_id=fusion_result.fusion_id,
            correlation_id=fusion_result.correlation_id,
            timestamp_ms=now_ms,
            authorization_state=AuthorizationState.GREEN,
            authorization_decision=AuthorizationDecision.AUTHORIZED,
            requested_command=requested_cmd,
            authorized_command=requested_cmd,
            crs_score=fusion_result.CRS,
            crs_status=fusion_result.CRS_status.value,
            evidence_completeness=fusion_result.evidence_completeness,
            contradiction_detected=False,
            reason=f"Command '{requested_cmd}' fully verified (CRS={fusion_result.CRS:.1f}/100, Complete Evidence, Sync OK). Simulation authorized.",
            auth_token=auth_token,
            expires_at_ms=expires_at,
            is_latched=False,
            is_simulation=True,
        )

    def evaluate_confirmation(
        self,
        pending_decision: SafetyDecision,
        action_confirm: bool,
        operator_id: str,
        is_emergency_latched: bool,
    ) -> Tuple[bool, SafetyDecision, str]:
        """
        Re-evaluates safety conditions and validates confirmation request.
        Protects against replay, timeouts, and environmental hazards arising during the hold.
        """
        now_ms = time.time() * 1000.0

        # Check 1: Must be in HOLD_PENDING_CONFIRMATION
        if pending_decision.authorization_decision != AuthorizationDecision.HOLD_PENDING_CONFIRMATION:
            return False, pending_decision, f"Decision {pending_decision.decision_id} is not in HOLD state."

        # Check 2: Timeout expiration check
        if pending_decision.expires_at_ms and now_ms > pending_decision.expires_at_ms:
            pending_decision.authorization_state = AuthorizationState.RED
            pending_decision.authorization_decision = AuthorizationDecision.REJECTED
            pending_decision.is_confirmed = False
            pending_decision.confirmed_by = operator_id
            pending_decision.reason = "Confirmation TIMEOUT expired. Command rejected."
            return False, pending_decision, "Confirmation timed out."

        # Check 3: Operator rejected command
        if not action_confirm:
            pending_decision.authorization_state = AuthorizationState.RED
            pending_decision.authorization_decision = AuthorizationDecision.REJECTED
            pending_decision.is_confirmed = False
            pending_decision.confirmed_by = operator_id
            pending_decision.reason = f"Command explicitly rejected by operator {operator_id}."
            return True, pending_decision, "Command rejected by operator."

        # Check 4: Dynamic safety re-evaluation before granting confirmation
        # A. Emergency stop engaged while waiting
        if is_emergency_latched:
            pending_decision.authorization_state = AuthorizationState.EMERGENCY
            pending_decision.authorization_decision = AuthorizationDecision.EMERGENCY_HALT
            pending_decision.is_confirmed = False
            pending_decision.confirmed_by = operator_id
            pending_decision.is_latched = True
            pending_decision.reason = "Emergency Stop engaged during confirmation. Authorization refused."
            return False, pending_decision, "Emergency Stop engaged."

        # B. Re-check context obstacles
        ctx = context_service.get_state()
        if ctx.operating_mode == "EMERGENCY_STOP":
            pending_decision.authorization_state = AuthorizationState.RED
            pending_decision.authorization_decision = AuthorizationDecision.REJECTED
            pending_decision.is_confirmed = False
            pending_decision.reason = "Context entered EMERGENCY_STOP mode. Confirmation refused."
            return False, pending_decision, "Context safety violation."

        # Check 5: Authorize confirmed command
        cmd = pending_decision.requested_command or "STOP"
        token = generate_auth_token(pending_decision.decision_id, cmd, now_ms)
        pending_decision.authorization_state = AuthorizationState.GREEN
        pending_decision.authorization_decision = AuthorizationDecision.AUTHORIZED
        pending_decision.authorized_command = cmd
        pending_decision.auth_token = token
        pending_decision.expires_at_ms = now_ms + self.auth_token_ttl_ms
        pending_decision.is_confirmed = True
        pending_decision.confirmed_by = operator_id
        pending_decision.reason = f"Command '{cmd}' confirmed by operator {operator_id} (CRS={pending_decision.crs_score:.1f}). Simulation authorized."

        return True, pending_decision, "Command successfully confirmed and authorized."
