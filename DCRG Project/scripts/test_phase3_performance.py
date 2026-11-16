"""
Phase 3 Performance Benchmarking & Live Microphone Verification Script.
Measures actual inference latency, model loading times, CPU/Memory usage,
and executes live physical microphone capture.
"""

import os
import sys
import time
import numpy as np
import psutil

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.modules.voice_engine.whisper_service import WhisperService
from app.modules.prosody_engine.analyzer import ProsodyAnalyzer
from app.modules.semantic_engine.classifier import SemanticClassifier
from app.modules.voice_engine.microphone_service import MicrophoneService
from app.modules.voice_engine.manager import VoiceManager


def benchmark_whisper(model_size="tiny.en", num_runs=5):
    print(f"\n--- Benchmarking Faster-Whisper ({model_size}) ---")
    proc = psutil.Process(os.getpid())
    mem_before = proc.memory_info().rss / (1024 * 1024)
    cpu_before = proc.cpu_percent(interval=0.1)

    t0 = time.time()
    stt = WhisperService(model_name=model_size, device="cpu", compute_type="int8")
    loaded = stt.load_model()
    load_time = time.time() - t0
    mem_after_load = proc.memory_info().rss / (1024 * 1024)

    print(f"Model: {model_size}")
    print(f"Loaded: {loaded}")
    print(f"Model Loading Time: {load_time:.3f} s")
    print(f"Memory RSS after load: {mem_after_load:.1f} MB (Delta: +{mem_after_load - mem_before:.1f} MB)")

    # Test audio: 1.0 second synthetic speech-like harmonic tone
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # Fundamental + harmonics to simulate vocal cords
    synthetic_audio = (
        0.4 * np.sin(2 * np.pi * 150.0 * t) +
        0.2 * np.sin(2 * np.pi * 300.0 * t) +
        0.1 * np.sin(2 * np.pi * 450.0 * t)
    ).astype(np.float32)

    latencies = []
    cpu_measurements = []

    for i in range(num_runs):
        t_start = time.time()
        res = stt.transcribe(synthetic_audio, sample_rate=sr)
        lat = (time.time() - t_start) * 1000.0
        latencies.append(lat)
        cpu_measurements.append(proc.cpu_percent(interval=0.05))
        print(f"  Run {i+1}: {lat:.2f} ms | transcript='{res.transcript}' | conf={res.confidence:.3f}")

    avg_lat = np.mean(latencies)
    min_lat = np.min(latencies)
    max_lat = np.max(latencies)
    avg_cpu = np.mean(cpu_measurements)
    peak_mem = proc.memory_info().rss / (1024 * 1024)

    print(f"Average Recognition Latency: {avg_lat:.2f} ms (Min: {min_lat:.2f} ms, Max: {max_lat:.2f} ms)")
    print(f"Average CPU Usage during inference: {avg_cpu:.1f} %")
    print(f"Peak Memory Usage: {peak_mem:.1f} MB")

    return {
        "model": model_size,
        "load_time_s": round(load_time, 3),
        "avg_latency_ms": round(avg_lat, 2),
        "min_latency_ms": round(min_lat, 2),
        "max_latency_ms": round(max_lat, 2),
        "peak_mem_mb": round(peak_mem, 1),
        "avg_cpu_pct": round(avg_cpu, 1),
        "sample_rate": sr,
    }


def benchmark_prosody(num_runs=5):
    print("\n--- Benchmarking Prosody Feature Extraction (Librosa) ---")
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 180.0 * t)).astype(np.float32)

    analyzer = ProsodyAnalyzer(sample_rate=sr)
    # Warmup
    analyzer.analyze(audio)

    latencies = []
    for i in range(num_runs):
        t0 = time.time()
        metrics = analyzer.analyze(audio)
        lat = (time.time() - t0) * 1000.0
        latencies.append(lat)

    print(f"Prosody Average Latency: {np.mean(latencies):.2f} ms (Min: {np.min(latencies):.2f} ms, Max: {np.max(latencies):.2f} ms)")
    print(f"Extracted F0: {metrics.pitch_f0:.1f} Hz, Jitter: {metrics.jitter:.4f}, Shimmer: {metrics.shimmer:.4f}, Stress: {metrics.composite_stress_score:.3f}")
    return round(np.mean(latencies), 2)


