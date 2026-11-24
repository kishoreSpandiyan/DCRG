"""
Tiered Safety Authorization Engine Schemas for DCRG Phase 6.
Defines authorization states, decision contracts, confirmation requests,
emergency stop payloads, and simulated command gateway records.
Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
"""

from enum import Enum
from typing import List, Optional
from uuid import uuid4
import time
from pydantic import BaseModel, Field


class AuthorizationState(str, Enum):
    """Categorical Tiered Safety States."""
    GREEN = "GREEN"          # Fully verified, authorized for simulation execution
    YELLOW = "YELLOW"        # Tentative/provisional, held pending human confirmation
    RED = "RED"              # Hazardous/contradictory/invalid, strictly rejected
    EMERGENCY = "EMERGENCY"  # Emergency stop active, immediate halt and command lockout


class AuthorizationDecision(str, Enum):
    """Actionable decision classification for downstream dispatch."""
    AUTHORIZED = "AUTHORIZED"
    HOLD_PENDING_CONFIRMATION = "HOLD_PENDING_CONFIRMATION"
    REJECTED = "REJECTED"
    EMERGENCY_HALT = "EMERGENCY_HALT"


class ConfirmationAction(str, Enum):
    """Operator action on a YELLOW pending confirmation."""
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"


class EmergencySource(str, Enum):
    """Origin of an Emergency Stop trigger."""
    SOFTWARE_UI = "SOFTWARE_UI"
    HARDWARE_BUTTON = "HARDWARE_BUTTON"
    SYSTEM_INTERRUPT = "SYSTEM_INTERRUPT"
    KEYWORD_SPOTTER = "KEYWORD_SPOTTER"
    VOICE_COMMAND = "VOICE_COMMAND"


class SafetyDecision(BaseModel):
    """
    Authoritative safety decision contract emitted by the Safety Engine.
    Downstream gateways and simulation endpoints ONLY execute commands
    accompanied by an AUTHORIZED SafetyDecision with a valid auth_token.
    """
    decision_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique decision UUID")
    fusion_id: Optional[str] = Field(None, description="Source Phase 5 FusionResult UUID")
    correlation_id: Optional[str] = Field(None, description="Source Phase 4 CorrelatedEvent UUID")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000.0, description="Decision UTC timestamp")
    
    authorization_state: AuthorizationState = Field(..., description="Tiered state: GREEN, YELLOW, RED, EMERGENCY")
    authorization_decision: AuthorizationDecision = Field(..., description="Actionable outcome")
    
    requested_command: Optional[str] = Field(None, description="Original requested motion primitive")
    authorized_command: Optional[str] = Field(None, description="Permitted motion primitive (null if not authorized)")
    
    crs_score: Optional[float] = Field(None, description="Command Reliability Score [0.0 - 100.0]")
    crs_status: Optional[str] = Field(None, description="Completeness category of the underlying CRS")
    evidence_completeness: float = Field(0.0, ge=0.0, le=1.0, description="Evidence completeness metric")
    contradiction_detected: bool = Field(False, description="Flag indicating multimodal contradiction")
    
    reason: str = Field(..., description="Human-readable safety justification")
    auth_token: Optional[str] = Field(None, description="Cryptographic execution token for authorized commands")
    expires_at_ms: Optional[float] = Field(None, description="Expiration timestamp for command execution (TTL)")
    
    # Confirmation Workflow Attributes (For YELLOW state)
    confirmation_id: Optional[str] = Field(None, description="Pending confirmation identifier")
    confirmation_timeout_ms: Optional[float] = Field(None, description="Time remaining for operator confirmation")
    is_confirmed: Optional[bool] = Field(None, description="Whether confirmation was granted or denied")
    confirmed_by: Optional[str] = Field(None, description="Operator ID who resolved the confirmation")
    
    is_latched: bool = Field(False, description="Whether system is latched in EMERGENCY state")
    is_simulation: bool = Field(True, description="Strict enforcement: simulation only")


class ConfirmationRequest(BaseModel):
    """Payload to confirm or reject a pending YELLOW command decision."""
    decision_id: str = Field(..., description="UUID of the decision on HOLD")
    action: ConfirmationAction = Field(..., description="CONFIRM or REJECT")
    operator_id: str = Field("OP-PRIMARY", description="Identity of operator performing action")
    reason: Optional[str] = Field(None, description="Optional justification for audit log")


class EmergencyStopRequest(BaseModel):
    """Payload to activate an Emergency Stop."""
    source: EmergencySource = Field(EmergencySource.SOFTWARE_UI, description="E-Stop ingress source")
    reason: str = Field("Manual emergency stop triggered by operator", description="Reason for activation")
    operator_id: str = Field("OP-PRIMARY", description="Operator identity")


class EmergencyResetRequest(BaseModel):
    """Payload to authorize reset and unlatch an Emergency Stop."""
    reset_pin: str = Field(..., description="Authorization credential for resetting E-Stop")
    operator_id: str = Field("OP-PRIMARY", description="Operator identity")
    reason: str = Field("Operator authorized safety reset", description="Audit explanation")


class SafetyEngineStatus(BaseModel):
    """Comprehensive runtime telemetry for the Safety Authorization Engine."""
    active_state: AuthorizationState = Field(AuthorizationState.GREEN, description="Current global safety state")
    is_emergency_latched: bool = Field(False, description="True if Emergency Stop is currently latched")
    emergency_source: Optional[EmergencySource] = Field(None, description="Origin of active emergency trigger")
    emergency_timestamp_ms: Optional[float] = Field(None, description="Timestamp when E-Stop was engaged")
    pending_confirmations_count: int = Field(0, description="Number of decisions currently on YELLOW hold")
    total_decisions: int = Field(0, description="Cumulative count of evaluated decisions")
    total_green: int = Field(0, description="Total GREEN authorizations")
    total_yellow: int = Field(0, description="Total YELLOW holds")
    total_red: int = Field(0, description="Total RED rejections")
    total_emergency: int = Field(0, description="Total EMERGENCY halts")
    green_threshold: float = Field(85.0, description="Configured CRS threshold for GREEN")
    yellow_threshold: float = Field(50.0, description="Configured CRS threshold for YELLOW")
    last_decision: Optional[SafetyDecision] = Field(None, description="Most recent SafetyDecision")


class GatewayExecutionRecord(BaseModel):
    """Audit log entry for a simulated command received by the Command Gateway."""
    execution_id: str = Field(default_factory=lambda: str(uuid4()), description="Gateway execution UUID")
    decision_id: str = Field(..., description="Safety decision UUID")
    command: str = Field(..., description="Motion command attempted")
    accepted: bool = Field(..., description="Whether gateway accepted or rejected the command")
    timestamp_ms: float = Field(default_factory=lambda: time.time() * 1000.0, description="Execution timestamp")
    reason: str = Field(..., description="Gateway validation result or rejection rationale")
    auth_token: Optional[str] = Field(None, description="Authorization token verified")

