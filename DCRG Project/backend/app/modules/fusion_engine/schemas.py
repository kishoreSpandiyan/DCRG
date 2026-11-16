"""
DCRG Fusion Engine and Command Reliability Score (CRS) Schemas.
Defines data structures, enums, factors, and evaluation contracts for Phase 5.
Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
"""

from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4
import time
from pydantic import BaseModel, Field, model_validator


class CRSStatus(str, Enum):
    """Categorical assessment of input evidence completeness and reliability."""
    COMPLETE = "COMPLETE"        # Both voice and joystick paired within window, context verified
    PROVISIONAL = "PROVISIONAL"  # Valid single-modality or missing context, scored conservatively
    INCOMPLETE = "INCOMPLETE"    # Critical data absent or low confidence across inputs
    INVALID = "INVALID"          # Data corrupted, invalid timestamps, or unparseable payload


class AnalyticalFinding(str, Enum):
    """High-level semantic categorization of the multimodal relationship."""
    AGREEMENT = "AGREEMENT"
    CONTRADICTION = "CONTRADICTION"
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    UNCERTAIN_COMMAND = "UNCERTAIN_COMMAND"
    NEUTRAL_JOYSTICK = "NEUTRAL_JOYSTICK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"
    CONTEXT_VIOLATION = "CONTEXT_VIOLATION"


class FusionFactors(BaseModel):
    """Component reliability factors normalized to [0.0, 1.0]."""
    semantic_score: float = Field(..., ge=0.0, le=1.0, description="Semantic certainty factor S")
    motor_agreement: float = Field(..., ge=0.0, le=1.0, description="Motor agreement factor M")
    context_consistency: float = Field(..., ge=0.0, le=1.0, description="Context consistency factor C")
    angular_delta_deg: Optional[float] = Field(None, description="Angular separation between vectors in degrees")
    cosine_similarity: Optional[float] = Field(None, description="Cosine similarity cos(Delta theta) [-1.0, 1.0]")
    sync_quality: float = Field(1.0, ge=0.0, le=1.0, description="Temporal alignment quality factor Q_sync")


class FusionResult(BaseModel):
    """
    Standardized Fusion Result emitted by the DCRG Fusion Engine.
    Represents multimodal evidence consistency across voice, joystick, and context.
    Compliant with DCRG-ARCH-005 and DCRG-ARCH-011.
    """
    fusion_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique fusion evaluation UUID")
    correlation_id: str = Field(..., description="ID of underlying Phase 4 CorrelatedEvent")
    sync_id: Optional[str] = Field(None, description="Compatibility alias for correlation_id")
    timestamp: float = Field(default_factory=lambda: time.time() * 1000.0, description="Evaluation timestamp in UTC ms")
    timestamp_ms: Optional[float] = Field(None, description="Compatibility alias for timestamp")

    # Command Modality Summaries
    voice_command: Optional[str] = Field(None, description="Recognized voice command primitive")
    joystick_direction: Optional[str] = Field(None, description="Classified joystick direction")
    joystick_intensity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized deflection magnitude")

    # Normalized Component Scores [0.0, 1.0]
    semantic_reliability: float = Field(..., ge=0.0, le=1.0, description="Semantic factor S")
    motor_agreement: float = Field(..., ge=0.0, le=1.0, description="Motor agreement factor M")
    context_consistency: float = Field(..., ge=0.0, le=1.0, description="Context factor C")
    factors: FusionFactors = Field(..., description="Structured factor details")

    # Composite Command Reliability Score [0.0, 100.0]
    CRS: float = Field(..., ge=0.0, le=100.0, description="Scaled Command Reliability Score [0.0 - 100.0]")
    crs_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Compatibility alias for CRS")
    CRS_status: CRSStatus = Field(..., description="Completeness category of the evaluation")

    # Contradiction Veto Filter Interlock
    contradiction_detected: bool = Field(False, description="Flag indicating opposing voice/joystick commands")
    veto_asserted: bool = Field(False, description="Compatibility alias for contradiction_detected")
    contradiction_reason: Optional[str] = Field(None, description="Detailed justification if veto asserted")

    # Quality and Lineage Metrics
    synchronization_status: str = Field(..., description="Phase 4 synchronization classification")
    temporal_delta_ms: Optional[float] = Field(None, description="Temporal delta between inputs in ms")
    evidence_completeness: float = Field(..., ge=0.0, le=1.0, description="Fraction of required evidence present")
    missing_components: List[str] = Field(default_factory=list, description="List of unpartnered/missing modalities")
    scoring_config_version: str = Field("v1.0-prototype", description="Scoring calibration version tag")
    weights: Dict[str, float] = Field(default_factory=dict, description="Factor weights applied during calculation")

    # Explainability & Semantic Reasoning
    explanation: str = Field(..., description="Transparent textual explanation of the CRS score calculation")
    analytical_finding: AnalyticalFinding = Field(..., description="Categorical outcome classification")

    # Transitional recommendation (Non-binding placeholder before Phase 6 Safety Engine)
    recommended_state: Optional[str] = Field(
        None, description="Preliminary guidance indicator: GREEN, YELLOW, or RED"
    )

    @model_validator(mode="after")
    def populate_compatibility_fields(self) -> "FusionResult":
        if self.sync_id is None:
            self.sync_id = self.correlation_id
        if self.timestamp_ms is None:
            self.timestamp_ms = self.timestamp
        if self.crs_score is None:
            self.crs_score = self.CRS
        if self.veto_asserted != self.contradiction_detected:
            self.veto_asserted = self.contradiction_detected
        return self


