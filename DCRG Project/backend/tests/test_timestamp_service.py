"""
Automated unit tests for Timestamp Management Service (Phase 4).
Verifies UTC normalization, monotonic clock recording, chronological bounds,
clock drift estimation, delayed detection, and out-of-order sequence identification.
"""

import math
import time
import pytest
from app.modules.sync_engine.timestamp_service import TimestampManager


@pytest.fixture
def ts_mgr():
    mgr = TimestampManager(clock_drift_threshold_ms=50.0, delay_threshold_ms=200.0)
    mgr.reset_tracking()
    return mgr


class TestTimestampValidation:
    """Verifies strict validation of incoming timestamps."""

    def test_valid_current_timestamp(self, ts_mgr):
        now_ms = time.time() * 1000.0
        valid, reason = ts_mgr.validate_timestamp(now_ms)
        assert valid is True
        assert reason == "Valid"

    def test_missing_timestamp_rejected(self, ts_mgr):
        valid, reason = ts_mgr.validate_timestamp(None)
        assert valid is False
        assert "Missing" in reason

    def test_historical_timestamp_rejected(self, ts_mgr):
        # Ancient epoch timestamp (year 1970)
        valid, reason = ts_mgr.validate_timestamp(1000.0)
        assert valid is False
        assert "Invalid historical" in reason

    def test_absurd_future_timestamp_rejected(self, ts_mgr):
        far_future = time.time() * 1000.0 + (3600.0 * 24 * 365 * 1000.0)  # +1 year
        valid, reason = ts_mgr.validate_timestamp(far_future)
        assert valid is False
        assert "Invalid future" in reason

    def test_nan_and_inf_rejected(self, ts_mgr):
        valid_nan, _ = ts_mgr.validate_timestamp(float("nan"))
        assert valid_nan is False

        valid_inf, _ = ts_mgr.validate_timestamp(float("inf"))
        assert valid_inf is False


class TestTimestampProcessingAndDrift:
    """Verifies metadata extraction, latency calculation, and out-of-order detection."""

    def test_reception_time_recorded_separately(self, ts_mgr):
        now_ms = time.time() * 1000.0 - 50.0  # Event created 50ms ago
        meta = ts_mgr.process_event_timestamp(now_ms, "voice")

        assert meta.event_time_utc_ms == round(now_ms, 3)
        assert meta.reception_time_utc_ms >= now_ms
        assert meta.latency_ms >= 40.0
        assert meta.reception_monotonic_ns > 0
        assert meta.is_delayed is False
        assert meta.is_out_of_order is False

    def test_delayed_event_flagging(self, ts_mgr):
        # Event created 250ms ago (exceeds 200ms delay threshold)
        delayed_ts = time.time() * 1000.0 - 250.0
        meta = ts_mgr.process_event_timestamp(delayed_ts, "joystick")

        assert meta.is_delayed is True
        assert meta.latency_ms >= 240.0

    def test_out_of_order_detection(self, ts_mgr):
        base_t = time.time() * 1000.0

        # Event 1 at t=100
        meta1 = ts_mgr.process_event_timestamp(base_t, "voice")
        assert meta1.is_out_of_order is False

        # Event 2 at t=110
        meta2 = ts_mgr.process_event_timestamp(base_t + 10.0, "voice")
        assert meta2.is_out_of_order is False

        # Event 3 arrives out-of-order at t=95 (older than t=110)
        meta3 = ts_mgr.process_event_timestamp(base_t - 5.0, "voice")
        assert meta3.is_out_of_order is True

