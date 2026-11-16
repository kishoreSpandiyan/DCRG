"""
DCRG Phase 5 Fusion Engine & CRS Computation Performance Benchmark.
Evaluates:
- Evaluation latency (mean, median, p95, p99, max)
- Maximum throughput (evaluations / sec)
- Contradiction veto detection latency
- Memory RSS baseline vs under sustained load
"""

import time
import os
import sys
import statistics

# Ensure backend modules are on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.modules.fusion_engine.calculator import CRSCalculator
from app.modules.sync_engine.schemas import CorrelatedEvent, SynchronizationStatus
from app.modules.voice_engine.schemas import VoiceEvent, CanonicalCommand
from app.modules.actuator_engine.schemas import CommonJoystickEvent, JoystickDirection, JoystickSource


def get_memory_mb():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def benchmark_fusion_performance(iterations: int = 10000):
    print("=" * 70)
    print("DCRG Phase 5 Fusion Engine & CRS Performance Benchmark")
    print("=" * 70)
    print(f"Total benchmark iterations: {iterations:,}")

    calc = CRSCalculator()

    # Pre-generate diverse events (Agreements, Contradictions, Neutral, Diagonal)
    test_events = []
    
    # 1. Matching Agreement Pair (FORWARD)
    v_fwd = VoiceEvent(
        transcript="forward",
        normalized_transcript="forward",
        recognized_command=CanonicalCommand.FORWARD,
        recognition_confidence=0.95,
        composite_stress_score=0.10,
    )
    j_fwd = CommonJoystickEvent(
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="BENCH-001",
        axis_x=0.0,
        axis_y=0.90,
        direction=JoystickDirection.FORWARD,
        intensity=0.90,
        is_simulation=True,
    )
    test_events.append(CorrelatedEvent(
        voice_command="FORWARD",
        joystick_direction="FORWARD",
        joystick_intensity=0.90,
        timestamp_difference_ms=12.0,
        synchronization_status=SynchronizationStatus.SYNCHRONIZED,
        voice_available=True,
        joystick_available=True,
        voice_event=v_fwd,
        joystick_event=j_fwd,
    ))

    # 2. Contradiction Pair (Voice LEFT vs Joystick RIGHT)
    v_left = VoiceEvent(
        transcript="left",
        normalized_transcript="left",
        recognized_command=CanonicalCommand.LEFT,
        recognition_confidence=0.92,
        composite_stress_score=0.20,
    )
    j_right = CommonJoystickEvent(
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="BENCH-002",
        axis_x=0.88,
        axis_y=0.0,
        direction=JoystickDirection.RIGHT,
        intensity=0.88,
        is_simulation=True,
    )
    test_events.append(CorrelatedEvent(
        voice_command="LEFT",
        joystick_direction="RIGHT",
        joystick_intensity=0.88,
        timestamp_difference_ms=8.0,
        synchronization_status=SynchronizationStatus.SYNCHRONIZED,
        voice_available=True,
        joystick_available=True,
        voice_event=v_left,
        joystick_event=j_right,
    ))

    # 3. STOP Command with Neutral Joystick
    v_stop = VoiceEvent(
        transcript="stop",
        normalized_transcript="stop",
        recognized_command=CanonicalCommand.STOP,
        recognition_confidence=0.98,
        composite_stress_score=0.40,
    )
    j_center = CommonJoystickEvent(
        source=JoystickSource.VIRTUAL_SIMULATION,
        device_id="BENCH-003",
        axis_x=0.0,
        axis_y=0.0,
        direction=JoystickDirection.CENTER,
        intensity=0.0,
        is_simulation=True,
    )
    test_events.append(CorrelatedEvent(
        voice_command="STOP",
        joystick_direction="CENTER",
        joystick_intensity=0.0,
        timestamp_difference_ms=5.0,
        synchronization_status=SynchronizationStatus.SYNCHRONIZED,
        voice_available=True,
        joystick_available=True,
        voice_event=v_stop,
        joystick_event=j_center,
    ))

    mem_before = get_memory_mb()

    # Warmup
    for _ in range(500):
        for ev in test_events:
            calc.evaluate(ev)

    # Timing Run
    latencies_us = []
    contradiction_latencies_us = []

    start_total = time.perf_counter()

    for i in range(iterations):
        ev = test_events[i % len(test_events)]
        t0 = time.perf_counter_ns()
        res = calc.evaluate(ev)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        latencies_us.append(elapsed_us)

        if res.contradiction_detected:
            contradiction_latencies_us.append(elapsed_us)

    total_time_sec = time.perf_counter() - start_total
    mem_after = get_memory_mb()

    # Metrics
    mean_lat = statistics.mean(latencies_us)
    median_lat = statistics.median(latencies_us)
    p95_lat = statistics.quantiles(latencies_us, n=100)[94]
    p99_lat = statistics.quantiles(latencies_us, n=100)[98]
    max_lat = max(latencies_us)
    throughput = iterations / total_time_sec

    mean_veto_lat = statistics.mean(contradiction_latencies_us) if contradiction_latencies_us else 0.0

    print(f"\nExecution Metrics:")
    print(f"  Total Duration:            {total_time_sec:.4f} s")
    print(f"  Throughput:                {throughput:,.1f} evaluations / sec")
    print(f"\nLatency Distribution:")
    print(f"  Mean Evaluation Latency:   {mean_lat:.2f} us ({mean_lat / 1000.0:.4f} ms)")
    print(f"  Median Latency (p50):      {median_lat:.2f} us")
    print(f"  95th Percentile (p95):     {p95_lat:.2f} us")
    print(f"  99th Percentile (p99):     {p99_lat:.2f} us")
    print(f"  Max Latency:               {max_lat:.2f} us")
    print(f"  Contradiction Veto Mean:   {mean_veto_lat:.2f} us")
    print(f"\nMemory Profile:")
    print(f"  Initial RSS:               {mem_before:.2f} MB")
    print(f"  Post-Load RSS:             {mem_after:.2f} MB")
    print(f"  RSS Delta:                 {mem_after - mem_before:+.2f} MB")
    print("=" * 70)
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    benchmark_fusion_performance()

