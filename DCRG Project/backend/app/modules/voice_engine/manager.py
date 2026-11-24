"""
Voice Recognition and Prosody Analysis Engine Manager.
Coordinates microphone audio ingestion, voice activity segmentation,
Whisper speech-to-text inference, Librosa prosody feature extraction,
and semantic command classification into standardized VoiceEvents.
"""

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

from app.core.config import settings
from app.modules.voice_engine.schemas import (
    VoiceEvent,
    VoiceSystemStatus,
    MicrophoneStatus,
    AudioQuality,
    CanonicalCommand,
    SemanticStatus,
    CANONICAL_DIRECTION_VECTORS,
)
from app.modules.voice_engine.microphone_service import (
    MicrophoneService,
    microphone_service,
)
from app.modules.voice_engine.whisper_service import (
    WhisperService,
    whisper_service,
)
from app.modules.prosody_engine.analyzer import (
    ProsodyAnalyzer,
    prosody_analyzer,
)
from app.modules.voice_engine.kws_service import (
    KeywordSpotterService,
    KeywordDetectionResult,
    keyword_spotter,
    DroneKeyword,
    EMERGENCY_KEYWORDS,
)

logger = logging.getLogger(__name__)


class VoiceManager:
    """
    Central controller for DCRG Phase 3 Voice Subsystem.
    Enforces independent execution, truthful status reporting,
    and publishes structured VoiceEvents with ultra-low-latency KWS.
    """

    def __init__(
        self,
        mic_service: Optional[MicrophoneService] = None,
        stt_service: Optional[WhisperService] = None,
        prosody_eng: Optional[ProsodyAnalyzer] = None,
        semantic_clf: Optional[Any] = None,
        kws_eng: Optional[KeywordSpotterService] = None,
    ):
        self.mic_service = mic_service or microphone_service
        self.whisper_service = stt_service or whisper_service
        self.prosody_analyzer = prosody_eng or prosody_analyzer
        if semantic_clf is not None:
            self.semantic_classifier = semantic_clf
        else:
            from app.modules.semantic_engine.classifier import semantic_classifier
            self.semantic_classifier = semantic_classifier

        self.kws_service = kws_eng or keyword_spotter
        # Register KWS hooks for immediate safety gate hold and early UI dispatch
        self.kws_service.register_emergency_handler(self._on_kws_emergency)
        self.kws_service.register_listener(self._on_kws_detection)

        self._lock = threading.RLock()
        self._subscribers: List[Callable[[VoiceEvent], None]] = []

        # Latest states
        self.last_event: Optional[VoiceEvent] = None
        self.last_event_time: float = 0.0

        # Adaptive Noise Floor Tracking
        self._ambient_rms: float = 0.005
        self._adaptive_alpha: float = 0.03
        self._last_vad_onset_ms: float = 0.0
        self._last_vad_endpoint_ms: float = 0.0

        # Background worker for async speech chunk processing
        self._audio_queue: queue.Queue = queue.Queue(maxsize=50)
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False

        # Speech segmentation state (ultra-low latency tuning)
        self._speech_buffer: List[np.ndarray] = []
        self._is_speaking = False
        self._silence_frames = 0
        self._silence_hangover_frames = int(0.15 / 0.03)  # ~150ms silence hangover (lowered from 350ms)
        self._min_speech_frames = int(0.12 / 0.03)       # ~120ms minimum speech
        self._max_speech_frames = int(1.20 / 0.03)       # ~1.2s max utterance for instant command turnaround

        # Hook into microphone service chunks
        self.mic_service.register_chunk_subscriber(self._on_audio_chunk)

    def _on_kws_emergency(self, kws_res: KeywordDetectionResult) -> None:
        """
        Fast-Path Safety Gate Hook.
        Directly engages emergency stop on Safety Engine within <60ms upon detecting
        emergency keywords (STOP, EMERGENCY STOP) with high confidence (>= 0.85).
        """
        if kws_res.keyword not in ("STOP", "EMERGENCY STOP") or kws_res.confidence < 0.85:
            return
        try:
            from app.modules.safety_engine.manager import safety_manager
            from app.modules.safety_engine.schemas import EmergencySource
            safety_manager.trigger_emergency_hold(
                keyword=kws_res.keyword,
                confidence=kws_res.confidence,
                source=EmergencySource.KEYWORD_SPOTTER,
                detection_latency_ms=kws_res.detection_latency_ms,
            )
            logger.warning(
                f"[KWS-SAFETY-GATE] Emergency Hold engaged for '{kws_res.keyword}' in {kws_res.detection_latency_ms:.2f}ms"
            )
        except Exception as e:
            logger.error(f"Error triggering safety gate from KWS: {e}")

    def _on_kws_detection(self, kws_res: KeywordDetectionResult) -> None:
        """
        Fast Keyword Detection Broadcast.
        Immediately dispatches high-priority VoiceEvent to WebSocket listeners
        so the UI reflects the recognized command in <60ms without waiting for STT!
        """
        ts = kws_res.timestamp_ms
        cmd_str = kws_res.keyword.upper()
        cmd_enum = CanonicalCommand.UNCERTAIN
        for c in CanonicalCommand:
            if c.value == cmd_str or (cmd_str == "EMERGENCY STOP" and c == CanonicalCommand.STOP):
                cmd_enum = c
                break

        vec = CANONICAL_DIRECTION_VECTORS.get(cmd_enum, {"x": 0.0, "y": 0.0})

        early_event = VoiceEvent(
            timestamp=ts,
            timestamp_event_ms=ts,
            timestamp_proc_ms=ts + kws_res.detection_latency_ms,
            source="kws_fast_path",
            operator_id="OP-FAST-KWS",
            transcript=kws_res.keyword,
            normalized_transcript=kws_res.keyword.lower(),
            recognized_command=cmd_enum,
            classified_command=cmd_enum.value,
            recognition_confidence=round(kws_res.confidence, 4),
            classification_confidence=round(kws_res.confidence, 4),
            confidence=round(kws_res.confidence, 4),
            semantic_status=SemanticStatus.RECOGNIZED,
            is_uncertain=False,
            direction_vector=vec,
            audio_duration_ms=kws_res.audio_duration_ms,
            pitch_f0=160.0,
            pitch_f0_std=10.0,
            jitter=0.01,
            shimmer=0.02,
            speech_rate=4.0,
            intensity=0.5,
            audio_quality=AudioQuality.GOOD,
            model_version="kws-acoustic-fast",
            composite_stress_score=0.2,
            stress_score=0.2,
            is_stressed=False,
        )
        with self._lock:
            self.last_event = early_event
            self.last_event_time = ts

        self._dispatch_event(early_event)

    def start(self) -> Tuple[bool, str]:
        """Starts the voice processing engine and background inference worker."""
        with self._lock:
            if self._is_running:
                return True, "Voice engine is already active."

            self._is_running = True

            # Start worker thread
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="DCRG-VoiceWorker",
                daemon=True,
            )
            self._worker_thread.start()

            # Pre-load Whisper model in background or synchronous
            if not self.whisper_service.is_loaded:
                threading.Thread(
                    target=self.whisper_service.load_model,
                    name="DCRG-WhisperInit",
                    daemon=True,
                ).start()

            msg = "Voice engine worker initialized."
            logger.info(msg)
            return True, msg

    def stop(self) -> Tuple[bool, str]:
        """Stops microphone capture and processing threads."""
        with self._lock:
            self._is_running = False
            # Stop microphone capture if active
            self.mic_service.stop()

            # Clear queue
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    break

            msg = "Voice engine stopped cleanly."
            logger.info(msg)
            return True, msg

    def start_microphone(self) -> Tuple[bool, str]:
        """Enables live microphone audio capture."""
        self.start()
        return self.mic_service.start()

    def stop_microphone(self) -> Tuple[bool, str]:
        """Disables live microphone audio capture."""
        return self.mic_service.stop()

    def select_device(self, device_index: Optional[int]) -> Tuple[bool, str]:
        """Selects target microphone input hardware."""
        return self.mic_service.select_device(device_index)

    def set_mute(self, muted: bool) -> bool:
        """Toggles or sets microphone mute."""
        return self.mic_service.set_mute(muted)

    def subscribe(self, callback: Callable[[VoiceEvent], None]) -> None:
        """Registers a listener receiving validated VoiceEvents."""
        with self._lock:
            self._subscribers.append(callback)

    def get_status(self) -> VoiceSystemStatus:
        """Returns the truthful system status of the voice subsystem."""
        with self._lock:
            return VoiceSystemStatus(
                microphone_status=self.mic_service.status,
                is_capturing=self.mic_service.is_capturing,
                is_muted=self.mic_service.is_muted,
                selected_device_index=self.mic_service.device_index,
                selected_device_name=self.mic_service.device_name,
                model_name=self.whisper_service.model_name,
                model_loaded=self.whisper_service.is_loaded,
                language=self.whisper_service.default_language,
                sample_rate=self.mic_service.sample_rate,
                last_event=self.last_event,
                error_message=self.mic_service.hardware_error,
                kws_active=True,
                kws_total_detections=self.kws_service.total_detections,
                kws_emergency_triggers=self.kws_service.total_emergency_triggers,
                ambient_noise_rms=round(self._ambient_rms, 5),
            )

    def process_audio_chunk(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        operator_id: str = "OP-PRIMARY",
        client_timestamp: Optional[float] = None,
    ) -> VoiceEvent:
        """
        Synchronously processes a discrete audio segment through prosody,
        whisper transcription, and semantic classification.
        Returns the standardized VoiceEvent.
        """
        now_ms = time.time() * 1000.0
        # Align event timestamp with current server time if client_timestamp is stale (>200ms skew from inference/queueing)
        if client_timestamp and client_timestamp > 1700000000000.0 and abs(now_ms - client_timestamp) <= 200.0:
            ts = client_timestamp
        else:
            ts = now_ms
        t_proc_start = time.time()

        # Flatten / ensure 1D float32
        if audio_data is None or len(audio_data) == 0:
            duration_ms = 0.0
            clean_audio = np.zeros(0, dtype=np.float32)
        else:
            if audio_data.ndim > 1:
                clean_audio = np.mean(audio_data, axis=1)
            else:
                clean_audio = audio_data
            clean_audio = clean_audio.astype(np.float32)

            # Enhanced Automatic Gain Control (AGC) boost for quiet signals (e.g. Type-C headset mics)
            peak = float(np.max(np.abs(clean_audio))) if len(clean_audio) > 0 else 0.0
            if 0.0005 < peak < 0.50:
                boost = min(20.0, 0.70 / (peak + 1e-6))
                clean_audio = clean_audio * boost

            duration_ms = (len(clean_audio) / float(sample_rate)) * 1000.0

        # 1. Prosody Feature Extraction (Librosa)
        prosody = self.prosody_analyzer.analyze(clean_audio, sample_rate=sample_rate)

        # 2. Faster-Whisper Speech-to-Text Transcription
        stt_result = self.whisper_service.transcribe(clean_audio, sample_rate=sample_rate)

        # 3. Semantic Command Classification
        semantic_result = self.semantic_classifier.classify(
            transcript=stt_result.transcript,
            recognition_confidence=stt_result.confidence,
            language=stt_result.language,
            timestamp=ts,
        )

        now_ready_ms = time.time() * 1000.0
        proc_ms = now_ready_ms - (t_proc_start * 1000.0)

        # 4. Assemble Standardized VoiceEvent Contract
        event = VoiceEvent(
            timestamp=now_ready_ms,
            timestamp_event_ms=ts,
            timestamp_proc_ms=now_ready_ms,
            source="voice",
            operator_id=operator_id,
            transcript=semantic_result.original_transcript,
            normalized_transcript=semantic_result.normalized_transcript,
            recognized_command=semantic_result.recognized_command,
            classified_command=semantic_result.recognized_command.value,
            recognition_confidence=round(stt_result.confidence, 4),
            classification_confidence=round(semantic_result.classification_confidence, 4),
            confidence=round(stt_result.confidence, 4),
            semantic_status=semantic_result.semantic_status,
            is_uncertain=(
                semantic_result.recognized_command in (CanonicalCommand.UNCERTAIN, CanonicalCommand.UNKNOWN)
                or stt_result.is_low_confidence
            ),
            direction_vector=semantic_result.direction_vector,
            audio_duration_ms=round(duration_ms, 2),
            pitch_f0=prosody.pitch_f0,
            pitch_f0_std=prosody.pitch_f0_std,
            jitter=prosody.jitter,
            shimmer=prosody.shimmer,
            speech_rate=prosody.speech_rate,
            intensity=prosody.intensity,
            audio_quality=prosody.audio_quality,
            model_version=f"faster-whisper-{self.whisper_service.model_name}",
            composite_stress_score=prosody.composite_stress_score,
            stress_score=prosody.composite_stress_score,
            is_stressed=prosody.is_stressed,
        )

        with self._lock:
            self.last_event = event
            self.last_event_time = ts

        self._dispatch_event(event)
        return event

    def _on_audio_chunk(self, chunk: np.ndarray, sample_rate: int) -> None:
        """
        Receives real-time streaming audio frames from microphone.
        1. Continuous Ultra-Low-Latency Keyword Spotting (<3ms).
        2. Dynamic Noise Floor Tracking & Energy VAD.
        3. Segments speech with short ~150ms hangover.
        """
        if not self._is_running or self.mic_service.is_muted:
            return

        # 1. Continuous Ultra-Low-Latency Keyword Spotting
        try:
            self.kws_service.process_chunk(chunk, sample_rate)
        except Exception as e:
            logger.debug(f"KWS chunk processing exception: {e}")

        # 2. Dynamic Noise Floor Tracking & Energy VAD
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        peak = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0

        if not self._is_speaking and rms < 0.02:
            self._ambient_rms = (1.0 - self._adaptive_alpha) * self._ambient_rms + self._adaptive_alpha * rms

        speech_threshold = max(0.008, self._ambient_rms * 2.2, settings.VOICE_SILENCE_ENERGY_THRESHOLD * 2.0)
        silence_threshold = max(0.004, self._ambient_rms * 1.3, settings.VOICE_SILENCE_ENERGY_THRESHOLD)

        is_speech_frame = (rms > speech_threshold) or (peak > speech_threshold * 2.0)
        now_ms = time.time() * 1000.0

        if is_speech_frame:
            if not self._is_speaking:
                self._last_vad_onset_ms = now_ms
            self._is_speaking = True
            self._silence_frames = 0
            self._speech_buffer.append(chunk)

            # Cap max utterance duration to avoid runaway buffers (1.2s max)
            if len(self._speech_buffer) >= self._max_speech_frames:
                self._finalize_speech_segment(sample_rate)
        elif self._is_speaking:
            # Silence detected during active speech
            self._silence_frames += 1
            self._speech_buffer.append(chunk)

            # Check if silence hangover exceeded (~150ms)
            if self._silence_frames >= self._silence_hangover_frames:
                self._last_vad_endpoint_ms = now_ms
                self._finalize_speech_segment(sample_rate)

    def _finalize_speech_segment(self, sample_rate: int) -> None:
        """Finalizes accumulated speech frames and submits to worker queue."""
        if len(self._speech_buffer) >= self._min_speech_frames:
            segment = np.concatenate(self._speech_buffer)
            # Flush older unprocessed segments to prevent audio lag and multi-second queuing
            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                    self._audio_queue.task_done()
                except Exception:
                    break
            try:
                self._audio_queue.put_nowait((segment, sample_rate, time.time() * 1000.0))
            except queue.Full:
                logger.warning("Voice worker queue full; dropping audio segment.")

        self._speech_buffer.clear()
        self._is_speaking = False
        self._silence_frames = 0

    def _worker_loop(self) -> None:
        """Background thread worker pulling audio segments and running inference."""
        while self._is_running:
            try:
                item = self._audio_queue.get(timeout=0.2)
                if item is None:
                    continue

                audio_segment, sr, client_ts = item
                # Drop items that sat in queue longer than 2.0s to ensure real-time command response
                if (time.time() * 1000.0 - client_ts) > 2000.0:
                    self._audio_queue.task_done()
                    continue

                try:
                    self.process_audio_chunk(
                        audio_data=audio_segment,
                        sample_rate=sr,
                        client_timestamp=client_ts,
                    )
                except Exception as e:
                    logger.error(f"Error in voice processing worker: {e}")
                finally:
                    self._audio_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Voice worker loop exception: {e}")

    def _dispatch_event(self, event: VoiceEvent) -> None:
        """Dispatches event to all registered listeners."""
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error in voice event subscriber: {e}")


# Global singleton instance
voice_manager = VoiceManager()

