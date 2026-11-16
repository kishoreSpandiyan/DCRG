# DCRG Phase 7 – Simulation Controls & Dashboard Visualizer

## 1. Overview

The Phase 7 Robot Simulation Panel (`RobotSimulationPanel.tsx`) provides an interactive interface for supervising simulated vehicle behavior, tracking multi-modal pipeline correlation, inspecting kinematic telemetry, and executing administrative controls.

---

## 2. Interactive HTML5 Canvas Visualizer

The visualizer renders the continuous 2D environment at 20 Hz:
- **Dimensions:** $540 \times 540$ pixels, mapped to $[-50\text{ m}, +50\text{ m}]$.
- **Grid:** $10\text{ m}$ spacing intervals with highlighted coordinate center axes $(0, 0)$.
- **Vehicle Rendering:**
  - Orientable rectangular chassis with directional arrow indicating instantaneous heading $\theta$.
  - Circular collision envelope halo (color-coded by authorization state: Emerald for `GREEN`, Amber for `YELLOW`, Rose for `RED`, Bright Pulsating Red for `EMERGENCY`).
  - Real-time coordinate tag $(X, Y)$ floating beside the chassis.
- **Dynamic Trail:** Cyan path connecting breadcrumbs from recent vehicle motions.
- **Static Obstacles:** Gradient-shaded circular pylons with collision safety radii and identifier tags.
- **Diagnostic Overlays:** Visual hazard warnings when boundary limits or obstacles are contacted.

---

## 3. Telemetry HUD

| Metric | Source | Description |
| :--- | :--- | :--- |
| **Position $(X, Y)$** | `RobotPose` | Real-time vehicle coordinates in meters |
| **Heading ($\theta$)** | `RobotPose` | Rotation in degrees ($0^\circ = \text{North}, 90^\circ = \text{East}, 180^\circ = \text{South}, 270^\circ = \text{West}$) |
| **Linear Velocity ($v$)** | `RobotPose` | Translation speed in meters/second ($0.0$ to $3.0\text{ m/s}$) |
| **Angular Velocity ($\omega$)**| `RobotPose` | Rotational alignment speed in deg/s ($0.0$ to $120.0^\circ/\text{s}$) |
| **Active Primitive** | `SimulationState` | Current active motion primitive (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`) |
| **Authorization State** | `SimulationState` | `GREEN`, `YELLOW`, `RED`, or `EMERGENCY` |
| **Command Reliability (CRS)**| `FusionResult` | Score between $0.0$ and $100.0$ |
| **Voice Command** | `VoiceEvent` | Most recent transcript classification |
| **Joystick Vector** | `JoystickEvent` | Most recent physical or virtual deflection |

---

## 4. Control Operations

The control bar situated beneath the canvas supports the following operations:

1. **Pause / Resume:**
   - Temporarily halts time-stepped kinematic integration while preserving vehicle coordinates and state.
   - Endpoint: `POST /api/v1/simulation/control` with `action: "PAUSE"` or `"RESUME"`.
2. **Reset Origin:**
   - Resets the simulated vehicle coordinates to origin $(0.0, 0.0)$, resets heading to $0.0^\circ$, zeroes velocities, and clears collision flags.
   - Endpoint: `POST /api/v1/simulation/reset`.
3. **Speed Multiplier:**
   - Adjusts simulation time scaling to $0.5\times$, $1.0\times$, or $2.0\times$.
   - Endpoint: `POST /api/v1/simulation/control` with `action: "SET_SPEED"`.
4. **Software Emergency Stop:**
   - Instantly engages the Phase 6 Emergency Stop latch, arrests robot velocity, cancels all pending commands, and engages safety lockout until authorized operator PIN reset (`1234`).
   - Endpoint: `POST /api/v1/safety/estop`.

---

## 5. High-Frequency WebSocket Streaming

- **Path:** `/ws/simulation/stream`
- **Initial Connection Handshake:** Returns `SIMULATION_INIT` payload containing full state and 10 most recent execution logs.
- **Streaming Updates:** Broadcasts `SIMULATION_UPDATE` payload whenever the simulation steps forward.
- **Bidirectional Inbound Messages:** Accepts `PING`, `PAUSE`, `RESUME`, `RESET`, and `SET_SPEED` commands over WebSocket.

