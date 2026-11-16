"""
Dynamic Command Reliability Graph (DCRG)
FastAPI Main Application Entrypoint.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from app.database.audit_hooks import install_audit_subscribers
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.voice_engine.manager import voice_manager
from app.modules.sync_engine.manager import sync_manager
from app.modules.fusion_engine.manager import fusion_manager
from app.modules.safety_engine.manager import safety_manager
from app.modules.simulation_engine.manager import simulation_manager
from app.api.v1.endpoints.joystick import websocket_joystick_stream
from app.api.v1.endpoints.voice import websocket_voice_stream
from app.api.v1.endpoints.sync import websocket_sync_stream
from app.api.v1.endpoints.fusion import websocket_fusion_stream
from app.api.v1.endpoints.safety import websocket_safety_stream
from app.api.v1.endpoints.simulation import simulation_stream_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize audit hooks, hardware/virtual joysticks, voice, sync, fusion, safety, & simulation
    install_audit_subscribers()
    actuator_manager.start()
    voice_manager.start()
    sync_manager.start()
    fusion_manager.start()
    safety_manager.start()
    simulation_manager.start()
    yield
    # Shutdown: Cleanly stop all background threads
    actuator_manager.stop()
    voice_manager.stop()
    sync_manager.stop()
    fusion_manager.stop()
    safety_manager.stop()
    simulation_manager.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Real-time multi-modal command verification, safety authorization, and 2D simulation engine.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Direct Root-level WebSocket Routes
@app.websocket("/ws/joystick/stream")
async def root_websocket_joystick_stream(websocket: WebSocket):
    await websocket_joystick_stream(websocket)


@app.websocket("/ws/voice/stream")
async def root_websocket_voice_stream(websocket: WebSocket):
    await websocket_voice_stream(websocket)


@app.websocket("/ws/sync/stream")
async def root_websocket_sync_stream(websocket: WebSocket):
    await websocket_sync_stream(websocket)


@app.websocket("/ws/fusion/stream")
async def root_websocket_fusion_stream(websocket: WebSocket):
    await websocket_fusion_stream(websocket)


@app.websocket("/ws/safety/stream")
async def root_websocket_safety_stream(websocket: WebSocket):
    await websocket_safety_stream(websocket)


@app.websocket("/ws/simulation/stream")
async def root_websocket_simulation_stream(websocket: WebSocket):
    await simulation_stream_endpoint(websocket)


@app.get("/", tags=["Root"])
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "phase": "Phase 8 – Complete Dashboard & End-to-End Integration",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
        "joystick_status": f"{settings.API_V1_STR}/joystick/status",
        "voice_status": f"{settings.API_V1_STR}/voice/status",
        "sync_status": f"{settings.API_V1_STR}/sync/status",
        "fusion_status": f"{settings.API_V1_STR}/fusion/status",
        "safety_status": f"{settings.API_V1_STR}/safety/status",
        "simulation_state": f"{settings.API_V1_STR}/simulation/state",
        "system_overview": f"{settings.API_V1_STR}/system/overview",
        "detailed_health": f"{settings.API_V1_STR}/system/health/detailed",
        "system_config": f"{settings.API_V1_STR}/system/config",
        "audit_logs": f"{settings.API_V1_STR}/system/logs",
        "ws_joystick": "/ws/joystick/stream",
        "ws_voice": "/ws/voice/stream",
        "ws_sync": "/ws/sync/stream",
        "ws_fusion": "/ws/fusion/stream",
        "ws_safety": "/ws/safety/stream",
        "ws_simulation": "/ws/simulation/stream",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
