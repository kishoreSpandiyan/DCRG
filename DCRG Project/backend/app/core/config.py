"""
Core Configuration and System-Wide Settings for DCRG.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Dynamic Command Reliability Graph (DCRG)"
    VERSION: str = "0.4.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Subsystem Flags
    HARDWARE_ENABLED: bool = False  # Physical joystick/serial integration
    SIMULATION_ENABLED: bool = True
    AUDIT_LOG_ENABLED: bool = True
    VOICE_ENABLED: bool = True
    SYNC_ENABLED: bool = True
    FUSION_ENABLED: bool = True

    # Fusion Threshold Defaults
    CRS_AUTHORIZATION_THRESHOLD: float = 0.85  # Minimum score required to authorize movement
    PROSODY_STRESS_THRESHOLD: float = 0.60    # Prosody stress trigger level

    # Voice & Speech Recognition Configuration (Phase 3)
    WHISPER_MODEL_SIZE: str = "tiny.en"       # "tiny.en" for low-latency CPU, or "base.en"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = "en"              # Extensible to "ta" (Tamil)
    VOICE_SAMPLE_RATE: int = 16000            # Mono 16 kHz native to Whisper
    VOICE_FRAME_DURATION_MS: int = 30         # 30 ms frames (480 samples)
    VOICE_BUFFER_SECONDS: float = 3.0         # Sliding context window
    VOICE_RECOGNITION_CONFIDENCE_THRESHOLD: float = 0.40  # Minimum confidence for clear speech (tuned for low-gain mics)
    VOICE_CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.70
    VOICE_SILENCE_ENERGY_THRESHOLD: float = 0.0012        # Optimized for Type-C headsets & low-gain mics (lowered from 0.005)
    VOICE_AUTO_START_MIC: bool = False                    # Do not capture audio automatically until requested
    DEFAULT_MICROPHONE_DEVICE_INDEX: Optional[int] = None

    # Event Synchronization & Correlation Configuration (Phase 4)
    SYNC_WINDOW_MS: float = 150.0              # Default correlation matching window per DCRG-ARCH-004
    SYNC_MAX_EVENT_AGE_MS: float = 2500.0      # Bounded multi-modal retention window (allows async STT to pair)
    SYNC_BUFFER_CAPACITY: int = 200            # Queue capacity per modality buffer
    SYNC_CLOCK_DRIFT_THRESHOLD_MS: float = 50.0 # Warn when client/server clock skew exceeds this
    SYNC_DELAYED_THRESHOLD_MS: float = 200.0   # Flag events as delayed if ingestion latency > 200ms
    SYNC_DUPLICATE_CACHE_SIZE: int = 1000      # Max seen event IDs tracked to drop duplicates

    # Fusion Engine & Command Reliability Score (CRS) Configuration (Phase 5)
    # Prototype baseline weights per DCRG-ARCH-005: Ws = 0.35, Wm = 0.50, Wc = 0.15
    CRS_WEIGHT_SEMANTIC: float = 0.35
    CRS_WEIGHT_MOTOR: float = 0.50
    CRS_WEIGHT_CONTEXT: float = 0.15
    CRS_STRESS_DAMPING: float = 0.25           # Beta coefficient for prosody stress attenuation
    CRS_CONTRADICTION_CAP: float = 30.0        # Max CRS ceiling when contradiction is asserted
    CRS_CONTRADICTION_WHISPER_MIN: float = 0.60 # Minimum Whisper confidence to trigger veto (calibrated to 0.60 to capture all speech commands while filtering noise < 0.60)
    CRS_CONTRADICTION_JOYSTICK_MIN: float = 0.30 # Minimum stick deflection to trigger veto
    CRS_JOYSTICK_DEADZONE: float = 0.08        # Radial deadzone threshold
    CRS_SCORING_CONFIG_VERSION: str = "v1.0-prototype"

    # Tiered Safety Authorization Engine Configuration (Phase 6)
    SAFETY_GREEN_THRESHOLD: float = 65.0       # CRS >= 65 required for automatic GREEN authorization (calibrated for real speech-motor agreement)
    SAFETY_YELLOW_THRESHOLD: float = 50.0      # 50 <= CRS < 65 enters YELLOW hold requiring confirmation
    SAFETY_CONFIRMATION_TIMEOUT_MS: float = 5000.0  # Time allowed for human confirmation before auto-reject
    SAFETY_AUTH_TOKEN_TTL_MS: float = 2000.0   # Lifetime of simulation execution token
    SAFETY_GATEWAY_SIMULATION_ONLY: bool = True  # Strict safeguard: physical actuators disabled
    SAFETY_EMERGENCY_RESET_PIN: str = "1234"   # Prototype pin for authorized emergency unlatch

    # Robot Simulation & Command Execution Configuration (Phase 7)
    SIMULATION_BOUNDARY_MIN_X: float = -50.0   # Environment boundary limits in meters
    SIMULATION_BOUNDARY_MAX_X: float = 50.0
    SIMULATION_BOUNDARY_MIN_Y: float = -50.0
    SIMULATION_BOUNDARY_MAX_Y: float = 50.0
    SIMULATION_BASE_SPEED: float = 3.0         # Robot maximum linear speed (m/s)
    SIMULATION_TURN_SPEED_DEG: float = 120.0   # Robot angular rotation speed (deg/s)
    SIMULATION_TICK_RATE_HZ: float = 20.0      # Physics loop update rate
    SIMULATION_ROBOT_RADIUS: float = 1.0       # Collision radius (m)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
