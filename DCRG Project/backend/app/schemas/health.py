"""
Pydantic Schemas for Health & Status Endpoints.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall backend health status", examples=["operational"])
    phase: str = Field(..., description="Active project phase", examples=["Phase 0 - Initialization"])
    version: str = Field(..., description="Software version", examples=["0.1.0"])
    backendConnected: bool = Field(True, description="Backend connection heartbeat")
    hardwareDetected: bool = Field(False, description="Physical hardware presence status")
    activeSafetyState: str = Field("NORMAL", description="Current safety authorization state")
    modulesStaged: Dict[str, str] = Field(
        default_factory=dict,
        description="List of staged modules and their scheduled roadmap phase",
    )
    details: Optional[Dict[str, Any]] = None

