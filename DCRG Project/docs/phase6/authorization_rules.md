# DCRG Phase 6: Deterministic Safety Rule Engine

> **Specification Standard:** DCRG-SPEC-006-RULES  
> **Status:** Operational  

---

## 1. Strict Priority Hierarchy

The Safety Rule Engine evaluates all inbound commands deterministically according to strict hierarchical precedence:

$$\text{Priority 1 (EMERGENCY)} > \text{Priority 2 (RED)} > \text{Priority 3 (YELLOW)} > \text{Priority 4 (GREEN)}$$

A lower-tier state can **never** bypass or override a higher-tier state under any circumstance.

---

## 2. Formal Decision Predicates

### Priority 1: EMERGENCY
```python
if is_emergency_latched:
    return AuthorizationState.EMERGENCY, AuthorizationDecision.EMERGENCY_HALT
```
- Overrides all evidence, including perfect CRS scores ($100.0$).
- Purges all pending YELLOW holds.
- Disables simulation dispatch.

### Priority 2: RED (Immediate Rejection)
Evaluates to `RED` (`REJECTED`) if **ANY** of the following predicates are true:
1. **Contradiction Veto Filter:** `fusion.contradiction_detected == True` or `fusion.veto_asserted == True`.
   - *Example:* Operator speaks `"FORWARD"` while joystick is pulled `"BACKWARD"` ($\cos(\Delta \theta) \le 0.0$).
2. **Low Evidence Reliability:** `fusion.CRS < 50.0`.
3. **Speech Ambiguity:** `fusion.voice_command == "UNKNOWN"`.
4. **Hardware Failure:**
   - Physical joystick disconnected while in `REAL_HARDWARE` mode.
   - Microphone hardware reports `ERROR` state.
5. **Data Corruption:** `fusion.CRS_status == CRSStatus.INVALID` or sync status is `INVALID_TIMESTAMP`, `DUPLICATE`, or `STALE`.
6. **Environmental Boundary Violation:** `fusion.analytical_finding == CONTEXT_VIOLATION` (e.g. commanding motion directly into an obstacle within stopping distance $d_{\text{obs}} \le 1.0\text{ m}$, or operating in `EMERGENCY_STOP` context mode).

### Priority 3: YELLOW (Human Confirmation Required)
Evaluates to `YELLOW` (`HOLD_PENDING_CONFIRMATION`) if not RED/EMERGENCY and **ANY** of the following are true:
1. **Intermediate Reliability:** $50.0 \le \text{CRS} < 85.0$.
2. **Provisional / Unpartnered Evidence:** `fusion.CRS_status == CRSStatus.PROVISIONAL` or `evidence_completeness < 1.0` (e.g. voice-only command with centered stick).
3. **Uncertain Speech Token:** `fusion.voice_command == "UNCERTAIN"` or `analytical_finding == UNCERTAIN_COMMAND`.
4. **Context Telemetry Offline:** `analytical_finding == CONTEXT_UNAVAILABLE`.

#### Workflow Rules:
- Generates a unique `confirmation_id` with a strict $5000\text{ ms}$ timeout.
- Command remains un-dispatched until operator clicks **CONFIRM** or **REJECT**.
- **Dynamic Re-Evaluation:** When the operator confirms, the rule engine re-checks environmental obstacles and emergency states before authorizing. If an obstacle has moved closer or E-Stop was engaged during the hold, confirmation is refused and command is rejected.

### Priority 4: GREEN (Simulation Authorization)
Evaluates to `GREEN` (`AUTHORIZED`) **ONLY** if:
1. $\text{CRS} \ge 85.0$.
2. Evidence is complete (`CRS_status == COMPLETE` and `evidence_completeness == 1.0`).
3. Speech and joystick inputs are valid and temporally synchronized within $\tau_{\text{sync}} = 150\text{ ms}$.
4. No contradiction exists.
5. Operational and environmental constraints are satisfied.
6. System is not latched in emergency stop.

#### Token Generation:
- Generates a cryptographic HMAC-SHA256 signature token:
  $$\text{AuthToken} = \text{HMAC-SHA256}(\text{SecretKey}, \text{decision\_id} \,\|\, \text{command} \,\|\, \text{timestamp})$$
- Sets an expiration TTL of $2000\text{ ms}$.
- Automatically submits to the Simulated Command Gateway.

