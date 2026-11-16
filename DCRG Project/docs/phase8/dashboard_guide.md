# DCRG Phase 8 – Command-Control Dashboard Operator Guide

## 1. Overview & Purpose

The DCRG (Dynamic Command Reliability Graph) Dashboard provides a centralized, industrial-grade operational interface for human operators. It delivers real-time telemetry across all 8 phases of the DCRG mission architecture, integrating multi-modal telemetry (speech recognition and prosody, physical/virtual flight stick deflection, temporal synchronization, multi-factor Command Reliability Scoring, four-state safety gating, and high-fidelity 2D kinematic robot simulation).

> [!IMPORTANT]
> The DCRG Dashboard operates in **SIMULATION** mode. No physical motors, industrial manipulators, or live actuators are energized. All motion commands drive the internal simulated 2D robot vehicle within the software safety boundary.

---

## 2. Dashboard Top Bar & Global Controls

Located persistently at the top of the interface:

- **System Status Indicator**: Displays real-time WebSocket connectivity (`ONLINE` / `DISCONNECTED`) with auto-reconnection and a manual reconnect button.
- **Operating Mode Badge**: Fixed to `SIMULATION` with an amber industrial indicator badge.
- **Active Operator**: Shows current operator credential/callsign (`OPERATOR_01`).
- **Emergency Stop (E-STOP)**:
  - Large red high-visibility actuator.
  - **Clicking Trigger**: Immediately latches the safety system into state `EMERGENCY`. Both the gateway and robot simulator immediately zero all velocities, clamp rotation, and refuse all new command dispatches until manually disengaged.
  - **Reset Button**: Appears when E-Stop is active, allowing operators to reset the latch back to nominal standby.

---

## 3. Section A: System Overview Bar

The System Overview Bar spans the full viewport width beneath the navigation header and offers rapid health glanceability:

| Indicator Tile | Telemetry Source | Description | Normal Status |
| :--- | :--- | :--- | :--- |
| **Connection** | Global WebSocket | Real-time bi-directional pipeline connectivity | `ONLINE` |
| **Voice Engine** | Voice Subsystem | Microphone device state, active listener | `READY` / `LISTENING` |
| **Joystick** | Actuator Subsystem | Physical USB / Virtual controller state | `CONNECTED` |
| **Sync Engine** | Correlation Engine | Sliding temporal correlation status | `NOMINAL` |
| **Fusion Engine**| Multi-factor CRS | Multi-factor fusion engine readiness | `ONLINE` |
| **Safety Gate** | Authorization | Current authorization state and decision | `STANDBY` / `AUTHORIZED` |
| **Simulator** | Kinematics Engine | Kinematic simulation step loop | `RUNNING` |

---

## 4. Navigation Tabs

The dashboard provides dedicated tabbed views tailored to operational roles:

1. **Command Center**: The primary operational screen presenting the unified real-time workflow (System Overview Bar, Voice & Joystick Quick Monitors, Fusion Score gauge, Safety Authorization state, Simulation viewport, and Live Event Timeline).
2. **Multi-Modal Monitors**: Deep-dive telemetry for acoustic prosody, Whisper recognition metrics, and dual-axis flight stick deflection.
3. **Fusion & Safety**: Mathematical decomposition of the Command Reliability Score (Semantic, Motor, Contextual, Completeness) and the Tiered Safety Engine.
4. **Robot Simulation**: Dedicated large-canvas simulation viewport with obstacle editor, coordinate tracker, and execution replay controls.
5. **Audit Logs**: Forensic query engine with multi-criteria filtering, event inspection, and CSV/JSON export.
6. **Configuration**: Live tunable runtime parameters (weights, deadzones, windows, thresholds) backed by validation rules.
7. **System Health**: Subsystem probe table displaying ping latencies, error states, and component dependencies.

---

## 5. Section B: Voice Monitor

