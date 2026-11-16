# DCRG Phase 7 – Command Execution & Safety Gateway Interlock

## 1. Safety Gateway Interlock Architecture

The DCRG Robot Simulation is protected by a strict architectural invariant: **The simulation vehicle cannot be directly commanded by raw inputs or frontend events.**

Every motion command must successfully traverse the entire multi-modal pipeline:
$$\text{Voice} + \text{Joystick} \xrightarrow{\text{Sync (Phase 4)}} \text{Fusion CRS (Phase 5)} \xrightarrow{\text{Tiered Rules (Phase 6)}} \text{Simulated Gateway} \xrightarrow{} \text{Simulator Execution (Phase 7)}$$

```
+-----------------------------------------------------------------------------------------+
|                                    DCRG PIPELINE                                        |
|                                                                                         |
|  [Voice Engine]   [Joystick Engine]                                                     |
|         \                /                                                              |
|          v              v                                                               |
|     [Event Synchronization Engine (Phase 4)]                                            |
|                    |                                                                    |
|                    v                                                                    |
|     [Multi-factor Fusion Engine & CRS (Phase 5)]                                        |
|                    |                                                                    |
|                    v                                                                    |
|     [Tiered Safety Authorization Engine (Phase 6)]                                      |
|          |                 |                 |                     |                    |
|       (GREEN)           (YELLOW)           (RED)              (EMERGENCY)               |
|          |                 |                 |                     |                    |
|          v                 v                 v                     v                    |
|   +--------------+  +--------------+  +--------------+     +---------------+            |
|   | Cryptographic|  | Hold Command |  | Reject & Log |     | Zero Velocity |            |
|   | Gateway Sign |  | Await Operator|  | Fail Safe    |     | Lockout Latch |            |
|   +--------------+  +--------------+  +--------------+     +---------------+            |
|          |                 |                                       |                    |
|          |                 +-(Human Confirm)-+                     |                    |
|          |                                   |                     |                    |
|          v                                   v                     v                    |
|   +-------------------------------------------------------------------------+           |
|   |                   Simulated Command Gateway                             |           |
|   |       Checks: Token Replay, Expiration TTL, Command Match               |           |
|   +-------------------------------------------------------------------------+           |
|                                     |                                                   |
|                                     v                                                   |
|   +-------------------------------------------------------------------------+           |
|   |            2D Kinematic Robot Simulator (Phase 7)                       |           |
|   |         Smooth Movement, Angular Alignment, Collision Stops             |           |
|   +-------------------------------------------------------------------------+           |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Command Execution Lifecycle & Audit Log

Every evaluated command is assigned an immutable `CommandExecutionRecord` tracking its entire lifecycle:

```json
{
  "command_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "decision_id": "c1f609e2-2e55-46f9-8664-508b9cd2bf69",
  "timestamp_ms": 1793929768520.0,
  "requested_command": "FORWARD",
  "authorized_command": "FORWARD",
  "crs": 92.4,
  "authorization_state": "GREEN",
  "execution_result": "EXECUTED",
  "rejection_reason": null,
  "pose_before": { "x": 0.0, "y": 0.0, "heading_deg": 0.0, "linear_speed": 0.0, "angular_speed": 0.0 },
  "pose_after": { "x": 0.0, "y": 0.15, "heading_deg": 0.0, "linear_speed": 3.0, "angular_speed": 0.0 }
}
```

### Execution Outcome Categories (`ExecutionResultType`)

1. **`EXECUTED`**: Command was authenticated, signed, verified through gateway, and kinematic actuation was applied by the simulation physics engine.
2. **`HELD`**: Command was evaluated with moderate reliability ($50 \le \text{CRS} < 85$) or unverified multi-modal evidence. Motion is withheld pending explicit human confirmation.
3. **`REJECTED`**: Command was evaluated as unsafe ($\text{CRS} < 50$), contradictory, violating mission constraints, or failing token authentication.
4. **`CANCELLED`**: Command held on pending confirmation was cancelled due to timeout, operator rejection, or an upstream interrupt.
5. **`EMERGENCY_STOPPED`**: Motion was instantly halted due to hardware or software Emergency Stop engagement.

---

## 3. Cryptographic Gateway Defenses

The `SimulatedCommandGateway` guarantees fail-safe security through four verification gates:

1. **HMAC-SHA256 Token Signature**:
   Every authorized decision generated by the Safety Rule Engine contains a time-stamped signature token:
   $$\tau = \text{HMAC-SHA256}(K_{secret}, \text{decision\_id} \parallel \text{cmd} \parallel \text{expires\_at})$$
2. **Replay Attack Defense**:
   Tokens are stored in a consumed token cache upon dispatch. Re-submitting an already executed command token is rejected outright.
3. **Authorization Expiration (TTL)**:
   Authorizations carry a strict 1000 ms Time-To-Live. Stale commands arriving after expiration are rejected.
4. **Command Mismatch Check**:
   If an incoming request attempts to actuate a primitive different from the authorized signature (e.g., authorized `FORWARD` but requesting `BACKWARD`), dispatch fails immediately.

