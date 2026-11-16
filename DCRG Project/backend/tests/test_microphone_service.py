"""
Automated unit tests for Microphone Audio Ingestion Service (Phase 3).
Verifies ring buffer mechanics, status state machines, device queries, and mute handling.
"""

import numpy as np
import pytest
from app.modules.voice_engine.microphone_service import (
    MicrophoneService,
    RingBuffer,
)
from app.modules.voice_engine.schemas import MicrophoneStatus


class TestRingBuffer:
    """Verifies circular audio buffer functionality and boundary handling."""

    def test_ring_buffer_append_and_get(self):
        capacity = 100
        rb = RingBuffer(capacity)

        # Append 40 samples
        chunk1 = np.ones(40, dtype=np.float32) * 1.0
        rb.append(chunk1)
        res = rb.get_latest(40)
        assert len(res) == 40
        assert np.allclose(res, 1.0)

        # Append another 80 samples (causing wrap-around)
        chunk2 = np.ones(80, dtype=np.float32) * 2.0
        rb.append(chunk2)

        # Latest 50 should all be 2.0
        res = rb.get_latest(50)
        assert len(res) == 50
        assert np.allclose(res, 2.0)

        # Latest 100 (capacity) should have 20 of 1.0 and 80 of 2.0
        res_full = rb.get_latest(100)
        assert len(res_full) == 100
        assert np.allclose(res_full[:20], 1.0)
        assert np.allclose(res_full[20:], 2.0)

    def test_ring_buffer_oversized_chunk(self):
        capacity = 50
        rb = RingBuffer(capacity)
        oversized = np.arange(100, dtype=np.float32)
        rb.append(oversized)

        # Should retain only the last 50 samples [50..99]
        latest = rb.get_latest(50)
        assert len(latest) == 50
        assert latest[0] == 50.0
        assert latest[-1] == 99.0

    def test_ring_buffer_clear(self):
        rb = RingBuffer(100)
        rb.append(np.ones(50, dtype=np.float32))
        rb.clear()
        assert len(rb.get_latest(50)) == 0


class TestMicrophoneService:
    """Tests microphone lifecycle, status reporting, and safety states."""

    def test_available_devices_query(self):
        mic = MicrophoneService()
        devices = mic.get_available_devices()
        assert isinstance(devices, list)
        for d in devices:
            assert "index" in d
            assert "name" in d
            assert "max_input_channels" in d
            assert d["max_input_channels"] > 0

    def test_initial_state_disconnected(self):
        mic = MicrophoneService()
        assert mic.status == MicrophoneStatus.DISCONNECTED
        assert mic.is_capturing is False
        assert mic.is_muted is False

    def test_mute_toggle(self):
        mic = MicrophoneService()
        mic.set_mute(True)
        assert mic.is_muted is True
        # If not capturing, status remains DISCONNECTED
        assert mic.status == MicrophoneStatus.DISCONNECTED

        mic.set_mute(False)
        assert mic.is_muted is False

    def test_invalid_device_selection(self):
        mic = MicrophoneService()
        success, msg = mic.select_device(99999)  # Non-existent index
        assert success is False
        assert "not found" in msg.lower()

    def test_subscriber_registration(self):
        mic = MicrophoneService()
        received = []

        def callback(chunk, sr):
            received.append((chunk, sr))

        mic.register_chunk_subscriber(callback)
        # Directly invoke callback handler
        test_frame = np.ones((480, 1), dtype=np.float32)
        mic.is_capturing = True
        mic._audio_callback(test_frame, 480, None, None)

        assert len(received) == 1
        assert len(received[0][0]) == 480
        assert received[0][1] == 16000

