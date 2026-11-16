"""
Event Synchronization and Correlation Engine for DCRG Phase 4.
Aligns asynchronous voice and joystick events across biological and network delays,
enforcing non-blocking buffering, duplicate elimination, and truthful correlation reporting.
"""

from collections import OrderedDict
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from app.core.config import settings
from app.modules.voice_engine.schemas import VoiceEvent
from app.modules.actuator_engine.schemas import CommonJoystickEvent
from app.modules.sync_engine.schemas import (
    CorrelatedEvent,
    SynchronizationStatus,
    SyncEngineStatus,
    TimestampMetadata,
)
from app.modules.sync_engine.timestamp_service import (
    TimestampManager,
    timestamp_manager,
)

logger = logging.getLogger(__name__)


class EventSynchronizer:
    """
    Core Synchronization and Correlation Engine.
    Maintains independent sliding buffers for voice and joystick streams,
    compares event inception timestamps (t_event), and associates matching pairs
    within the configurable synchronization window (default 150ms).
    """

    def __init__(
        self,
        sync_window_ms: float = 150.0,
        max_event_age_ms: float = 350.0,
        buffer_capacity: int = 200,
        duplicate_cache_size: int = 1000,
        ts_manager: Optional[TimestampManager] = None,
    ):
        self.sync_window_ms = sync_window_ms
        self.max_event_age_ms = max_event_age_ms
        self.buffer_capacity = buffer_capacity
        self.duplicate_cache_size = duplicate_cache_size
        self.ts_manager = ts_manager or timestamp_manager

        self._lock = threading.RLock()

        # Separate time-indexed sliding buffers
        # Lists of tuples: (event_time_utc_ms, event_obj, metadata)
        self._voice_buffer: List[Tuple[float, VoiceEvent, TimestampMetadata]] = []
        self._joystick_buffer: List[Tuple[float, CommonJoystickEvent, TimestampMetadata]] = []

        # LRU cache for recently processed event IDs (to reject duplicates)
        self._seen_event_ids: OrderedDict[str, float] = OrderedDict()

        # Counters and statistics
        self.total_synchronized = 0
        self.total_voice_only = 0
        self.total_joystick_only = 0
        self.total_out_of_window = 0
        self.total_delayed = 0
        self.total_stale = 0
        self.total_duplicate = 0
        self.total_invalid_timestamp = 0

        self.last_correlation: Optional[CorrelatedEvent] = None
        self._subscribers: List[Callable[[CorrelatedEvent], None]] = []

    def configure(
        self,
        sync_window_ms: Optional[float] = None,
        max_event_age_ms: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """Dynamically adjusts synchronization thresholds."""
        with self._lock:
            if sync_window_ms is not None:
                self.sync_window_ms = float(sync_window_ms)
            if max_event_age_ms is not None:
                self.max_event_age_ms = float(max_event_age_ms)
            msg = f"Configured sync_window_ms={self.sync_window_ms}, max_event_age_ms={self.max_event_age_ms}"
            logger.info(msg)
            return True, msg

    def subscribe(self, callback: Callable[[CorrelatedEvent], None]) -> None:
        """Registers a listener for emitted CorrelatedEvents."""
        with self._lock:
            self._subscribers.append(callback)

    def ingest_voice_event(self, event: VoiceEvent) -> Optional[CorrelatedEvent]:
        """
        Asynchronously ingests a VoiceEvent from Phase 3 voice_engine.
        Performs validation, duplicate checks, and temporal matching against joystick buffer.
        """
        with self._lock:
            # 1. Duplicate check
            if event.event_id in self._seen_event_ids:
                self.total_duplicate += 1
                corr = self._build_duplicate_event(event.event_id, "voice", event.timestamp)
                self._dispatch(corr)
                return corr
            self._mark_seen(event.event_id)

            # 2. Timestamp validation
            valid, reason = self.ts_manager.validate_timestamp(event.timestamp)
            if not valid:
                self.total_invalid_timestamp += 1
                corr = self._build_invalid_timestamp_event(event.event_id, "voice", event.timestamp, reason)
                self._dispatch(corr)
                return corr

            # Process timestamp metadata
            meta = self.ts_manager.process_event_timestamp(event.timestamp, "voice")
            if meta.is_delayed:
                self.total_delayed += 1

            # 3. Clean up expired items in both buffers
            self._cleanup_expired_events()

            # 4. Search joystick buffer for temporal match
            # Match condition: |t_voice - t_joystick| <= sync_window_ms
            best_idx = None
            best_delta = float("inf")

            for idx, (j_time, j_event, j_meta) in enumerate(self._joystick_buffer):
                delta = abs(event.timestamp - j_time)
                if delta <= self.sync_window_ms and delta < best_delta:
                    best_delta = delta
                    best_idx = idx

            if best_idx is not None:
                # Match found! Remove matched joystick event from buffer
                _, matched_joy, joy_meta = self._joystick_buffer.pop(best_idx)
                status = SynchronizationStatus.DELAYED if (meta.is_delayed or joy_meta.is_delayed) else SynchronizationStatus.SYNCHRONIZED
                self.total_synchronized += 1

                corr = CorrelatedEvent(
                    correlation_timestamp=time.time() * 1000.0,
                    voice_event_id=event.event_id,
                    joystick_event_id=matched_joy.event_id,
                    voice_command=event.recognized_command.value,
                    joystick_direction=matched_joy.direction.value,
                    joystick_intensity=matched_joy.intensity,
                    timestamp_difference_ms=round(best_delta, 2),
                    synchronization_status=status,
                    voice_available=True,
                    joystick_available=True,
                    correlation_reason=f"Paired within {self.sync_window_ms}ms window (delta: {best_delta:.1f}ms)",
                    voice_event=event,
                    joystick_event=matched_joy,
                )
                self._dispatch(corr)
                return corr

            # 5. Check if there is an existing joystick event that is explicitly OUT OF WINDOW
            # If the closest joystick event exceeds the window but was recent
            closest_j_delta = float("inf")
            for j_time, _, _ in self._joystick_buffer:
                d = abs(event.timestamp - j_time)
                if d < closest_j_delta:
                    closest_j_delta = d

            # 6. If no match yet, buffer the voice event
            self._voice_buffer.append((event.timestamp, event, meta))
            self._enforce_buffer_capacity(self._voice_buffer)
            return None

    def ingest_joystick_event(self, event: CommonJoystickEvent) -> Optional[CorrelatedEvent]:
        """
        Asynchronously ingests a CommonJoystickEvent from Phase 2 actuator_engine.
        Performs validation, duplicate checks, and temporal matching against voice buffer.
        """
        with self._lock:
            # 1. Duplicate check
            if event.event_id in self._seen_event_ids:
                self.total_duplicate += 1
                corr = self._build_duplicate_event(event.event_id, "joystick", event.timestamp)
                self._dispatch(corr)
                return corr
            self._mark_seen(event.event_id)

            # 2. Timestamp validation
            valid, reason = self.ts_manager.validate_timestamp(event.timestamp)
            if not valid:
                self.total_invalid_timestamp += 1
                corr = self._build_invalid_timestamp_event(event.event_id, "joystick", event.timestamp, reason)
                self._dispatch(corr)
                return corr

            # Process timestamp metadata
            meta = self.ts_manager.process_event_timestamp(event.timestamp, "joystick")
            if meta.is_delayed:
                self.total_delayed += 1

            # 3. Clean up expired items
            self._cleanup_expired_events()

            # 4. Search voice buffer for temporal match
            best_idx = None
            best_delta = float("inf")

            for idx, (v_time, v_event, v_meta) in enumerate(self._voice_buffer):
                delta = abs(event.timestamp - v_time)
                if delta <= self.sync_window_ms and delta < best_delta:
                    best_delta = delta
                    best_idx = idx

            if best_idx is not None:
                # Match found! Remove matched voice event from buffer
                _, matched_voice, voice_meta = self._voice_buffer.pop(best_idx)
                status = SynchronizationStatus.DELAYED if (meta.is_delayed or voice_meta.is_delayed) else SynchronizationStatus.SYNCHRONIZED
                self.total_synchronized += 1

                corr = CorrelatedEvent(
                    correlation_timestamp=time.time() * 1000.0,
                    voice_event_id=matched_voice.event_id,
                    joystick_event_id=event.event_id,
                    voice_command=matched_voice.recognized_command.value,
                    joystick_direction=event.direction.value,
                    joystick_intensity=event.intensity,
                    timestamp_difference_ms=round(best_delta, 2),
                    synchronization_status=status,
                    voice_available=True,
                    joystick_available=True,
                    correlation_reason=f"Paired within {self.sync_window_ms}ms window (delta: {best_delta:.1f}ms)",
                    voice_event=matched_voice,
                    joystick_event=event,
                )
                self._dispatch(corr)
                return corr

            # 5. Buffer joystick event for potential upcoming voice matching
            self._joystick_buffer.append((event.timestamp, event, meta))
            self._enforce_buffer_capacity(self._joystick_buffer)
            return None

    def process_pending_timeouts(self) -> List[CorrelatedEvent]:
        """
        Evaluates unpartnered buffered events exceeding the matching or max-age window.
        Emits VOICE_ONLY, JOYSTICK_ONLY, OUT_OF_WINDOW, or STALE events accordingly.
        """
        emitted = []
        now_ms = time.time() * 1000.0

        with self._lock:
            # 1. Check unpartnered voice events
            retained_voice = []
            for v_time, v_event, v_meta in self._voice_buffer:
                age = now_ms - v_time
                if age > self.max_event_age_ms:
                    self.total_stale += 1
                    corr = CorrelatedEvent(
                        correlation_timestamp=now_ms,
                        voice_event_id=v_event.event_id,
                        joystick_event_id=None,
                        voice_command=v_event.recognized_command.value,
                        joystick_direction=None,
                        joystick_intensity=None,
                        timestamp_difference_ms=None,
                        synchronization_status=SynchronizationStatus.STALE,
                        voice_available=True,
                        joystick_available=False,
                        correlation_reason=f"Voice event unpartnered after {age:.1f}ms (window: {self.sync_window_ms}ms)",
                        voice_event=v_event,
                        joystick_event=None,
                    )
                    self._dispatch(corr)
                    emitted.append(corr)
                else:
                    retained_voice.append((v_time, v_event, v_meta))
            self._voice_buffer = retained_voice

            # 2. Check unpartnered active joystick events
            retained_joy = []
            for j_time, j_event, j_meta in self._joystick_buffer:
                age = now_ms - j_time
                is_active = j_event.intensity > 0.10
                if age > self.max_event_age_ms:
                    if is_active:
                        self.total_stale += 1
                        corr = CorrelatedEvent(
                            correlation_timestamp=now_ms,
                            voice_event_id=None,
                            joystick_event_id=j_event.event_id,
                            voice_command=None,
                            joystick_direction=j_event.direction.value,
                            joystick_intensity=j_event.intensity,
                            timestamp_difference_ms=None,
                            synchronization_status=SynchronizationStatus.STALE,
                            voice_available=False,
                            joystick_available=True,
                            correlation_reason=f"Joystick active deflection unpartnered after {age:.1f}ms",
                            voice_event=None,
                            joystick_event=j_event,
                        )
                        self._dispatch(corr)
                        emitted.append(corr)
                    else:
                        self.total_stale += 1
                else:
                    retained_joy.append((j_time, j_event, j_meta))
            self._joystick_buffer = retained_joy

        return emitted

    def correlate_manual_pair(
        self,
        voice_event: Optional[VoiceEvent],
        joystick_event: Optional[CommonJoystickEvent],
    ) -> CorrelatedEvent:
        """
        Deterministic, synchronous correlation method for explicit pair testing and simulation.
        Compares timestamps, checks sync window, and returns evaluated CorrelatedEvent.
        """
        now_ms = time.time() * 1000.0

        if voice_event is None and joystick_event is None:
            return CorrelatedEvent(
                correlation_timestamp=now_ms,
                synchronization_status=SynchronizationStatus.STALE,
                voice_available=False,
                joystick_available=False,
                correlation_reason="Both modalities missing/null",
            )

        if voice_event is not None and joystick_event is None:
            self.total_voice_only += 1
            corr = CorrelatedEvent(
                correlation_timestamp=now_ms,
                voice_event_id=voice_event.event_id,
                voice_command=voice_event.recognized_command.value,
                synchronization_status=SynchronizationStatus.VOICE_ONLY,
                voice_available=True,
                joystick_available=False,
                correlation_reason="Voice-only event; joystick stream missing or unpartnered",
                voice_event=voice_event,
            )
            self._dispatch(corr)
            return corr

        if voice_event is None and joystick_event is not None:
            self.total_joystick_only += 1
            corr = CorrelatedEvent(
                correlation_timestamp=now_ms,
                joystick_event_id=joystick_event.event_id,
                joystick_direction=joystick_event.direction.value,
                joystick_intensity=joystick_event.intensity,
                synchronization_status=SynchronizationStatus.JOYSTICK_ONLY,
                voice_available=False,
                joystick_available=True,
                correlation_reason="Joystick-only event; voice stream missing or silent",
                joystick_event=joystick_event,
            )
            self._dispatch(corr)
            return corr

        # Both events present
        delta_ms = abs(voice_event.timestamp - joystick_event.timestamp)

        if delta_ms <= self.sync_window_ms:
            status = SynchronizationStatus.SYNCHRONIZED
            self.total_synchronized += 1
            reason = f"Synchronized within {self.sync_window_ms}ms window (delta: {delta_ms:.1f}ms)"
        else:
            status = SynchronizationStatus.OUT_OF_WINDOW
            self.total_out_of_window += 1
            reason = f"Diverged outside {self.sync_window_ms}ms window (delta: {delta_ms:.1f}ms)"

        corr = CorrelatedEvent(
            correlation_timestamp=now_ms,
            voice_event_id=voice_event.event_id,
            joystick_event_id=joystick_event.event_id,
            voice_command=voice_event.recognized_command.value,
            joystick_direction=joystick_event.direction.value,
            joystick_intensity=joystick_event.intensity,
            timestamp_difference_ms=round(delta_ms, 2),
            synchronization_status=status,
            voice_available=True,
            joystick_available=True,
            correlation_reason=reason,
            voice_event=voice_event,
            joystick_event=joystick_event,
        )
        self._dispatch(corr)
        return corr

    def get_status(self) -> SyncEngineStatus:
        """Returns truthful system status, buffer counts, and statistics."""
        with self._lock:
            return SyncEngineStatus(
                sync_window_ms=self.sync_window_ms,
                max_event_age_ms=self.max_event_age_ms,
                voice_buffer_count=len(self._voice_buffer),
                joystick_buffer_count=len(self._joystick_buffer),
                total_synchronized_count=self.total_synchronized,
                total_voice_only_count=self.total_voice_only,
                total_joystick_only_count=self.total_joystick_only,
                total_out_of_window_count=self.total_out_of_window,
                total_delayed_count=self.total_delayed,
                total_stale_count=self.total_stale,
                total_duplicate_count=self.total_duplicate,
                total_invalid_timestamp_count=self.total_invalid_timestamp,
                last_correlation=self.last_correlation,
                voice_pipeline_active=True,
                joystick_pipeline_active=True,
            )

    def _cleanup_expired_events(self) -> None:
        """Removes items older than max_event_age_ms to prevent buffer buildup."""
        now_ms = time.time() * 1000.0
        cutoff = now_ms - self.max_event_age_ms

        prev_v = len(self._voice_buffer)
        self._voice_buffer = [item for item in self._voice_buffer if item[0] >= cutoff]
        self.total_stale += (prev_v - len(self._voice_buffer))

        prev_j = len(self._joystick_buffer)
        self._joystick_buffer = [item for item in self._joystick_buffer if item[0] >= cutoff]
        self.total_stale += (prev_j - len(self._joystick_buffer))

    def _enforce_buffer_capacity(self, buf: list) -> None:
        """Limits buffer length to prevent memory starvation during high-frequency bursts."""
        while len(buf) > self.buffer_capacity:
            buf.pop(0)

    def _mark_seen(self, event_id: str) -> None:
        """Stores event_id in bounded LRU cache."""
        self._seen_event_ids[event_id] = time.time()
        if len(self._seen_event_ids) > self.duplicate_cache_size:
            self._seen_event_ids.popitem(last=False)

    def _build_duplicate_event(self, event_id: str, modality: str, ts: float) -> CorrelatedEvent:
        return CorrelatedEvent(
            correlation_timestamp=time.time() * 1000.0,
            voice_event_id=event_id if modality == "voice" else None,
            joystick_event_id=event_id if modality == "joystick" else None,
            synchronization_status=SynchronizationStatus.DUPLICATE,
            voice_available=(modality == "voice"),
            joystick_available=(modality == "joystick"),
            correlation_reason=f"Rejected duplicate event_id '{event_id}' from {modality}",
        )

    def _build_invalid_timestamp_event(self, event_id: str, modality: str, ts: float, reason: str) -> CorrelatedEvent:
        return CorrelatedEvent(
            correlation_timestamp=time.time() * 1000.0,
            voice_event_id=event_id if modality == "voice" else None,
            joystick_event_id=event_id if modality == "joystick" else None,
            synchronization_status=SynchronizationStatus.INVALID_TIMESTAMP,
            voice_available=(modality == "voice"),
            joystick_available=(modality == "joystick"),
            correlation_reason=f"Rejected invalid timestamp on {modality}: {reason}",
        )

    def _dispatch(self, event: CorrelatedEvent) -> None:
        """Updates latest state and broadcasts to registered listeners."""
        self.last_correlation = event
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error in synchronization subscriber callback: {e}")

