# Multi-Modal Event Correlation Engine Specification

> **Document ID:** DCRG-DOC-P4-003  
> **Status:** Completed Phase 4 Deliverable  
> **Modules Covered:** `backend/app/modules/sync_engine/synchronizer.py`

---

## 1. Correlation Objective & Scope

The **Event Correlation Engine** identifies and pairs independent telemetry events arriving from the Voice Engine and Actuator Engine that originate within the same temporal operational window.

### Example Correlation Scenario
- **Voice Ingress:** Operator speaks *"MOVE LEFT"* ($t_{\text{event}} = 100\text{ ms}$, recognized command: `LEFT`).
- **Joystick Ingress:** Operator pushes physical joystick `RIGHT` ($t_{\text{event}} = 135\text{ ms}$, direction: `RIGHT`, intensity: `0.85`).
- **Correlation Result:**
  - $\Delta t = |100 - 135| = 35\text{ ms} \le 150\text{ ms}$
  - Status: **`SYNCHRONIZED`**
  - Result: The engine bundles both the `LEFT` voice primitive and `RIGHT` joystick vector into a single `CorrelatedEvent` and forwards them to the downstream pipeline.

```mermaid
graph LR
    subgraph INPUTS ["Independent Input Telemetry"]
        V["VoiceEvent: 'MOVE LEFT' (t=100ms)"]
        J["CommonJoystickEvent: RIGHT (t=135ms)"]
    end

    subgraph PHASE4 ["Phase 4 Correlation Engine"]
        V --> MATCH{"|t_v - t_j| ≤ 150ms?"}
        J --> MATCH
        MATCH -->|Yes (Δt=35ms)| CORR["CorrelatedEvent (SYNCHRONIZED)"]
    end

    subgraph PHASE5_BOUNDARY ["Phase 5 Fusion (Future Scope)"]
        CORR -.->|Provides Both Signals| CRS["CRS Fusion Engine (Future)"]
    end
```

---

## 2. Synchronization Status Taxonomy

| Status | Trigger Condition | Operational Implication |
| :--- | :--- | :--- |
| **`SYNCHRONIZED`** | Both voice and joystick events exist with $\Delta t \le \tau_{\text{sync}}$ ($150\text{ms}$) | Dual-modality event ready for multi-modal fusion |
| **`VOICE_ONLY`** | Spoken command completed; joystick reports neutral or absent for $>\tau_{\text{sync}}$ | Voice command without concurrent joystick actuation |
| **`JOYSTICK_ONLY`** | Active joystick deflection ($I > 0.10$); voice reports silence for $>\tau_{\text{sync}}$ | Manual joystick deflection without concurrent verbal command |
| **`OUT_OF_WINDOW`** | Both modalities active but temporal divergence $\Delta t > \tau_{\text{sync}}$ | Actions are temporally decoupled (operator hesitation or lag) |
| **`DELAYED`** | Event transit or processing latency $> 200 \text{ ms}$ | Lagged telemetry; paired with degraded flag |
| **`STALE`** | Unpartnered event resided in buffer longer than $\tau_{\text{max\_age}} = 350\text{ ms}$ | Dropped from active matching; logged to audit trail |
| **`INVALID_TIMESTAMP`** | Timestamp is null, NaN, Inf, historical, or far future | Event rejected immediately; discarded from matching queues |
| **`DUPLICATE`** | Event ID matches previously ingested packet | Suppressed to prevent double actuation |

---

## 3. Strict Safety Boundary

> **MANDATORY BOUNDARY RULE:**  
> **The Correlation Engine does NOT compute reliability scores (CRS), does NOT evaluate safety, and does NOT authorize movement.**  
> - If an operator speaks *"LEFT"* while moving the joystick `RIGHT`, Phase 4 pairs them truthfully with status `SYNCHRONIZED`.
> - Whether this constitutes a dangerous conflict, an operator error, or a vetoed maneuver is strictly the responsibility of Phase 5 (CRS Graph Fusion) and Phase 6 (Safety Authorization Engine).
> - **Never fabricate a missing event:** If voice is absent, `voice_event = None`. If joystick is absent, `joystick_event = None`.

