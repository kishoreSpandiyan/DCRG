# DCRG Phase 5: Fusion Event Contracts & Schemas

> **Specification Standard:** DCRG-ARCH-011 Section 1.6  
> **Status:** Operational  

---

## 1. Fusion Result Contract (`FusionResult`)

The primary output schema emitted by the DCRG Fusion Engine over REST and WebSocket streams:

```json
{
  "fusion_id": "771e89b4-522f-4c91-a1b7-9918231c5011",
  "correlation_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "sync_id": "55b1e621-3c29-411a-82ee-06bdf2c38410",
  "timestamp": 1730851200155.0,
  "timestamp_ms": 1730851200155.0,
  "voice_command": "FORWARD",
  "joystick_direction": "FORWARD",
  "joystick_intensity": 0.86,
  "semantic_reliability": 0.914,
  "motor_agreement": 0.978,
  "context_consistency": 1.000,
  "factors": {
    "semantic_score": 0.914,
    "motor_agreement": 0.978,
    "context_consistency": 1.000,
    "angular_delta_deg": 0.0,
    "cosine_similarity": 1.0,
    "sync_quality": 0.98
  },
  "CRS": 95.8,
  "crs_score": 95.8,
  "CRS_status": "COMPLETE",
  "contradiction_detected": false,
  "veto_asserted": false,
  "contradiction_reason": null,
  "synchronization_status": "SYNCHRONIZED",
  "temporal_delta_ms": 12.0,
  "evidence_completeness": 1.0,
  "missing_components": [],
  "scoring_config_version": "v1.0-prototype",
  "weights": {
    "semantic": 0.35,
    "motor": 0.50,
    "context": 0.15
  },
  "explanation": "Evaluated multimodal pair [Voice: FORWARD (conf=0.94) | Joystick: FORWARD (intensity=0.86)]. Factors: Semantic=0.91, Motor=0.98, Context=1.00. Weights: [Ws=0.35, Wm=0.50, Wc=0.15]. Raw CRS: 95.8 -> Final CRS: 95.8/100 (COMPLETE). Finding: AGREEMENT.",
  "analytical_finding": "AGREEMENT",
  "recommended_state": "GREEN"
}
```

---

## 2. Enumerations

### 2.1 `CRSStatus`
- **`COMPLETE`**: Voice and joystick paired within matching window; context valid.
- **`PROVISIONAL`**: Single-modality input evaluated or context unverified; scored conservatively without fabrication.
- **`INCOMPLETE`**: Critical information missing or speech classifier reported `UNKNOWN`/`UNCERTAIN`.
- **`INVALID`**: Timestamps corrupted, out of chronological bounds, or malformed payload.

### 2.2 `AnalyticalFinding`
- **`AGREEMENT`**: Multimodal alignment verified ($S > 0.60, M > 0.60$).
- **`CONTRADICTION`**: Direct opposing directions or active joystick during spoken `STOP`.
- **`UNKNOWN_COMMAND`**: Speech classifier returned `UNKNOWN`.
- **`UNCERTAIN_COMMAND`**: Speech classifier flagged command as `UNCERTAIN`.
- **`NEUTRAL_JOYSTICK`**: Operator commanded motion via voice but physical joystick is centered.
- **`INSUFFICIENT_EVIDENCE`**: Insufficient multimodal evidence to confirm intent.
- **`CONTEXT_UNAVAILABLE`**: Operational context telemetry offline.
- **`CONTEXT_VIOLATION`**: Commanded motion violates mission mode, obstacle buffers, or active constraints.

---

## 3. Configuration Contract (`FusionConfig`)

```json
{
  "weight_semantic": 0.35,
  "weight_motor": 0.50,
  "weight_context": 0.15,
  "stress_damping": 0.25,
  "contradiction_cap": 30.0,
  "contradiction_whisper_min": 0.70,
  "contradiction_joystick_min": 0.30,
  "joystick_deadzone": 0.08,
  "scoring_config_version": "v1.0-prototype"
}
```
Validation Rule: `weight_semantic + weight_motor + weight_context == 1.0` within $\pm 0.0001$.

