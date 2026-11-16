"""
Physical Joystick Service using Pygame-CE (SDL2).
Direct hardware integration for USB and Bluetooth game controllers.
Maintains strict single-thread SDL2 affinity to prevent Windows COM / XInput deadlocks.
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Callable, Any
import pygame

from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
)
from app.modules.actuator_engine.calibration import (
    JoystickProfileRegistry,
    JoystickProfile,
    apply_radial_deadzone,
    calibrate_axis,
)
from app.modules.actuator_engine.classifier import classify_joystick_vector

logger = logging.getLogger(__name__)


class DeviceMetadata:
    def __init__(self, index: int, name: str, guid: str, num_axes: int, num_buttons: int, num_hats: int):
        self.index = index
        self.name = name
        self.guid = guid
        self.num_axes = num_axes
        self.num_buttons = num_buttons
        self.num_hats = num_hats
        self.device_id = f"USB-{name.replace(' ', '_')}-{index}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "guid": self.guid,
            "device_id": self.device_id,
            "axes_count": self.num_axes,
            "buttons_count": self.num_buttons,
            "hats_count": self.num_hats,
        }


class PhysicalJoystickService:
    """
    Manages hardware communication with USB and Bluetooth controllers.
    Operates an isolated background worker thread at 50Hz.
    """
    def __init__(self, profile_registry: Optional[JoystickProfileRegistry] = None):
        self.profile_registry = profile_registry or JoystickProfileRegistry()
        self._is_running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Connected devices indexed by SDL instance id
        self.joysticks: Dict[int, pygame.joystick.Joystick] = {}
        self.metadata: Dict[int, DeviceMetadata] = {}
        self.active_device_index: Optional[int] = None
        self.active_profile: Optional[JoystickProfile] = None

        # Event callbacks
        self.event_callbacks: List[Callable[[CommonJoystickEvent], None]] = []

        # Latest raw state
        self.latest_axes: List[float] = []
        self.latest_buttons: List[bool] = []
        self.latest_hats: List[tuple] = []
        self.last_event: Optional[CommonJoystickEvent] = None
        self.hardware_error: Optional[str] = None

        self._ready_event = threading.Event()

    def start(self) -> None:
        """Starts 50Hz background hardware polling thread."""
        with self._lock:
            if self._is_running:
                return
            self._ready_event.clear()
            self._is_running = True
            self._thread = threading.Thread(target=self._polling_loop, daemon=True, name="DCRG-JoystickPoll")
            self._thread.start()
        # Wait up to 1 second for initial SDL enumeration to complete
        self._ready_event.wait(timeout=1.0)
        logger.info("Physical joystick background polling thread started at 50Hz.")

    def stop(self) -> None:
        """Stops polling and releases hardware handles cleanly."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        with self._lock:
            self.metadata.clear()
            self.joysticks.clear()
            self.active_device_index = None
        logger.info("Physical joystick service stopped cleanly.")

    def get_connected_devices(self) -> List[Dict[str, Any]]:
        """Returns metadata for all detected physical controllers."""
        with self._lock:
            return [m.to_dict() for m in self.metadata.values()]

    def is_hardware_connected(self) -> bool:
        """Truthful check whether a physical controller is currently plugged in."""
        with self._lock:
            return len(self.metadata) > 0 and self.active_device_index is not None

    def rescan(self) -> List[Dict[str, Any]]:
        """Forces SDL2 re-enumeration to discover hotplugged USB flight sticks / controllers."""
        with self._lock:
            try:
                pygame.joystick.quit()
                pygame.joystick.init()
                self._refresh_connected_devices()
                logger.info(f"Rescanned physical joysticks. Found: {len(self.metadata)} device(s).")
            except Exception as e:
                logger.warning(f"Error during physical joystick rescan: {e}")
            return self.get_connected_devices()

    def register_callback(self, callback: Callable[[CommonJoystickEvent], None]) -> None:
        """Registers listener callback for processed joystick events."""
        with self._lock:
            self.event_callbacks.append(callback)

    def _refresh_connected_devices(self) -> None:
        """Enumerates and connects available joysticks within the polling thread."""
        count = pygame.joystick.get_count()
        self.joysticks.clear()
        self.metadata.clear()

        for idx in range(count):
            try:
                joy = pygame.joystick.Joystick(idx)
                instance_id = joy.get_instance_id()
                self.joysticks[instance_id] = joy
                meta = DeviceMetadata(
                    index=idx,
                    name=joy.get_name(),
                    guid=joy.get_guid(),
                    num_axes=joy.get_numaxes(),
                    num_buttons=joy.get_numbuttons(),
                    num_hats=joy.get_numhats(),
                )
                self.metadata[instance_id] = meta

                if self.active_device_index is None or self.active_device_index not in self.joysticks:
                    self.active_device_index = instance_id
                    self.active_profile = self.profile_registry.get_profile_for_device(meta.name)
                    logger.info(f"Selected active joystick: {meta.name} (Profile: {self.active_profile.profile_name})")
            except Exception as e:
                logger.warning(f"Failed to initialize joystick at index {idx}: {e}")

        if count == 0:
            self.active_device_index = None
            self.active_profile = None

    def _polling_loop(self) -> None:
        """Dedicated 50Hz polling loop with full SDL2 thread-local lifecycle."""
        try:
            pygame.init()
            pygame.joystick.init()
            with self._lock:
                self._refresh_connected_devices()
            self._ready_event.set()
        except Exception as e:
            self.hardware_error = f"Failed to initialize SDL in poll thread: {e}"
            logger.error(self.hardware_error)
            self._ready_event.set()
            return

        clock = pygame.time.Clock()
        tick_counter = 0
        while self._is_running:
            try:
                self._poll_once()
                tick_counter += 1
                # Periodically re-check for hotplugged hardware every 100 ticks (~2s) if no hardware is active
                if tick_counter % 100 == 0:
                    with self._lock:
                        if len(self.metadata) == 0:
                            if pygame.joystick.get_count() > 0:
                                self._refresh_connected_devices()
                clock.tick(50)  # Rate limit to ~50 Hz
            except Exception as e:
                logger.error(f"Error in joystick polling loop: {e}")
                self.hardware_error = str(e)
                time.sleep(0.05)

        # Thread-local SDL cleanup
        try:
            with self._lock:
                self.joysticks.clear()
            pygame.joystick.quit()
            pygame.quit()
        except Exception:
            pass

    def _poll_once(self) -> Optional[CommonJoystickEvent]:
        """Polls SDL event queue, updates state, and emits CommonJoystickEvent."""
        pygame.event.pump()

        # Handle device addition / removal
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEADDED:
                logger.info(f"Physical joystick connected: device index {event.device_index}")
                with self._lock:
                    self._refresh_connected_devices()
            elif event.type == pygame.JOYDEVICEREMOVED:
                logger.warning(f"Physical joystick disconnected: instance {event.instance_id}")
                with self._lock:
                    if event.instance_id in self.joysticks:
                        del self.joysticks[event.instance_id]
                    if event.instance_id in self.metadata:
                        del self.metadata[event.instance_id]
                    if self.active_device_index == event.instance_id:
                        self.active_device_index = next(iter(self.joysticks.keys()), None)
                        if self.active_device_index:
                            self.active_profile = self.profile_registry.get_profile_for_device(
                                self.metadata[self.active_device_index].name
                            )
                        else:
                            self.active_profile = None

        with self._lock:
            if not self.is_hardware_connected():
                # Fallback A: Poll XInput for ViGEm / PC Remote Xbox 360 controller emulation
                xi_ev = self._poll_xinput_fallback()
                if xi_ev:
                    return xi_ev
                # Fallback B: Poll global Windows keystrokes for PC Remote D-pad (Arrow keys / WASD)
                kb_ev = self._poll_global_keyboard_fallback()
                if kb_ev:
                    return kb_ev
                return None

            active_joy = self.joysticks.get(self.active_device_index)
            meta = self.metadata.get(self.active_device_index)
            profile = self.active_profile or self.profile_registry.get_profile_for_device("default")

        if not active_joy or not meta:
            return None

        # Read raw axes
        num_axes = active_joy.get_numaxes()
        raw_axes = [active_joy.get_axis(i) for i in range(num_axes)]

        # Read raw buttons
        num_buttons = active_joy.get_numbuttons()
        raw_buttons = [bool(active_joy.get_button(i)) for i in range(num_buttons)]

        # Read raw POV hats
        num_hats = active_joy.get_numhats()
        raw_hats = [active_joy.get_hat(i) for i in range(num_hats)]

        self.latest_axes = raw_axes
        self.latest_buttons = raw_buttons
        self.latest_hats = raw_hats

        # Map axes based on profile
        x_cfg = profile.axis_mapping.get("x", {"index": 0, "inverted": False, "deadzone": 0.08})
        y_cfg = profile.axis_mapping.get("y", {"index": 1, "inverted": True, "deadzone": 0.08})

        x_idx = x_cfg.get("index", 0)
        y_idx = y_cfg.get("index", 1)

        raw_x = raw_axes[x_idx] if x_idx < num_axes else 0.0
        raw_y = raw_axes[y_idx] if y_idx < num_axes else 0.0

        # Apply per-axis calibration (inversion & min/max)
        calibrated_x = calibrate_axis(
            raw_x,
            inverted=x_cfg.get("inverted", False),
            deadzone=x_cfg.get("deadzone", 0.0),
            center=x_cfg.get("center", 0.0),
            axis_min=x_cfg.get("min", -1.0),
            axis_max=x_cfg.get("max", 1.0),
            sensitivity=x_cfg.get("sensitivity", 1.0)
        )
        calibrated_y = calibrate_axis(
            raw_y,
            inverted=y_cfg.get("inverted", True),
            deadzone=y_cfg.get("deadzone", 0.0),
            center=y_cfg.get("center", 0.0),
            axis_min=y_cfg.get("min", -1.0),
            axis_max=y_cfg.get("max", 1.0),
            sensitivity=y_cfg.get("sensitivity", 1.0)
        )

        # Apply radial deadzone filtering for 2D movement
        radial_dz = profile.radial_deadzone
        norm_x, norm_y, intensity = apply_radial_deadzone(calibrated_x, calibrated_y, deadzone=radial_dz)

        # Classify direction
        direction, _ = classify_joystick_vector(
            norm_x,
            norm_y,
            connection_status=ConnectionStatus.CONNECTED,
            data_validity=DataValidity.VALID,
            center_deadzone=radial_dz
        )

        now_ms = time.time() * 1000.0
        event = CommonJoystickEvent(
            source=JoystickSource.PHYSICAL_HARDWARE,
            is_simulation=False,
            device_id=meta.device_id,
            timestamp=now_ms,
            axis_x=norm_x,
            axis_y=norm_y,
            direction=direction,
            intensity=intensity,
            buttons=raw_buttons,
            connection_status=ConnectionStatus.CONNECTED,
            calibration_status=CalibrationStatus.CALIBRATED,
            data_validity=DataValidity.VALID,
        )

        self.last_event = event

        # Notify callbacks
        for cb in self.event_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error executing joystick callback: {e}")

        return event

    def _poll_xinput_fallback(self) -> Optional[CommonJoystickEvent]:
        """Reads XInput controller state for PC Remote / ViGEm virtual Xbox 360 gamepads."""
        try:
            import ctypes
            try:
                xinput = ctypes.windll.xinput1_4
            except Exception:
                try:
                    xinput = ctypes.windll.xinput1_3
                except Exception:
                    return None

            class XINPUT_STATE(ctypes.Structure):
                _fields_ = [
                    ('dwPacketNumber', ctypes.c_uint32),
                    ('wButtons', ctypes.c_ushort),
                    ('bLeftTrigger', ctypes.c_ubyte),
                    ('bRightTrigger', ctypes.c_ubyte),
                    ('sThumbLX', ctypes.c_short),
                    ('sThumbLY', ctypes.c_short),
                    ('sThumbRX', ctypes.c_short),
                    ('sThumbRY', ctypes.c_short)
                ]

            for slot in range(4):
                state = XINPUT_STATE()
                if xinput.XInputGetState(slot, ctypes.byref(state)) == 0:
                    raw_x = state.sThumbLX / 32768.0
                    raw_y = state.sThumbLY / 32768.0
                    btns = state.wButtons
                    if btns & 0x0001:  # DPAD_UP
                        raw_y = 1.0
                    elif btns & 0x0002:  # DPAD_DOWN
                        raw_y = -1.0
                    if btns & 0x0004:  # DPAD_LEFT
                        raw_x = -1.0
                    elif btns & 0x0008:  # DPAD_RIGHT
                        raw_x = 1.0

                    norm_x, norm_y, intensity = apply_radial_deadzone(raw_x, raw_y, deadzone=0.08)
                    direction, _ = classify_joystick_vector(
                        norm_x, norm_y,
                        connection_status=ConnectionStatus.CONNECTED,
                        data_validity=DataValidity.VALID,
                        center_deadzone=0.08
                    )
                    now_ms = time.time() * 1000.0
                    event = CommonJoystickEvent(
                        source=JoystickSource.PHYSICAL_HARDWARE,
                        is_simulation=False,
                        device_id=f"PCREMOTE-XINPUT-{slot}",
                        timestamp=now_ms,
                        axis_x=norm_x,
                        axis_y=norm_y,
                        direction=direction,
                        intensity=intensity,
                        buttons=[bool(btns & (1 << b)) for b in range(12)],
                        connection_status=ConnectionStatus.CONNECTED,
                        calibration_status=CalibrationStatus.CALIBRATED,
                        data_validity=DataValidity.VALID,
                    )
                    self.last_event = event
                    self.latest_axes = [norm_x, norm_y]
                    for cb in self.event_callbacks:
                        try:
                            cb(event)
                        except Exception:
                            pass
                    return event
        except Exception:
            pass
        return None

    def _poll_global_keyboard_fallback(self) -> Optional[CommonJoystickEvent]:
        """Reads global Windows keystrokes for PC Remote mobile D-Pad (Arrow keys / WASD)."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            up = bool((user32.GetAsyncKeyState(0x26) & 0x8000) or (user32.GetAsyncKeyState(0x57) & 0x8000))
            down = bool((user32.GetAsyncKeyState(0x28) & 0x8000) or (user32.GetAsyncKeyState(0x53) & 0x8000))
            left = bool((user32.GetAsyncKeyState(0x25) & 0x8000) or (user32.GetAsyncKeyState(0x41) & 0x8000))
            right = bool((user32.GetAsyncKeyState(0x27) & 0x8000) or (user32.GetAsyncKeyState(0x44) & 0x8000))

            if not (up or down or left or right):
                if getattr(self, "_last_global_k_active", False):
                    self._last_global_k_active = False
                    now_ms = time.time() * 1000.0
                    event = CommonJoystickEvent(
                        source=JoystickSource.PHYSICAL_HARDWARE,
                        is_simulation=False,
                        device_id="PCREMOTE-MOBILE-DPAD",
                        timestamp=now_ms,
                        axis_x=0.0,
                        axis_y=0.0,
                        direction=JoystickDirection.CENTER,
                        intensity=0.0,
                        buttons=[],
                        connection_status=ConnectionStatus.CONNECTED,
                        calibration_status=CalibrationStatus.CALIBRATED,
                        data_validity=DataValidity.VALID,
                    )
                    self.last_event = event
                    for cb in self.event_callbacks:
                        try:
                            cb(event)
                        except Exception:
                            pass
                    return event
                return None

            self._last_global_k_active = True
            raw_x = (-1.0 if left else 0.0) + (1.0 if right else 0.0)
            raw_y = (1.0 if up else 0.0) + (-1.0 if down else 0.0)

            norm_x, norm_y, intensity = apply_radial_deadzone(raw_x, raw_y, deadzone=0.08)
            direction, _ = classify_joystick_vector(
                norm_x, norm_y,
                connection_status=ConnectionStatus.CONNECTED,
                data_validity=DataValidity.VALID,
                center_deadzone=0.08
            )
            now_ms = time.time() * 1000.0
            event = CommonJoystickEvent(
                source=JoystickSource.PHYSICAL_HARDWARE,
                is_simulation=False,
                device_id="PCREMOTE-MOBILE-DPAD",
                timestamp=now_ms,
                axis_x=norm_x,
                axis_y=norm_y,
                direction=direction,
                intensity=intensity,
                buttons=[],
                connection_status=ConnectionStatus.CONNECTED,
                calibration_status=CalibrationStatus.CALIBRATED,
                data_validity=DataValidity.VALID,
            )
            self.last_event = event
            self.latest_axes = [norm_x, norm_y]
            for cb in self.event_callbacks:
                try:
                    cb(event)
                except Exception:
                    pass
            return event
        except Exception:
            return None
