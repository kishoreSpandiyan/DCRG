"""
Standardized Voice Event Contracts, Enums, and Schemas for DCRG Phase 3.
Compliant with DCRG-ARCH-002 and DCRG-ARCH-011.
"""

from enum import Enum
from typing import Dict, Literal, Optional
from uuid import uuid4
import time
from pydantic import BaseModel, Field, field_validator, model_validator


class MicrophoneStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    MUTED = "MUTED"
    ERROR = "ERROR"


class AudioQuality(str, Enum):
    GOOD = "GOOD"
    NOISY = "NOISY"
    DEGRADED = "DEGRADED"
    SILENCE = "SILENCE"


class CanonicalCommand(str, Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    STOP = "STOP"
    UNKNOWN = "UNKNOWN"
    UNCERTAIN = "UNCERTAIN"


class SemanticStatus(str, Enum):
    VALID = "VALID"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


# Direction vectors corresponding to canonical commands (per DCRG-ARCH-002)
CANONICAL_DIRECTION_VECTORS: Dict[CanonicalCommand, Dict[str, float]] = {
    CanonicalCommand.FORWARD: {"x": 0.0, "y": 1.0},
    CanonicalCommand.BACKWARD: {"x": 0.0, "y": -1.0},
    CanonicalCommand.LEFT: {"x": -1.0, "y": 0.0},
    CanonicalCommand.RIGHT: {"x": 1.0, "y": 0.0},
    CanonicalCommand.STOP: {"x": 0.0, "y": 0.0},
    CanonicalCommand.UNKNOWN: {"x": 0.0, "y": 0.0},
    CanonicalCommand.UNCERTAIN: {"x": 0.0, "y": 0.0},
}


class ProsodyMetrics(BaseModel):
    """Acoustic prosody and stress feature set extracted from speech audio."""
    pitch_f0: float = Field(0.0, ge=0.0, le=1000.0, description="Mean fundamental frequency in Hz")
    pitch_f0_std: float = Field(0.0, ge=0.0, description="Standard deviation of fundamental frequency")
    jitter: float = Field(0.0, ge=0.0, le=1.0, description="Local pitch period perturbation (relative jitter)")
    shimmer: float = Field(0.0, ge=0.0, le=1.0, description="Local amplitude perturbation (relative shimmer)")
    speech_rate: float = Field(0.0, ge=0.0, description="Estimated speech tempo in syllables/second")
    intensity: float = Field(0.0, ge=0.0, le=1.0, description="Normalized RMS voice intensity/loudness [0.0, 1.0]")
    intensity_db: float = Field(-96.0, description="Audio intensity in dBFS")
    composite_stress_score: float = Field(0.0, ge=0.0, le=1.0, description="Normalized cognitive stress metric [0.0, 1.0]")
    is_stressed: bool = Field(False, description="Flag indicating acoustic stress above threshold")
    audio_quality: AudioQuality = Field(AudioQuality.GOOD, description="Audio quality classification")


class VoiceEvent(BaseModel):
    """
    Standardized Voice Event Contract consumed by DCRG Fusion & Safety layers.
    Enforces strict typing, confidence gating, and compatibility with DCRG-ARCH-011.
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event identifier (UUID)")
    timestamp: float = Field(default_factory=lambda: time.time() * 1000.0, description="Event Unix timestamp in milliseconds")
    timestamp_event_ms: Optional[float] = Field(None, description="Compatibility alias for timestamp")
    timestamp_proc_ms: Optional[float] = Field(None, description="Processing timestamp in milliseconds")
    source: Literal["voice"] = Field("voice", description="Ingress modality identifier")
    operator_id: str = Field("OP-PRIMARY", description="Operator identity identifier")
    
    # Speech Recognition & Transcript
    transcript: str = Field("", description="Raw recognized speech transcript")
    normalized_transcript: str = Field("", description="Normalized clean transcript")
    recognized_command: CanonicalCommand = Field(CanonicalCommand.UNKNOWN, description="Canonical motion or safety primitive")
    classified_command: Optional[str] = Field(None, description="Compatibility alias for recognized_command string")
    recognition_confidence: float = Field(0.0, ge=0.0, le=1.0, description="STT acoustic/decoder confidence [0.0, 1.0]")
    classification_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Semantic classification confidence [0.0, 1.0]")
    confidence: Optional[float] = Field(None, description="Compatibility alias for recognition_confidence")
    semantic_status: SemanticStatus = Field(SemanticStatus.UNKNOWN, description="Semantic classification state")
    is_uncertain: bool = Field(False, description="Flag indicating speech ambiguity or low confidence")
    direction_vector: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0},
        description="2D unit displacement vector (x, y) for the command"
    )
    audio_duration_ms: float = Field(0.0, ge=0.0, description="Duration of processed audio segment in ms")

    # Prosody & Acoustic Metrics
    pitch_f0: float = Field(0.0, ge=0.0, description="Mean fundamental frequency in Hz")
    pitch_f0_std: float = Field(0.0, ge=0.0, description="Pitch standard deviation")
    jitter: float = Field(0.0, ge=0.0, description="Local jitter perturbation")
    shimmer: float = Field(0.0, ge=0.0, description="Local shimmer perturbation")
    speech_rate: float = Field(0.0, ge=0.0, description="Estimated speech rate in syllables/second")
    intensity: float = Field(0.0, ge=0.0, le=1.0, description="Normalized RMS acoustic intensity")
    audio_quality: AudioQuality = Field(AudioQuality.GOOD, description="Audio quality rating")
    model_version: str = Field("faster-whisper-tiny.en", description="Speech model identifier")
    composite_stress_score: float = Field(0.0, ge=0.0, le=1.0, description="Synthesized cognitive stress score")
    stress_score: Optional[float] = Field(None, description="Compatibility alias for composite_stress_score")
    is_stressed: bool = Field(False, description="Stress threshold flag")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: float) -> float:
        now_ms = time.time() * 1000.0
        if v < 1700000000000.0 or v > (now_ms + 600000.0):
            raise ValueError(f"Timestamp {v} is outside valid chronological bounds")
        return v

    @model_validator(mode="after")
    def populate_compatibility_fields(self) -> "VoiceEvent":
        if self.timestamp_event_ms is None:
            self.timestamp_event_ms = self.timestamp
        if self.timestamp_proc_ms is None:
            self.timestamp_proc_ms = self.timestamp
        if self.classified_command is None:
            self.classified_command = self.recognized_command.value
        if self.confidence is None:
            self.confidence = self.recognition_confidence
        if self.stress_score is None:
            self.stress_score = self.composite_stress_score
        
        # Ensure direction vector matches canonical command if unset
        if not self.direction_vector or (self.direction_vector.get("x") == 0.0 and self.direction_vector.get("y") == 0.0):
            self.direction_vector = CANONICAL_DIRECTION_VECTORS.get(
                self.recognized_command, {"x": 0.0, "y": 0.0}
            )

        # Safety Guardrail: If recognized command is UNCERTAIN or UNKNOWN, is_uncertain must be true or status updated
        if self.recognized_command in (CanonicalCommand.UNCERTAIN, CanonicalCommand.UNKNOWN):
            if self.recognized_command == CanonicalCommand.UNCERTAIN:
                self.is_uncertain = True
                self.semantic_status = SemanticStatus.UNCERTAIN
            elif self.semantic_status not in (SemanticStatus.UNKNOWN, SemanticStatus.REJECTED):
                self.semantic_status = SemanticStatus.UNKNOWN

        return self


class VoiceSystemStatus(BaseModel):
    """System-level voice recognition and prosody subsystem status."""
    microphone_status: MicrophoneStatus = Field(default=MicrophoneStatus.DISCONNECTED)
    is_capturing: bool = Field(default=False)
    is_muted: bool = Field(default=False)
    selected_device_index: Optional[int] = None
    selected_device_name: Optional[str] = None
    model_name: str = Field(default="tiny.en")
    model_loaded: bool = Field(default=False)
    language: str = Field(default="en")
    sample_rate: int = Field(default=16000)
    last_event: Optional[VoiceEvent] = None
    error_message: Optional[str] = None

