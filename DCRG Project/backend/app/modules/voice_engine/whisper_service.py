"""
Faster-Whisper Local Speech-to-Text Recognition Service.
Compliant with DCRG-ARCH-002: low-latency int8 inference, greedy decoding,
confidence extraction, and extensible multilingual vocabulary.
"""

import logging
import math
import threading
import time
from typing import Dict, List, Optional, Tuple
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class WhisperTranscriptionResult:
    """Structured transcription output with confidence and timing."""
    def __init__(
        self,
        transcript: str,
        confidence: float,
        avg_logprob: float,
        language: str,
        duration_ms: float,
        latency_ms: float,
        is_empty: bool = False,
        is_low_confidence: bool = False,
        segments: Optional[List[Dict]] = None,
    ):
        self.transcript = transcript
        self.confidence = confidence
        self.avg_logprob = avg_logprob
        self.language = language
        self.duration_ms = duration_ms
        self.latency_ms = latency_ms
        self.is_empty = is_empty
        self.is_low_confidence = is_low_confidence
        self.segments = segments or []

    def to_dict(self) -> Dict:
        return {
            "transcript": self.transcript,
            "confidence": round(self.confidence, 4),
            "avg_logprob": round(self.avg_logprob, 4),
            "language": self.language,
            "duration_ms": round(self.duration_ms, 2),
            "latency_ms": round(self.latency_ms, 2),
            "is_empty": self.is_empty,
            "is_low_confidence": self.is_low_confidence,
        }


