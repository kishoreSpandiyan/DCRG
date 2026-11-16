"""
Event Synchronization and Correlation Module (Phase 4).
Aligns asynchronous multi-modal streams, enforces temporal windows,
and synthesizes CorrelatedEvents.
"""

from app.modules.sync_engine.schemas import (
    SynchronizationStatus,
    TimestampMetadata,
    CorrelatedEvent,
    SyncEngineStatus,
    ConfigureSyncRequest,
)
from app.modules.sync_engine.timestamp_service import (
    TimestampManager,
    timestamp_manager,
)
from app.modules.sync_engine.synchronizer import (
    EventSynchronizer,
)
from app.modules.sync_engine.manager import (
    SyncManager,
    sync_manager,
)

__all__ = [
    "SynchronizationStatus",
    "TimestampMetadata",
    "CorrelatedEvent",
    "SyncEngineStatus",
    "ConfigureSyncRequest",
    "TimestampManager",
    "timestamp_manager",
    "EventSynchronizer",
    "SyncManager",
    "sync_manager",
]

