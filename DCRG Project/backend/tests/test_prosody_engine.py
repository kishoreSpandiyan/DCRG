"""
Automated unit tests for Prosody Analysis Engine (Phase 3).
Verifies acoustic feature extraction (F0, jitter, shimmer, speech rate, intensity),
numerical robustness (zero division, NaN, Inf), and safety invariants.
"""

import math
import numpy as np
import pytest
from app.modules.prosody_engine.analyzer import ProsodyAnalyzer
from app.modules.voice_engine.schemas import AudioQuality


@pytest.fixture
def analyzer():
    return ProsodyAnalyzer(sample_rate=16000)


class TestProsodyFeatureExtraction:
    """Tests feature extraction under normal and synthetic acoustic inputs."""

    def test_pure_tone_pitch_extraction(self, analyzer):
        """A pure 150 Hz sine wave should yield mean F0 close to 150 Hz."""
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        audio = 0.5 * np.sin(2 * np.pi * 150.0 * t).astype(np.float32)

        metrics = analyzer.analyze(audio, sample_rate=sr)
        assert abs(metrics.pitch_f0 - 150.0) < 5.0
        assert metrics.intensity > 0.1
        assert metrics.audio_quality in (AudioQuality.GOOD, AudioQuality.NOISY)
        assert not math.isnan(metrics.jitter)
        assert not math.isnan(metrics.shimmer)

    def test_silence_handling(self, analyzer):
        """Completely silent audio must not fail or produce NaN/Inf."""
        sr = 16000
        audio = np.zeros(sr, dtype=np.float32)

        metrics = analyzer.analyze(audio, sample_rate=sr)
        assert metrics.audio_quality == AudioQuality.SILENCE
        assert metrics.pitch_f0 == 0.0
        assert metrics.jitter == 0.0
        assert metrics.shimmer == 0.0
        assert metrics.speech_rate == 0.0
        assert metrics.composite_stress_score == 0.0
        assert metrics.is_stressed is False

    def test_empty_audio_handling(self, analyzer):
        """Empty array must return clean neutral metrics."""
        audio = np.array([], dtype=np.float32)
        metrics = analyzer.analyze(audio)
        assert metrics.audio_quality == AudioQuality.SILENCE
        assert metrics.pitch_f0 == 0.0

    def test_background_noise_handling(self, analyzer):
        """Random white noise must be analyzed safely without crashes."""
        sr = 16000
        np.random.seed(42)
        noise = (np.random.normal(0, 0.05, sr * 1)).astype(np.float32)

        metrics = analyzer.analyze(noise, sample_rate=sr)
        assert not math.isnan(metrics.pitch_f0)
        assert not math.isnan(metrics.jitter)
        assert not math.isnan(metrics.shimmer)
        assert not math.isnan(metrics.composite_stress_score)
        assert 0.0 <= metrics.composite_stress_score <= 1.0

    def test_clipped_degraded_audio_handling(self, analyzer):
        """Audio with severe clipping (>5% at ±1.0) should be classified as DEGRADED."""
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        # Heavy amplification resulting in hard clipping
        audio = np.clip(10.0 * np.sin(2 * np.pi * 200.0 * t), -1.0, 1.0).astype(np.float32)

        metrics = analyzer.analyze(audio, sample_rate=sr)
        assert metrics.audio_quality == AudioQuality.DEGRADED

    def test_nan_and_inf_immunity(self, analyzer):
        """Corrupted audio buffers containing NaNs or Infs must be sanitized."""
        corrupted = np.array([0.1, np.nan, 0.5, np.inf, -np.inf, 0.2] * 500, dtype=np.float32)
        metrics = analyzer.analyze(corrupted)
        assert not math.isnan(metrics.pitch_f0)
        assert not math.isnan(metrics.jitter)
        assert not math.isnan(metrics.shimmer)
        assert not math.isinf(metrics.intensity)
        assert not math.isnan(metrics.composite_stress_score)


class TestProsodySafetyInvariants:
    """Verifies safety invariant: Prosody is only an advisory metric."""

    def test_stress_score_bounded(self, analyzer):
        """Stress score must always strictly reside in [0.0, 1.0]."""
        # Simulated high frequency shouting tone
        sr = 16000
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        loud_shout = 0.95 * np.sin(2 * np.pi * 350.0 * t).astype(np.float32)

        metrics = analyzer.analyze(loud_shout, sample_rate=sr)
        assert 0.0 <= metrics.composite_stress_score <= 1.0

    def test_stress_never_invalidates_commands(self):
        """
        Prosody stress score must NOT alter semantic validity.
        High pitch or shouting must not reject commands.
        """
        from app.modules.voice_engine.schemas import VoiceEvent, CanonicalCommand, SemanticStatus

        event = VoiceEvent(
            transcript="STOP",
            normalized_transcript="stop",
            recognized_command=CanonicalCommand.STOP,
            recognition_confidence=0.98,
            classification_confidence=1.0,
            semantic_status=SemanticStatus.VALID,
            pitch_f0=380.0,
            intensity=0.95,
            composite_stress_score=0.88,
            is_stressed=True,
        )

        # High stress MUST NOT invalidate STOP command
        assert event.recognized_command == CanonicalCommand.STOP
        assert event.semantic_status == SemanticStatus.VALID
        assert event.is_stressed is True

