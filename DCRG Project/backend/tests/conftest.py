"""
Pytest configuration and test client fixture.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is in Python module search path
backend_root = Path(__file__).parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_subsystems():
    """Resets manager singletons between tests to prevent inter-test state contamination."""
    from app.modules.sync_engine.manager import sync_manager
    from app.modules.safety_engine.manager import safety_manager
    from app.modules.fusion_engine.manager import fusion_manager
    from app.modules.actuator_engine.manager import actuator_manager

    sync_manager.reset_stats()
    safety_manager.reset_stats()
    fusion_manager.reset_stats()
    actuator_manager.last_event = None
    yield
    sync_manager.reset_stats()
    safety_manager.reset_stats()
    fusion_manager.reset_stats()
    actuator_manager.last_event = None
