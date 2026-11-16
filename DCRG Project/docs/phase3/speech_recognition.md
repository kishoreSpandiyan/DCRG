# Local Speech Recognition & Semantic Classification Specification

> **Document ID:** DCRG-DOC-P3-002  
> **Status:** Completed Phase 3 Deliverable  
> **Modules Covered:** `backend/app/modules/voice_engine/whisper_service.py`, `backend/app/modules/semantic_engine/classifier.py`

---

## 1. Engine Architecture & Model Selection

The DCRG speech recognition subsystem executes entirely on local compute using `faster-whisper`, a high-performance CTranslate2 port of OpenAI's Whisper model.

### 1.1 Model Configuration
- **Model Size:** `tiny.en` (Default for real-time CPU deployment; footprint $<165\text{MB}$)
- **Quantization:** `int8` (quantized weights and activations for minimal latency and memory)
- **Execution Device:** `cpu` (compatible with standard commercial host hardware without requiring dedicated CUDA GPUs)
- **Decoding Search:** Greedy search (`beam_size=1`, `best_of=1`) to optimize inference speed.
- **VAD Pre-filtering:** Enabled via Silero VAD parameters (`min_silence_duration_ms=250`) to avoid hallucinations on silence.

### 1.2 Lexical Conditioning Prompt
To bias the decoder logits toward operational robotics primitives, every inference run is pre-conditioned with an initial prompt:
```text
Robot command: forward, backward, left, right, stop, halt, freeze, move left, turn right, don't move.
```

---

## 2. Confidence Calculation Formulation

Whisper output segments include token-level log probabilities and average segment log probability ($\text{avg\_logprob}$).

The acoustic recognition confidence score is calculated as:
$$\text{Confidence}_{\text{STT}} = \min\left(1.0, \max\left(0.0, \exp\left(\overline{\log P}\right)\right)\right)$$

### 2.1 Confidence Gating Rule
- If $\text{Confidence}_{\text{STT}} < \tau_{\text{confidence}}$ (default threshold $\tau_{\text{confidence}} = 0.60$) OR $\overline{\log P} < -1.0$:
  - The utterance is tagged as `is_low_confidence = True`.
  - The Semantic Classifier immediately downgrades the command to `UNCERTAIN`.
  - **BINDING SAFETY RULE:** The engine NEVER guesses a movement command from unclear or low-confidence speech.

---

## 3. Canonical Command Vocabulary & Semantic Lexicon

| Canonical Command | Direction Vector $\vec{V} = (x, y)$ | Standard English Utterances | Classification Confidence |
| :--- | :--- | :--- | :--- |
| **`FORWARD`** | $(0.0, +1.0)$ | "forward", "move forward", "go forward", "ahead", "straight", "advance" | $0.88 - 1.00$ |
| **`BACKWARD`** | $(0.0, -1.0)$ | "backward", "backwards", "move backward", "back up", "reverse", "go back" | $0.88 - 1.00$ |
| **`LEFT`** | $(-1.0, 0.0)$ | "left", "move left", "turn left", "steer left", "rotate left", "step left" | $0.88 - 1.00$ |
| **`RIGHT`** | $(+1.0, 0.0)$ | "right", "move right", "turn right", "steer right", "rotate right", "step right" | $0.88 - 1.00$ |
| **`STOP`** | $(0.0, 0.0)$ | "stop", "halt", "freeze", "brake", "hold position", "don't move", "abort" | $0.92 - 1.00$ |
| **`UNCERTAIN`** | $(0.0, 0.0)$ | Contradictory phrases (e.g. "move left and right") or STT confidence $< 0.60$ | $0.00$ |
| **`UNKNOWN`** | $(0.0, 0.0)$ | Out-of-lexicon utterances (e.g. "hello", "what time is it") or empty audio | $0.00$ |

---

## 4. Ambiguity Resolution & Emergency Priority

1. **Emergency STOP Absolute Precedence:**
   - If an utterance contains emergency keywords ("stop", "halt", "don't move", "freeze"), `STOP` is immediately asserted regardless of any other directional tokens in the transcript.
   - Example: *"Stop moving left"* $\to$ Classifies as **`STOP`** (motion primitive $(0.0, 0.0)$).

2. **Directional Contradiction Handling:**
   - If an utterance contains conflicting directional commands without a stop keyword (e.g. *"Move left and right"* or *"Go forward and backward"*):
     - The engine rejects the input and classifies it as **`UNCERTAIN`**.
     - No directional motion is permitted.

3. **Shouting & Loud Voice Handling:**
   - An operator in a crisis shouting *"STOP"* with elevated vocal intensity and high pitch is validated as a legitimate `STOP` command. Shouting is never used to reject a safety command.

---

## 5. Multilingual Extensibility (Tamil Support)

The architecture separates language-dependent lexicon dictionaries and conditioning prompts:
- English (`en`): Active baseline.
- Tamil (`ta`): Implemented and extensible:
  - `STOP`: "நில்", "நிறுத்து", "நில்லு", "அப்படியே நில்"
  - `FORWARD`: "முன்னே போ", "முன்னாடி போ", "நேராக போ"
  - `BACKWARD`: "பின்னே போ", "பின்னாடி போ", "பின்னோக்கி போ"
  - `LEFT`: "இடது", "இடப்பக்கம்", "இடது பக்கம் திரும்பு"
  - `RIGHT`: "வலது", "வலப்பக்கம்", "வலது பக்கம் திரும்பு"

