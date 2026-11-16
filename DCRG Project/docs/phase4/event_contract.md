# Event Synchronization Data Contracts & Wire Specifications

> **Document ID:** DCRG-DOC-P4-004  
> **Status:** Completed Phase 4 Deliverable  
> **Compliance:** Strict Compatibility with `DCRG-ARCH-011` Section 1.5

---

## 1. Unified `CorrelatedEvent` Contract

The `CorrelatedEvent` model encapsulates paired multi-modal inputs, synchronization metrics, and raw payloads.

```json
{
  "correlation_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "sync_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "correlation_timestamp": 1730851200150.0,
  "timestamp_ms": 1730851200150.0,
  "voice_event_id": "c7a840e6-5b32-4217-91a0-d4cf3832b8aa",
  "joystick_event_id": "8d3e91b2-10f4-4e32-9cb7-64219a770e21",
  "voice_command": "FORWARD",
  "joystick_direction": "FORWARD",
  "joystick_intensity": 0.861,
  "timestamp_difference_ms": 15.0,
  "temporal_delta_ms": 15.0,
  "synchronization_status": "SYNCHRONIZED",
  "voice_available": true,
  "joystick_available": true,
  "correlation_reason": "Paired within 150.0ms window (delta: 15.0ms)",
  "voice_event": {
    "event_id": "c7a840e6-5b32-4217-91a0-d4cf3832b8aa",
    "timestamp": 1730851200100.0,
    "transcript": "MOVE FORWARD",
    "normalized_transcript": "move forward",
    "recognized_command": "FORWARD",
    "recognition_confidence": 0.942,
    "classification_confidence": 0.950,
    "semantic_status": "VALID",
    "direction_vector": { "x": 0.0, "y": 1.0 },
    "audio_duration_ms": 420.0,
    "pitch_f0": 158.4,
    "intensity": 0.28,
    "audio_quality": "GOOD",
    "is_stressed": false
  },
  "joystick_event": {
    "event_id": "8d3e91b2-10f4-4e32-9cb7-64219a770e21",
    "source": "VIRTUAL_SIMULATION",
    "device_id": "VIRT-REACT-CANVAS",
    "timestamp": 1730851200115.0,
    "axis_x": 0.04,
    "axis_y": 0.86,
    "direction": "FORWARD",
    "intensity": 0.861,
    "connection_status": "CONNECTED",
    "data_validity": "VALID",
    "is_simulation": true
  },
  "context": {
    "current_velocity": 0.0,
    "nearest_obstacle_m": 4.5
  }
}
```

---

## 2. Field Definitions & Constraints

| Field | Type | Constraint | Description |
| :--- | :--- | :--- | :--- |
| `correlation_id` | `string` | UUID v4 | Primary unique identifier for the correlation record |
| `sync_id` | `string` | Alias | DCRG-ARCH-011 compatibility alias |
| `correlation_timestamp` | `float` | UTC ms epoch | Moment correlation was performed on server |
| `voice_event_id` | `string?` | UUID or null | Paired voice event ID |
| `joystick_event_id` | `string?` | UUID or null | Paired joystick event ID |
| `voice_command` | `string?` | CanonicalCommand | Recognized voice primitive (e.g. `'LEFT'`) |
| `joystick_direction` | `string?` | JoystickDirection | Classified joystick motion (e.g. `'RIGHT'`) |
| `joystick_intensity` | `float?` | $[0.0, 1.0]$ | Normalized joystick deflection magnitude |
| `timestamp_difference_ms`| `float?` | $\ge 0.0$ | $\|t_{\text{voice}} - t_{\text{joystick}}\|$ in milliseconds |
| `synchronization_status` | `enum` | SynchronizationStatus | `SYNCHRONIZED`, `VOICE_ONLY`, `JOYSTICK_ONLY`, `OUT_OF_WINDOW`, `DELAYED`, `STALE`, `INVALID_TIMESTAMP`, `DUPLICATE` |
| `voice_available` | `boolean` | `true`/`false` | Flag indicating voice presence |
| `joystick_available` | `boolean` | `true`/`false` | Flag indicating joystick presence |
| `correlation_reason` | `string` | UTF-8 string | Diagnostic narrative describing correlation decision |
| `voice_event` | `object?` | `VoiceEvent` | Full nested voice payload (null if absent) |
| `joystick_event` | `object?` | `CommonJoystickEvent`| Full nested joystick payload (null if absent) |

---

## 3. WebSocket Wire Protocol (`/ws/sync/stream`)

### Inbound Frames (Client $\to$ Backend)
- **Configure Parameters:**
  ```json
  { "type": "CONFIGURE", "sync_window_ms": 175.0, "max_event_age_ms": 400.0 }
  ```
- **Ping Keepalive:**
  ```json
  { "type": "PING", "timestamp": 1730851200000 }
  ```

### Outbound Broadcast Frames (Backend $\to$ Client)
- **Initial Status & History Frame:**
  ```json
  {
    "type": "INITIAL_STATUS",
    "status": { ...SyncEngineStatus... },
    "history": [ ...Array of recent CorrelatedEvent objects... ]
  }
  ```
- **Real-time Correlation Frame:**
  ```json
  {
    "type": "CORRELATED_EVENT",
    "data": { ...CorrelatedEvent... }
  }
  ```
- **Configuration Update Ack:**
  ```json
  {
    "type": "CONFIG_UPDATED",
    "status": { ...Updated SyncEngineStatus... }
  }
  ```