class WhisperService:
    """
    Local Faster-Whisper inference engine wrapper.
    Uses CTranslate2 quantized execution with greedy search (beam_size=1) for minimal latency.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        default_language: Optional[str] = None,
        confidence_threshold: Optional[float] = None,
    ):
        self.model_name = model_name or settings.WHISPER_MODEL_SIZE
        self.device = device or settings.WHISPER_DEVICE
        self.compute_type = compute_type or settings.WHISPER_COMPUTE_TYPE
        self.default_language = default_language or settings.WHISPER_LANGUAGE
        self.confidence_threshold = confidence_threshold or settings.VOICE_RECOGNITION_CONFIDENCE_THRESHOLD

        self._model = None
        self._model_lock = threading.Lock()
        self._is_loaded = False
        self.load_duration_seconds: float = 0.0

        # Lexical pre-conditioning prompts to bias decoder logits toward control vocabulary
        self._lexical_prompts: Dict[str, str] = {
            "en": "Robot command: move, move operation, move forward, forward, move backward, backward, move left, left, move right, right, stop, halt, freeze.",
            "ta": "ரோபோ கட்டளைகள்: நில், நிறுத்து, முன்னே போ, பின்னே போ, இடது பக்கம், வலது பக்கம்.",
        }

    def load_model(self) -> bool:
        """Loads the Faster-Whisper model into memory."""
        with self._model_lock:
            if self._is_loaded and self._model is not None:
                return True

            t0 = time.time()
            try:
                from faster_whisper import WhisperModel
                logger.info(
                    f"Loading Faster-Whisper model '{self.model_name}' on {self.device} ({self.compute_type})..."
                )
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                self.load_duration_seconds = time.time() - t0
                self._is_loaded = True
                logger.info(f"Faster-Whisper model '{self.model_name}' loaded in {self.load_duration_seconds:.3f}s")
                return True
            except Exception as e:
                logger.error(f"Failed to load Faster-Whisper model: {e}")
                self._is_loaded = False
                self._model = None
                return False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded and (self._model is not None)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> WhisperTranscriptionResult:
        """
        Transcribes 16kHz float32 mono audio array into text with confidence metrics.
        """
        # Guard against uninitialized model
        if not self.is_loaded:
            success = self.load_model()
            if not success or self._model is None:
                return WhisperTranscriptionResult(
                    transcript="",
                    confidence=0.0,
                    avg_logprob=-99.0,
                    language=language or self.default_language,
                    duration_ms=0.0,
                    latency_ms=0.0,
                    is_empty=True,
                    is_low_confidence=True,
                )

        # Preprocess and validate audio
        if audio is None or len(audio) == 0:
            return WhisperTranscriptionResult(
                transcript="",
                confidence=0.0,
                avg_logprob=-99.0,
                language=language or self.default_language,
                duration_ms=0.0,
                latency_ms=0.0,
                is_empty=True,
                is_low_confidence=True,
            )

        # Reshape / convert to 1D float32
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        audio = audio.astype(np.float32)

        # Silence guard: if RMS < threshold, avoid burning inference cycles
        rms = float(np.sqrt(np.mean(np.square(audio))))
        duration_ms = (len(audio) / float(sample_rate)) * 1000.0

        if rms < settings.VOICE_SILENCE_ENERGY_THRESHOLD or duration_ms < 100.0:
            return WhisperTranscriptionResult(
                transcript="",
                confidence=0.0,
                avg_logprob=-99.0,
                language=language or self.default_language,
                duration_ms=duration_ms,
                latency_ms=0.0,
                is_empty=True,
                is_low_confidence=True,
            )

        lang = language or self.default_language
        prompt = self._lexical_prompts.get(lang, self._lexical_prompts.get("en", ""))

        t_start = time.time()
        try:
            with self._model_lock:
                # beam_size=1 (greedy search) and bounded token decoding for ultra low latency
                segments_iter, info = self._model.transcribe(
                    audio,
                    beam_size=1,
                    best_of=1,
                    language=lang if lang != "auto" else None,
                    initial_prompt=prompt,
                    vad_filter=False,
                    word_timestamps=False,
                    without_timestamps=True,
                    condition_on_previous_text=False,
                    temperature=0.0,
                    max_new_tokens=12,
                )
                segment_list = list(segments_iter)

            latency_ms = (time.time() - t_start) * 1000.0

            if not segment_list:
                return WhisperTranscriptionResult(
                    transcript="",
                    confidence=0.0,
                    avg_logprob=-99.0,
                    language=lang,
                    duration_ms=duration_ms,
                    latency_ms=latency_ms,
                    is_empty=True,
                    is_low_confidence=True,
                )

            # Assemble transcript and compute aggregated confidence
            full_text_parts = []
            logprobs = []
            segment_data = []

            for seg in segment_list:
                clean_seg_text = seg.text.strip()
                if clean_seg_text:
                    full_text_parts.append(clean_seg_text)
                    logprobs.append(seg.avg_logprob)
                    segment_data.append({
                        "start": seg.start,
                        "end": seg.end,
                        "text": clean_seg_text,
                        "avg_logprob": seg.avg_logprob,
                        "no_speech_prob": seg.no_speech_prob,
                    })

            full_transcript = " ".join(full_text_parts).strip()
            if not full_transcript:
                return WhisperTranscriptionResult(
                    transcript="",
                    confidence=0.0,
                    avg_logprob=-99.0,
                    language=lang,
                    duration_ms=duration_ms,
                    latency_ms=latency_ms,
                    is_empty=True,
                    is_low_confidence=True,
                )

            # Aggregate log probability
            mean_logprob = float(np.mean(logprobs)) if logprobs else -99.0

            # Convert logprob to probability: P = exp(avg_logprob)
            try:
                confidence = float(math.exp(mean_logprob))
            except OverflowError:
                confidence = 0.0
            confidence = min(1.0, max(0.0, confidence))

            is_low_conf = (confidence < self.confidence_threshold) or (mean_logprob < -1.0)

            return WhisperTranscriptionResult(
                transcript=full_transcript,
                confidence=confidence,
                avg_logprob=mean_logprob,
                language=info.language if hasattr(info, "language") else lang,
                duration_ms=duration_ms,
                latency_ms=latency_ms,
                is_empty=False,
                is_low_confidence=is_low_conf,
                segments=segment_data,
            )

        except Exception as e:
            latency_ms = (time.time() - t_start) * 1000.0
            logger.error(f"Whisper inference error: {e}")
            return WhisperTranscriptionResult(
                transcript="",
                confidence=0.0,
                avg_logprob=-99.0,
                language=lang,
                duration_ms=duration_ms,
                latency_ms=latency_ms,
                is_empty=True,
                is_low_confidence=True,
            )


# Global singleton instance
whisper_service = WhisperService()

