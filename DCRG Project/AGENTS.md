# AGENTS.md – Permanent Development & Operational Guardrails

This document establishes the binding architectural, safety, and coding rules for all AI agents, pair programmers, and human contributors working on the **Dynamic Command Reliability Graph (DCRG)** codebase.

---

## 1. Safety & Verification Guardrails (Absolute Priority)

### 1.1 Never Allow Frontend Authorization of Physical Robot Movement
- The React frontend is an observation, visualization, and operator interaction surface only.
- **Under no circumstances may client-side JavaScript or browser-side logic emit authorization tokens or drive motor actuators.**
- Movement authorization is the sole, non-delegable responsibility of the backend `safety_engine` running on trusted compute.

### 1.2 Emergency Stop (E-STOP) Independence
- The Emergency Stop system **MUST NOT** depend on AI processing, machine learning inference, speech recognition, or statistical fusion.
- E-STOP signals must be processed synchronously and deterministically via direct interrupt/state machine logic with \(O(1)\) time complexity.
- Triggering E-STOP immediately overrides all active authorizations and halts movement commands.

### 1.3 Fail Safely on Missing or Stale Data
- Any sensor or telemetry channel (voice transcript, prosody metrics, joystick position) with missing packets or staleness exceeding threshold (default: 150ms) must immediately trigger a fail-safe state.
- In the presence of stale data, the system must downgrade authorization or transition to a safety hold (`DEGRADED` or `HOLD`). Never extrapolate or predict missing safety-critical inputs.

### 1.4 Do Not Fabricate Sensor or Hardware Data
- Agents must never generate fabricated, simulated, or synthetic responses disguised as real hardware.
- If a physical USB/Bluetooth joystick or serial microcontroller is not connected, the system must truthfully report `connected: false` and `hardwareDetected: false`.
- Do not generate fake successful test results or fake hardware handshakes.

### 1.5 Strict Separation of Real Hardware and Simulation
- Real hardware interfaces (`backend/app/hardware/`, `hardware/`) and simulation subsystems (`backend/app/simulation/`, `frontend/src/simulation/`) must remain architecturally separated.
- All telemetry payloads emitted by simulation engines must be explicitly tagged with:
  ```json
  { "is_simulation": true }
  ```
- Simulated telemetry must never be injected into physical actuator channels.

### 1.6 Prototype Safety Disclaimer
- **Do not claim the prototype is an industrial certified safety system.**
- DCRG is an experimental research and development prototype evaluating multi-modal command verification concepts.
- It is NOT certified under ISO 13849 (Performance Levels), IEC 61508 (SIL), or ISO 10218 (Industrial Robot Safety), and must never be deployed on machinery capable of causing physical harm without certified external safety interlocks.

---

## 2. Software Architecture & Engineering Standards

### 2.1 Modular Architecture
- Every module must maintain high cohesion and low coupling.
- Keep the six DCRG core engines strictly separated in `backend/app/modules/`:
  - `voice_engine/`: Speech ingestion and STT.
  - `prosody_engine/`: Acoustic stress and pitch feature extraction.
  - `semantic_engine/`: Intent extraction and NLP command classification.
  - `actuator_engine/`: Joystick input ingestion, deadzone filtering, and rate limiting.
  - `fusion_engine/`: Multi-modal graph alignment and CRS scoring.
  - `safety_engine/`: Authorization state machine and threshold gating.
  - `context_engine/`: Operational environment state tracking.

### 2.2 Python Type Hints & Code Quality
- All Python backend code must use PEP 484 type annotations (`typing`, Pydantic models).
- Do not use bare `except:` blocks; always catch specific exceptions and log with context.
- Use asynchronous (`async`/`await`) patterns where I/O bound (WebSockets, network, database) and thread/process pools for CPU-heavy tasks.

### 2.3 Frontend TypeScript Discipline
- All frontend code must use TypeScript with strict typing.
- Avoid the use of `any`; define explicit interfaces in `frontend/src/types/`.
- Ensure clean separation between presentation components and API/WebSocket services.

### 2.4 Error Handling & Graceful Degradation
- All external inputs (audio chunks, serial packets, WebSocket frames) must be validated using Pydantic or TypeScript schema guards.
- Corrupted packets must be safely rejected, logged to the audit log, and never allowed to crash the service loops.

### 2.5 Unit & Integration Testing
- Every new engine, calculation, and safety gate must be accompanied by comprehensive Pytest tests in `backend/tests/`.
- Tests must verify normal execution paths, edge cases, and safety fault-injection scenarios (e.g., conflicting commands, network timeouts, sudden disconnections).

