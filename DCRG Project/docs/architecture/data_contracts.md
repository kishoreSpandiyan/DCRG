# Formal Data Contracts & JSON Specifications

> **Document ID:** DCRG-ARCH-011  
> **Status:** Approved Architecture Draft (Phase 1)  
> **Format:** JSON Schema / Pydantic Models

---

## 1. Core Event Schemas

### 1.1 Voice Event (`VoiceEvent`)
Emitted by `voice_engine` + `semantic_engine` upon VAD utterance finalization:

```json
{
  "event_id": "c7a840e6-5b32-4217-91a0-d4cf3832b8aa",
  "operator_id": "OP-042",
  "timestamp_event_ms": 1730851200100,
  "timestamp_proc_ms": 1730851200145,
  "transcript": "MOVE FORWARD",
  "classified_command": "FORWARD",
  "confidence": 0.942,
  "is_uncertain": false,
  "direction_vector": { "x": 0.0, "y": 1.0 },
  "audio_duration_ms": 420
}
```

### 1.2 Prosody Event (`ProsodyEvent`)
Emitted by `prosody_engine` concurrently with Voice Event:

```json
{
  "event_id": "f293b6e1-45cd-4f91-8ba3-e029c211f32a",
  "operator_id": "OP-042",
  "timestamp_event_ms": 1730851200100,
  "pitch_f0_mean": 158.4,
  "pitch_f0_std": 14.2,
  "f0_elevation_pct": 21.8,
  "jitter_local": 0.012,
  "shimmer_local": 0.028,
  "speech_rate_syl_per_sec": 4.8,
  "composite_stress_score": 0.28,
  "is_stressed": false
}
```

### 1.3 Real Joystick Event (`PhysicalJoystickEvent`)
Emitted by `backend/app/hardware/` via Pygame SDL2 HAL at $50\text{Hz}$:

```json
{
  "event_id": "8d3e91b2-10f4-4e32-9cb7-64219a770e21",
  "source": "PHYSICAL_HARDWARE",
  "is_simulation": false,
  "device_id": "USB-046d-c215",
  "timestamp_event_ms": 1730851200115,
  "axis_x": 0.04,
  "axis_y": 0.86,
  "direction": "FORWARD",
  "intensity": 0.861,
  "buttons": [false, false, false, false, false, false, false, false, false, false, false, false],
  "connection_status": "CONNECTED",
  "calibration_status": "CALIBRATED",
  "data_validity": "VALID"
}
```

### 1.4 Virtual Joystick Event (`VirtualJoystickEvent`)
Emitted by React canvas or keyboard handler via WebSocket at $50\text{Hz}$:

```json
{
  "event_id": "a910f274-984e-4b2a-829d-58721c43b999",
  "source": "VIRTUAL_SIMULATION",
  "is_simulation": true,
  "device_id": "VIRT-REACT-CANVAS",
  "timestamp_event_ms": 1730851200118,
  "axis_x": 0.00,
  "axis_y": 0.85,
  "direction": "FORWARD",
  "intensity": 0.850,
  "buttons": [false, false, false, false],
  "connection_status": "CONNECTED",
  "calibration_status": "DEFAULT",
  "data_validity": "VALID"
}
```

### 1.5 Synchronized Event Bundle (`SynchronizedEventBundle`)
Assembled by `event_synchronization_service`:

```json
{
  "sync_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "timestamp_ms": 1730851200150,
  "temporal_delta_ms": 15.0,
  "voice": {
    "event_id": "c7a840e6-5b32-4217-91a0-d4cf3832b8aa",
    "command": "FORWARD",
    "confidence": 0.942,
    "stress_score": 0.28
  },
  "joystick": {
    "event_id": "8d3e91b2-10f4-4e32-9cb7-64219a770e21",
    "direction": "FORWARD",
    "intensity": 0.861,
    "is_simulation": false
  },
  "context": {
    "current_velocity": 0.0,
    "nearest_obstacle_m": 4.5
  },
  "alignment_status": "ALIGNED"
}
```

### 1.6 Fusion Result (`FusionResult`)
Emitted by `fusion_engine`:

```json
{
  "fusion_id": "771e89b4-522f-4c91-a1b7-9918231c5011",
  "sync_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "timestamp_ms": 1730851200155,
  "factors": {
    "semantic_score": 0.914,
    "motor_agreement": 0.978,
    "context_consistency": 1.000
  },
  "angular_delta_deg": 2.66,
  "crs_score": 95.8,
  "veto_asserted": false,
  "recommended_state": "GREEN"
}
```

### 1.7 Safety Decision (`SafetyDecision`)
Emitted by `safety_engine`:

```json
{
  "decision_id": "90e1bc3a-96c8-472d-88b9-43c224a1b029",
  "fusion_id": "771e89b4-522f-4c91-a1b7-9918231c5011",
  "timestamp_ms": 1730851200156,
  "authorization_state": "GREEN",
  "movement_authorized": true,
  "denial_reason": null,
  "auth_token": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "active_motion": {
    "primitive": "FORWARD",
    "linear_velocity": 0.75,
    "angular_velocity": 0.0
  }
}
```

### 1.8 Robot Command (`RobotCommand`)
Received and processed by `SimulationGateway` (or hardware gateway):

```json
{
  "command_id": "33fa29c1-419b-449e-bc21-081977cf2010",
  "decision_id": "90e1bc3a-96c8-472d-88b9-43c224a1b029",
  "timestamp_ms": 1730851200158,
  "auth_token": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "linear_velocity_mps": 0.60,
  "angular_velocity_radps": 0.0,
  "motion_primitive": "FORWARD",
  "is_simulation": true
}
```

### 1.9 Emergency Stop Event (`EstopEvent`)
Out-of-band immediate interrupt trigger:

```json
{
  "estop_id": "ee114400-0000-4444-8888-000000000001",
  "source": "HARDWARE_PUSHBUTTON",
  "timestamp_ms": 1730851200160,
  "interrupt_level": "HARD_INTERRUPT",
  "previous_state": "GREEN",
  "new_state": "EMERGENCY",
  "relay_cut_asserted": true,
  "message": "Physical emergency stop mushroom head depressed"
}
```

---

## 2. Validation Rules & Standard Error Responses

```json
{
  "error": "SCHEMA_VALIDATION_ERROR",
  "status_code": 422,
  "timestamp_ms": 1730851200200,
  "detail": [
    {
      "loc": ["body", "axis_x"],
      "msg": "Input should be greater than or equal to -1.0",
      "type": "greater_than_equal"
    }
  ],
  "safety_action": "REJECT_PACKET_TRANSITION_TO_YELLOW"
}
```

