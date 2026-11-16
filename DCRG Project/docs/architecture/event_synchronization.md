# Event Synchronization Architecture

> **Document ID:** DCRG-ARCH-004  
> **Status:** Approved Architecture Draft (Phase 1)  
> **Service:** `event_synchronization_service`

---

## 1. The Asynchronous Modality Alignment Challenge

Human speech and manual joystick control operate over fundamentally divergent biological and mechanical latencies:
- **Speech Pipeline Delay:** Vocal chord vibration $\to$ VAD closure ($250\text{ms}$) $\to$ Whisper transcription ($45\text{ms}$) $\to$ Semantic parsing ($5\text{ms}$). Total pipeline latency: **$300\text{ms} \pm 50\text{ms}$**.
- **Joystick Pipeline Delay:** Physical hand deflection $\to$ USB HID polling ($20\text{ms}$) $\to$ normalization ($2\text{ms}$). Total pipeline latency: **$22\text{ms} \pm 5\text{ms}$**.

If raw system arrival times were naively compared, a spoken command uttered *concurrently* with a joystick deflection would arrive at the fusion layer $280\text{ms}$ after the joystick packet, causing catastrophic misalignments (e.g., comparing an operator's old turn command with a new forward acceleration).

```mermaid
sequenceDiagram
    autonumber
    participant H as Operator Action
    participant V_RAW as Audio Buffer (VAD)
    participant J_RAW as Joystick HID (50Hz)
    participant SYNC as Synchronization Buffer
    participant OUT as Aligned Event Pair

    Note over H: Operator acts at t=0ms:<br/>Speaks "LEFT" & pushes stick LEFT
    H->>J_RAW: Stick deflects at t=0ms
    H->>V_RAW: Vocalization spans t=0ms to t=400ms

    J_RAW->>SYNC: JoystickEvent (t_event = 10ms, t_arrival = 20ms)
    Note over SYNC: Buffer retains joystick event;<br/>awaits corresponding speech window

    V_RAW->>SYNC: VoiceEvent (t_event = 50ms, t_arrival = 480ms)
    Note over SYNC: Match found!<br/>Temporal delta |t_voice - t_joy| = 40ms ≤ 150ms

    SYNC->>OUT: Emit SynchronizedPair(Voice_LEFT, Joy_LEFT, Δt=40ms)
```

---

## 2. Core Temporal Definitions

1. **Event Time ($t_{\text{event}}$):**
   - The authoritative wall-clock timestamp (Unix Epoch in milliseconds with microsecond resolution) corresponding to the *physical inception* of the input.
   - Voice: Time when VAD detected speech onset.
   - Joystick: Time when USB HID interrupt or browser gamepad poll read the raw axis frame.
2. **Processing Time ($t_{\text{proc}}$):**
   - Timestamp when an engine completed its transformation (e.g., when Whisper emitted text tokens).
3. **Arrival Time ($t_{\text{arrival}}$):**
   - Timestamp when the packet entered the `event_synchronization_service` ingestion queue.
4. **Synchronization Window ($\tau_{\text{sync}}$):**
   - Maximum allowable temporal divergence between the physical event times of two paired modalities:
     $$\Delta t = |t_{\text{event, voice}} - t_{\text{event, joystick}}| \le \tau_{\text{sync}}$$
   - **Default: $150 \text{ ms}$** (Configurable from $100\text{ms}$ to $250\text{ms}$).
5. **Maximum Allowed Event Age ($\tau_{\text{max\_age}}$):**
   - Absolute staleness threshold. Any unpartnered event residing in the sliding buffer exceeding **$\tau_{\text{max\_age}} = 350 \text{ ms}$** is dropped and classified as an isolated, unconfirmed action.

---

## 3. Sliding Buffer & Alignment Algorithm

The synchronization service maintains a FIFO Circular Time-Indexed Priority Queue for each input channel:

```mermaid
flowchart TD
    IN_VOICE[Incoming Voice Events] --> Q_VOICE[Voice Circular Buffer max 1000ms]
    IN_JOY[Incoming Joystick Events] --> Q_JOY[Joystick Circular Buffer 50Hz max 1000ms]
    IN_CTX[Mission Context Events] --> Q_CTX[Context State Register]

    Q_VOICE --> MATCHER{Temporal Match Engine}
    Q_JOY --> MATCHER
    Q_CTX --> MATCHER

    MATCHER -->|Valid Pair found: |t_v - t_j| ≤ 150ms| BUNDLE[Assemble Synchronized Event Bundle]
    MATCHER -->|Age > 350ms: Single Modality Timeout| ISOLATE[Emit Unsynchronized / Hold Event]
    MATCHER -->|Duplicate event_id| DROP_DUP[Discard Duplicate]
    MATCHER -->|Out of order: t_event < t_last_emitted| REORDER[Sliding Window Re-Sort]

    BUNDLE --> OUT[Forward to DCRG Fusion Engine]
    ISOLATE --> SAFETY_HOLD[Downgrade to YELLOW State]
```

### 3.1 The Matching Procedure
When a new event $E_{\text{new}}$ arrives:
1. Validate schema integrity and check `event_id` against a Bloom filter / LRU cache of recently processed IDs to eliminate duplicates.
2. If $E_{\text{new}}$ is a `VoiceEvent`:
   - Query the `JoystickBuffer` for the sample whose $t_{\text{event, joy}}$ is closest to $E_{\text{new}}.t_{\text{event}}$.
   - If $|t_{\text{voice}} - t_{\text{joy}}| \le \tau_{\text{sync}}$, extract the paired pair, bundle the prevailing `ContextState`, and dispatch to the Fusion Engine.
3. If $E_{\text{new}}$ is a `JoystickEvent`:
   - If the joystick indicates active deflection ($I > 0.15$) and no voice event exists within $\tau_{\text{sync}}$, the joystick event is buffered for up to $\tau_{\text{sync}}$ before emitting a *Manual-Only* provisional event.

---

## 4. Fault Handling Matrix for Synchronization

| Synchronization Fault | Detection Condition | Corrective Action & Safety Response |
| :--- | :--- | :--- |
| **Missing Voice Stream** | Joystick active for $>350\text{ms}$ with zero speech events | Do not synthesize voice; tag as `VOICE_ABSENT`. Lower max CRS ceiling to $0.70$ (State: `YELLOW`). |
| **Missing Joystick Stream** | Spoken command completed but joystick reports no packets for $>150\text{ms}$ | Tag as `JOYSTICK_MISSING`. Inhibit motion; require manual verification. |
| **Out-of-Order Packets** | Incoming $t_{\text{event}} < t_{\text{last\_processed}}$ due to network jitter | Insert into sorted buffer position if within $100\text{ms}$ window; otherwise drop as stale. |
| **Stale Sensor Packet** | $t_{\text{current}} - t_{\text{event}} > \tau_{\text{max\_age}}$ | Discard packet; log anomaly; never extrapolate or predict missing safety-critical data. |
| **Clock Drift / De-synchronization** | Host vs Client timestamp skew $> 50\text{ms}$ | Re-synchronize timestamps using monotonic clock offsets ($\Delta t_{\text{monotonic}}$). |
| **Contradictory Temporal Overlap** | Previous command still executing while new opposite command arrives | Flag as preemption; initiate controlled deceleration to zero velocity before re-evaluating. |

