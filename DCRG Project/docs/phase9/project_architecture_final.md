# DCRG – Complete Final System Architecture Specification (Phases 1–9)

## 1. System Architecture Overview

The **Dynamic Command Reliability Graph (DCRG)** is an AI + IoT multi-modal command verification and safety authorization architecture. It continuously monitors, aligns, and cross-correlates human vocal intentions with physical manual control deflections, deterministically gating command execution based on an explainable **Command Reliability Score (CRS)**.

```
+-------------------------------------------------------------------------------------------------------------+
|                                        DCRG MULTI-MODAL PIPELINE                                            |
|                                                                                                             |
|  [ Operator Speech Audio ]                                          [ Physical/Virtual Joystick ]           |
|             |                                                                     |                         |
|   (Phase 3 Voice Engine)                                                (Phase 2 Actuator Engine)           |
|   - Microphone Capture (16kHz)                                          - Pygame-CE 50Hz Polling            |
|   - Faster-Whisper int8 STT                                             - Deadzone Calibration              |
|   - Librosa Prosody Analysis                                            - Directional Classifier            |
|             |                                                                     |                         |
|        VoiceEvent                                                            JoystickEvent                  |
|             \                                                                     /                         |
|              +---------------------------------+---------------------------------+                          |
|                                                |                                                            |
|                                                v                                                            |
|                           [ Phase 4: Event Synchronization Engine ]                                         |
|                           - Dual Sliding Buffers (350ms window)                                             |
|                           - Inception Timestamp Comparison (t_v vs t_j)                                     |
|                           - Temporal Skew Penalty Q_sync                                                    |
|                                                |                                                            |
|                                         CorrelatedEvent                                                     |
|                                                |                                                            |
|                                                v                                                            |
|                             [ Phase 5: Multi-Factor Fusion Engine ]                                         |
|                             - Semantic Reliability (Rs)                                                     |
|                             - Motor Vector Cosine Agreement (Am)                                            |
|                             - Contextual Consistency (Cc)                                                   |
|                             - Evidence Completeness Factor (Ec)                                             |
|                             - Contradiction Veto Filter (Cap <= 30.0)                                       |
|                                                |                                                            |
|                                           FusionResult                                                      |
|                                                |                                                            |
|                                                v                                                            |
|                           [ Phase 6: Tiered Safety Authorization ]                                          |
|                           - Four-State Deterministic State Machine                                          |
|                           - GREEN: Autonomous Simulation Dispatch                                           |
|                           - YELLOW: Provisional Hold + Operator Confirm                                     |
|                           - RED: Hazardous Rejection / Stationary                                           |
|                           - EMERGENCY: Zero-Velocity Hard Latch                                             |
|                                                |                                                            |
|                                          SafetyDecision                                                     |
|                                                |                                                            |
|                                                v                                                            |
|                           [ Phase 7: Simulated Command Gateway ]                                            |
|                           - HMAC SHA-256 Token Signature Check                                              |
|                           - Anti-Replay Cache Defense                                                       |
|                           - 3.0s Expiration TTL Enforcement                                                 |
|                                                |                                                            |
|                                        AuthorizedCommand                                                    |
|                                                |                                                            |
|                                                v                                                            |
|                           [ Phase 7: 2D Kinematic Robot Simulator ]                                         |
|                           - Coordinate Updates (X, Y, theta)                                                |
|                           - Static Pylon Obstacle Collision Rings                                           |
|                           - Safety Boundary Containment                                                     |
|                                                |                                                            |
|                                                v                                                            |
|                           [ Phase 8/9: Persistence & Telemetry ]                                            |
|                           - Thread-Safe SQLite WAL Audit Logging                                            |
|                           - WebSocket Multiplexer (/ws/all)                                                 |
|                           - React 19 Operator Control Dashboard                                             |
+-------------------------------------------------------------------------------------------------------------+
```

---

## 2. Core Mathematical Formulations

### 2.1 Acoustic Prosody Stress Attenuation
Acoustic stress ($S_v \in [0, 1]$) is computed by normalizing vocal pitch jitter, fundamental frequency variance ($\sigma_{F_0}$), and speech energy:
$$S_v = \text{clip}\Big(0.40 \cdot \tilde{\sigma}_{F_0} + 0.35 \cdot \tilde{\text{jitter}} + 0.25 \cdot \tilde{\text{RMS}},\ 0.0,\ 1.0\Big)$$

