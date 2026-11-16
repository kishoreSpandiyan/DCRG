"""
DCRG Phase 6 Tiered Safety Authorization Engine Performance Benchmark.
Evaluates:
- Safety decision evaluation latency (mean, median, p95, max)
- Maximum decision throughput (decisions / sec)
- Emergency stop assertion latency
- Gateway verification and simulation dispatch latency
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

from app.modules.fusion_engine.schemas import CRSStatus, FusionFactors, FusionResult, AnalyticalFinding
from app.modules.safety_engine.rules import SafetyRuleEngine
from app.modules.safety_engine.gateway import SimulatedCommandGateway
from app.modules.safety_engine.schemas import EmergencySource


def get_memory_mb():
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def benchmark_safety_performance(iterations: int = 10000):
    print("=" * 70)
    print("DCRG Phase 6 Safety Authorization Engine Performance Benchmark")
    print("=" * 70)
    print(f"Total benchmark iterations: {iterations:,}")

    rule_engine = SafetyRuleEngine()
    gateway = SimulatedCommandGateway()

    # Create diverse fusion results (GREEN, YELLOW, RED)
    fusion_green = FusionResult(
        fusion_id="bench-f-green",
        correlation_id="bench-c-green",
        timestamp=time.time() * 1000.0,
        voice_command="FORWARD",
        joystick_direction="FORWARD",
        joystick_intensity=0.90,
        semantic_reliability=0.95,
        motor_agreement=0.95,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.95,
            motor_agreement=0.95,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=1.0,
        ),
        CRS=92.5,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=5.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0-prototype",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Benchmark GREEN",
        analytical_finding=AnalyticalFinding.AGREEMENT,
    )

    fusion_yellow = FusionResult(
        fusion_id="bench-f-yellow",
        correlation_id="bench-c-yellow",
        timestamp=time.time() * 1000.0,
        voice_command="LEFT",
        joystick_direction="LEFT",
        joystick_intensity=0.55,
        semantic_reliability=0.65,
        motor_agreement=0.70,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.65,
            motor_agreement=0.70,
            context_consistency=1.00,
            angular_delta_deg=0.0,
            cosine_similarity=1.0,
            sync_quality=0.9,
        ),
        CRS=72.0,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=False,
        veto_asserted=False,
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=15.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0-prototype",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Benchmark YELLOW",
        analytical_finding=AnalyticalFinding.AGREEMENT,
    )

    fusion_red = FusionResult(
        fusion_id="bench-f-red",
        correlation_id="bench-c-red",
        timestamp=time.time() * 1000.0,
        voice_command="LEFT",
        joystick_direction="RIGHT",
        joystick_intensity=0.85,
        semantic_reliability=0.90,
        motor_agreement=0.0,
        context_consistency=1.00,
        factors=FusionFactors(
            semantic_score=0.90,
            motor_agreement=0.0,
            context_consistency=1.00,
            angular_delta_deg=180.0,
            cosine_similarity=-1.0,
            sync_quality=1.0,
        ),
        CRS=28.0,
        CRS_status=CRSStatus.COMPLETE,
        contradiction_detected=True,
        veto_asserted=True,
        contradiction_reason="Contradiction",
        synchronization_status="SYNCHRONIZED",
        temporal_delta_ms=8.0,
        evidence_completeness=1.0,
        missing_components=[],
        scoring_config_version="v1.0-prototype",
        weights={"semantic": 0.35, "motor": 0.50, "context": 0.15},
        explanation="Benchmark RED",
        analytical_finding=AnalyticalFinding.CONTRADICTION,
    )

    test_fusions = [fusion_green, fusion_yellow, fusion_red]

    mem_before = get_memory_mb()

    # Warmup
    for _ in range(500):
        for f in test_fusions:
            rule_engine.evaluate(f, is_emergency_latched=False)

    latencies_us = []
    gateway_latencies_us = []

    start_total = time.perf_counter()

    for i in range(iterations):
        f = test_fusions[i % len(test_fusions)]
        t0 = time.perf_counter_ns()
        decision = rule_engine.evaluate(f, is_emergency_latched=False)
        elapsed_us = (time.perf_counter_ns() - t0) / 1000.0
        latencies_us.append(elapsed_us)

        # Dispatch GREEN decisions to gateway
        if decision.authorization_state.value == "GREEN":
            t_gw = time.perf_counter_ns()
            # Clear gateway token cache periodically to avoid exhaustion in benchmark
            if len(gateway._used_tokens) > 2000:
                gateway._used_tokens.clear()
            gateway.dispatch(decision, decision.authorized_command, decision.auth_token)
            gw_elapsed_us = (time.perf_counter_ns() - t_gw) / 1000.0
            gateway_latencies_us.append(gw_elapsed_us)

    total_time_sec = time.perf_counter() - start_total
    mem_after = get_memory_mb()

    # Measure Emergency Stop response latency
    estop_times_us = []
    for _ in range(100):
        t_es = time.perf_counter_ns()
        es_dec = rule_engine.evaluate(fusion_green, is_emergency_latched=True, emergency_source="SOFTWARE_UI")
        estop_times_us.append((time.perf_counter_ns() - t_es) / 1000.0)

    # Metrics
    mean_lat = statistics.mean(latencies_us)
    median_lat = statistics.median(latencies_us)
    p95_lat = statistics.quantiles(latencies_us, n=100)[94]
    p99_lat = statistics.quantiles(latencies_us, n=100)[98]
    max_lat = max(latencies_us)
    throughput = iterations / total_time_sec

    mean_gw_lat = statistics.mean(gateway_latencies_us) if gateway_latencies_us else 0.0
    mean_estop_lat = statistics.mean(estop_times_us)

    print(f"\nExecution Metrics:")
    print(f"  Total Duration:            {total_time_sec:.4f} s")
    print(f"  Decision Throughput:       {throughput:,.1f} decisions / sec")
    print(f"\nLatency Distribution (Rule Engine):")
    print(f"  Mean Evaluation Latency:   {mean_lat:.2f} us ({mean_lat / 1000.0:.4f} ms)")
    print(f"  Median Latency (p50):      {median_lat:.2f} us")
    print(f"  95th Percentile (p95):     {p95_lat:.2f} us")
    print(f"  99th Percentile (p99):     {p99_lat:.2f} us")
    print(f"  Max Latency:               {max_lat:.2f} us")
    print(f"\nSubsystem Latencies:")
    print(f"  Emergency Stop Assertion:  {mean_estop_lat:.2f} us ({mean_estop_lat / 1000.0:.4f} ms)")
    print(f"  Gateway Auth & Dispatch:   {mean_gw_lat:.2f} us ({mean_gw_lat / 1000.0:.4f} ms)")
    print(f"\nMemory Profile:")
    print(f"  Initial RSS:               {mem_before:.2f} MB")
    print(f"  Post-Load RSS:             {mem_after:.2f} MB")
    print(f"  RSS Delta:                 {mem_after - mem_before:+.2f} MB")
    print("=" * 70)
    print("PHASE 6 BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    benchmark_safety_performance()

