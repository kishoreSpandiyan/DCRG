"""
API v1 Router aggregating subsystem endpoints.
"""

from fastapi import APIRouter
from app.schemas.health import HealthResponse
from app.core.config import settings
from app.api.v1.endpoints.joystick import router as joystick_router
from app.api.v1.endpoints.voice import router as voice_router
from app.api.v1.endpoints.sync import router as sync_router
from app.api.v1.endpoints.fusion import router as fusion_router
from app.api.v1.endpoints.safety import router as safety_router
from app.api.v1.endpoints.simulation import router as simulation_router
from app.api.v1.endpoints.system import router as system_router
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.voice_engine.manager import voice_manager
from app.modules.sync_engine.manager import sync_manager
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.context_engine.service import context_service
from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.manager import simulation_manager

api_router = APIRouter()

# Include Subsystem Routers
api_router.include_router(joystick_router)
api_router.include_router(voice_router)
api_router.include_router(sync_router)
api_router.include_router(fusion_router)
api_router.include_router(safety_router)
api_router.include_router(simulation_router)
api_router.include_router(system_router)


@api_router.get("/health", response_model=HealthResponse, tags=["System Health"])
async def get_system_health() -> HealthResponse:
    """
    Health check and system status endpoint.
    Reports active phase, module readiness, and safety state.
    """
    joy_status = actuator_manager.get_status()
    v_status = voice_manager.get_status()
    s_status = sync_manager.get_status()
    f_status = fusion_manager.get_status()
    ctx_state = context_service.get_state()
    saf_status = safety_manager.get_status()
    sim_state = simulation_manager.get_state()

    return HealthResponse(
        status="operational",
        phase="Phase 8 – Complete Dashboard & End-to-End Integration",
        version=settings.VERSION,
        backendConnected=True,
        hardwareDetected=joy_status.physical_hardware_detected,
        activeSafetyState=saf_status.active_state.value,
        modulesStaged={
            "voice_engine": f"Active (Phase 3 Operational - Whisper {v_status.model_name})",
            "prosody_engine": "Active (Phase 3 Operational - Librosa Prosody)",
            "semantic_engine": "Active (Phase 3 Operational - Intent Classification)",
            "actuator_engine": "Active (Phase 2 Operational)",
            "sync_engine": f"Active (Phase 4 Operational - Window: {s_status.sync_window_ms}ms)",
            "fusion_engine": f"Active (Phase 5 Operational - Multi-factor CRS {f_status.scoring_config_version})",
            "context_engine": f"Active (Phase 5 Operational - Mode: {ctx_state.operating_mode.value})",
            "safety_engine": f"Active (Phase 6 Operational - State: {saf_status.active_state.value})",
            "simulation_engine": f"Active (Phase 7 Operational - Pose: ({sim_state.pose.x:.1f}, {sim_state.pose.y:.1f}))",
            "system_integration": "Active (Phase 8 Operational - Full Multimodal Pipeline & Audit)",
        },
        details={
            "environment": settings.ENVIRONMENT,
            "crsThreshold": settings.CRS_AUTHORIZATION_THRESHOLD,
            "activeJoystickMode": joy_status.active_mode,
            "connectedControllers": joy_status.connected_device_count,
            "hardwareIsolationEnforced": True,
            "microphoneStatus": v_status.microphone_status,
            "microphoneDevice": v_status.selected_device_name,
            "whisperModel": v_status.model_name,
            "whisperLoaded": v_status.model_loaded,
            "syncWindowMs": s_status.sync_window_ms,
            "totalSynchronized": s_status.total_synchronized_count,
            "fusionActive": f_status.is_active,
            "totalFused": f_status.total_evaluations,
            "averageCrs": f_status.average_crs,
            "scoringConfigVersion": f_status.scoring_config_version,
            "contextOperatingMode": ctx_state.operating_mode.value,
            "safetyActiveState": saf_status.active_state.value,
            "isEmergencyLatched": saf_status.is_emergency_latched,
            "pendingConfirmations": saf_status.pending_confirmations_count,
            "totalAuthorized": saf_status.total_green,
            "totalRejected": saf_status.total_red,
            "totalEmergency": saf_status.total_emergency,
            "simulationActiveCommand": sim_state.active_command,
            "simulationSpeedMultiplier": sim_state.speed_multiplier,
            "simulationPaused": sim_state.is_paused,
            "simulationCollision": sim_state.is_collision,
            "simulationBoundaryHit": sim_state.boundary_hit,
        },
    )
