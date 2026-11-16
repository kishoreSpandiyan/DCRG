# DCRG Phase 5: Command Reliability Score (CRS) Mathematical Specification

> **Document ID:** DCRG-SPEC-005-CRS  
> **Status:** Operational Implementation  
> **Calibration Profile:** `v1.0-prototype`  

---

## 1. Mathematical Formulation

The Command Reliability Score ($\text{CRS}$) is a continuous evidence metric on the scale $[0.0, 100.0]$:

$$\text{CRS}_{\text{raw}} = 100.0 \times \left( W_s \cdot S + W_m \cdot M + W_c \cdot C \right)$$

$$\text{CRS} = \text{round}\left( \min\left( \text{CRS}_{\text{raw}}, \text{Cap}_{\text{veto}} \right), 1 \right)$$

### Prototype Weight Distribution
Per DCRG-ARCH-005, the prototype baseline weights are:
- $W_s = 0.35$ (Semantic Reliability Weight)
- $W_m = 0.50$ (Motor Agreement Weight — physical confirmation is prioritized)
- $W_c = 0.15$ (Contextual Consistency Weight)
- Constraint: $W_s + W_m + W_c = 1.0, \quad W_i \ge 0$

---

## 2. Component Factor Formulations

### 2.1 Semantic Reliability Factor ($S$)
Measures the acoustic clarity and intent probability of the spoken utterance:

$$S = C_{\text{whisper}} \times \left( 1.0 - \beta \cdot S_{\text{stress}} \right)$$

- **$C_{\text{whisper}} \in [0.0, 1.0]$:** Speech recognition confidence reported by Faster-Whisper.
- **$S_{\text{stress}} \in [0.0, 1.0]$:** Normalized cognitive stress score synthesized by the Prosody Engine.
- **$\beta = 0.25$:** Configurable stress damping coefficient. Ensures acoustic tension attenuates confidence without vetoing clear emergency speech.
- **Defensive Invariants:**
  - If the recognized token is `UNKNOWN` or `UNCERTAIN`, $S = 0.0$ strictly.
  - If prosody telemetry is absent, $S_{\text{stress}} = 0.0$ (missing prosody is not treated as stress).
  - Shouted `STOP` preservation: At maximum stress ($S_{\text{stress}} = 1.0$), $1.0 - (0.25 \times 1.0) = 0.75$. Therefore, an urgent shouted `STOP` ($C_{\text{whisper}} \approx 1.0$) retains $S \ge 0.75$.

### 2.2 Motor / Actuator Agreement Factor ($M$)
Measures directional alignment between the spoken intention vector $\vec{V}_{\text{voice}}$ and the joystick vector $\vec{J}_{\text{norm}}$:

$$M = \left( \frac{1.0 + \cos(\Delta \theta)}{2.0} \right) \times \sqrt{I_{\text{joy}}} \times Q_{\text{sync}}$$

Where:
- **Cosine Similarity:** $\cos(\Delta \theta) = \frac{\vec{V}_{\text{voice}} \cdot \vec{J}_{\text{norm}}}{\|\vec{V}_{\text{voice}}\| \|\vec{J}_{\text{norm}}\|}$
  - Exact match ($\Delta \theta = 0^\circ \implies \cos = 1.0$): Multiplier $= 1.0$
  - Perpendicular ($\Delta \theta = 90^\circ \implies \cos = 0.0$): Multiplier $= 0.5$
  - Direct contradiction ($\Delta \theta = 180^\circ \implies \cos = -1.0$): Multiplier $= 0.0$
- **Deflection Intensity:** $I_{\text{joy}} \in [0.0, 1.0]$ with radial deadzone threshold $r_{\text{dead}} = 0.08$. If $\sqrt{x^2 + y^2} < r_{\text{dead}}$, $I_{\text{joy}} = 0.0$.
- **Temporal Synchrony Multiplier:**
  $$Q_{\text{sync}} = \max\left( 0.0, 1.0 - \frac{|\Delta t|}{\tau_{\text{sync}}} \right)$$
  For $\tau_{\text{sync}} = 150.0\text{ ms}$.

#### Non-Directional Command Exception (`STOP` Logic)
When the spoken command is `STOP`:
1. **Neutral Joystick ($I_{\text{joy}} < 0.10$):** High motor agreement ($M = 1.0 \times Q_{\text{sync}}$), indicating mutual intent to halt.
2. **Deflected Joystick ($I_{\text{joy}} \ge 0.30$):** Contradiction! Moving physical stick while speaking STOP yields $M = 0.0$ and triggers the Contradiction Veto Filter.
3. **Transitional Deflection ($0.10 \le I_{\text{joy}} < 0.30$):** Tapered linear agreement.

### 2.3 Contextual Consistency Factor ($C$)
Measures adherence to operating modes, permitted movement boundaries, and obstacle proximities:

- **Operating Modes:**
  - `EMERGENCY_STOP` or `DOCKED`: Non-STOP movement yields $C = 0.0$.
  - `NORMAL`: Admissible motion yields nominal $C = 1.0$.
- **Permitted Directions:** Commands outside `permitted_directions` yield $C = 0.0$.
- **Obstacle Buffer:**
  - If obstacle distance $d_{\text{obs}} \le d_{\text{stop}}$ (1.0m threshold) in commanded direction: $C = 0.0$.
  - If $d_{\text{stop}} < d_{\text{obs}} < 2 \cdot d_{\text{stop}}$: Linear proximity warning penalty applied.
- **Unavailable Context:** When context telemetry is offline, $C = 0.5$ (neutral default) without fabricating full compliance, and evaluation status is marked `PROVISIONAL`.

---

## 3. Evidence Completeness & Categorical Status

| Status | Required Evidence | Typical Scenarios |
| :--- | :--- | :--- |
| **`COMPLETE`** | Completeness $= 1.0$, `SYNCHRONIZED` within window | Voice + Joystick paired within 150ms + active Context |
| **`PROVISIONAL`** | Single modality or missing context | Voice-only command, Joystick-only input, or Context offline |
| **`INCOMPLETE`** | Critical data absent or low confidence | UNKNOWN/UNCERTAIN speech, ambiguous deflection |
| **`INVALID`** | Corrupted timestamps or malformed payloads | Clock drift violation, transit packet corruption, duplicate IDs |

