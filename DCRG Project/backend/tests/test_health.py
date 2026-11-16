"""
Unit and integration tests for system health and phase verification.
"""

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Test the root index endpoint returns project metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "Dynamic Command Reliability Graph (DCRG)"
    assert any(p in data["phase"] for p in ["Phase 2", "Phase 3", "Phase 4", "Phase 5", "Phase 6", "Phase 7", "Phase 8"])
    assert "health" in data
    assert "voice_status" in data
    assert "sync_status" in data
    assert "simulation_state" in data
    assert "system_overview" in data


def test_health_endpoint(client: TestClient):
    """Test the API v1 health endpoint reports operational state and staged modules."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["backendConnected"] is True
    assert data["activeSafetyState"] in ("NORMAL", "GREEN", "YELLOW", "RED", "EMERGENCY")
    assert "modulesStaged" in data
    assert "actuator_engine" in data["modulesStaged"]
    assert "Active" in data["modulesStaged"]["actuator_engine"]
    assert "voice_engine" in data["modulesStaged"]
    assert "Active" in data["modulesStaged"]["voice_engine"]
    assert "sync_engine" in data["modulesStaged"]
    assert "Active" in data["modulesStaged"]["sync_engine"]
    assert "simulation_engine" in data["modulesStaged"]
    assert "Active" in data["modulesStaged"]["simulation_engine"]
    assert "system_integration" in data["modulesStaged"]
    assert "Active" in data["modulesStaged"]["system_integration"]
