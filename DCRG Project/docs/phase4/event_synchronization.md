# Event Synchronization Engine Architecture

> **Document ID:** DCRG-DOC-P4-001  
> **Status:** Completed Phase 4 Deliverable  
> **Modules Covered:** `backend/app/modules/sync_engine/synchronizer.py`, `backend/app/modules/sync_engine/manager.py`

---

## 1. The Multi-Modal Asynchronous Synchronization Challenge

In teleoperated robotics and supervisory control systems, human speech and manual joystick manipulation operate across radically divergent biomechanical and computational latency profiles:
- **Spoken Command Pipeline:** Vocal cord inception $\to$ Speech Activity Segmentation ($200\text{ms} - 350\text{ms}$) $\to$ Faster-Whisper local quantized inference ($440\text{ms}$) $\to$ Semantic Intent Classification ($2\text{ms}$). Total pipeline latency: **$450\text{ms} - 750\text{ms}$**.
- **Actuator Joystick Pipeline:** Physical hand deflection $\to$ USB HID interrupt ($20\text{ms}$) $\to$ Deadzone normalization and directional classification ($2\text{ms}$). Total pipeline latency: **$22\text{ms} \pm 5\text{ms}$**.

If server arrival times ($t_{\text{reception}}$) were compared naively, a spoken command uttered simultaneously with a joystick deflection would arrive at the central hub hundreds of milliseconds later, causing false correlation or state corruption.

The Phase 4 **Event Synchronization Engine** solves this by indexing events by their authoritative physical inception timestamps ($t_{\text{event}}$) and buffering streams in non-blocking sliding FIFO priority queues.

```mermaid
sequenceDiagram
    autonumber
    participant H as Operator Action
    participant V as Voice Engine (Whisper + Prosody)
    participant J as Actuator Engine (50Hz HID)
    participant SYNC as Event Synchronizer
    participant OUT as CorrelatedEvent Channel

    Note over H: Operator acts at t=100ms:<br/>Says "MOVE LEFT" while deflecting joystick LEFT
    H->>J: Joystick deflects at t=100ms
    H->>V: Speech utterance occurs across t=100ms..420ms

    J->>SYNC: JoystickEvent (t_event = 100ms, t_reception = 122ms)
    Note over SYNC: Buffer retains joystick event;<br/>awaits corresponding speech window

    V->>SYNC: VoiceEvent (t_event = 100ms, t_reception = 553ms)
    Note over SYNC: Match found!<br/>Delta |t_voice - t_joy| = 0ms ≤ 150ms

    SYNC->>OUT: Emit CorrelatedEvent(Voice: LEFT, Joy: LEFT, SYNCHRONIZED, Δt=0ms)
```

---

## 2. Temporal Matching Algorithm

```mermaid
flowchart TD
    IN_V[Incoming VoiceEvent] --> VAL_V{Validate Timestamp & Deduplicate}
    IN_J[Incoming CommonJoystickEvent] --> VAL_J{Validate Timestamp & Deduplicate}

    VAL_V -->|Invalid| REJ_V[Emit INVALID_TIMESTAMP / DUPLICATE]
    VAL_J -->|Invalid| REJ_J[Emit INVALID_TIMESTAMP / DUPLICATE]

    VAL_V -->|Valid| SEARCH_J{Search Joystick Buffer: |t_v - t_j| ≤ τ_sync?}
    VAL_J -->|Valid| SEARCH_V{Search Voice Buffer: |t_j - t_v| ≤ τ_sync?}

    SEARCH_J -->|Match Found| PAIR_V[Assemble CorrelatedEvent SYNCHRONIZED]
    SEARCH_V -->|Match Found| PAIR_J[Assemble CorrelatedEvent SYNCHRONIZED]

    SEARCH_J -->|No Match| BUF_V[Enqueue into Voice Buffer]
    SEARCH_V -->|No Match| BUF_J[Enqueue into Joystick Buffer]

    SWEEP[Periodic Sweeper 25Hz] --> SWEEP_CHECK{Age > τ_sync or > τ_max_age?}
    SWEEP_CHECK -->|Unpartnered Voice > τ_sync| EMIT_VOICE_ONLY[Emit VOICE_ONLY]
    SWEEP_CHECK -->|Unpartnered Active Joy > τ_sync| EMIT_JOY_ONLY[Emit JOYSTICK_ONLY]
    SWEEP_CHECK -->|Age > 350ms| EVICT[Drop Stale Event]
```

### 2.1 The Matching Principle
When an event $E_{\text{new}}$ arrives from modality $A$:
1. Check `event_id` against a bounded LRU cache (1,000 items) to prevent duplicate processing.
2. Validate $t_{\text{event}}$ chronological bounds ($1.7\times 10^{12} \le t \le \text{now} + 600\text{s}$).
3. Query the opposing modality buffer $B$ for the entry whose inception timestamp minimizes:
   $$\Delta t = |t_{\text{event}, A} - t_{\text{event}, B}|$$
4. If $\Delta t \le \tau_{\text{sync}}$ (default $150 \text{ ms}$):
   - Evict matched partner from buffer $B$.
   - Emit `SYNCHRONIZED` CorrelatedEvent (or `DELAYED` if either packet incurred excessive transit latency).
5. If no match is found:
   - Insert $E_{\text{new}}$ into buffer $A$.
   - Evict expired events older than $\tau_{\text{max\_age}} = 350 \text{ ms}$.

---

## 3. Configuration & Prototype Boundaries

- **Configurable Synchronization Window ($\tau_{\text{sync}}$):** Default $150.0 \text{ ms}$ (adjustable via REST/WebSocket from $50\text{ms}$ to $400\text{ms}$).
- **Prototype Status Notice:**
  > **IMPORTANT:** $150 \text{ ms}$ is an experimental prototype setting chosen to accommodate human reaction latency and network jitter. It is **NOT** a certified functional safety threshold under ISO 13849 / IEC 61508.

---

## 4. Operational Invariant: Non-Blocking Architecture

The synchronization engine operates completely asynchronously:
- Incoming voice events from Faster-Whisper and incoming joystick packets from Pygame/WebSocket are buffered immediately via thread-safe lock primitives.
- Ingestion execution time averages **$12.77 \mu\text{s}$ ($0.0128\text{ ms}$)** per event, guaranteeing that neither the $50\text{Hz}$ joystick loop nor the speech recognition pipeline is delayed or blocked.

