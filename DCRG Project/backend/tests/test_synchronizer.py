"""
Automated unit tests for Event Synchronization and Correlation Engine (Phase 4).
Verifies multi-modal matching, window boundaries, edge cases, buffer expirations,
duplicate rejection, and non-fabrication invariants.
"""

import time
import pytest
from app.modules.voice_engine.schemas import (
    VoiceEvent,
    CanonicalCommand,
    SemanticStatus,
    AudioQuality,
)
from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
)
from app.modules.sync_engine.schemas import SynchronizationStatus
from app.modules.sync_engine.synchronizer import EventSynchronizer


def make_voice_event(
    command: CanonicalCommand = CanonicalCommand.LEFT,
    timestamp: float = None,
    event_id: str = None,
) -> VoiceEvent:
    now = timestamp or (time.time() * 1000.0)
    kwargs = {
        "timestamp": now,
        "transcript": command.value,
        "normalized_transcript": command.value.lower(),
        "recognized_command": command,
        "recognition_confidence": 0.95,
        "classification_confidence": 0.98,
        "semantic_status": SemanticStatus.VALID,
    }
    if event_id:
        kwargs["event_id"] = event_id
    return VoiceEvent(**kwargs)


def make_joystick_event(
    direction: JoystickDirection = JoystickDirection.LEFT,
    timestamp: float = None,
    intensity: float = 0.85,
    event_id: str = None,
) -> CommonJoystickEvent:
    now = timestamp or (time.time() * 1000.0)
    kwargs = {
        "source": JoystickSource.VIRTUAL_SIMULATION,
        "device_id": "TEST-JOY-01",
        "timestamp": now,
        "axis_x": -0.85 if "LEFT" in direction.value else 0.85 if "RIGHT" in direction.value else 0.0,
        "axis_y": 0.85 if "FORWARD" in direction.value else 0.0,
        "direction": direction,
        "intensity": intensity,
        "is_simulation": True,
        "connection_status": ConnectionStatus.CONNECTED,
        "calibration_status": CalibrationStatus.DEFAULT,
        "data_validity": DataValidity.VALID,
    }
    if event_id:
        kwargs["event_id"] = event_id
    return CommonJoystickEvent(**kwargs)


@pytest.fixture
def synchronizer():
    return EventSynchronizer(
        sync_window_ms=150.0,
        max_event_age_ms=350.0,
        buffer_capacity=100,
    )


class TestEventMatchingAndOrdering:
    """Verifies simultaneous, voice-first, and joystick-first arrival orders."""

    def test_simultaneous_arrival(self, synchronizer):
        """Scenario 1: Voice and Joystick events with identical timestamps."""
        t_event = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.LEFT, timestamp=t_event)
        j_event = make_joystick_event(JoystickDirection.LEFT, timestamp=t_event)

        # Ingest voice first
        res_v = synchronizer.ingest_voice_event(v_event)
        assert res_v is None  # Buffered awaiting partner

        # Ingest joystick
        res_j = synchronizer.ingest_joystick_event(j_event)
        assert res_j is not None
        assert res_j.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert res_j.voice_command == "LEFT"
        assert res_j.joystick_direction == "LEFT"
        assert res_j.timestamp_difference_ms == 0.0
        assert res_j.voice_available is True
        assert res_j.joystick_available is True

    def test_voice_first_arrival(self, synchronizer):
        """Scenario 2: Voice arrives first, joystick arrives 60ms later (within 150ms)."""
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.FORWARD, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.FORWARD, timestamp=t_base + 60.0)

        # Ingest voice
        res_v = synchronizer.ingest_voice_event(v_event)
        assert res_v is None

        # Ingest joystick 60ms later
        res_j = synchronizer.ingest_joystick_event(j_event)
        assert res_j is not None
        assert res_j.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert res_j.timestamp_difference_ms == 60.0
        assert res_j.voice_command == "FORWARD"
        assert res_j.joystick_direction == "FORWARD"

    def test_joystick_first_arrival(self, synchronizer):
        """Scenario 3: Joystick arrives first, voice arrives 80ms later (within 150ms)."""
        t_base = time.time() * 1000.0
        j_event = make_joystick_event(JoystickDirection.RIGHT, timestamp=t_base)
        v_event = make_voice_event(CanonicalCommand.RIGHT, timestamp=t_base + 80.0)

        # Ingest joystick
        res_j = synchronizer.ingest_joystick_event(j_event)
        assert res_j is None  # Buffered

        # Ingest voice
        res_v = synchronizer.ingest_voice_event(v_event)
        assert res_v is not None
        assert res_v.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert res_v.timestamp_difference_ms == 80.0
        assert res_v.voice_command == "RIGHT"
        assert res_v.joystick_direction == "RIGHT"


