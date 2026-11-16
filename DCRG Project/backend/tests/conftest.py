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
