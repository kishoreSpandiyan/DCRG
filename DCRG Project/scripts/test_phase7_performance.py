"""
DCRG Phase 7 Robot Simulation and Command Execution Performance Benchmark.
Evaluates:
- End-to-end pipeline latency (Input -> Sync -> Fusion -> Safety -> Gateway -> Sim step)
- Authorization-to-simulation dispatch latency
- Kinematic physics tick update latency (mean, median, p95, max)
- Maximum physics step throughput (steps / sec)
- Sustained 20 Hz tick loop timing stability and jitter
- Memory RSS baseline vs under sustained simulation load
"""

import os
import sys
import time
import statistics

# Ensure backend modules are on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.modules.fusion_engine.schemas import CRSStatus, FusionFactors, FusionResult, AnalyticalFinding
from app.modules.safety_engine.rules import SafetyRuleEngine
from app.modules.safety_engine.gateway import SimulatedCommandGateway
from app.modules.simulation_engine.simulator import RobotSimulator
from app.modules.simulation_engine.manager import SimulationManager


def get_memory_mb():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def benchmark_simulation_performance(iterations: int = 10000):
    print("=" * 75)
    print("DCRG Phase 7 Robot Simulation & Command Execution Performance Benchmark")
    print("=" * 75)
    print(f"Total benchmark iterations: {iterations:,}")

    rule_engine = SafetyRuleEngine()
    gateway = SimulatedCommandGateway()
    simulator = RobotSimulator()
    sim_mgr = SimulationManager(simulator=simulator, autostart=False)

    mem_baseline = get_memory_mb()
    print(f"Baseline Process Memory: {mem_baseline:.2f} MB\n")

    # ---------------------------------------------------------
    # 1. Kinematic Physics Step Latency & Throughput
    # ---------------------------------------------------------
    print("[-] Benchmarking Kinematic Physics Step Latency (dt = 0.05s)...")
    simulator.apply_authorized_command("FORWARD", "GREEN")
    step_latencies_us = []

    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulator.step(0.05)
        t1 = time.perf_counter()
        step_latencies_us.append((t1 - t0) * 1_000_000.0)
    t_total = time.perf_counter() - t_start

    step_throughput = iterations / t_total
    mean_step_us = statistics.mean(step_latencies_us)
    median_step_us = statistics.median(step_latencies_us)
    sorted_steps = sorted(step_latencies_us)
    p95_step_us = sorted_steps[int(iterations * 0.95)]
    p99_step_us = sorted_steps[int(iterations * 0.99)]
    max_step_us = max(step_latencies_us)

    print(f"    Mean Step Latency:    {mean_step_us:.2f} µs ({mean_step_us / 1000.0:.4f} ms)")
    print(f"    Median Step Latency:  {median_step_us:.2f} µs")
    print(f"    P95 Step Latency:     {p95_step_us:.2f} µs")
    print(f"    P99 Step Latency:     {p99_step_us:.2f} µs")
    print(f"    Max Step Latency:     {max_step_us:.2f} µs")
    print(f"    Throughput:           {step_throughput:,.1f} steps/second\n")

    # ---------------------------------------------------------
    # 2. Authorization-to-Simulation Dispatch Latency
    # ---------------------------------------------------------
    print("[-] Benchmarking Safety Decision -> Gateway -> Simulation Dispatch Latency...")
    dispatch_latencies_us = []

    fusion_payload = FusionResult(
        fusion_id="bench-f-001",
        correlation_id="bench-c-001",
        timestamp=time.time() * 1000.0,
        voice_command="FORWARD",
        joystick_direction="FORWARD",
        joystick_intensity=0.88,
        semantic_reliability=0.92,
        motor_agreement=0.92,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.92,
            motor_agreement=0.92,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=91.5,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        contradiction_reason=None,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=10.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Benchmark",
        analytical_finding=AnalyticalFinding.AGREEMENT,
        recommended_state="GREEN",
    )

    for _ in range(iterations):
        # Generate fresh authorized decision
        decision = rule_engine.evaluate(fusion_payload, is_emergency_latched=False)
        t0 = time.perf_counter()
        sim_mgr.on_safety_decision(decision)
        t1 = time.perf_counter()
        dispatch_latencies_us.append((t1 - t0) * 1_000_000.0)

    mean_disp_us = statistics.mean(dispatch_latencies_us)
    median_disp_us = statistics.median(dispatch_latencies_us)
    sorted_disp = sorted(dispatch_latencies_us)
    p95_disp_us = sorted_disp[int(iterations * 0.95)]
    p99_disp_us = sorted_disp[int(iterations * 0.99)]

    print(f"    Mean Dispatch Latency:   {mean_disp_us:.2f} µs ({mean_disp_us / 1000.0:.4f} ms)")
    print(f"    Median Dispatch Latency: {median_disp_us:.2f} µs")
    print(f"    P95 Dispatch Latency:    {p95_disp_us:.2f} µs")
    print(f"    P99 Dispatch Latency:    {p99_disp_us:.2f} µs\n")

    # ---------------------------------------------------------
    # 3. End-to-End Pipeline Evaluation Latency
    # ---------------------------------------------------------
    print("[-] Benchmarking Full End-to-End Pipeline Latency (Decision + Dispatch + Physics Step)...")
    e2e_latencies_us = []

    for _ in range(iterations):
        t0 = time.perf_counter()
        decision = rule_engine.evaluate(fusion_payload, is_emergency_latched=False)
        sim_mgr.on_safety_decision(decision)
        sim_mgr.step(0.05)
        t1 = time.perf_counter()
        e2e_latencies_us.append((t1 - t0) * 1_000_000.0)

    mean_e2e_us = statistics.mean(e2e_latencies_us)
    median_e2e_us = statistics.median(e2e_latencies_us)
    sorted_e2e = sorted(e2e_latencies_us)
    p95_e2e_us = sorted_e2e[int(iterations * 0.95)]
    p99_e2e_us = sorted_e2e[int(iterations * 0.99)]

    print(f"    Mean E2E Latency:   {mean_e2e_us:.2f} µs ({mean_e2e_us / 1000.0:.4f} ms)")
    print(f"    Median E2E Latency: {median_e2e_us:.2f} µs")
    print(f"    P95 E2E Latency:    {p95_e2e_us:.2f} µs")
    print(f"    P99 E2E Latency:    {p99_e2e_us:.2f} µs\n")

    # ---------------------------------------------------------
    # 4. Sustained 20 Hz Tick Stability (100 real-time ticks)
    # ---------------------------------------------------------
    print("[-] Benchmarking Real-Time 20 Hz Loop Stability (100 ticks = 5.0 seconds target)...")
    target_hz = 20.0
    dt_target = 1.0 / target_hz
    tick_intervals = []
    t_prev = time.perf_counter()

    for _ in range(100):
        t_now = time.perf_counter()
        elapsed = t_now - t_prev
        t_prev = t_now
        tick_intervals.append(elapsed)
        simulator.step(dt_target)
        # Sleep remainder of 50ms period
        comp = time.perf_counter() - t_now
        rem = dt_target - comp
        if rem > 0:
            time.sleep(rem)

    real_intervals = tick_intervals[1:]  # skip first
    mean_interval_ms = statistics.mean(real_intervals) * 1000.0
    jitter_ms = statistics.stdev(real_intervals) * 1000.0
    actual_hz = 1.0 / (mean_interval_ms / 1000.0)

    print(f"    Target Tick Interval: 50.00 ms (20.0 Hz)")
    print(f"    Actual Mean Interval: {mean_interval_ms:.2f} ms")
    print(f"    Effective Frequency:  {actual_hz:.2f} Hz")
    print(f"    Timing Jitter (Std):  {jitter_ms:.3f} ms\n")

    # ---------------------------------------------------------
    # 5. Memory Footprint
    # ---------------------------------------------------------
    mem_peak = get_memory_mb()
    print("[-] Memory Diagnostics:")
    print(f"    Baseline Memory: {mem_baseline:.2f} MB")
    print(f"    Peak Memory:     {mem_peak:.2f} MB")
    print(f"    Net Delta:       +{max(0.0, mem_peak - mem_baseline):.2f} MB\n")

    print("=" * 75)
    print("Phase 7 Robot Simulation Benchmark Completed Successfully.")
    print("=" * 75)


if __name__ == "__main__":
    benchmark_simulation_performance(iterations=10000)

