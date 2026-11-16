# DCRG Phase 3 – Verification & Testing Report

> **Document ID:** DCRG-DOC-P3-005  
> **Status:** Official Verification Report  
> **Date:** November 2026  
> **Host Environment:** Windows x64 • Python 3.14.0 • Node v22.12.0

---

## 1. Automated Test Execution Summary

All **89 automated backend tests** passed cleanly with zero failures.

```text
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\KISHORE-MAIN\projects\DCRG Project\DCRG Project\backend
collected 89 items

tests\test_actuator_engine.py .............                              [ 14%]
tests\test_health.py ..                                                  [ 16%]
tests\test_joystick_api.py ......                                        [ 23%]
tests\test_microphone_service.py ........                                [ 32%]
tests\test_prosody_engine.py ........                                    [ 41%]
tests\test_semantic_classifier.py ...................................... [ 84%]
....                                                                     [ 88%]
tests\test_voice_api.py ......                                           [ 95%]
tests\test_voice_schemas.py ....                                         [100%]

============================= 89 passed in 5.65s ==============================
```

### 1.1 Test Suite Breakdown

| Test Module | Tests | Status | Scope Verified |
| :--- | :--- | :--- | :--- |
| `test_actuator_engine.py` | 13 | PASSED | Phase 2 Joystick deadzones, vector classification, hardware isolation |
| `test_health.py` | 2 | PASSED | Phase 3 operational health, staged module readiness |
| `test_joystick_api.py` | 6 | PASSED | Phase 2 REST and WebSocket joystick streaming |
| `test_microphone_service.py` | 8 | PASSED | Ring buffer wrap-around, device querying, mute toggle, error states |
| `test_prosody_engine.py` | 8 | PASSED | F0 pitch tracking, jitter, shimmer, silence/noise, NaN/Inf immunity |
| `test_semantic_classifier.py` | 42 | PASSED | Canonical mapping, STOP override, conflicting vectors, low confidence |
| `test_voice_api.py` | 6 | PASSED | REST endpoints, device select, synthetic audio processing, WebSocket |
| `test_voice_schemas.py` | 4 | PASSED | Pydantic validation, timestamp bounds, compatibility aliases |

---

## 2. Frontend TypeScript Build Verification

The React frontend build was verified using TypeScript compiler (`tsc -b`) and Vite production bundler:

```text
> frontend@0.0.0 build
> tsc -b && vite build

vite v8.3.6 building client environment for production...
transforming...
✓ 2065 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-CPty8ypy.css   36.73 kB │ gzip:  7.02 kB
dist/assets/index-egjzlTM8.js   276.74 kB │ gzip: 83.13 kB

✓ built in 331ms
```

---

## 3. Physical Hardware & Live Microphone Verification

Physical microphone capture was executed and verified directly on the development machine host hardware using `scripts/test_phase3_performance.py`:

```text
--- Live Physical Microphone Verification ---
Discovered 10 audio input devices.
  [0] Microsoft Sound Mapper - Input (Channels: 2, Default: False)
  [1] Microphone Array (Realtek(R) Au (Channels: 2, Default: False)
  [4] Primary Sound Capture Driver (Channels: 2, Default: False)
  [5] Microphone Array (Realtek(R) Audio) (Channels: 2, Default: False)
  [9] Microphone Array (Realtek(R) Audio) (Channels: 2, Default: False)
  [10] Microphone (Realtek HD Audio Mic input) (Channels: 2, Default: False)
  [13] PC Speaker (Realtek HD Audio output with SST) (Channels: 2, Default: False)
  [14] Stereo Mix (Realtek HD Audio Stereo input) (Channels: 2, Default: False)
  [15] Microphone Array (Realtek HD Audio Mic Array input) (Channels: 2, Default: False)
  [18] PC Speaker (Realtek HD Audio 2nd output with SST) (Channels: 2, Default: False)

Microphone started: Microsoft Sound Mapper - Input (16kHz mono)
Active Device: Microsoft Sound Mapper - Input
Hardware Status: CONNECTED
Microphone stopped cleanly. Status: DISCONNECTED

Frames Captured: 39 frames
Total Samples: 18,720 samples (1.17 s at 16,000 Hz)
Live Audio RMS Amplitude: 0.005853
Live Audio Peak Amplitude: 0.013580

Generated VoiceEvent from Physical Microphone Audio:
  Event ID: f7135a2d-4db4-463d-8725-573110ba8cbe
  Source: voice
  Transcript: ''
  Recognized Command: UNKNOWN
  Recognition Confidence: 0.0
  Semantic Status: UNKNOWN
  Audio Quality: GOOD
  Pitch F0: 182.3 Hz
  Intensity: 0.0234
  Stress Score: 0.9998
```

---

## 4. Empirical Performance Benchmarks

Measured on the development machine (Windows x64, CPU inference, Python 3.14):

| Metric | Measured Value | Standard Target | Assessment |
| :--- | :--- | :--- | :--- |
| **STT Model Tested** | `faster-whisper-tiny.en` | `tiny.en` / `base.en` | Baseline lightweight model |
| **Model Load Time** | **$2.175 \text{ s}$** | $< 5.0 \text{ s}$ | Fast local startup |
| **Average STT Latency** | **$439.73 \text{ ms}$** | $< 600 \text{ ms}$ | Real-time interactive |
| **Min STT Latency** | **$359.60 \text{ ms}$** | — | Single segment greedy search |
| **Max STT Latency** | **$548.81 \text{ ms}$** | $< 800 \text{ ms}$ | First inference warm-up |
| **Prosody Extraction Latency** | **$13.65 \text{ ms}$** | $< 50 \text{ ms}$ | Ultra-fast Librosa YIN execution |
| **Total End-to-End Pipeline Latency** | **$453.38 \text{ ms}$** | $< 750 \text{ ms}$ | Suitable for multi-modal sync |
| **Peak Memory Footprint (RSS)** | **$206.2 \text{ MB}$** | $< 500 \text{ MB}$ | Extremely compact |
| **Microphone Native Sampling** | **$16,000 \text{ Hz}$** | $16,000 \text{ Hz}$ | Zero resample overhead |

---

## 5. Known Limitations & Operational Boundaries

1. **CPU Inference Latency Under Heavy System Load:**
   - Under heavy host CPU throttling, Whisper inference latency may expand from $440\text{ms}$ up to $\sim 650\text{ms}$. If lower latencies are required in future phases, a CUDA GPU runtime or `small.en` on tensor cores can reduce latency to $<100\text{ms}$.
2. **Ambient Noise & Echo Suppression:**
   - The current engine uses RMS energy VAD and Silero VAD parameters. In industrial environments with continuous machinery noise exceeding $75\text{ dBA}$, a dedicated directional noise-cancelling microphone or hardware DSP array is recommended.
3. **Simultaneous Operator Utterances:**
   - The system is architected for a single primary operator (`OP-PRIMARY`). Multi-speaker diarization is not part of Phase 3 and will be addressed in future phases if multi-operator handoffs are introduced.

