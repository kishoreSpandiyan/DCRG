# Dynamic Command Reliability Graph (DCRG)

> **Real-Time AI + IoT Multi-Modal Command Verification and Safety Authorization System**

---

## 1. Project Overview

The **Dynamic Command Reliability Graph (DCRG)** is an AI + IoT verification system engineered to prevent catastrophic human-robot interaction failures. It cross-examines an operator's simultaneous spoken voice commands against physical manual joystick inputs in real time, computing a continuous **Command Reliability Score (CRS)** before authorizing simulated robot actuators to execute motion.

If an operator says *"Emergency Stop!"* while inadvertently nudging the joystick forward, or conversely shouts *"Move Forward"* while violently yanking the joystick backward in cognitive distress, DCRG flags the multi-modal discrepancy, suppresses the conflicting movement, and enforces fail-safe degradation.

> [!IMPORTANT]
> **SIMULATION MODE ONLY:** Through all phases of DCRG, the system operates strictly within software simulation. No physical motors, industrial manipulators, or live actuators are energized.

---

## 2. Problem Statement

In critical human-robot teleoperation (search-and-rescue, defense robotics, nuclear materials handling, and industrial manufacturing):
- **Single-Modality Fragility:** Sole reliance on manual joystick controls exposes operations to involuntary muscle spasms, slips, or cognitive panic deflections. Sole reliance on voice control is vulnerable to acoustic noise, transcription delays, homophone confusion, and background interference.
- **Cognitive Dissonance Under Stress:** Operators under extreme stress frequently experience intention-action decoupling—vocalizing one intention while reflexively moving hand controls in another direction.
- **Lack of Multi-Modal Safety Interlocks:** Conventional robotic command architectures lack a deterministic, real-time verification gate that mathematically proves alignment between acoustic intent and physical manual vectors prior to actuator execution.

---

## 3. Proposed Solution

DCRG introduces a multi-tier, multi-modal verification and authorization pipeline:

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
             [ Persistent SQLite Audit Log (Phase 8/9) ]
```

---

## 4. Architecture & Mathematics

### 4.1 Acoustic Prosody Stress Attenuation
Vocal pitch jitter, fundamental frequency variance ($\sigma_{F_0}$), and speech energy yield a stress metric $S_v \in [0, 1]$. Speech recognition confidence ($c_{\text{rec}}$) is attenuated by stress:
$$R_s = c_{\text{rec}} \cdot \Big(1.0 - \beta \cdot S_v\Big) \quad \text{where } \beta = 0.30$$
*(Spoken `STOP` commands bypass stress attenuation).*

### 4.2 Motor Vector Agreement & Temporal Quality
Vector cosine alignment between speech intention ($\vec{v}$) and manual flight stick deflection ($\vec{j}$):
$$\cos(\Delta\theta) = \frac{\vec{v} \cdot \vec{j}}{\|\vec{v}\| \cdot \|\vec{j}\|}$$
$$A_m = \left(\frac{1.0 + \cos(\Delta\theta)}{2.0}\right) \cdot \sqrt{r_{\text{joy}}} \cdot Q_{\text{sync}}$$
where $Q_{\text{sync}} = \exp\left(-\frac{\Delta t^2}{2 \cdot \sigma_{\text{sync}}^2}\right)$ penalizes arrival offsets exceeding $150\text{ ms}$.

### 4.3 Contradiction Veto Filter
If speech intent opposes manual stick deflection ($\Delta\theta > 90^\circ$ under active inputs), the contradiction veto trips and caps the CRS:
$$\text{is\_contradiction} = \text{True} \implies \text{CRS} \le 30.0$$

### 4.4 Command Reliability Score (CRS)
$$\text{CRS} = \Big( W_s \cdot R_s + W_m \cdot A_m + W_c \cdot C_c + W_e \cdot E_c \Big) \times 100$$
- $W_s = 0.30$ (Semantic Reliability), $W_m = 0.40$ (Motor Agreement), $W_c = 0.15$ (Contextual Consistency), $W_e = 0.15$ (Evidence Completeness).

### 4.5 Tiered Safety Authorization States
- **`GREEN` ($\text{CRS} \ge 85.0$)**: Autonomous simulated execution through cryptographic gateway token.
- **`YELLOW` ($50.0 \le \text{CRS} < 85.0$)**: Motion held until operator clicks manual confirmation.
- **`RED` ($\text{CRS} < 50.0$ or Contradiction)**: Command rejected; vehicle remains stationary.
- **`EMERGENCY`**: Zero-velocity clamp ($8.3\ \mu\text{s}$), immediate lockout until authorized PIN reset.

---

## 5. Technology Stack

### Backend
- **Language:** Python 3.14+
- **API & Streaming:** FastAPI, Uvicorn, Starlette WebSockets
- **Hardware Integration:** Pygame-CE 2.5.8 (SDL2 DirectInput / XInput), SoundDevice
- **AI & NLP:** Faster-Whisper (quantized int8 local CTranslate2), Librosa
- **Database:** SQLite with Write-Ahead Logging (`WAL` mode)
- **Validation:** Pydantic v2
- **Testing:** Pytest (229 passing tests)

### Frontend
- **Framework:** React 19 (TypeScript)
- **Build Tool:** Vite 8
- **Styling:** Tailwind CSS v4
- **Visualization:** HTML5 2D Canvas & SVG Gauges
- **Icons:** Lucide React

---

## 6. Directory Structure

```
DCRG Project/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/     # REST & WebSocket endpoints (system, voice, joy, sync, fusion, safety, sim)
│   │   ├── core/                 # App settings & dynamic runtime config manager
│   │   ├── database/             # SQLite audit logger (WAL mode) and pipeline audit hooks
│   │   ├── hardware/             # Physical joystick service (Pygame-CE SDL2)
│   │   ├── modules/              # Subsystem engines (actuator, voice, prosody, semantic, sync, fusion, safety, sim)
│   │   └── schemas/              # Common Pydantic contracts
│   ├── tests/                    # 229 automated pytest test cases
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # UI panels (OverviewBar, Timeline, Health, Config, Audit, Canvas)
│   │   ├── pages/                # MainPage unified command center
│   │   ├── services/             # REST & WebSocket API client
│   │   └── types/                # TypeScript type definitions
│   └── package.json
├── docs/
│   ├── architecture/             # Phase 1 specifications
│   ├── phase3/ to phase8/        # Module guides and integration reports
│   └── phase9/                   # Final validation, hardware test, and performance reports
└── scripts/
    ├── dev_backend.bat           # Run FastAPI server
    ├── dev_frontend.bat          # Run Vite development server
    └── run_tests.ps1             # Full test execution script