class FusionConfig(BaseModel):
    """Configurable scoring weights, thresholds, and damping parameters for the Fusion Engine."""
    weight_semantic: float = Field(0.35, ge=0.0, le=1.0, description="Weight W_s for semantic reliability")
    weight_motor: float = Field(0.50, ge=0.0, le=1.0, description="Weight W_m for motor agreement")
    weight_context: float = Field(0.15, ge=0.0, le=1.0, description="Weight W_c for context consistency")
    stress_damping: float = Field(0.25, ge=0.0, le=1.0, description="Stress damping coefficient beta")
    contradiction_cap: float = Field(30.0, ge=0.0, le=100.0, description="Maximum CRS ceiling when contradiction occurs")
    contradiction_whisper_min: float = Field(0.70, ge=0.0, le=1.0, description="Min voice confidence to trigger veto")
    contradiction_joystick_min: float = Field(0.30, ge=0.0, le=1.0, description="Min stick intensity to trigger veto")
    joystick_deadzone: float = Field(0.08, ge=0.0, le=0.5, description="Radial joystick deadzone threshold")
    scoring_config_version: str = Field("v1.0-prototype", description="Calibration tag")

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "FusionConfig":
        total_weight = self.weight_semantic + self.weight_motor + self.weight_context
        if abs(total_weight - 1.0) > 1e-4:
            raise ValueError(
                f"Scoring weights must sum to 1.0: W_s({self.weight_semantic}) + "
                f"W_m({self.weight_motor}) + W_c({self.weight_context}) = {total_weight:.4f}"
            )
        return self


class FusionEngineStatus(BaseModel):
    """Runtime operational status and performance telemetry of the Fusion Engine."""
    is_active: bool = Field(True, description="Whether fusion evaluation is enabled")
    total_evaluations: int = Field(0, description="Cumulative count of events fused")
    total_agreements: int = Field(0, description="Count of evaluations yielding AGREEMENT")
    total_contradictions: int = Field(0, description="Count of evaluations where contradiction veto asserted")
    average_crs: float = Field(0.0, description="Mean CRS across processed events")
    last_crs: Optional[float] = Field(None, description="Most recent evaluated CRS")
    last_status: Optional[CRSStatus] = Field(None, description="Status of most recent evaluation")
    scoring_config_version: str = Field("v1.0-prototype", description="Active calibration profile")
    weights: Dict[str, float] = Field(default_factory=dict, description="Active weight distribution")
