# DCRG Phase 8 – System Health Diagnostics & Fail-Safe Architecture

## 1. Diagnostics Probe Architecture

The DCRG System Health monitoring framework delivers continuous visibility into the operational readiness of all core pipeline components. Diagnostics run active probes against internal services without masking failures or reporting false healthy states.

Probes are queried via `GET /api/v1/system/health/detailed` and rendered in real-time in the **System Health** panel on the operator dashboard.

---

## 2. Monitored Subsystems & Health Probes

| Subsystem | Health Probe Mechanism | Healthy Condition | Degraded / Failed Condition |
| :--- | :--- | :--- | :--- |
| **Backend Core** | FastAPI process memory, active event loop | Uptime $>0$, memory within nominal limits | Event loop blocked or unhandled exception |
| **Frontend Web** | WebSocket client heartbeat & round-trip ping | RTT $\le 100\text{ ms}$, continuous socket frame streaming | Disconnected socket, WebSocket reconnect loop |
| **Voice Engine** | PortAudio / SoundDevice device handle query | Microphone attached, status `READY` or `LISTENING` | `MUTED` (Degraded), `DISCONNECTED` or `ERROR` (Failed) |
| **Joystick Engine**| OS joystick driver polling / virtual fallback | Controller connected, axis polling active | `DISCONNECTED` (Failed), virtual fallback active (Degraded) |
| **Database** | SQLite WAL file integrity, query execution latency | Read/write test transaction latency $< 5\text{ ms}$ | SQLite disk I/O lock, disk full, or write failure |
| **WebSockets** | Multiplexed `/ws/all` subscriber registry | Active clients receiving frames | Client connection drops, socket buffer overflow |
| **Safety Gateway** | Cryptographic token validator & E-Stop latch probe | HMAC key loaded, E-Stop unlatched | E-Stop latched (Degraded/Safety Lockout), signature error |
| **Robot Simulator**| Kinematic update loop interval (60 Hz) | Step jitter $< 5\text{ ms}$, vehicle in bounds | Collision stop (Degraded), boundary breach, loop freeze |

---

## 3. Health State Classifications

1. **HEALTHY (Green)**:
   - Component is fully operational.
   - All diagnostic checks pass.
   - Latency is within SLA tolerances.

2. **DEGRADED (Yellow)**:
   - Component is functional but running under constrained or non-ideal conditions.
   - Examples: Single modality input active (joystick connected but microphone muted); Virtual joystick in use instead of physical flight stick; E-Stop active; High temporal jitter.

3. **FAILED / OFFLINE (Red)**:
   - Critical component unavailable or disconnected.
   - Examples: Physical joystick unplugged while in strict mode; Microphone device error; Database transaction write failure; Simulator loop frozen.

---

## 4. Fail-Safe Recovery Protocols

- **Fail-Safe Invariant**: If any upstream sensory subsystem (Voice or Joystick) enters `FAILED` or `DISCONNECTED`, the Synchronization Engine immediately drops to single-modality or stale state.
- **Safety Fallback**: The Safety Authorization Engine downgrades any incoming single-modality command to `YELLOW` (requiring explicit human confirmation) or `RED` (if contradictory or missing context), guaranteeing that unverified sensory failures cannot produce autonomous `GREEN` dispatches.
- **Microphone Disconnection**: Voice status shifts to `DISCONNECTED`. Intent confidence drops to 0.0. CRS calculations automatically scale down Evidence Completeness $E_c$ to $0.50$, forcing commands to `YELLOW`.
- **Joystick Disconnection**: Joystick status shifts to `DISCONNECTED`. The actuator subsystem resets axes to neutral $(0.0, 0.0)$ to prevent stuck-deflection "phantom driving".
- **Database Resilience**: SQLite WAL (Write-Ahead Logging) mode guarantees that crash-recovery is atomic. If the database file is temporarily locked, audit events are queued in an in-memory ring buffer until the storage engine acknowledges writes.

