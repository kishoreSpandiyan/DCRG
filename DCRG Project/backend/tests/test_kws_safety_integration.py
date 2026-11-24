"""
Automated unit & integration tests for Ultra-Low-Latency Keyword Spotting (KWS)
and Fast-Path Safety Gate Hold Integration.
"""

import time
import numpy as np
import pytest
from app.modules.voice_engine.kws_service import (
    KeywordSpotterService,
    DroneKeyword,
    EMERGENCY_KEYWORDS,
    KeywordDetectionResult,
)
from app.modules.safety_engine.manager import SafetyManager
from app.modules.safety_engine.schemas import (
    AuthorizationState,
    AuthorizationDecision,
    EmergencySource,
)


@pytest.fixture
def kws():
    """Isolated KWS instance with 16kHz sample rate."""
    return KeywordSpotterService(
        sample_rate=16000,
        window_duration_sec=0.40,
        confidence_threshold=0.60,
        debounce_duration_sec=0.30,
    )


@pytest.fixture
def safety_mgr():
    """Isolated SafetyManager."""
    return SafetyManager()


def generate_synthetic_stop_audio(sr: int = 16000, duration_sec: float = 0.40) -> np.ndarray:
    """
    Synthesizes an acoustic waveform matching the phonetic signature of 'STOP':
    - Sibilant /s/ onset: high frequency noise (3500-6000 Hz)
    - Unvoiced plosive /t/ burst
    - Vowel /ɒ/ nucleus (low-mid formant energy)
    - Sudden bilabial /p/ closure (decay at coda)
    """
    n_samples = int(duration_sec * sr)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    audio = np.zeros(n_samples, dtype=np.float32)

    # 1. /s/ onset (first 30% of window): High-frequency sibilance
    n_s = int(0.35 * n_samples)
    noise = np.random.normal(0, 0.4, n_s).astype(np.float32)
    # High-pass filter simulation via high-frequency sine bank
    s_wave = 0.3 * np.sin(2 * np.pi * 4200 * t[:n_s]) + 0.2 * np.sin(2 * np.pi * 5500 * t[:n_s]) + noise * 0.3
    audio[:n_s] = s_wave

    # 2. /t/ + /ɒ/ vowel nucleus (35% to 75% of window): formant energy around 800-1500 Hz
    n_v_start = n_s
    n_v_end = int(0.75 * n_samples)
    t_v = t[n_v_start:n_v_end]
    vowel = 0.6 * np.sin(2 * np.pi * 850 * t_v) + 0.3 * np.sin(2 * np.pi * 1400 * t_v)
    audio[n_v_start:n_v_end] = vowel

    # 3. /p/ closure (75% to 100%): sudden energy drop / silence
    audio[n_v_end:] = 0.01 * np.random.normal(0, 0.05, n_samples - n_v_end)

    return audio.astype(np.float32)


class TestKeywordSpotter:
    """Verifies KWS spotting accuracy, timing, and debounce invariants."""

    def test_kws_detects_stop_keyword(self, kws):
        """Synthesized STOP waveform must trigger STOP keyword with high confidence."""
        audio = generate_synthetic_stop_audio(sr=16000, duration_sec=0.40)

        # Feed audio chunk into KWS
        res = kws.process_chunk(audio, sample_rate=16000)

        assert res is not None
        assert res.keyword == DroneKeyword.STOP.value
        assert res.is_emergency is True
        assert res.confidence >= 0.60
        assert res.detection_latency_ms < 60.0  # Must evaluate in < 60ms

    def test_kws_debounce_prevents_duplicate_triggers(self, kws):
        """Successive chunks within debounce duration must not re-trigger duplicate events."""
        audio = generate_synthetic_stop_audio(sr=16000, duration_sec=0.40)

        res1 = kws.process_chunk(audio, sample_rate=16000)
        assert res1 is not None

        # Immediate second invocation with same audio
        res2 = kws.process_chunk(audio, sample_rate=16000)
        assert res2 is None, "Debounce must suppress immediate duplicate trigger"

    def test_kws_ignores_silence_and_low_energy(self, kws):
        """Silent or ambient noise chunks must return None without triggering false positives."""
        silent = np.zeros(16000 // 2, dtype=np.float32)
        assert kws.process_chunk(silent) is None

        low_noise = np.random.normal(0, 0.003, 16000 // 2).astype(np.float32)
        assert kws.process_chunk(low_noise) is None

    def test_kws_emergency_handler_callback(self, kws):
        """Emergency callback must be invoked synchronously with valid detection payload."""
        captured = []
        kws.register_emergency_handler(lambda r: captured.append(r))

        audio = generate_synthetic_stop_audio()
        kws.process_chunk(audio)

        assert len(captured) == 1
        assert captured[0].keyword == "STOP"
        assert captured[0].is_emergency is True


class TestFastSafetyGateHoldIntegration:
    """Verifies that an emergency keyword immediately halts motion in the safety engine."""

    def test_emergency_keyword_triggers_immediate_hold(self, safety_mgr):
        """KWS emergency STOP must engage emergency hold and latch in < 60ms."""
        t0 = time.perf_counter_ns()
        estop = safety_mgr.trigger_emergency_hold(
            keyword="STOP",
            confidence=0.95,
            source=EmergencySource.KEYWORD_SPOTTER,
            detection_latency_ms=12.5,
        )
        latency_ms = (time.perf_counter_ns() - t0) / 1e6

        assert latency_ms < 60.0
        assert estop.authorization_state == AuthorizationState.EMERGENCY
        assert estop.authorization_decision == AuthorizationDecision.EMERGENCY_HALT
        assert estop.is_latched is True
        assert "STOP" in estop.reason

    def test_safety_hold_requires_explicit_pin_recovery(self, safety_mgr):
        """An established emergency hold must never automatically reset without PIN."""
        safety_mgr.trigger_emergency_hold(keyword="STOP", confidence=0.90)

        # Invalid PIN attempt
        success_bad, msg_bad = safety_mgr.reset_emergency_stop(reset_pin="0000")
        assert not success_bad
        assert safety_mgr._is_emergency_latched is True

        # Valid PIN attempt
        success_ok, msg_ok = safety_mgr.reset_emergency_stop(reset_pin="1234")
        assert success_ok
        assert safety_mgr._is_emergency_latched is False
