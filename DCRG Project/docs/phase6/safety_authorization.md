# DCRG Phase 6: Tiered Safety Authorization Engine Specification

> **Module:** `app.modules.safety_engine`  
> **Phase:** 6 (Tiered Safety Authorization Engine)  
> **Status:** Operational & Interlocked  
> **Specification Compliance:** DCRG-ARCH-005, DCRG-ARCH-011  

---

## 1. Executive Purpose & Scope Boundaries

The **Tiered Safety Authorization Engine** serves as the supreme decision gatekeeper of the Dynamic Command Reliability Graph (DCRG) architecture. It receives multi-factor evidence evaluations from the Phase 5 Fusion Engine and determines whether motion commands are authorized for simulation dispatch, held for human confirmation, or rejected.

```mermaid
flowchart TD
    subgraph INGRESS ["Evidence Stream"]
        FUSION["Phase 5 FusionResult (CRS, Factors, Veto, Finding)"]
        ESTOP_IN["Emergency Stop Circuit (Software UI / Physical HW)"]
        HEALTH["Subsystem Telemetry (Mic, Joystick, Timestamps, Context)"]
    end

    subgraph RULE_CORE ["Tiered Priority Rule Engine"]
        P1{"1. Emergency Stop Latched?"}
        P2{"2. Contradiction / CRS < 50 / Fault?"}
        P3{"3. 50 <= CRS < 85 / Provisional / Uncertain?"}
        P4["4. CRS >= 85 & Complete Synchronized Evidence"]
    end

    subgraph STATES ["Authorization State Outputs"]
        S_EMERGENCY["EMERGENCY (Halt All Motion, Command Lockout)"]
        S_RED["RED (Rejected, Motion Prohibited)"]
        S_YELLOW["YELLOW (Hold, Operator Confirmation Required)"]
        S_GREEN["GREEN (Simulation Authorized, HMAC Token Issued)"]
    end

    subgraph GATEWAY ["Command Execution Boundary"]
        CONFIRM_FLOW["Human Confirmation Action (Confirm / Reject)"]
        GW["Simulated Command Gateway (Token Check, Replay Defense, TTL)"]
        SIM_MODEL["Simulated Kinematic Model (No Physical Actuators)"]
    end

    ESTOP_IN --> P1
    FUSION --> P1
    HEALTH --> P1

    P1 -->|YES| S_EMERGENCY
    P1 -->|NO| P2

    P2 -->|YES| S_RED
    P2 -->|NO| P3

    P3 -->|YES| S_YELLOW
    P3 -->|NO| P4

    P4 --> S_GREEN

    S_YELLOW --> CONFIRM_FLOW
    CONFIRM_FLOW -->|Dynamic Re-check Passed| S_GREEN
    CONFIRM_FLOW -->|Operator Reject / Timeout| S_RED

    S_GREEN --> GW
    GW --> SIM_MODEL
```

### Strict Non-Actuation Invariant
- **Simulation Only:** This prototype executes commands within a simulated environment.
- **Physical Actuators Disconnected:** Physical robot motors, relays, and servo drives are **NOT** connected.
- **Non-Certification Disclosure:** This software is an experimental prototype and is **NOT certified** as an ISO 13849-1, IEC 61508, or ISO 10218 safety-critical emergency-stop circuit.

---

## 2. Four Authorization States

| State | Entry Conditions | Decision Output | Command Action |
| :--- | :--- | :--- | :--- |
| **`GREEN`** | $\text{CRS} \ge 85.0$, complete evidence, valid inputs, synchronized within $150\text{ ms}$, zero contradictions, context clear. | `AUTHORIZED` | Dispatches command with cryptographic signature token (TTL: $2000\text{ ms}$). |
| **`YELLOW`** | $50.0 \le \text{CRS} < 84.9$, unpartnered/provisional evidence, or `UNCERTAIN` classification. | `HOLD_PENDING_CONFIRMATION` | Command held in pending buffer for up to $5000\text{ ms}$. Requires operator confirmation. |
| **`RED`** | Contradiction detected, $\text{CRS} < 50.0$, sensor/mic/joystick error, stale timestamp, or boundary violation. | `REJECTED` | Command dropped immediately. Movement strictly prohibited. |
| **`EMERGENCY`** | Software or physical E-Stop button depressed. | `EMERGENCY_HALT` | Immediate zero-velocity halt. Command queue purged. Lockout latched until authorized reset. |

