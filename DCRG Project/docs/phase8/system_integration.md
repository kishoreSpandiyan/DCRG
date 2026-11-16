# DCRG Phase 8 – System Integration & Pipeline Architecture

## 1. End-to-End Operational Pipeline

The DCRG platform fuses asynchronous multi-modal operator telemetry into a deterministic, explainable safety pipeline. The complete data path links all subsystems developed across Phases 1 through 7:

```
[ Operator Voice Audio ]               [ Joystick Deflection ]
          |                                       |
   (Phase 3 Engine)                        (Phase 2 Engine)
          |                                       |
    VoiceEvent                              JoystickEvent
          \                                      /
           +-----------------+------------------+
                             |
                             v
           [ Event Synchronization Engine (Phase 4) ]
                             |
                     CorrelatedEvent
                             |
                             v
           [ Multi-factor Fusion Engine & CRS (Phase 5) ]
                             |
                        FusionResult
                             |
                             v
           [ Tiered Safety Authorization Engine (Phase 6) ]
                             |
                       SafetyDecision
                             |
                             v
           [ Simulated Command Gateway (Phase 7 Interlock) ]
                             |
                     AuthorizedCommand
                             |
                             v
           [ 2D Kinematic Robot Simulator (Phase 7 Engine) ]
                             |
                             v
             [ Persistent SQLite Audit Log (Phase 8) ]
```

---

## 2. Subsystem Interface Contracts

