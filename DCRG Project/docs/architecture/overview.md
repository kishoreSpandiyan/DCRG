# DCRG System Architecture Documentation Index

> **Dynamic Command Reliability Graph (DCRG)**  
> **Phase 1 – Complete System Architecture & Detailed Technical Specifications**

---

## Architecture Documentation Suite

| Document | File | Summary |
| :--- | :--- | :--- |
| **01. System Architecture** | [`system_architecture.md`](./system_architecture.md) | High-level system topology, six core engines, end-to-end latency budget, and component communication flows. |
| **02. Voice Processing** | [`voice_processing_architecture.md`](./voice_processing_architecture.md) | Audio capture, Silero VAD, Faster-Whisper STT, Librosa prosody/stress extraction, and canonical command lexicon. |
| **03. Joystick Subsystem** | [`joystick_architecture.md`](./joystick_architecture.md) | Dual-mode input architecture (Mode A: Physical USB/BT via Pygame; Mode B: Virtual canvas/WASD), deadzones, and normalization. |
| **04. Event Synchronization**| [`event_synchronization.md`](./event_synchronization.md) | Independent temporal alignment service, sliding buffer mechanics, $\Delta t \le 150\text{ms}$ matching window, and out-of-order handling. |
| **05. Fusion Engine Design** | [`fusion_engine_design.md`](./fusion_engine_design.md) | Topological reliability graph, CRS formula $W_s \cdot S + W_m \cdot M + W_c \cdot C$, and the Contradiction Veto Filter. |
| **06. Safety State Machine** | [`safety_state_machine.md`](./safety_state_machine.md) | 4-state deterministic finite state machine (`GREEN`, `YELLOW`, `RED`, `EMERGENCY`), decision tables, and fail-safe transitions. |
| **07. Robot Simulation** | [`robot_simulation_architecture.md`](./robot_simulation_architecture.md) | 2D differential-drive kinematics model, token-gated simulation gateway, obstacle avoidance, and state management. |
| **08. Backend & WebSockets** | [`backend_api_design.md`](./backend_api_design.md) | FastAPI RESTful route specifications (`/api/v1`) and high-throughput bidirectional WebSocket telemetry protocol. |
| **09. Database Schema** | [`database_schema.md`](./database_schema.md) | SQLite WAL mode audit trail, 9 relational entity models, foreign key relationships, and forensic logging. |
| **10. Operator Dashboard** | [`dashboard_architecture.md`](./dashboard_architecture.md) | React 19 + TypeScript component hierarchy, 12 primary dashboard modules, Recharts widgets, and hardware vs simulation badging. |
| **11. Data Contracts** | [`data_contracts.md`](./data_contracts.md) | Formal JSON schemas for Voice, Prosody, Joystick, Synchronized, Fusion, Safety, Robot, and E-STOP events. |
| **12. Failure & Security** | [`failure_handling.md`](./failure_handling.md) | Fail-closed triage matrix for sensor disconnection, packet corruption, replay attacks, mTLS, and watchdog interlocks. |
