"""
Synchronization Manager.
Coordinates automated ingestion from voice and joystick managers,
runs the periodic timeout sweeper, and dispatches CorrelatedEvents to WebSockets.
"""

import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

from app.core.config import settings
from app.modules.voice_engine.schemas import VoiceEvent
from app.modules.actuator_engine.schemas import CommonJoystickEvent
from app.modules.voice_engine.manager import voice_manager
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.sync_engine.schemas import (
    CorrelatedEvent,
    SyncEngineStatus,
    SynchronizationStatus,
)
from app.modules.sync_engine.synchronizer import EventSynchronizer

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Central Coordinator for DCRG Phase 4 Event Synchronization and Correlation.
    Subscribes directly to voice_engine and actuator_engine event streams.
    """

    def __init__(self, synchronizer: Optional[EventSynchronizer] = None):
        self.synchronizer = synchronizer or EventSynchronizer(
            sync_window_ms=settings.SYNC_WINDOW_MS,
            max_event_age_ms=settings.SYNC_MAX_EVENT_AGE_MS,
            buffer_capacity=settings.SYNC_BUFFER_CAPACITY,
            duplicate_cache_size=settings.SYNC_DUPLICATE_CACHE_SIZE,
        )

        self._lock = threading.RLock()
        self._history: List[CorrelatedEvent] = []
        self._max_history = 100
        self._is_running = False
        self._sweeper_thread: Optional[threading.Thread] = None

        # Hook internal history tracker to synchronizer
        self.synchronizer.subscribe(self._record_history)

        # Hook into Actuator and Voice subsystems
        actuator_manager.subscribe(self._on_joystick_event)
        voice_manager.subscribe(self._on_voice_event)

    def start(self) -> Tuple[bool, str]:
        """Starts periodic timeout evaluation thread."""
        with self._lock:
            if self._is_running:
                return True, "Sync engine is already active."

            self._is_running = True
            self._sweeper_thread = threading.Thread(
                target=self._sweeper_loop,
                name="DCRG-SyncSweeper",
                daemon=True,
            )
            self._sweeper_thread.start()
            msg = "Event Synchronization Engine started successfully."
            logger.info(msg)
            return True, msg

    def stop(self) -> Tuple[bool, str]:
        """Stops background timeout thread."""
        with self._lock:
            self._is_running = False
            msg = "Event Synchronization Engine stopped cleanly."
            logger.info(msg)
            return True, msg

    def configure(
        self,
        sync_window_ms: Optional[float] = None,
        max_event_age_ms: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """Configures synchronization matching parameters."""
        return self.synchronizer.configure(sync_window_ms, max_event_age_ms)

    def subscribe(self, callback: Callable[[CorrelatedEvent], None]) -> None:
        """Registers a listener for emitted CorrelatedEvents."""
        self.synchronizer.subscribe(callback)

    def get_status(self) -> SyncEngineStatus:
        """Returns comprehensive status and telemetry metrics."""
        return self.synchronizer.get_status()

    def get_history(self, limit: int = 50) -> List[CorrelatedEvent]:
        """Returns recent correlated event history."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def correlate_manual_pair(
        self,
        voice_event: Optional[VoiceEvent],
        joystick_event: Optional[CommonJoystickEvent],
    ) -> CorrelatedEvent:
        """Manual pair evaluation for tests and simulation."""
        return self.synchronizer.correlate_manual_pair(voice_event, joystick_event)

    def _on_joystick_event(self, event: CommonJoystickEvent) -> None:
        """Ingests live joystick events emitted by actuator_manager."""
        try:
            self.synchronizer.ingest_joystick_event(event)
        except Exception as e:
            logger.error(f"Error ingesting joystick event into synchronizer: {e}")

    def _on_voice_event(self, event: VoiceEvent) -> None:
        """Ingests live voice events emitted by voice_manager."""
        try:
            self.synchronizer.ingest_voice_event(event)
        except Exception as e:
            logger.error(f"Error ingesting voice event into synchronizer: {e}")

    def _record_history(self, event: CorrelatedEvent) -> None:
        """Records event into bounded in-memory audit log."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

    def _sweeper_loop(self) -> None:
        """Background thread executing periodic unpartnered timeout checks."""
        while self._is_running:
            try:
                time.sleep(0.04)  # ~25 Hz sweep frequency
                if self._is_running:
                    self.synchronizer.process_pending_timeouts()
            except Exception as e:
                logger.error(f"Error in synchronization sweeper loop: {e}")


# Global singleton instance
sync_manager = SyncManager()

