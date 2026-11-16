# DCRG Phase 9 – Known Limitations & Physical Boundary Constraints

## 1. Hardware Constraints & Untested Elements

1. **Physical USB Flight Joystick Hardware Absence**:
   - **Limitation**: While the Pygame-CE (SDL2 DirectInput / XInput) background polling loop (50Hz) and device disconnection recovery were validated, no physical flight-simulator joystick was physically connected to the host USB ports during testing.
   - **Impact**: Physical potentiometer resistance curves, hardware deadband calibration for specific flight sticks, and physical trigger tactile release could not be physically evaluated on real hardware.
   - **Mitigation / Fallback**: The Virtual Touch/Mouse Canvas and Browser Gamepad API (`useGamepad.ts`) were used and verified.

2. **Acoustic Transducer Environment**:
   - **Limitation**: Acoustic validation was conducted using the laptop's integrated Realtek(R) Audio microphone array. External industrial noise-cancelling boom headsets or specialized far-field beamforming microphone arrays were not tested in physical noise chambers.
   - **Impact**: Heavy industrial background environments ($> 85\text{ dBA}$ ambient noise from factory machinery) were evaluated via synthetic signal-to-noise ratio testing rather than real acoustic reverberation chambers.

3. **Disabled Physical Actuators (Software Containment)**:
   - **Limitation**: In strict adherence to project safety rules, all physical motor outputs, CAN bus interfaces, and microcontroller PWM drivers were disabled.
   - **Impact**: Physical motor torque, back-EMF, motor slip, and mechanical latency cannot be observed.
   - **Status**: By design; all execution is directed to the 2D kinematic simulation engine.

---

## 2. Algorithmic & Environmental Limitations

1. **Local Neural STT Latency on CPU**:
   - Faster-Whisper `tiny.en` running quantized int8 inference on an x86_64 CPU requires an average of $426.0\text{ ms}$ per 1-second utterance. While optimal for CPU deployment, hardware-accelerated GPU inference (CUDA / TensorRT) would reduce this to $< 50\text{ ms}$.

2. **Vocabulary Scope**:
   - The primary speech recognition vocabulary is currently optimized for English operational primitives (`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`, `HALT`, `FREEZE`). Commands outside this canonical vocabulary are categorized defensively as `UNKNOWN` ($c=0.00$) to prevent hazardous guessing.

3. **Safety Certification Disclaimer**:
   - This prototype is designed for research, academic evaluation, and proof-of-concept demonstration. It has **NOT** undergone formal functional safety certification under IEC 61508 (SIL 3), ISO 13849-1 (Category 4 PLe), or ISO 10218 standards. Independent hardware safety cutoffs must precede any real-world physical machinery deployment.

