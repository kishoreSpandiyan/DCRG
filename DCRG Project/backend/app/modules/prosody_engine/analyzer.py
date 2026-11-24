"""
Prosody Analysis Engine for DCRG Phase 3.
Extracts fundamental frequency (F0), jitter, shimmer, speech rate, intensity, and
cognitive stress indicators from acoustic speech segments using Librosa.
"""

import math
import logging
from typing import Optional, Tuple
import numpy as np
import librosa

from app.modules.voice_engine.schemas import (
    ProsodyMetrics,
    AudioQuality,
)

logger = logging.getLogger(__name__)


class ProsodyAnalyzer:
    """
    Acoustic feature extractor and stress estimator.
    
    SAFETY INVARIANT:
    Prosody is purely a telemetry and contextual signal.
    Elevated stress, loudness, or jitter NEVER independently rejects or vetoes a command.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        baseline_f0: float = 160.0,
        f0_std_ref: float = 50.0,
        baseline_jitter: float = 0.012,
        jitter_std_ref: float = 0.010,
        baseline_shimmer: float = 0.030,
        shimmer_std_ref: float = 0.025,
        baseline_intensity: float = 0.15,
        intensity_std_ref: float = 0.10,
        stress_threshold: float = 0.60,
        silence_rms_threshold: float = 0.005,
    ):
        self.sr = sample_rate
        self.baseline_f0 = baseline_f0
        self.f0_std_ref = f0_std_ref
        self.baseline_jitter = baseline_jitter
        self.jitter_std_ref = jitter_std_ref
        self.baseline_shimmer = baseline_shimmer
        self.shimmer_std_ref = shimmer_std_ref
        self.baseline_intensity = baseline_intensity
        self.intensity_std_ref = intensity_std_ref
        self.stress_threshold = stress_threshold
        self.silence_threshold = silence_rms_threshold

    def analyze(self, audio: np.ndarray, sample_rate: Optional[int] = None) -> ProsodyMetrics:
        """
        Extracts prosody and acoustic stress features from a float32 numpy audio chunk.
        Guarantees safe numerical output (no NaN, inf, or division-by-zero).
        """
        sr = sample_rate or self.sr

        # 1. Guard against empty or microscopic audio
        if audio is None or len(audio) == 0:
            return self._empty_metrics(AudioQuality.SILENCE)

        # Flatten to 1D mono float32
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        audio = audio.astype(np.float32)

        # 2. Check for NaN or Inf in raw audio
        if not np.isfinite(audio).all():
            audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)

        duration_sec = len(audio) / float(sr)
        if duration_sec < 0.05:  # Audio shorter than 50ms is too brief for pitch tracking
            return self._empty_metrics(AudioQuality.SILENCE)

        # 3. Intensity and Loudness
        rms = float(np.sqrt(np.mean(np.square(audio))))
        peak_amp = float(np.max(np.abs(audio)))
        intensity_db = float(20.0 * np.log10(max(rms, 1e-6)))
        # Normalized intensity [0.0, 1.0]
        norm_intensity = min(1.0, max(0.0, rms * 4.0))

        # Check silence
        if rms < self.silence_threshold or peak_amp < 1e-4:
            metrics = self._empty_metrics(AudioQuality.SILENCE)
            metrics.intensity = round(norm_intensity, 4)
            metrics.intensity_db = round(intensity_db, 2)
            return metrics

        # 4. Audio Quality Assessment
        quality = AudioQuality.GOOD
        # Check for clipping distortion
        clipping_ratio = np.sum(np.abs(audio) > 0.98) / float(len(audio))
        if clipping_ratio > 0.05:
            quality = AudioQuality.DEGRADED
        else:
            # Check SNR / noise estimate via fast NumPy spectral flatness
            try:
                fft_mag = np.abs(np.fft.rfft(audio)) + 1e-12
                geom_mean = np.exp(np.mean(np.log(fft_mag)))
                arith_mean = np.mean(fft_mag)
                flatness = float(geom_mean / arith_mean)
                if flatness > 0.40:
                    quality = AudioQuality.NOISY
            except Exception:
                pass

        # 5. Fundamental Frequency (F0 / Pitch) Extraction via High-Speed Normalized Autocorrelation
        # Target typical speech range: 65 Hz - 400 Hz
        f0_mean = 0.0
        f0_std = 0.0
        jitter = 0.0
        shimmer = 0.0
        voiced_frames_count = 0

        try:
            frame_len = min(1024, len(audio))
            hop_len = max(256, frame_len // 2)
            f0_track = []
            voiced_energies = []

            for i in range(0, len(audio) - frame_len + 1, hop_len):
                frame = audio[i : i + frame_len]
                energy = float(np.sqrt(np.mean(frame**2)))
                ac = np.correlate(frame, frame, mode='full')[frame_len - 1:]
                min_lag = int(sr / 400.0)
                max_lag = int(sr / 65.0)

                if max_lag < len(ac) and ac[0] > 1e-8:
                    peak_lag = np.argmax(ac[min_lag:max_lag]) + min_lag
                    # Voicing peak threshold
                    if ac[peak_lag] > 0.35 * ac[0]:
                        f0 = sr / float(peak_lag)
                        if 65.0 <= f0 <= 400.0:
                            f0_track.append(f0)
                            voiced_energies.append(energy)

            voiced_frames_count = len(f0_track)
            if voiced_frames_count >= 1:
                f0_mean = float(np.mean(f0_track))
                f0_std = float(np.std(f0_track))

                # 6. Jitter Calculation (Local Period Perturbation)
                if voiced_frames_count >= 2:
                    periods = 1.0 / np.array(f0_track)
                    period_diffs = np.abs(np.diff(periods))
                    mean_period = float(np.mean(periods))
                    if mean_period > 0 and len(period_diffs) > 0:
                        jitter = float(np.mean(period_diffs) / mean_period)
                        jitter = min(1.0, max(0.0, jitter))

                # 7. Shimmer Calculation (Local Frame Amplitude Perturbation)
                if len(voiced_energies) >= 2:
                    amp_diffs = np.abs(np.diff(voiced_energies))
                    mean_amp = float(np.mean(voiced_energies))
                    if mean_amp > 1e-6:
                        shimmer = float(np.mean(amp_diffs) / mean_amp)
                        shimmer = min(1.0, max(0.0, shimmer))

        except Exception as e:
            logger.debug(f"Prosody pitch tracking note: {e}")

        # 8. Speech Rate Estimation (Syllables / Second) via Fast NumPy Energy Onsets
        speech_rate = 0.0
        try:
            frame_hop = int(0.02 * sr)  # 20ms frames
            if len(audio) >= frame_hop * 2:
                num_frames = len(audio) // frame_hop
                hops = audio[: num_frames * frame_hop].reshape(num_frames, frame_hop)
                rms_frames = np.sqrt(np.mean(hops**2, axis=1))
                diffs = np.diff(rms_frames)
                # Syllabic onset threshold above background noise
                onsets = np.where(diffs > 0.015)[0]
                if duration_sec > 0:
                    speech_rate = float(len(onsets) / duration_sec)
                    speech_rate = min(15.0, max(0.0, speech_rate))
        except Exception as e:
            logger.debug(f"Prosody speech rate detection note: {e}")

        # 9. Composite Cognitive Stress Score Synthesis
        stress_score, is_stressed = self._compute_stress_score(
            f0_mean=f0_mean,
            jitter=jitter,
            shimmer=shimmer,
            intensity=norm_intensity,
            has_voiced_speech=(voiced_frames_count >= 2),
        )

        return ProsodyMetrics(
            pitch_f0=round(self._sanitize(f0_mean), 2),
            pitch_f0_std=round(self._sanitize(f0_std), 2),
            jitter=round(self._sanitize(jitter), 4),
            shimmer=round(self._sanitize(shimmer), 4),
            speech_rate=round(self._sanitize(speech_rate), 2),
            intensity=round(self._sanitize(norm_intensity), 4),
            intensity_db=round(self._sanitize(intensity_db), 2),
            composite_stress_score=round(self._sanitize(stress_score), 4),
            is_stressed=is_stressed,
            audio_quality=quality,
        )

    def _compute_stress_score(
        self,
        f0_mean: float,
        jitter: float,
        shimmer: float,
        intensity: float,
        has_voiced_speech: bool,
    ) -> Tuple[float, bool]:
        """
        Synthesizes composite cognitive stress score in [0.0, 1.0] via normalized logistic activation:
        S = sigmoid(alpha1 * z_f0 + alpha2 * z_jitter + alpha3 * z_shimmer + alpha4 * z_int)
        """
        if not has_voiced_speech or f0_mean <= 0.0:
            return 0.0, False

        # Z-score deviations against baseline
        z_f0 = (f0_mean - self.baseline_f0) / self.f0_std_ref
        z_jitter = (jitter - self.baseline_jitter) / self.jitter_std_ref
        z_shimmer = (shimmer - self.baseline_shimmer) / self.shimmer_std_ref
        z_int = (intensity - self.baseline_intensity) / self.intensity_std_ref

        # Acoustic stress synthesis weights (per DCRG-ARCH-002: alpha1=0.4, alpha2=0.2, alpha3=0.2, alpha4=0.2)
        z = (0.4 * z_f0) + (0.2 * z_jitter) + (0.2 * z_shimmer) + (0.2 * z_int)

        # Logistic sigmoid bounded to [0.0, 1.0]
        try:
            score = 1.0 / (1.0 + math.exp(-z))
        except OverflowError:
            score = 1.0 if z > 0 else 0.0

        score = min(1.0, max(0.0, score))
        is_stressed = score >= self.stress_threshold
        return score, is_stressed

    @staticmethod
    def _sanitize(val: float) -> float:
        """Sanitizes floating point numbers against NaN, inf, or corruptions."""
        if math.isnan(val) or math.isinf(val):
            return 0.0
        return float(val)

    def _empty_metrics(self, quality: AudioQuality = AudioQuality.SILENCE) -> ProsodyMetrics:
        """Returns baseline neutral metrics for silent/empty chunks."""
        return ProsodyMetrics(
            pitch_f0=0.0,
            pitch_f0_std=0.0,
            jitter=0.0,
            shimmer=0.0,
            speech_rate=0.0,
            intensity=0.0,
            intensity_db=-96.0,
            composite_stress_score=0.0,
            is_stressed=False,
            audio_quality=quality,
        )


# Global singleton prosody analyzer
prosody_analyzer = ProsodyAnalyzer()

