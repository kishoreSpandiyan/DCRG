# Tiered Safety Authorization State Machine Specification

> **Document ID:** DCRG-ARCH-006  
> **Status:** Approved Architecture Draft (Phase 1)  
> **Module Covered:** `safety_engine`

---

## 1. Safety State Machine Architecture

The DCRG Safety Engine governs movement authorization via a deterministic, finite state machine executing in $O(1)$ time complexity on trusted backend compute.

```mermaid
stateDiagram-v2
    [*] --> YELLOW: System Initialization / Standby

    state GREEN {
        description: Command Authorized (CRS >= 85, Agreement Validated)
    }

    state YELLOW {
        description: Hold & Confirm (Ambiguous Input / Stale Data / Low Confidence)
    }

    state RED {
        description: Hazardous Contradiction Hold (Veto Asserted)
    }

    state EMERGENCY {
        description: Deterministic E-STOP (Physical Relay Cut / Zero Motion Lockout)
    }

    %% Transitions from YELLOW
    YELLOW --> GREEN: CRS >= 85 AND No Veto AND Fresh Telemetry
    YELLOW --> RED: Direct Contradiction Detected (Veto Asserted)
    YELLOW --> EMERGENCY: Hard E-STOP Pressed (Hardware or Software)

    %% Transitions from GREEN
    GREEN --> YELLOW: CRS drops < 85 OR Input Unclear OR Telemetry Stale (>150ms)
    GREEN --> RED: Opposite Command Issued OR Veto Triggered
    GREEN --> EMERGENCY: Hard E-STOP Pressed OR Physical Guard Trip

    %% Transitions from RED
    RED --> YELLOW: Inputs return to Neutral Center (t_hold > 500ms)
    RED --> EMERGENCY: Hard E-STOP Pressed

    %% Transitions from EMERGENCY
    EMERGENCY --> YELLOW: Manual Multi-Step Physical Clearance Handshake
```

---

## 2. Formal State Definitions

### 2.1 `GREEN` (Authorized Execution)
- **Operational Status:** Movement authorization active. Signed motion tokens dispatched to the Robot Simulation Gateway (or Phase 9 Hardware Gateway).
- **Entry Conditions (All must be strictly TRUE):**
  1. $\text{CRS} \ge 85.0$.
  2. `veto_asserted == FALSE`.
  3. Direction alignment $\cos(\Delta \theta) \ge 0.707$ ($\Delta \theta \le 45^\circ$).
  4. Sensor age $\Delta t_{\text{sensor}} \le 150 \text{ ms}$ on all active streams.
  5. E-STOP status `NORMAL`.

### 2.2 `YELLOW` (Safe Hold & Confirmation Requested)
- **Operational Status:** Actuators held in neutral zero-velocity state. No drive torque permitted.
- **Trigger Conditions:**
  - $50.0 \le \text{CRS} < 85.0$.
  - Voice command is `UNCERTAIN` or `UNKNOWN`.
  - Manual-only input (joystick active without accompanying spoken command, or vice-versa).
  - Telemetry jitter or sensor staleness ($150\text{ms} < \text{age} \le 350\text{ms}$).
- **Operator Recovery:** Requires re-issuing a synchronized concordant command or depressing a physical "Confirm" button.

### 2.3 `RED` (Hazardous Contradiction Hold)
- **Operational Status:** Immediate active electrical braking / motion lockout.
- **Trigger Conditions:**
  - `veto_asserted == TRUE` (e.g., vocal "FORWARD" while stick is pushed "BACKWARD", or vocal "STOP" while stick is active).
  - $\text{CRS} < 50.0$ with high individual modal energies.
- **Safety Interlock:** Moving back to `YELLOW` requires releasing the joystick to physical neutral center ($I_{\text{joy}} < 0.08$) and maintaining neutral silence for at least $500\text{ms}$ (`t_hold_release`).

### 2.4 `EMERGENCY` (Independent Emergency Stop)
- **Operational Status:** Complete galvanic motor power drop / software zero-override lock.
- **Trigger Conditions:**
  - Hardware E-STOP button pressed (normally-closed circuit broken).
  - Backend watchdog timeout ($>100\text{ms}$ service freeze).
  - Dashboard emergency button asserted.
- **AI Independence:** **Bypasses all speech recognition, NLP, prosody analysis, and graph fusion.** Evaluated on an independent hardware/OS interrupt line in $<1\text{ms}$.

---

## 3. Comprehensive Safety Decision Matrix

| Spoken Intent | Joystick Intent | CRS Score | Veto Flag | E-STOP | Resulting State | Actuator Command |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FORWARD` | `FORWARD` | $94.0$ | `CLEAR` | Normal | **`GREEN`** | Drive Forward ($+Y$) |
| `LEFT` | `LEFT` | $89.5$ | `CLEAR` | Normal | **`GREEN`** | Steer Left ($-X$) |
| `FORWARD` | `RIGHT` | $62.0$ | `CLEAR` | Normal | **`YELLOW`** | Zero Velocity (Hold) |
| `FORWARD` | `BACKWARD`| $25.0$ | `ARMED` | Normal | **`RED`** | Zero Velocity (Lockout) |
| `STOP` | `FORWARD` | $15.0$ | `ARMED` | Normal | **`RED`** | Emergency Brake |
| `UNCERTAIN` | `FORWARD` | $48.0$ | `CLEAR` | Normal | **`YELLOW`** | Zero Velocity (Hold) |
| `FORWARD` | Neutral | $52.0$ | `CLEAR` | Normal | **`YELLOW`** | Zero Velocity (Hold) |
| Any | Any | Any | Any | **TRIPPED** | **`EMERGENCY`** | Hard Power Cut |
| `FORWARD` (Stale) | `FORWARD` | N/A ($0.0$) | `CLEAR` | Normal | **`YELLOW`** | Zero Velocity (Hold) |

---

## 4. Architectural Safety Invariants & Guardrails

1. **Deterministic Immediate Stop Policy:**
   When the verbal token `"STOP"` is classified with confidence $\ge 0.60$, or any E-STOP event is received, all active authorizations are revoked synchronously. The system does not wait for the next fusion cycle.
2. **Missing & Stale Sensor Fail-Safe:**
   If the telemetry stream from either the microphone or joystick is interrupted for $>150\text{ms}$, authorization immediately transitions from `GREEN` to `YELLOW`. The system strictly prohibits extrapolating missing joystick coordinates or predicting speech tokens.
3. **Frontend Zero-Trust Rule:**
   The React frontend cannot issue motor drive commands. The backend `Safety Authorization Gateway` validates an internal cryptographic or tokenized state sequence before forwarding instructions to the simulation or physical robot.
4. **Physical Hardware Lockdown:**
   Virtual joystick packets (`is_simulation: true`) are physically airgapped at the safety gateway and cannot route to real motor controllers.
5. **Formal Disclaimer:**
   DCRG is an experimental university/research prototype. It is **NOT certified under ISO 13849 (PLr), IEC 61508 (SIL), or ISO 10218**.

