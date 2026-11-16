"""
DCRG Tiered Safety Authorization Engine for Phase 6.
Enforces multi-tier state machine (GREEN, YELLOW, RED, EMERGENCY),
software emergency stop latch, human confirmation workflows,
and simulated command gateway execution.
"""

from app.modules.safety_engine.schemas import (
    AuthorizationDecision,
    AuthorizationState,
    ConfirmationAction,
    ConfirmationRequest,
    EmergencyResetRequest,
    EmergencySource,
    EmergencyStopRequest,
    GatewayExecutionRecord,
    SafetyDecision,
    SafetyEngineStatus,
)
from app.modules.safety_engine.rules import SafetyRuleEngine, generate_auth_token
from app.modules.safety_engine.gateway import SimulatedCommandGateway, simulated_gateway
from app.modules.safety_engine.manager import SafetyManager, safety_manager

__all__ = [
    "AuthorizationDecision",
    "AuthorizationState",
    "ConfirmationAction",
    "ConfirmationRequest",
    "EmergencyResetRequest",
    "EmergencySource",
    "EmergencyStopRequest",
    "GatewayExecutionRecord",
    "SafetyDecision",
    "SafetyEngineStatus",
    "SafetyRuleEngine",
    "generate_auth_token",
    "SimulatedCommandGateway",
    "simulated_gateway",
    "SafetyManager",
    "safety_manager",
]