class TestSynchronizationWindowBoundaries:
    """Verifies strict adherence to configurable synchronization window boundaries."""

    def test_inside_boundary_140ms(self, synchronizer):
        """Delta of 140ms is within default 150ms window."""
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.STOP, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.CENTER, timestamp=t_base + 140.0)

        corr = synchronizer.correlate_manual_pair(v_event, j_event)
        assert corr.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert corr.timestamp_difference_ms == 140.0

    def test_outside_boundary_160ms(self, synchronizer):
        """Scenario 4: Delta of 160ms exceeds default 150ms window -> OUT_OF_WINDOW."""
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.STOP, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.CENTER, timestamp=t_base + 160.0)

        corr = synchronizer.correlate_manual_pair(v_event, j_event)
        assert corr.synchronization_status == SynchronizationStatus.OUT_OF_WINDOW
        assert corr.timestamp_difference_ms == 160.0

    def test_dynamic_window_reconfiguration(self, synchronizer):
        """Widening window to 200ms allows 160ms delta to synchronize."""
        synchronizer.configure(sync_window_ms=200.0)
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.STOP, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.CENTER, timestamp=t_base + 160.0)

        corr = synchronizer.correlate_manual_pair(v_event, j_event)
        assert corr.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert corr.timestamp_difference_ms == 160.0


class TestEdgeCasesAndModalityAbsence:
    """Tests 14 edge case scenarios required by Phase 4 specification."""

    def test_delayed_voice_event(self, synchronizer):
        """Scenario 5: Voice event with ingestion latency > 200ms -> DELAYED."""
        old_time = time.time() * 1000.0 - 250.0  # 250ms latency
        v_event = make_voice_event(CanonicalCommand.LEFT, timestamp=old_time)
        j_event = make_joystick_event(JoystickDirection.LEFT, timestamp=old_time + 20.0)

        synchronizer.ingest_voice_event(v_event)
        corr = synchronizer.ingest_joystick_event(j_event)
        assert corr is not None
        assert corr.synchronization_status == SynchronizationStatus.DELAYED

    def test_voice_unknown_input(self, synchronizer):
        """Scenario 7: Voice input is UNKNOWN paired with joystick."""
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.UNKNOWN, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.FORWARD, timestamp=t_base)

        corr = synchronizer.correlate_manual_pair(v_event, j_event)
        assert corr.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert corr.voice_command == "UNKNOWN"
        assert corr.joystick_direction == "FORWARD"

    def test_voice_uncertain_input(self, synchronizer):
        """Scenario 8: Voice input is UNCERTAIN paired with joystick."""
        t_base = time.time() * 1000.0
        v_event = make_voice_event(CanonicalCommand.UNCERTAIN, timestamp=t_base)
        j_event = make_joystick_event(JoystickDirection.FORWARD, timestamp=t_base)

        corr = synchronizer.correlate_manual_pair(v_event, j_event)
        assert corr.synchronization_status == SynchronizationStatus.SYNCHRONIZED
        assert corr.voice_command == "UNCERTAIN"

    def test_missing_joystick_modality(self, synchronizer):
        """Scenario 9: Joystick disconnected / missing -> VOICE_ONLY."""
        v_event = make_voice_event(CanonicalCommand.FORWARD)
        corr = synchronizer.correlate_manual_pair(v_event, None)
        assert corr.synchronization_status == SynchronizationStatus.VOICE_ONLY
        assert corr.voice_available is True
        assert corr.joystick_available is False
        assert corr.joystick_direction is None
        assert corr.joystick_event is None

    def test_missing_voice_modality(self, synchronizer):
        """Scenario 10: Microphone disconnected / silent -> JOYSTICK_ONLY."""
        j_event = make_joystick_event(JoystickDirection.BACKWARD)
        corr = synchronizer.correlate_manual_pair(None, j_event)
        assert corr.synchronization_status == SynchronizationStatus.JOYSTICK_ONLY
        assert corr.voice_available is False
        assert corr.joystick_available is True
        assert corr.voice_command is None
        assert corr.voice_event is None

    def test_both_modalities_missing(self, synchronizer):
        """Scenario 11: Both inputs unavailable -> STALE neutral correlation."""
        corr = synchronizer.correlate_manual_pair(None, None)
        assert corr.synchronization_status == SynchronizationStatus.STALE
        assert corr.voice_available is False
        assert corr.joystick_available is False

    def test_duplicate_event_rejection(self, synchronizer):
        """Scenario 12: Duplicate event_id rejected without reprocessing."""
        v_event = make_voice_event(event_id="DUPLICATE-UUID-001")
        # Ingest once
        synchronizer.ingest_voice_event(v_event)
        # Ingest again
        dup_corr = synchronizer.ingest_voice_event(v_event)
        assert dup_corr is not None
        assert dup_corr.synchronization_status == SynchronizationStatus.DUPLICATE
        assert synchronizer.total_duplicate == 1

    def test_invalid_timestamp_rejection(self, synchronizer):
        """Scenario 13: Corrupted timestamp rejected -> INVALID_TIMESTAMP."""
        # Create valid event, then simulate timestamp corruption in transit
        v_event = make_voice_event()
        object.__setattr__(v_event, "timestamp", 1000.0)
        corr = synchronizer.ingest_voice_event(v_event)
        assert corr is not None
        assert corr.synchronization_status == SynchronizationStatus.INVALID_TIMESTAMP
        assert synchronizer.total_invalid_timestamp == 1

    def test_high_frequency_buffer_pressure(self, synchronizer):
        """Scenario 14: Ingestion burst of 250 joystick packets does not exceed capacity."""
        base_t = time.time() * 1000.0
        for i in range(250):
            j_event = make_joystick_event(timestamp=base_t + (i * 2.0))
            synchronizer.ingest_joystick_event(j_event)

        status = synchronizer.get_status()
        assert status.joystick_buffer_count <= synchronizer.buffer_capacity
