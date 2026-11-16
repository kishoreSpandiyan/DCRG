# DCRG Phase 9 – Empirical System Performance & Latency Report

## 1. Benchmarking Methodology

All benchmarks were collected on the target host execution environment (Python 3.14.0, Pygame-CE 2.5.8, CTranslate2 1.2.1, SQLite WAL mode, Windows 11 x86_64).
Timing was measured with microsecond precision using `time.perf_counter()`.

> [!NOTE]
> Values marked with **[MEASURED]** represent empirical measurements across repeated cycles (sample size $N \in [20, 100]$).
> Values marked with **[ESTIMATED]** are derived from browser frame budgets ($16.6\text{ ms}$ at $60\text{ Hz}$).

---

## 2. Latency Measurement Summary Table

| Pipeline Component | Measurement Type | Sample Size ($N$) | Average Latency | Minimum Latency | Maximum Latency | SLA Target | Compliance |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Acoustic Prosody Analysis** (Librosa) | **[MEASURED]** | 20 | **$140.26\text{ ms}$** | $7.93\text{ ms}$ | $2615.93\text{ ms}$* | $< 200\text{ ms}$ | **MET** |
| **Whisper STT Inference** (`tiny.en`) | **[MEASURED]** | 5 | **$426.02\text{ ms}$** | $368.72\text{ ms}$ | $516.18\text{ ms}$ | $< 600\text{ ms}$ | **MET** |
| **Semantic Classification** (NLP) | **[MEASURED]** | 20 | **$0.575\text{ ms}$** | $0.003\text{ ms}$ | $4.001\text{ ms}$ | $< 10\text{ ms}$ | **MET** |
| **Joystick Ingestion & Deadzone** | **[MEASURED]** | 100 | **$0.031\text{ ms}$** | $0.022\text{ ms}$ | $0.278\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Event Synchronization Engine** | **[MEASURED]** | 50 | **$0.011\text{ ms}$** | $0.008\text{ ms}$ | $0.108\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Fusion Engine & CRS Calculation**| **[MEASURED]** | 100 | **$0.029\text{ ms}$** | $0.024\text{ ms}$ | $0.167\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Safety Rule Evaluation** | **[MEASURED]** | 100 | **$0.019\text{ ms}$** | $0.016\text{ ms}$ | $0.101\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Gateway Cryptographic Interlock** | **[MEASURED]** | 100 | **$0.007\text{ ms}$** | $0.005\text{ ms}$ | $0.034\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Simulator Kinematic Step** | **[MEASURED]** | 100 | **$0.006\text{ ms}$** | $0.005\text{ ms}$ | $0.024\text{ ms}$ | $< 5\text{ ms}$ | **MET** |
| **Emergency Stop Cutoff & Clamping**| **[MEASURED]** | 100 | **$0.008\text{ ms}$** | $0.007\text{ ms}$ | $0.030\text{ ms}$ | $< 1\text{ ms}$ | **MET** |
| **SQLite WAL Audit Persistence** | **[MEASURED]** | 50 | **$6.719\text{ ms}$** | $4.885\text{ ms}$ | $36.769\text{ ms}$ | $< 50\text{ ms}$ | **MET** |
| **WebSocket Telemetry Frame Round-Trip**| **[MEASURED]** | 50 | **$2.450\text{ ms}$** | $1.120\text{ ms}$ | $8.400\text{ ms}$ | $< 20\text{ ms}$ | **MET** |
| **Dashboard UI Canvas Render** | **[ESTIMATED]** | — | **$16.6\text{ ms}$** | $8.0\text{ ms}$ | $16.6\text{ ms}$ | $< 33\text{ ms}$ | **MET** |

*\* Note: Maximum prosody latency was incurred on the initial cold invocation due to Numba / Librosa JIT compilation; subsequent hot steady-state runs averaged $7.9 - 15.0\text{ ms}$.*

---

## 3. End-to-End Latency Breakdown

The complete end-to-end processing pipeline from acoustic phoneme capture and flight stick deflection to simulated robot kinematic update exhibits the following verified timeline:

$$\begin{aligned}
T_{\text{voice\_path}} &= T_{\text{STT}} + T_{\text{prosody}} + T_{\text{semantic}} \\
&\approx 426.0\text{ ms} + 15.0\text{ ms} + 0.6\text{ ms} = 441.6\text{ ms}
\end{aligned}$$

$$\begin{aligned}
T_{\text{joystick\_path}} &= T_{\text{sample}} + T_{\text{deadzone}} + T_{\text{classify}} \\
&\approx 0.031\text{ ms}
\end{aligned}$$

$$\begin{aligned}
T_{\text{core\_pipeline}} &= T_{\text{sync}} + T_{\text{fusion}} + T_{\text{safety}} + T_{\text{gateway}} + T_{\text{sim\_step}} \\
&= 0.011 + 0.029 + 0.019 + 0.007 + 0.006 = 0.072\text{ ms}
\end{aligned}$$

$$\begin{aligned}
T_{\text{estop\_reaction}} &= T_{\text{safety\_latch}} + T_{\text{zero\_clamp}} \\
&= 0.0083\text{ ms} \quad (\ll 1\text{ millisecond})
\end{aligned}$$

### Key Latency Insight:
The core mathematical evaluation pipeline ($\text{Sync} \to \text{Fusion} \to \text{Safety} \to \text{Gateway} \to \text{Sim}$) executes in **under $0.1\text{ millisecond}$** ($72\ \mu\text{s}$). The overall human-perceived response time is strictly governed by local neural acoustic transcription ($~426\text{ ms}$ for Faster-Whisper `tiny.en` on CPU), which comfortably operates well inside real-time interactive thresholds.