Semantic reliability factor ($R_s$) scales the speech recognition confidence ($c_{\text{rec}}$) inversely by cognitive acoustic stress:
$$R_s = c_{\text{rec}} \cdot \Big(1.0 - \beta \cdot S_v\Big) \quad \text{where } \beta = 0.30$$
*(Exception: Spoken STOP commands bypass stress attenuation to prevent hazardous failure under panic).*

### 2.2 Motor Directional Vector Cosine Agreement
Given normalized unit direction vectors for vocal intent ($\vec{v}$) and manual flight stick deflection ($\vec{j}$):
$$\cos(\Delta\theta) = \frac{\vec{v} \cdot \vec{j}}{\|\vec{v}\| \cdot \|\vec{j}\|}$$

Temporal alignment quality factor decays exponentially with arrival skew:
$$Q_{\text{sync}} = \exp\left(-\frac{\Delta t^2}{2 \cdot \sigma_{\text{sync}}^2}\right) \quad \text{where } \Delta t = |t_v - t_j|$$

Motor Agreement Factor ($A_m$):
$$A_m = \left(\frac{1.0 + \cos(\Delta\theta)}{2.0}\right) \cdot \sqrt{r_{\text{joy}}} \cdot Q_{\text{sync}}$$

### 2.3 Contradiction Veto Filter
If active speech intent and active manual joystick deflection diverge by more than $90^\circ$:
$$\Delta\theta > 90^\circ \quad \land \quad c_{\text{rec}} \ge 0.60 \quad \land \quad r_{\text{joy}} \ge 0.30$$
The contradiction veto is engaged, and the final CRS score is strictly bounded:
$$\text{is\_contradiction} = \text{True} \implies \text{CRS} \le 30.0$$

### 2.4 Command Reliability Score (CRS)
The composite CRS score combines the weighted evidence factors:
$$\text{CRS} = \Big( W_s \cdot R_s + W_m \cdot A_m + W_c \cdot C_c + W_e \cdot E_c \Big) \times 100$$
Default Weights:
$$W_s = 0.30, \quad W_m = 0.40, \quad W_c = 0.15, \quad W_e = 0.15 \quad \left(\sum W = 1.00\right)$$

---

## 3. Four-Tier Safety Authorization States

| Authorization State | Trigger Criteria | Action Taken | Motion Permitted |
| :---: | :--- | :--- | :---: |
| **`GREEN`** | $\text{CRS} \ge 85.0$, $E_c = 1.0$, synchronized, no veto | Cryptographic token signed, autonomous dispatch | **YES (Simulated)** |
| **`YELLOW`** | $50.0 \le \text{CRS} < 85.0$, single modality, or stress | Command held, UI confirmation requested | **HELD (Pending)** |
| **`RED`** | $\text{CRS} < 50.0$, contradiction veto, or invalid input | Outright rejection, event logged, vehicle idle | **NO (Blocked)** |
| **`EMERGENCY`** | E-STOP pressed, obstacle crash, or boundary breach | Velocity zero-clamped ($8.3\ \mu\text{s}$), hard lockout | **NO (Latched)** |

---

## 4. Subsystem Module Layout

| Subsystem | File Path | Core Role |
| :--- | :--- | :--- |
| **Actuator Engine** | `backend/app/modules/actuator_engine/` | Pygame SDL2 polling, deadzones, vector classifier |
| **Voice Engine** | `backend/app/modules/voice_engine/` | SoundDevice audio capture, Faster-Whisper int8 STT |
| **Prosody Engine** | `backend/app/modules/prosody_engine/` | Librosa pitch, jitter, and stress feature extraction |
| **Semantic Engine** | `backend/app/modules/semantic_engine/` | Intent mapping, canonical robot vocabulary classifier |
| **Synchronization** | `backend/app/modules/sync_engine/` | Temporal alignment, sliding buffers, drift compensation |
| **Fusion Engine** | `backend/app/modules/fusion_engine/` | Vector cosine alignment, contradiction filter, CRS |
| **Safety Engine** | `backend/app/modules/safety_engine/` | 4-state tiered rules, E-Stop latch, confirmation |
| **Gateway Interlock**| `backend/app/modules/safety_engine/gateway.py` | HMAC token verification, anti-replay, TTL check |
| **Simulator** | `backend/app/modules/simulation_engine/` | 2D kinematic robot vehicle, pylon obstacle collision |
| **Audit Logger** | `backend/app/database/` | SQLite WAL persistence, forensic query, CSV/JSON export |
| **Config Manager** | `backend/app/core/system_config.py` | Runtime parameter catalog, validation invariants |
| **Operator UI** | `frontend/src/` | React 19 TypeScript dashboard, canvas simulation |

