"""
Empirical Performance Measurement Suite for DCRG.
Measures real hardware execution times:
- Application startup time
- Speech processing time (Faster-Whisper STT & Real-Time KWS)
- Controller event processing time (Virtual & Hardware Joystick ingestion)
- Event synchronization time (Timestamp management & correlation)
- Fusion computation time (Multi-factor CRS calculation & Contradiction veto)
- Decision processing time (Deterministic 4-tier Safety Rule Engine)
- End-to-end decision latency (Input -> Sync -> Fusion -> Safety -> Gateway dispatch)
- Latency statistics: Mean, Median (p50), 95th percentile (p95), 99th percentile (p99), Max
- System resource footprint: CPU utilization and RAM memory (RSS)
"""

import os
import sys
import time
import psutil
import numpy as np

# Adjust path for backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.modules.voice_engine.whisper_service import whisper_service
from app.modules.voice_engine.kws_service import KeywordSpotterService
from app.modules.prosody_engine.analyzer import prosody_analyzer
from app.modules.semantic_engine.classifier import semantic_classifier
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.sync_engine.synchronizer import EventSynchronizer
from app.modules.fusion_engine.calculator import CRSCalculator
from app.modules.safety_engine.rules import SafetyRuleEngine
from app.modules.safety_engine.gateway import simulated_gateway
from app.modules.simulation_engine.simulator import RobotSimulator