### 2.1 Voice Subsystem Contract (`VoiceEvent`)
- **Event ID**: UUID string (`v-xxxx`).
- **Timestamp**: High-precision Unix epoch seconds ($t_v$).
- **Recognized Command**: String token (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`, `UNKNOWN`).
- **Raw Transcript**: Transcribed acoustic speech text.
- **Confidence Scores**: Recognition confidence ($c_{\text{rec}} \in [0, 1]$) and classification confidence ($c_{\text{intent}} \in [0, 1]$).
- **Prosody Metrics**: Pitch ($F_0$), RMS energy, jitter, and normalized stress factor ($S_v \in [0, 1]$).

### 2.2 Joystick Subsystem Contract (`JoystickEvent`)
- **Event ID**: UUID string (`j-xxxx`).
- **Timestamp**: High-precision Unix epoch seconds ($t_j$).
- **Axis Telemetry**: $X$ lateral deflection $[-1.0, 1.0]$, $Y$ longitudinal deflection $[-1.0, 1.0]$ ($+Y$ is forward in DCRG Cartesian convention).
- **Polar Magnitude**: Radial intensity $r = \sqrt{x^2 + y^2}$, normalized to $[0, 1]$.
- **Directional Categorization**: Cardinal/diagonal direction or `NEUTRAL`.
- **Button States**: Boolean array of physical/virtual trigger states.
- **Input Source**: `PHYSICAL_JOYSTICK` or `VIRTUAL_JOYSTICK`.

### 2.3 Synchronization Engine Contract (`CorrelatedEvent`)
- **Correlation ID**: UUID string (`corr-xxxx`).
- **Timestamp**: Canonical correlation epoch time ($t_{\text{corr}} = \max(t_v, t_j)$).
- **Time Difference**: Absolute offset $\Delta t = |t_v - t_j| \times 1000\text{ ms}$.
- **Status**: `SYNCHRONIZED`, `UNSYNCHRONIZED`, `VOICE_ONLY`, `JOYSTICK_ONLY`, `TIMEOUT`, `STALE_EVENT`.
- **Modality Flags**: `voice_available: bool`, `joystick_available: bool`.

### 2.4 Fusion Engine Contract (`FusionResult`)
- **Fusion ID**: UUID string (`fuse-xxxx`).
- **Command Reliability Score (CRS)**: Scalar composite score $S_{\text{CRS}} \in [0, 100]$.
- **Factor Decomposition**:
  - $R_s$: Semantic reliability factor $[0, 1]$.
  - $A_m$: Motor agreement factor $[0, 1]$ based on vector cosine difference $\cos(\Delta\theta)$.
  - $C_c$: Contextual consistency factor $[0, 1]$.
  - $E_c$: Evidence completeness factor $[0, 1]$.
- **Contradiction Flag**: `is_contradiction: bool` (true when $\Delta\theta > 90^\circ$ under active inputs).
- **Veto Enforcement**: If `is_contradiction == True`, CRS is strictly clamped to $\min(S_{\text{CRS}}, 30.0)$.

### 2.5 Safety Authorization Contract (`SafetyDecision`)
- **Decision ID**: Cryptographic token string (`DEC-xxxx`).
- **Authorization State**: Enum (`GREEN`, `YELLOW`, `RED`, `EMERGENCY`).
- **Decision**: `AUTHORIZED`, `HELD_FOR_CONFIRMATION`, `REJECTED`, `LATCHED_EMERGENCY`.
- **Reason**: Human-readable explainable rationale string.
- **Command**: Authorized command token (`FORWARD`, `STOP`, etc.) if approved, else `None`.
- **Expiration TTL**: Token validity lifetime (default 3.0 seconds).
- **Gateway Signature**: SHA-256 HMAC cryptographic token string.

### 2.6 Simulation Execution Contract (`RobotState`)
- **Robot ID**: Identifier string.
- **Coordinates**: Cartesian $(X, Y)$ in grid meters.
- **Heading**: Orientation angle $\theta$ in radians.
- **Velocity**: Current linear speed $v$ (m/s) and angular speed $\omega$ (rad/s).
- **Execution State**: `IDLE`, `MOVING`, `BLOCKED`, `COLLISION_STOP`, `EMERGENCY_STOP`.
- **Traveled Path**: Historical list of recent positions for path replay.

---

## 3. Communication & WebSocket Protocols

The DCRG backend exposes unified REST and WebSocket endpoints under `/api/v1`:

| Endpoint | Protocol | Purpose |
| :--- | :--- | :--- |
| `/api/v1/ws/all` | WebSocket | Multi-modal multiplexed telemetry streaming (Voice, Stick, Sync, Fusion, Safety, Sim) |
| `/api/v1/system/overview` | REST GET | Consolidated System Overview summary |
| `/api/v1/system/health/detailed` | REST GET | Diagnostics probe results across all subsystems |
| `/api/v1/system/config` | REST GET/POST | Dynamic parameter catalog inspect & update |
| `/api/v1/system/config/reset` | REST POST | Reverts runtime configuration to safe factory defaults |
| `/api/v1/system/logs` | REST GET | Forensic query endpoint with level, phase, time filtering |
| `/api/v1/system/logs/export` | REST GET | Streaming download of audit records as JSON or CSV |
| `/api/v1/system/timeline` | REST GET | Recent chronological event timeline feed |
| `/api/v1/safety/confirm` | REST POST | Operator confirmation endpoint for `YELLOW` state commands |
| `/api/v1/safety/emergency-stop` | REST POST | Global Emergency Stop latch trigger |
| `/api/v1/safety/reset-emergency` | REST POST | Global Emergency Stop reset trigger |

---

## 4. Architectural Invariants

1. **Simulation Containment**: Under no circumstances does the backend communicate with physical motor drives or robotic actuators. All gateway-approved tokens dispatch exclusively to the simulated kinematic vehicle.
2. **Deterministic Priority**: E-Stop overrides all pending tokens, active trajectories, and held commands.
3. **Contradiction Ceiling**: No command exhibiting motor contradiction ($\Delta\theta > 90^\circ$ between speech and deflection) can exceed a CRS score of 30.0 or be evaluated as `GREEN`.
4. **Token Expiration**: Any authorized command token not received by the simulator gateway within its 3.0-second TTL is discarded.
5. **Persistent Audit Trail**: Every voice transcript, joystick deflection, synchronization event, fusion score, safety decision, and configuration mutation is written to SQLite WAL storage.

