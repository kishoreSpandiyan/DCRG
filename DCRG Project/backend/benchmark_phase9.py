import time
import numpy as np
from app.modules.voice_engine.whisper_service import whisper_service
from app.modules.prosody_engine.analyzer import prosody_analyzer
from app.modules.semantic_engine.classifier import semantic_classifier
from app.modules.actuator_engine.manager import actuator_manager
from app.modules.sync_engine.synchronizer import EventSynchronizer
from app.modules.fusion_engine.calculator import CRSCalculator
from app.modules.safety_engine import SafetyRuleEngine, simulated_gateway
from app.modules.simulation_engine.simulator import RobotSimulator
from app.database.audit_logger import audit_logger

def run_benchmarks():
    print("=== DCRG PHASE 9 EMPIRICAL BENCHMARKS ===")

    # 1. Prosody Analyzer
    audio_1s = (0.5 * np.sin(2 * np.pi * 220 * np.linspace(0, 1.0, 16000))).astype(np.float32)
    prosody_times = []
    for _ in range(20):
        t0 = time.perf_counter()
        p = prosody_analyzer.analyze(audio_1s, 16000)
        prosody_times.append((time.perf_counter() - t0) * 1000)
    print(f"Prosody Latency (ms): avg={np.mean(prosody_times):.2f}, min={np.min(prosody_times):.2f}, max={np.max(prosody_times):.2f}")

    # 2. Whisper Speech-to-Text
    whisper_service.load_model()
    whisper_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        w = whisper_service.transcribe(audio_1s, 16000)
        whisper_times.append((time.perf_counter() - t0) * 1000)
    print(f"Whisper STT Latency (ms): avg={np.mean(whisper_times):.2f}, min={np.min(whisper_times):.2f}, max={np.max(whisper_times):.2f}")

    # 3. Semantic Classification
    commands = [
        "MOVE LEFT", "MOVE RIGHT", "MOVE FORWARD", "MOVE BACKWARD", "STOP",
        "turn around", "unknown noise", "can you please move forward", ""
    ]
    sem_times = []
    for cmd in commands:
        t0 = time.perf_counter()
        res = semantic_classifier.classify(transcript=cmd, recognition_confidence=0.92, timestamp=time.time())
        sem_times.append((time.perf_counter() - t0) * 1000)
        print(f"  Command: '{cmd:22}' -> Canonical: {res.recognized_command.value:10} | Conf: {res.classification_confidence:.2f} | Status: {res.semantic_status.value}")
    print(f"Semantic Classification (ms): avg={np.mean(sem_times):.3f}, min={np.min(sem_times):.3f}, max={np.max(sem_times):.3f}")

    # 4. Joystick Input Ingestion & Deadzone Classification
    joy_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        ev = actuator_manager.ingest_virtual_input(0.85, 0.05)
        joy_times.append((time.perf_counter() - t0) * 1000)
    print(f"Joystick Ingestion Latency (ms): avg={np.mean(joy_times):.4f}, min={np.min(joy_times):.4f}, max={np.max(joy_times):.4f}")

    # 5. Event Synchronization Engine
    sync = EventSynchronizer(sync_window_ms=150.0)
    sync_times = []
    for _ in range(50):
        t0 = time.perf_counter()
        c = sync.correlate_manual_pair(None, ev)
        sync_times.append((time.perf_counter() - t0) * 1000)
    print(f"Event Sync Delay (ms): avg={np.mean(sync_times):.4f}, min={np.min(sync_times):.4f}, max={np.max(sync_times):.4f}")

    # 6. Fusion Engine (CRS Multi-Factor Vector Calculation)
    calc = CRSCalculator()
    fuse_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        fr = calc.evaluate(c)
        fuse_times.append((time.perf_counter() - t0) * 1000)
    print(f"Fusion CRS Engine (ms): avg={np.mean(fuse_times):.4f}, min={np.min(fuse_times):.4f}, max={np.max(fuse_times):.4f}")

    # 7. Safety Authorization Engine (Deterministic State Rule Evaluation)
    safety = SafetyRuleEngine()
    safe_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        dec = safety.evaluate(fr, is_emergency_latched=False)
        safe_times.append((time.perf_counter() - t0) * 1000)
    print(f"Safety Rule Evaluation (ms): avg={np.mean(safe_times):.4f}, min={np.min(safe_times):.4f}, max={np.max(safe_times):.4f}")

    # 8. Cryptographic Gateway Verification
    gate_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        simulated_gateway.dispatch(dec, command_attempted=dec.authorized_command or "STOP", auth_token=dec.auth_token)
        gate_times.append((time.perf_counter() - t0) * 1000)
    print(f"Gateway Interlock Latency (ms): avg={np.mean(gate_times):.4f}, min={np.min(gate_times):.4f}, max={np.max(gate_times):.4f}")

    # 9. Kinematic Simulator Step Execution
    sim = RobotSimulator()
    sim_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        sim.step(dt=0.016)
        sim_times.append((time.perf_counter() - t0) * 1000)
    print(f"Simulation Kinematic Step (ms): avg={np.mean(sim_times):.4f}, min={np.min(sim_times):.4f}, max={np.max(sim_times):.4f}")

    # 10. Emergency Stop Interlock & Zero-Clamp
    estop_times = []
    for _ in range(100):
        t0 = time.perf_counter()
        dec_estop = safety.evaluate(fr, is_emergency_latched=True)
        sim.apply_authorized_command("STOP", auth_state="EMERGENCY")
        estop_times.append((time.perf_counter() - t0) * 1000)
    print(f"Emergency Stop Interlock Latency (ms): avg={np.mean(estop_times):.4f}, min={np.min(estop_times):.4f}, max={np.max(estop_times):.4f}")

    # 11. SQLite Audit Log Write Latency (WAL mode)
    db_times = []
    for i in range(50):
        t0 = time.perf_counter()
        audit_logger.log_event(
            category="BENCHMARK",
            command="TEST",
            safety_state="GREEN",
            details={"iteration": i}
        )
        db_times.append((time.perf_counter() - t0) * 1000)
    print(f"Audit Log Persistence Latency (ms): avg={np.mean(db_times):.3f}, min={np.min(db_times):.3f}, max={np.max(db_times):.3f}")

if __name__ == "__main__":
    run_benchmarks()
