"""
Event Synchronization and Correlation Schemas for DCRG Phase 4.
Compliant with DCRG-ARCH-004 and DCRG-ARCH-011 (SynchronizedEventBundle).
"""

from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4
import time
from pydantic import BaseModel, Field, model_validator

from app.modules.voice_engine.schemas import VoiceEvent
from app.modules.actuator_engine.schemas import CommonJoystickEvent


class SynchronizationStatus(str, Enum):
    SYNCHRONIZED = "SYNCHRONIZED"
    VOICE_ONLY = "VOICE_ONLY"
    JOYSTICK_ONLY = "JOYSTICK_ONLY"
    OUT_OF_WINDOW = "OUT_OF_WINDOW"
    DELAYED = "DELAYED"
    STALE = "STALE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    DUPLICATE = "DUPLICATE"


class TimestampMetadata(BaseModel):
    """Detailed temporal metrics differentiating inception time from server arrival."""
    event_time_utc_ms: float = Field(..., description="Inception timestamp in milliseconds UTC")
    reception_time_utc_ms: float = Field(..., description="Server arrival timestamp in milliseconds UTC")
    reception_monotonic_ns: int = Field(..., description="Server monotonic clock snapshot in nanoseconds")
    latency_ms: float = Field(0.0, description="Elapsed duration between event creation and arrival (ms)")
    clock_drift_estimate_ms: float = Field(0.0, description="Estimated clock difference between host and server")
    is_out_of_order: bool = Field(False, description="Flag indicating arrival prior to older timestamps")
    is_delayed: bool = Field(False, description="Flag indicating ingestion latency exceeded delay threshold")


class CorrelatedEvent(BaseModel):
    """
    Standardized Correlated Event structure emitted by Phase 4 Synchronization Engine.
    Compatible with DCRG-ARCH-011 SynchronizedEventBundle specification.
    """
    correlation_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique correlation identifier (UUID)")
    sync_id: Optional[str] = Field(None, description="Compatibility alias for correlation_id")
    correlation_timestamp: float = Field(default_factory=lambda: time.time() * 1000.0, description="UTC timestamp in ms")
    timestamp_ms: Optional[float] = Field(None, description="Compatibility alias for correlation_timestamp")

    # Modality Identifiers & Summaries
    voice_event_id: Optional[str] = Field(None, description="Associated VoiceEvent UUID")
    joystick_event_id: Optional[str] = Field(None, description="Associated CommonJoystickEvent UUID")
    voice_command: Optional[str] = Field(None, description="Recognized voice command primitive (e.g., 'LEFT', 'STOP')")
    joystick_direction: Optional[str] = Field(None, description="Classified joystick direction (e.g., 'RIGHT', 'FORWARD')")
    joystick_intensity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized deflection intensity")

    # Synchronization Metrics
    timestamp_difference_ms: Optional[float] = Field(
        None, description="Absolute temporal divergence |t_voice - t_joystick| in ms"
    )
    temporal_delta_ms: Optional[float] = Field(None, description="Compatibility alias for timestamp_difference_ms")
    synchronization_status: SynchronizationStatus = Field(
        SynchronizationStatus.SYNCHRONIZED, description="Classification of modality pairing"
    )
    voice_available: bool = Field(False, description="Whether a voice event was paired")
    joystick_available: bool = Field(False, description="Whether a joystick event was paired")
    correlation_reason: str = Field("", description="Human-readable justification for the correlation decision")

    # Complete Nested Modality Payloads (Never fabricated if missing)
    voice_event: Optional[VoiceEvent] = Field(None, description="Original voice event contract")
    joystick_event: Optional[CommonJoystickEvent] = Field(None, description="Original joystick event contract")

    # Operational Context Placeholder (for Phase 5/6 alignment)
    context: Dict[str, float] = Field(
        default_factory=lambda: {"current_velocity": 0.0, "nearest_obstacle_m": 5.0},
        description="Environmental state register"
    )

    @model_validator(mode="after")
    def populate_compatibility_aliases(self) -> "CorrelatedEvent":
        if self.sync_id is None:
            self.sync_id = self.correlation_id
        if self.timestamp_ms is None:
            self.timestamp_ms = self.correlation_timestamp
        if self.temporal_delta_ms is None and self.timestamp_difference_ms is not None:
            self.temporal_delta_ms = self.timestamp_difference_ms
        elif self.timestamp_difference_ms is None and self.temporal_delta_ms is not None:
            self.timestamp_difference_ms = self.temporal_delta_ms
        return self


class SyncEngineStatus(BaseModel):
    """Truthful system status of the Event Synchronization and Correlation Subsystem."""
    sync_window_ms: float = Field(default=150.0, description="Configured temporal matching window (ms)")
    max_event_age_ms: float = Field(default=350.0, description="Maximum event buffer retention before staleness (ms)")
    voice_buffer_count: int = Field(default=0, description="Unpartnered voice events currently buffered")
    joystick_buffer_count: int = Field(default=0, description="Unpartnered joystick events currently buffered")
    total_synchronized_count: int = Field(default=0, description="Total successfully synchronized event pairs")
    total_voice_only_count: int = Field(default=0, description="Total isolated voice-only events")
    total_joystick_only_count: int = Field(default=0, description="Total isolated joystick-only events")
    total_out_of_window_count: int = Field(default=0, description="Total events exceeding synchronization window")
    total_delayed_count: int = Field(default=0, description="Total events flagged as delayed")
    total_stale_count: int = Field(default=0, description="Total expired/stale events dropped")
    total_duplicate_count: int = Field(default=0, description="Total duplicate events rejected")
    total_invalid_timestamp_count: int = Field(default=0, description="Total events with corrupted timestamps rejected")
    last_correlation: Optional[CorrelatedEvent] = None
    voice_pipeline_active: bool = Field(default=False)
    joystick_pipeline_active: bool = Field(default=False)


class ConfigureSyncRequest(BaseModel):
    """Runtime configuration request to adjust synchronization thresholds."""
    sync_window_ms: Optional[float] = Field(None, ge=10.0, le=2000.0, description="Matching window in ms")
    max_event_age_ms: Optional[float] = Field(None, ge=50.0, le=5000.0, description="Max buffer lifetime in ms")