```

---

## 7. Installation & Setup

### 1. Backend Environment Setup
```powershell
Set-Location "DCRG Project\backend"
python -m venv .venv
.\.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### 2. Frontend Dependencies Setup
```powershell
Set-Location "DCRG Project\frontend"
npm.cmd install
```

---

## 8. How to Run

### Automated Test Suite
To run all 229 automated unit and integration tests:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_tests.ps1
```
*Result: 229 passed in ~8.9s; Vite frontend build verified in ~350ms.*

### Running the Services

**Terminal 1 – Launch Backend:**
```powershell
Set-Location "DCRG Project\backend"
.\.venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*API Swagger Documentation: `http://127.0.0.1:8000/docs`*

**Terminal 2 – Launch Frontend:**
```powershell
Set-Location "DCRG Project\frontend"
npm.cmd run dev
```
*Operator Dashboard: `http://localhost:5173`*

---

## 9. Dashboard Instructions

The DCRG Dashboard features 7 operational views accessible via navigation tabs:
1. **Command Center**: The primary command-and-control cockpit showing live monitors, fusion CRS radial gauge, safety decision cards, robot canvas, and live event ticker.
2. **Multi-Modal Monitors**: Deep-dive telemetry for Faster-Whisper confidence, acoustic prosody stress metrics ($F_0$, RMS, jitter), and joystick deflection plots.
3. **Fusion & Safety**: Factor breakdown ($R_s, A_m, C_c, E_c$), cosine directional alignment, and contradiction veto alerts.
4. **Robot Simulation**: Full 2D kinematic canvas with coordinate tracking, static pylon obstacles, and trajectory history.
5. **Audit Logs**: Forensic search table with multi-criteria filters, JSON payload viewer, and CSV/JSON export.
6. **Configuration**: Live tunable runtime parameter sliders (weights, deadzones, thresholds) with strict mathematical invariant validation.
7. **System Health**: Active probe diagnostics table for 8 core subsystems (never reports false healthy).

---

## 10. Demonstration Workflow

1. **System Health**: Navigate to **System Health** tab and confirm all services show `HEALTHY`.
2. **Agreement Demo (GREEN)**: In the virtual joystick, deflect **LEFT** while speaking *"MOVE LEFT"*. Observe $\text{CRS} > 90.0$, `GREEN` state, and vehicle moving left.
3. **Contradiction Demo (RED)**: Deflect joystick **RIGHT** while speaking *"MOVE LEFT"*. Observe red contradiction veto badge, $\text{CRS} \le 30.0$, `RED` rejection, and vehicle staying stationary.
4. **Hold Demo (YELLOW)**: Move joystick forward with mic muted. Observe $\text{CRS} \approx 60.0$, `YELLOW` state. Click **CONFIRM COMMAND** to dispatch motion.
5. **STOP Priority**: While vehicle is moving, speak *"STOP"*. The vehicle decelerates to zero immediately.
6. **Emergency Stop**: Click the red **E-STOP** button. Observe instant velocity clamp ($8.3\ \mu\text{s}$) and lockout until PIN reset (`1234`).
7. **Audit Logs**: Open **Audit Logs** tab to inspect and export forensic records.

---

## 11. Known Limitations

- **Physical USB Joystick Absence**: Physical flight stick hardware was not physically attached to the host during testing. Background SDL2 polling loop and disconnect recovery were validated; virtual canvas and browser gamepad fallback active.
- **Acoustic Transducer Environment**: Audio tested using integrated laptop microphone array; high-noise industrial chambers were tested via SNR synthesis.
- **Simulation Containment**: All physical motor outputs are strictly disabled in software; motion execution is confined to 2D simulation.
- **Safety Certification Disclaimer**: Developed for academic, research, and proof-of-concept evaluation. NOT certified under ISO 13849 or IEC 61508.

---

## 12. Final Validation Status

- **Phases 1 through 9: COMPLETED & FULLY VERIFIED**
- **Test Suite Status: 229 / 229 Automated Tests Passed (100%)**
- **Ready for Final Demonstration.**
