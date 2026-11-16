"""
Microphone Audio Input Service.
Captures live mono 16 kHz audio via SoundDevice, maintains a real-time circular ring buffer,
handles device selection, mute states, and hardware errors/disconnections safely.
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional
import numpy as np

from app.core.config import settings
from app.modules.voice_engine.schemas import MicrophoneStatus

logger = logging.getLogger(__name__)


class RingBuffer:
    """Thread-safe circular audio buffer for sliding-window speech analysis."""
    def __init__(self, capacity_samples: int):
        self.capacity = capacity_samples
        self._buffer = np.zeros(capacity_samples, dtype=np.float32)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()

    def append(self, samples: np.ndarray) -> None:
        """Appends new 1D float32 audio samples into the ring buffer."""
        if samples is None or len(samples) == 0:
            return

        flat = samples.flatten().astype(np.float32)
        num_samples = len(flat)

        with self._lock:
            if num_samples >= self.capacity:
                # Samples exceed entire capacity, keep latest tail
                self._buffer[:] = flat[-self.capacity:]
                self._write_pos = 0
                self._total_written += num_samples
                return

            end_pos = self._write_pos + num_samples
            if end_pos <= self.capacity:
                self._buffer[self._write_pos:end_pos] = flat
                self._write_pos = (end_pos % self.capacity)
            else:
                first_part = self.capacity - self._write_pos
                second_part = num_samples - first_part
                self._buffer[self._write_pos:] = flat[:first_part]
                self._buffer[:second_part] = flat[first_part:]
                self._write_pos = second_part

            self._total_written += num_samples

    def get_latest(self, num_samples: int) -> np.ndarray:
        """Extracts the most recent N samples in chronological order."""
        with self._lock:
            n = min(num_samples, self.capacity, self._total_written)
            if n <= 0:
                return np.zeros(0, dtype=np.float32)

            # Circular reconstruct
            if self._total_written < self.capacity:
                return self._buffer[:self._write_pos][-n:].copy()

            start_pos = (self._write_pos - n) % self.capacity
            if start_pos < self._write_pos:
                return self._buffer[start_pos:self._write_pos].copy()
            else:
                return np.concatenate((self._buffer[start_pos:], self._buffer[:self._write_pos]))

    def clear(self) -> None:
        with self._lock:
            self._buffer.fill(0.0)
            self._write_pos = 0
            self._total_written = 0


class MicrophoneService:
    """
    Microphone hardware ingestion service.
    Enforces non-continuous raw storage, mono 16 kHz ingestion, error isolation,
    and truthful status reporting (CONNECTED, DISCONNECTED, MUTED, ERROR).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        buffer_seconds: float = 3.0,
        device_index: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.capacity_samples = int(sample_rate * buffer_seconds)
        self.ring_buffer = RingBuffer(self.capacity_samples)

        self.device_index = device_index
        self.device_name: Optional[str] = None
        self.status = MicrophoneStatus.DISCONNECTED
        self.is_capturing = False
        self.is_muted = False
        self.hardware_error: Optional[str] = None

        self._stream = None
        self._lock = threading.RLock()
        self._subscribers: List[Callable[[np.ndarray, int], None]] = []

    def get_available_devices(self) -> List[Dict]:
        """Queries physical and virtual host audio input devices."""
        devices = []
        try:
            import sounddevice as sd
            # Force re-initialization of PortAudio to pick up hot-plugged Type-C/USB devices
            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass

            dev_list = sd.query_devices()
            default_input = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else -1

            for idx, dev in enumerate(dev_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name", f"Microphone {idx}"),
                        "hostapi": dev.get("hostapi", 0),
                        "max_input_channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 16000.0),
                        "is_default": (idx == default_input),
                    })
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
        return devices

    def select_device(self, device_index: Optional[int]) -> Tuple[bool, str]:
        """Allows selecting a specific microphone device."""
        with self._lock:
            devices = self.get_available_devices()
            if device_index is not None:
                matched = next((d for d in devices if d["index"] == device_index), None)
                if not matched:
                    msg = f"Device index {device_index} not found in available input devices."
                    logger.warning(msg)
                    return False, msg
                self.device_index = device_index
                self.device_name = matched["name"]
            else:
                self.device_index = None
                self.device_name = "System Default"

            # If stream is running, restart on new device
            if self.is_capturing:
                self.stop()
                return self.start()

            return True, f"Selected audio device: {self.device_name}"

    def register_chunk_subscriber(self, callback: Callable[[np.ndarray, int], None]) -> None:
        """Registers a callback receiving raw audio frames (audio, sample_rate)."""
        with self._lock:
            self._subscribers.append(callback)

    def start(self) -> Tuple[bool, str]:
        """Opens the microphone input stream and starts continuous capture."""
        with self._lock:
            if self.is_capturing and self._stream is not None:
                return True, "Microphone capture is already active."

            try:
                import sounddevice as sd
                # Set default device if none chosen
                devices = self.get_available_devices()
                if not devices:
                    self.status = MicrophoneStatus.ERROR
                    self.hardware_error = "No microphone input devices detected on host system."
                    logger.error(self.hardware_error)
                    return False, self.hardware_error

                if self.device_index is None:
                    # Auto-detect and prioritize USB/Type-C microphone if connected
                    typec_dev = next(
                        (d for d in devices if any(k in d.get("name", "").lower() for k in ["type-c", "type c", "usb", "headphone", "earphone", "headset"])),
                        None
                    )
                    def_dev = next((d for d in devices if d.get("is_default")), devices[0])
                    target = typec_dev or def_dev
                    self.device_index = target["index"]
                    self.device_name = target["name"]
                else:
                    curr_dev = next((d for d in devices if d["index"] == self.device_index), None)
                    if curr_dev:
                        self.device_name = curr_dev["name"]

                self.ring_buffer.clear()
                self.hardware_error = None

                # Open 16 kHz mono InputStream
                self._stream = sd.InputStream(
                    device=self.device_index,
                    channels=1,
                    samplerate=self.sample_rate,
                    dtype="float32",
                    blocksize=int(self.sample_rate * 0.03),  # 30ms chunks = 480 samples
                    callback=self._audio_callback,
                )
                self._stream.start()
                self.is_capturing = True
                self.status = MicrophoneStatus.MUTED if self.is_muted else MicrophoneStatus.CONNECTED
                msg = f"Microphone started: {self.device_name} (16kHz mono)"
                logger.info(msg)
                return True, msg

            except Exception as e:
                self.status = MicrophoneStatus.ERROR
                self.hardware_error = f"Failed to initialize microphone stream: {str(e)}"
                self.is_capturing = False
                self._stream = None
                logger.error(self.hardware_error)
                return False, self.hardware_error

    def stop(self) -> Tuple[bool, str]:
        """Closes the audio input stream and releases audio hardware."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.warning(f"Error while closing audio stream: {e}")
                finally:
                    self._stream = None

            self.is_capturing = False
            self.status = MicrophoneStatus.DISCONNECTED
            msg = "Microphone capture stopped cleanly."
            logger.info(msg)
            return True, msg

    def set_mute(self, muted: bool) -> bool:
        """Sets mute state."""
        with self._lock:
            self.is_muted = muted
            if self.is_capturing:
                self.status = MicrophoneStatus.MUTED if muted else MicrophoneStatus.CONNECTED
            return self.is_muted

    def _audio_callback(self, indata, frames, time_info, status):
        """Audio streaming callback executed by sounddevice thread."""
        if status:
            logger.debug(f"SoundDevice status warning: {status}")

        if not self.is_capturing:
            return

        # If muted, append silence
        if self.is_muted:
            chunk = np.zeros(frames, dtype=np.float32)
        else:
            chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()

        # Push to sliding ring buffer
        self.ring_buffer.append(chunk)

        # Dispatch chunk to registered subscribers
        for sub in self._subscribers:
            try:
                sub(chunk, self.sample_rate)
            except Exception as e:
                logger.debug(f"Audio subscriber callback error: {e}")


# Global singleton microphone service
microphone_service = MicrophoneService()