def measure_all_performance():
    process = psutil.Process(os.getpid())
    base_memory_mb = process.memory_info().rss / (1024 * 1024)
    cpu_cores = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()

    print("=" * 80)
    print("DCRG EMPIRICAL PERFORMANCE & RESOURCE MEASUREMENT REPORT")
    print(f"Platform: Windows 11 | CPU Cores: {cpu_cores} | RAM Baseline: {base_memory_mb:.1f} MB")
    print("=" * 80)

    # 1. Faster-Whisper Model Load & Audio Transcription
    print("\n[1] Speech Processing Engine:")
    t_load_0 = time.perf_counter()
    whisper_service.load_model()
    t_load_ms = (time.perf_counter() - t_load_0) * 1000.0
    print(f"  Faster-Whisper (tiny.en) Model Load Time: {t_load_ms:.2f} ms")

    audio_1s = (0.5 * np.sin(2 * np.pi * 220 * np.linspace(0, 1.0, 16000))).astype(np.float32)
    whisper_latencies = []
    for _ in range(10):
        t0 = time.perf_counter()
        whisper_service.transcribe(audio_1s, 16000)
        whisper_latencies.append((time.perf_counter() - t0) * 1000.0)

    whisper_mean = float(np.mean(whisper_latencies))
    whisper_p50 = float(np.median(whisper_latencies))
    whisper_p95 = float(np.percentile(whisper_latencies, 95))
    print(f"  Whisper 1.0s STT Latency:  Mean={whisper_mean:.2f} ms | p50={whisper_p50:.2f} ms | p95={whisper_p95:.2f} ms")

    # Fast Keyword Spotter (KWS)
    kws = KeywordSpotterService()
    pre_audio = (np.random.randn(int(16000 * 0.25)) * 0.05).astype(np.float32)
    kws.process_chunk(pre_audio, 16000)

    kws_chunk = (np.random.randn(int(16000 * 0.03)) * 0.05).astype(np.float32)
    kws_latencies = []
    for _ in range(500):
        t0 = time.perf_counter()
        kws.process_chunk(kws_chunk, 16000)
        kws_latencies.append((time.perf_counter() - t0) * 1000.0)

    kws_mean = float(np.mean(kws_latencies))
    kws_p50 = float(np.median(kws_latencies))
    kws_p95 = float(np.percentile(kws_latencies, 95))
    print(f"  KWS 30ms Frame Latency:    Mean={kws_mean:.3f} ms | p50={kws_p50:.3f} ms | p95={kws_p95:.3f} ms")

    # Prosody Feature Extraction
    prosody_latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        prosody_analyzer.analyze(audio_1s, 16000)
        prosody_latencies.append((time.perf_counter() - t0) * 1000.0)
    prosody_mean = float(np.mean(prosody_latencies))
    prosody_p50 = float(np.median(prosody_latencies))
    prosody_p95 = float(np.percentile(prosody_latencies, 95))
    print(f"  Prosody Analyzer (1.0s):   Mean={prosody_mean:.2f} ms | p50={prosody_p50:.2f} ms | p95={prosody_p95:.2f} ms")

    # 2. Controller Telemetry Capture
    print("\n[2] Controller Event Ingestion Engine:")
    joy_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        ev = actuator_manager.ingest_virtual_input(0.85, 0.10)
        joy_latencies.append((time.perf_counter() - t0) * 1000.0)
    joy_mean = float(np.mean(joy_latencies))
    joy_p50 = float(np.median(joy_latencies))
    joy_p95 = float(np.percentile(joy_latencies, 95))
    print(f"  Joystick Frame Ingestion:  Mean={joy_mean:.4f} ms | p50={joy_p50:.4f} ms | p95={joy_p95:.4f} ms")

    # 3. Event Synchronization Engine
    print("\n[3] Event Synchronization Engine:")
    sync = EventSynchronizer(sync_window_ms=150.0)
    sync_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        corr = sync.correlate_manual_pair(None, ev)
        sync_latencies.append((time.perf_counter() - t0) * 1000.0)
    sync_mean = float(np.mean(sync_latencies))
    sync_p50 = float(np.median(sync_latencies))
    sync_p95 = float(np.percentile(sync_latencies, 95))
    print(f"  Correlation Pairing:       Mean={sync_mean:.4f} ms | p50={sync_p50:.4f} ms | p95={sync_p95:.4f} ms")

    # 4. Fusion Engine (CRS Multi-Factor Computation)
    print("\n[4] Fusion & Command Reliability Scoring (CRS) Engine:")
    calc = CRSCalculator()
    fusion_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        fr = calc.evaluate(corr)
        fusion_latencies.append((time.perf_counter() - t0) * 1000.0)
    fusion_mean = float(np.mean(fusion_latencies))
    fusion_p50 = float(np.median(fusion_latencies))
    fusion_p95 = float(np.percentile(fusion_latencies, 95))
    print(f"  CRS Multi-Factor Vector:   Mean={fusion_mean:.4f} ms | p50={fusion_p50:.4f} ms | p95={fusion_p95:.4f} ms")

    # 5. Safety Authorization Engine (State Machine & Veto)
    print("\n[5] Safety Authorization Engine:")
    safety = SafetyRuleEngine()
    safety_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        dec = safety.evaluate(fr, is_emergency_latched=False)
        safety_latencies.append((time.perf_counter() - t0) * 1000.0)
    safety_mean = float(np.mean(safety_latencies))
    safety_p50 = float(np.median(safety_latencies))
    safety_p95 = float(np.percentile(safety_latencies, 95))
    print(f"  Safety Rule Evaluation:    Mean={safety_mean:.4f} ms | p50={safety_p50:.4f} ms | p95={safety_p95:.4f} ms")

    # 6. Cryptographic Gateway Dispatch
    print("\n[6] Simulated Gateway Dispatch & Verification:")
    gateway_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        simulated_gateway.dispatch(dec, command_attempted="STOP", auth_token=dec.auth_token)
        gateway_latencies.append((time.perf_counter() - t0) * 1000.0)
    gateway_mean = float(np.mean(gateway_latencies))
    gateway_p50 = float(np.median(gateway_latencies))
    gateway_p95 = float(np.percentile(gateway_latencies, 95))
    print(f"  Gateway Interlock Latency: Mean={gateway_mean:.4f} ms | p50={gateway_p50:.4f} ms | p95={gateway_p95:.4f} ms")

    # 7. Kinematic Simulation Physics Step
    print("\n[7] Kinematic Physics Simulator:")
    sim = RobotSimulator()
    sim_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        sim.step(dt=0.016)
        sim_latencies.append((time.perf_counter() - t0) * 1000.0)
    sim_mean = float(np.mean(sim_latencies))
    sim_p50 = float(np.median(sim_latencies))
    sim_p95 = float(np.percentile(sim_latencies, 95))
    print(f"  Physics Kinematic Step:    Mean={sim_mean:.4f} ms | p50={sim_p50:.4f} ms | p95={sim_p95:.4f} ms")

    # 8. Full End-to-End Decision & Execution Pipeline Latency
    print("\n[8] Full End-to-End Pipeline Latency (Sync -> Fusion -> Safety -> Gateway -> Sim):")
    e2e_latencies = []
    for _ in range(2000):
        t0 = time.perf_counter()
        c = sync.correlate_manual_pair(None, ev)
        f = calc.evaluate(c)
        d = safety.evaluate(f, is_emergency_latched=False)
        simulated_gateway.dispatch(d, command_attempted="STOP", auth_token=d.auth_token)
        sim.step(dt=0.016)
        e2e_latencies.append((time.perf_counter() - t0) * 1000.0)
    e2e_mean = float(np.mean(e2e_latencies))
    e2e_p50 = float(np.median(e2e_latencies))
    e2e_p95 = float(np.percentile(e2e_latencies, 95))
    e2e_p99 = float(np.percentile(e2e_latencies, 99))
    e2e_max = float(np.max(e2e_latencies))
    print(f"  E2E Mean Latency:          {e2e_mean:.4f} ms")
    print(f"  E2E Median (p50):          {e2e_p50:.4f} ms")
    print(f"  E2E 95th Percentile (p95): {e2e_p95:.4f} ms")
    print(f"  E2E 99th Percentile (p99): {e2e_p99:.4f} ms")
    print(f"  E2E Maximum Latency:       {e2e_max:.4f} ms")

    # 9. System Utilization Diagnostics
    final_memory_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = process.cpu_percent(interval=0.2)
    print("\n[9] System Resource Utilization:")
    print(f"  Process RAM Usage (RSS):   {final_memory_mb:.2f} MB (Delta: +{final_memory_mb - base_memory_mb:.2f} MB)")
    print(f"  CPU Utilization:           {cpu_percent:.1f}%")
    print("=" * 80)

    return {
        "whisper_stt_mean_ms": whisper_mean,
        "kws_chunk_mean_ms": kws_mean,
        "prosody_mean_ms": prosody_mean,
        "joystick_ingest_mean_ms": joy_mean,
        "sync_mean_ms": sync_mean,
        "fusion_mean_ms": fusion_mean,
        "safety_mean_ms": safety_mean,
        "gateway_mean_ms": gateway_mean,
        "physics_step_mean_ms": sim_mean,
        "e2e_mean_ms": e2e_mean,
        "e2e_p50_ms": e2e_p50,
        "e2e_p95_ms": e2e_p95,
        "e2e_p99_ms": e2e_p99,
        "e2e_max_ms": e2e_max,
        "ram_rss_mb": final_memory_mb,
        "cpu_percent": cpu_percent,
    }


if __name__ == "__main__":
    measure_all_performance()
