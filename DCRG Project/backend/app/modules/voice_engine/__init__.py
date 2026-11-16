"""
Voice Engine Module (Phase 3).
Coordinates microphone audio ingestion, Faster-Whisper local speech recognition,
Prosody extraction, and Semantic command classification.
"""

from app.modules.voice_engine.schemas import (
    MicrophoneStatus,
    AudioQuality,
    CanonicalCommand,
    SemanticStatus,
    ProsodyMetrics,
    VoiceEvent,
    VoiceSystemStatus,
    CANONICAL_DIRECTION_VECTORS,
)
from app.modules.voice_engine.microphone_service import (
    MicrophoneService,
    microphone_service,
)
from app.modules.voice_engine.whisper_service import (
    WhisperService,
    whisper_service,
    WhisperTranscriptionResult,
)


def __getattr__(name: str):
    if name in ("VoiceManager", "voice_manager"):
        from app.modules.voice_engine.manager import VoiceManager, voice_manager
        if name == "VoiceManager":
            return VoiceManager
        return voice_manager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "MicrophoneStatus",
    "AudioQuality",
    "CanonicalCommand",
    "SemanticStatus",
    "ProsodyMetrics",
    "VoiceEvent",
    "VoiceSystemStatus",
    "CANONICAL_DIRECTION_VECTORS",
    "MicrophoneService",
    "microphone_service",
    "WhisperService",
    "whisper_service",
    "WhisperTranscriptionResult",
    "VoiceManager",
    "voice_manager",
]
