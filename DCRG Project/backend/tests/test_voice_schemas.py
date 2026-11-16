"""
Automated unit tests for Voice Event Contract and Data Schemas (Phase 3).
Verifies Pydantic model validation, backward compatibility, and DCRG-ARCH-011 compliance.
"""

import time
import pytest
from pydantic import ValidationError
from app.modules.voice_engine.schemas import (
    VoiceEvent,
    CanonicalCommand,
    SemanticStatus,
    AudioQuality,
    MicrophoneStatus,
    CANONICAL_DIRECTION_VECTORS,
)


class TestVoiceEventSchema:
    """Verifies fields, defaults, validations, and compatibility aliases."""

    def test_voice_event_defaults_and_aliases(self):
        now = time.time() * 1000.0
        event = VoiceEvent(
            timestamp=now,
            transcript="MOVE FORWARD",
            normalized_transcript="move forward",
            recognized_command=CanonicalCommand.FORWARD,
            recognition_confidence=0.942,
            classification_confidence=0.950,
            semantic_status=SemanticStatus.VALID,
        )

        assert event.source == "voice"
        assert event.timestamp_event_ms == now
        assert event.timestamp_proc_ms == now
        assert event.classified_command == "FORWARD"
        assert event.confidence == 0.942
        assert event.direction_vector == CANONICAL_DIRECTION_VECTORS[CanonicalCommand.FORWARD]
        assert event.is_uncertain is False
        assert event.audio_quality == AudioQuality.GOOD

    def test_voice_event_uncertain_state_enforcement(self):
        """When recognized_command is UNCERTAIN, is_uncertain must be true."""
        event = VoiceEvent(
            transcript="mumbled speech",
            normalized_transcript="mumbled speech",
            recognized_command=CanonicalCommand.UNCERTAIN,
            recognition_confidence=0.40,
            classification_confidence=0.20,
            semantic_status=SemanticStatus.UNCERTAIN,
        )
        assert event.is_uncertain is True
        assert event.semantic_status == SemanticStatus.UNCERTAIN
        assert event.direction_vector == {"x": 0.0, "y": 0.0}

    def test_timestamp_range_validation(self):
        """Historical timestamps prior to year 2024 or absurd future timestamps must fail."""
        with pytest.raises(ValidationError):
            VoiceEvent(
                timestamp=100.0,  # Far past
                recognized_command=CanonicalCommand.STOP,
            )

        with pytest.raises(ValidationError):
            VoiceEvent(
                timestamp=time.time() * 1000.0 + 999999999.0,  # Far future
                recognized_command=CanonicalCommand.STOP,
            )

    def test_confidence_range_validation(self):
        """Confidence outside [0.0, 1.0] must be rejected by Pydantic."""
        with pytest.raises(ValidationError):
            VoiceEvent(
                recognized_command=CanonicalCommand.FORWARD,
                recognition_confidence=1.5,
            )

        with pytest.raises(ValidationError):
            VoiceEvent(
                recognized_command=CanonicalCommand.FORWARD,
                recognition_confidence=-0.1,
            )

