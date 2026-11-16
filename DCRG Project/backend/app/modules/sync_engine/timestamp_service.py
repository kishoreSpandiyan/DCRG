"""
Timestamp Management Service for DCRG Event Synchronization.
Provides UTC normalization, monotonic interval tracking, validation, clock drift
estimation, and out-of-order / delayed event detection.
"""

import math
import time
from typing import Dict, Optional, Tuple
from app.modules.sync_engine.schemas import TimestampMetadata
from app.core.config import settings


class TimestampManager:
    """
    Handles temporal ingestion verification.
    
    SAFETY PRINCIPLES:
    - Never silently replace or overwrite an original event timestamp.
    - Record event creation time (t_event) and server reception time (t_reception) separately.
    - Detect corrupted or anomalous timestamps deterministically.
    """

    def __init__(
        self,
        clock_drift_threshold_ms: float = 50.0,
        delay_threshold_ms: float = 200.0,
    ):
        self.drift_threshold_ms = clock_drift_threshold_ms
        self.delay_threshold_ms = delay_threshold_ms

        # Track latest event timestamp per modality to detect out-of-order packets
        self._last_event_time: Dict[str, float] = {
            "voice": 0.0,
            "joystick": 0.0,
        }

    def validate_timestamp(self, ts: Optional[float]) -> Tuple[bool, str]:
        """
        Validates timestamp presence, numeric validity, and reasonable chronological bounds.
        Tolerance: must be > Nov 2023 (1.7e12 ms) and < now + 10 minutes.
        """
        if ts is None:
            return False, "Missing timestamp: value is None"

        if not isinstance(ts, (int, float)):
            return False, f"Invalid timestamp type: {type(ts).__name__}"

        if math.isnan(ts) or math.isinf(ts):
            return False, "Invalid timestamp: NaN or Inf detected"

        now_ms = time.time() * 1000.0
        # Historical bound: must be after approx Nov 2023
        if ts < 1700000000000.0:
            return False, f"Invalid historical timestamp {ts}: older than epoch threshold"

        # Future bound: cannot be more than 10 minutes in the future
        if ts > (now_ms + 600000.0):
            return False, f"Invalid future timestamp {ts}: exceeds current server time + 10m"

        return True, "Valid"

    def process_event_timestamp(
        self,
        event_time_ms: float,
        modality: str,
    ) -> TimestampMetadata:
        """
        Captures reception time using both UTC wall-clock and monotonic nanoseconds.
        Evaluates latency, clock drift, out-of-order sequence, and delayed status.
        Never alters the original event_time_ms.
        """
        reception_utc_ms = time.time() * 1000.0
        reception_mono_ns = time.monotonic_ns()

        # Ingestion latency: time between creation and server arrival
        latency_ms = max(0.0, reception_utc_ms - event_time_ms)

        # Clock drift estimate: if event_time is ahead of reception_time, client clock is fast
        clock_drift_ms = event_time_ms - reception_utc_ms

        # Out-of-order detection: is this event older than the previous event from the same modality?
        last_t = self._last_event_time.get(modality, 0.0)
        is_out_of_order = (last_t > 0.0) and (event_time_ms < last_t)

        if not is_out_of_order:
            self._last_event_time[modality] = event_time_ms

        # Delayed flag: ingestion latency exceeded delay threshold
        is_delayed = latency_ms > self.delay_threshold_ms

        return TimestampMetadata(
            event_time_utc_ms=round(event_time_ms, 3),
            reception_time_utc_ms=round(reception_utc_ms, 3),
            reception_monotonic_ns=reception_mono_ns,
            latency_ms=round(latency_ms, 3),
            clock_drift_estimate_ms=round(clock_drift_ms, 3),
            is_out_of_order=is_out_of_order,
            is_delayed=is_delayed,
        )

    def reset_tracking(self) -> None:
        """Resets chronological tracking state for testing or re-initialization."""
        self._last_event_time = {"voice": 0.0, "joystick": 0.0}


# Global singleton instance
timestamp_manager = TimestampManager()