The Voice Monitor provides real-time visibility into acoustic telemetry:
- **Microphone Status**: `CONNECTED`, `MUTED`, `DISCONNECTED`, or `ERROR`.
- **Live Transcript**: Dynamic text box displaying the latest transcribed speech string.
- **Recognized Command**: Standardized command token mapped from vocabulary (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`, `UNKNOWN`).
- **Confidence Metrics**: Dual progress meters displaying Acoustic / Whisper recognition confidence ($c_{\text{rec}} \in [0, 1]$) and Intent classification confidence ($c_{\text{intent}} \in [0, 1]$).
- **Prosody Analytics**:
  - Fundamental frequency ($F_0$ pitch in Hz).
  - Energy / RMS volume (dB).
  - Speaking rate (words/sec).
  - Pitch jitter and dynamic stress indicator ($S_v \in [0, 1]$).
- **Latency**: Speech processing pipeline latency in milliseconds.

---

## 6. Section C: Joystick Monitor

The Joystick Monitor renders input parameters from physical flight sticks or virtual controls:
- **Device Info**: Device name (e.g., `Logitech Extreme 3D Pro`), input source (`PHYSICAL` or `VIRTUAL`), and connection bus (`USB` / `BLUETOOTH`).
- **Axis Telemetry**: Real-time readouts of $X$ (lateral) and $Y$ (longitudinal) axes, clamped to $[-1.0, +1.0]$, plus polar magnitude deflection intensity ($r \in [0, 1]$).
- **Directional Classification**: Categorized direction (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `FORWARD_LEFT`, `NEUTRAL`, etc.).
- **Button States**: Digital bitfield array indicating active trigger and auxiliary buttons.
- **Deadzone Visualization**: Graphic circle showing configured radial deadzone threshold.

---

## 7. Section D: Synchronization Monitor

The Synchronization Monitor exposes correlation metrics between voice and joystick inputs:
- **Temporal Alignment ($\Delta t$)**: Offset in milliseconds ($|t_v - t_j|$).
- **Correlation Status**: `SYNCHRONIZED` (within window $\le 150\text{ ms}$), `UNSYNCHRONIZED`, `VOICE_ONLY`, `JOYSTICK_ONLY`, or `STALE_EVENT`.
- **Active Window**: Currently configured sliding temporal tolerance ($W_{\text{sync}}$).
- **Stale / Missing Warnings**: Alerts displayed when event arrival delta exceeds maximum freshness limit.

---

## 8. Section E: Fusion Engine & CRS

The Fusion Engine display visualizes multi-factor evidence synthesis:
- **Command Reliability Score (CRS)**: Prominent radial gauge (0 to 100) indicating synthesized reliability.
- **Sub-Score Decomposition**:
  - **Semantic Reliability ($R_s$)**: Voice confidence attenuated by operator acoustic stress.
  - **Motor Agreement ($A_m$)**: Directional vector alignment ($\cos \Delta\theta$) between voice intention and stick vector.
  - **Contextual Consistency ($C_c$)**: Alignment with mission phase, obstacle clearances, and battery state.
  - **Evidence Completeness ($E_c$)**: Multi-modal presence factor ($1.0$ for dual input, $0.5$ for degraded single modality).
- **Contradiction Veto Warning**: Flashing badge when opposing commands (e.g. Spoken FORWARD vs Joystick BACKWARD) trigger the safety veto filter (CRS capped at $\le 30.0$).

---

## 9. Section F: Tiered Safety Authorization

The Safety Authorization panel displays the verdict rendered by the deterministic rule engine:
- **Four States**:
  - `GREEN` (CRS $\ge 85$, Complete Evidence, Synchronized): Dispatched immediately with cryptographic gateway token.
  - `YELLOW` (CRS $50 - 84$, Missing Modality or Moderate Stress): Motion held. Operator must manually click **CONFIRM COMMAND** to dispatch.
  - `RED` (CRS $< 50$ or Contradiction Detected): Command rejected and blocked.
  - `EMERGENCY`: E-Stop active or safety perimeter breach. Hard lockout.
- **Decision Reason & Metadata**: Explicit reason string, Unique Decision ID, and Token TTL countdown timer.

---

## 10. Section G: Robot Simulation Viewport

The Robot Simulation panel displays the interactive 2D simulation environment:
- **Grid Canvas**: 2D coordinate space ($[0, 100] \times [0, 100]$ meters) with grid lines, coordinate origin, and perimeter safety boundary.
- **Robot Vehicle**: Rendered vehicle with orientation triangle showing heading ($\theta$), position coordinates $(X, Y)$, and linear velocity.
- **Obstacle Management**: Interactive obstacle fields with collision avoidance warning rings.
- **Execution Trajectory**: Real-time breadcrumb trail showing recent movement history.
- **Controls**: Speed scale multiplier, reset robot position button, and trajectory clear button.

