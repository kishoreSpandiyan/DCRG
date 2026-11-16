"""
Phase 4 Event Synchronization & Correlation Engine Benchmarking Script.
Measures actual throughput, average & max event processing times,
synchronization latency, buffer size under load, and memory usage.
"""

import os
import sys
import time
import numpy as np
import psutil

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.modules.voice_engine.schemas import VoiceEvent, CanonicalCommand, SemanticStatus
from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
)
from app.modules.sync_engine.synchronizer import EventSynchronizer


def generate_mock_voice_event(seq_id: int, timestamp: float) -> VoiceEvent:
    cmds = [CanonicalCommand.FORWARD, CanonicalCommand.BACKWARD, CanonicalCommand.LEFT, CanonicalCommand.RIGHT, CanonicalCommand.STOP]
    cmd = cmds[seq_id % len(cmds)]
    return VoiceEvent(
        event_id=f"MOCK-VOICE-{seq_id:06d}",
        timestamp=timestamp,
        transcript=cmd.value,
        normalized_transcript=cmd.value.lower(),
        recognized_command=cmd,
        recognition_confidence=0.95,
        classification_confidence=0.98,
        semantic_status=SemanticStatus.VALID,
    )


def generate_mock_joystick_event(seq_id: int, timestamp: float) -> CommonJoystickEvent:
    dirs = [JoystickDirection.FORWARD, JoystickDirection.BACKWARD, JoystickDirection.LEFT, JoystickDirection.RIGHT, JoystickDirection.CENTER]
    d = dirs[seq_id % len(dirs)]
    return CommonJoystickEvent(
        event_id=f"MOCK-JOY-{seq_id:06d}",
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="BENCH-JOY-01",
        timestamp=timestamp,
        axis_x=0.85 if "RIGHT" in d.value else -0.85 if "LEFT" in d.value else 0.0,
        axis_y=0.85 if "FORWARD" in d.value else 0.0,
        direction=d,
        intensity=0.85,
        is_simulation=True,
        connection_status=ConnectionStatus.CONNECTED,
        calibration_status=CalibrationStatus.DEFAULT,
        data_validity=DataValidity.VALID,
    )


def benchmark_synchronization_engine(num_pairs: int = 2000):
    print(f"\n========================================================")
    print(f" DCRG Phase 4: Event Synchronization Benchmark ({num_pairs} pairs)")
    print(f"========================================================")

    proc = psutil.Process(os.getpid())
    mem_before = proc.memory_info().rss / (1024 * 1024)

    sync = EventSynchronizer(sync_window_ms=150.0, max_event_age_ms=350.0, buffer_capacity=500)

    # Pre-generate events with varying deltas (0ms to 120ms within window)
    now_ms = time.time() * 1000.0
    v_events = []
    j_events = []

    np.random.seed(42)
    deltas = np.random.uniform(0.0, 120.0, num_pairs)

    for i in range(num_pairs):
        t_base = now_ms + (i * 20.0)  # 50Hz stream simulation
        v_events.append(generate_mock_voice_event(i, t_base))
        j_events.append(generate_mock_joystick_event(i, t_base + deltas[i]))

    # Benchmark: Ingestion and correlation time
    latencies_us = []
    t_start_total = time.perf_counter()

    for i in range(num_pairs):
        # Voice arrives
        t0 = time.perf_counter()
        sync.ingest_voice_event(v_events[i])
        t_v = time.perf_counter() - t0
        latencies_us.append(t_v * 1e6)

        # Joystick arrives
        t1 = time.perf_counter()
        corr = sync.ingest_joystick_event(j_events[i])
        t_j = time.perf_counter() - t1
        latencies_us.append(t_j * 1e6)

    total_duration_s = time.perf_counter() - t_start_total
    total_events = num_pairs * 2
    throughput = total_events / total_duration_s

    mem_after = proc.memory_info().rss / (1024 * 1024)

    avg_lat_us = float(np.mean(latencies_us))
    max_lat_us = float(np.max(latencies_us))
    p95_lat_us = float(np.percentile(latencies_us, 95))
    p99_lat_us = float(np.percentile(latencies_us, 99))

    avg_lat_ms = avg_lat_us / 1000.0
    max_lat_ms = max_lat_us / 1000.0

    status = sync.get_status()

    print(f"\n--- Empirical Results ---")
    print(f"Total Events Ingested: {total_events} ({num_pairs} Voice + {num_pairs} Joystick)")
    print(f"Total Synchronized Pairs: {status.total_synchronized_count}")
    print(f"Total Duration: {total_duration_s:.4f} seconds")
    print(f"Event Throughput: {throughput:,.1f} events/second")
    print(f"Average Processing Time: {avg_lat_us:.2f} µs ({avg_lat_ms:.4f} ms)")
    print(f"95th Percentile Latency: {p95_lat_us:.2f} µs ({p95_lat_us / 1000.0:.4f} ms)")
    print(f"99th Percentile Latency: {p99_lat_us:.2f} µs ({p99_lat_us / 1000.0:.4f} ms)")
    print(f"Maximum Processing Time: {max_lat_us:.2f} µs ({max_lat_ms:.4f} ms)")
    print(f"Peak Buffer Size Under Load: Voice={status.voice_buffer_count}, Joystick={status.joystick_buffer_count}")
    print(f"Peak Memory Footprint: {mem_after:.2f} MB (Delta: +{mem_after - mem_before:.2f} MB)")
    print(f"Synchronization Window: {sync.sync_window_ms} ms")
    print(f"Mean Paired Temporal Delta: {np.mean(deltas):.2f} ms")
    print(f"========================================================\n")

    return {
        "num_pairs": num_pairs,
        "total_events": total_events,
        "throughput": round(throughput, 1),
        "avg_lat_ms": round(avg_lat_ms, 4),
        "max_lat_ms": round(max_lat_ms, 4),
        "p99_lat_ms": round(p99_lat_us / 1000.0, 4),
        "mem_mb": round(mem_after, 2),
        "sync_window_ms": sync.sync_window_ms,
        "mean_temporal_delta_ms": round(float(np.mean(deltas)), 2),
    }


if __name__ == "__main__":
    benchmark_synchronization_engine(num_pairs=2000)

