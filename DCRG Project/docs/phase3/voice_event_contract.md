# Voice Event Data Contract & Specification

> **Document ID:** DCRG-DOC-P3-004  
> **Status:** Completed Phase 3 Deliverable  
> **Compliance:** Strict Compatibility with `DCRG-ARCH-011` & `DCRG-ARCH-002`

---

## 1. Unified `VoiceEvent` Data Contract

The `VoiceEvent` model provides a standardized representation of recognized speech and prosodic telemetry emitted by the Phase 3 subsystem.

```json
{
  "event_id": "c7a840e6-5b32-4217-91a0-d4cf3832b8aa",
  "timestamp": 1730851200100.0,
  "timestamp_event_ms": 1730851200100.0,
  "timestamp_proc_ms": 1730851200145.0,
  "source": "voice",
  "operator_id": "OP-PRIMARY",
  "transcript": "MOVE FORWARD",
  "normalized_transcript": "move forward",
  "recognized_command": "FORWARD",
  "classified_command": "FORWARD",
  "recognition_confidence": 0.942,
  "classification_confidence": 0.950,
  "confidence": 0.942,
  "semantic_status": "VALID",
  "is_uncertain": false,
  "direction_vector": {
    "x": 0.0,
    "y": 1.0
  },
  "audio_duration_ms": 420.0,
  "pitch_f0": 158.4,
  "pitch_f0_std": 14.2,
  "jitter": 0.012,
  "shimmer": 0.028,
  "speech_rate": 4.8,
  "intensity": 0.28,
  "audio_quality": "GOOD",
  "model_version": "faster-whisper-tiny.en",
  "composite_stress_score": 0.280,
  "stress_score": 0.280,
  "is_stressed": false
}
```

---

## 2. Field Directory & Validation Matrix

| Field | Type | Range / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `event_id` | `string` | UUID v4 | Unique identifier for the voice event |
| `timestamp` | `float` | $\ge 1.7\times 10^{12} \text{ ms}$ | Unix timestamp in milliseconds |
| `timestamp_event_ms`| `float` | Alias to `timestamp` | Backward compatibility with DCRG-ARCH-011 |
| `timestamp_proc_ms` | `float` | $\ge \text{timestamp}$ | Processing completion timestamp |
| `source` | `literal` | Fixed to `"voice"` | Modality ingress identifier |
| `operator_id` | `string` | Non-empty | Operator identification string |
| `transcript` | `string` | UTF-8 text | Raw recognized speech transcript |
| `normalized_transcript` | `string` | Lowercase, clean | Normalized transcript used for classification |
| `recognized_command` | `enum` | CanonicalCommand | `FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`, `UNKNOWN`, `UNCERTAIN` |
| `classified_command` | `string` | Alias | String value of recognized_command |
| `recognition_confidence` | `float` | $[0.0, 1.0]$ | STT acoustic/decoder probability $e^{\overline{\log P}}$ |
| `classification_confidence` | `float` | $[0.0, 1.0]$ | NLP classification certainty score |
| `semantic_status` | `enum` | SemanticStatus | `VALID`, `UNCERTAIN`, `UNKNOWN`, `REJECTED` |
| `is_uncertain` | `boolean` | `true` or `false` | Set when speech is ambiguous or below threshold |
| `direction_vector` | `object` | `{"x": [-1.0, 1.0], "y": [-1.0, 1.0]}` | Normalized 2D displacement unit vector |
| `audio_duration_ms` | `float` | $\ge 0.0$ | Length of speech segment in milliseconds |
| `pitch_f0` | `float` | $[0.0, 1000.0] \text{ Hz}$ | Fundamental frequency mean |
| `pitch_f0_std` | `float` | $\ge 0.0$ | Standard deviation of fundamental frequency |
| `jitter` | `float` | $[0.0, 1.0]$ | Local cycle period perturbation |
| `shimmer` | `float` | $[0.0, 1.0]$ | Local cycle amplitude perturbation |
| `speech_rate` | `float` | $[0.0, 15.0] \text{ syl/s}$ | Estimated speech tempo |
| `intensity` | `float` | $[0.0, 1.0]$ | Normalized RMS acoustic intensity |
| `audio_quality` | `enum` | AudioQuality | `GOOD`, `NOISY`, `DEGRADED`, `SILENCE` |
| `model_version` | `string` | Model identifier | E.g. `"faster-whisper-tiny.en"` |
| `composite_stress_score` | `float` | $[0.0, 1.0]$ | Synthesized cognitive stress index |
| `is_stressed` | `boolean` | `true` or `false` | Stress threshold indicator ($S_{\text{stress}} \ge 0.60$) |

---

## 3. Direction Vectors per Canonical Command

```typescript
export const CANONICAL_DIRECTION_VECTORS: Record<CanonicalCommand, { x: number; y: number }> = {
  FORWARD:   { x:  0.0, y:  1.0 },
  BACKWARD:  { x:  0.0, y: -1.0 },
  LEFT:      { x: -1.0, y:  0.0 },
  RIGHT:     { x:  1.0, y:  0.0 },
  STOP:      { x:  0.0, y:  0.0 },
  UNKNOWN:   { x:  0.0, y:  0.0 },
  UNCERTAIN: { x:  0.0, y:  0.0 },
};
```

---

## 4. WebSocket Wire Protocol (`/ws/voice/stream`)

### Inbound Client Frames (Browser $\to$ Backend)
- **Start Microphone:**
  ```json
  { "type": "START_MIC" }
  ```
- **Stop Microphone:**
  ```json
  { "type": "STOP_MIC" }
  ```
- **Mute Microphone:**
  ```json
  { "type": "SET_MUTE", "muted": true }
  ```
- **Ping Keepalive:**
  ```json
  { "type": "PING", "timestamp": 1730851200000 }
  ```

### Outbound Broadcast Frames (Backend $\to$ Browser)
- **Initial Handshake Frame:**
  ```json
  {
    "type": "INITIAL_STATUS",
    "status": {
      "microphone_status": "DISCONNECTED",
      "is_capturing": false,
      "model_name": "tiny.en",
      "sample_rate": 16000
    }
  }
  ```
- **Real-time Voice Event Packet:**
  ```json
  {
    "type": "VOICE_EVENT",
    "data": { ...VoiceEvent object... }
  }
  ```