def test_live_physical_microphone():
    print("\n--- Live Physical Microphone Verification ---")
    mic = MicrophoneService(sample_rate=16000)
    devices = mic.get_available_devices()
    print(f"Discovered {len(devices)} audio input devices.")
    for d in devices:
        print(f"  [{d['index']}] {d['name']} (Channels: {d['max_input_channels']}, Default: {d['is_default']})")

    captured_chunks = []

    def on_chunk(chunk, sr):
        captured_chunks.append((chunk, sr))

    mic.register_chunk_subscriber(on_chunk)

    print("\nAttempting to start live physical microphone capture...")
    success, msg = mic.start()
    print(f"Microphone start status: {success} ({msg})")
    print(f"Active Device: {mic.device_name}")
    print(f"Hardware Status: {mic.status.value}")

    if success:
        # Capture for 1.2 seconds
        time.sleep(1.2)
        mic.stop()
        print(f"Microphone stopped cleanly. Status: {mic.status.value}")
        print(f"Captured {len(captured_chunks)} audio frames.")

        total_samples = sum(len(c[0]) for c in captured_chunks)
        print(f"Total audio samples captured: {total_samples} samples ({total_samples / 16000.0:.2f} s)")

        if captured_chunks:
            all_samples = np.concatenate([c[0].flatten() for c in captured_chunks])
            rms = float(np.sqrt(np.mean(np.square(all_samples))))
            peak = float(np.max(np.abs(all_samples)))
            print(f"Live Audio RMS Amplitude: {rms:.6f}")
            print(f"Live Audio Peak Amplitude: {peak:.6f}")

            # Feed live audio into VoiceManager to verify full pipeline
            vm = VoiceManager()
            event = vm.process_audio_chunk(all_samples, sample_rate=16000)
            print("\nGenerated VoiceEvent from Physical Microphone Audio:")
            print(f"  Event ID: {event.event_id}")
            print(f"  Source: {event.source}")
            print(f"  Transcript: '{event.transcript}'")
            print(f"  Recognized Command: {event.recognized_command.value}")
            print(f"  Recognition Confidence: {event.recognition_confidence}")
            print(f"  Semantic Status: {event.semantic_status.value}")
            print(f"  Audio Quality: {event.audio_quality.value}")
            print(f"  Pitch F0: {event.pitch_f0:.1f} Hz")
            print(f"  Intensity: {event.intensity:.4f}")
            print(f"  Stress Score: {event.composite_stress_score:.4f}")
            return True, {
                "devices_found": len(devices),
                "device_name": mic.device_name,
                "samples_captured": total_samples,
                "rms": rms,
                "peak": peak,
                "event_created": True,
            }
    else:
        print(f"Could not open microphone: {mic.hardware_error}")
        return False, {"error": mic.hardware_error}


if __name__ == "__main__":
    whisper_perf = benchmark_whisper("tiny.en", num_runs=5)
    prosody_lat = benchmark_prosody(num_runs=5)
    mic_success, mic_data = test_live_physical_microphone()

    print("\n================ BENCHMARK SUMMARY ================")
    print(f"Whisper Model: {whisper_perf['model']}")
    print(f"Model Load Time: {whisper_perf['load_time_s']} s")
    print(f"Average Recognition Latency: {whisper_perf['avg_latency_ms']} ms")
    print(f"Average Prosody Latency: {prosody_lat} ms")
    print(f"Total Pipeline Latency: {whisper_perf['avg_latency_ms'] + prosody_lat:.2f} ms")
    print(f"Peak Memory: {whisper_perf['peak_mem_mb']} MB")
    print(f"Sample Rate: {whisper_perf['sample_rate']} Hz")
    print(f"Live Physical Microphone Test: {'PASSED' if mic_success else 'FAILED'}")
    print("====================================================")

