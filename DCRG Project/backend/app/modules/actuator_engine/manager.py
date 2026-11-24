"""
Actuator Manager.
Coordinates physical and virtual joystick modes, enforces strict isolation,
and exposes a unified stream for the DCRG Event Synchronization and Safety layers.
"""

import logging
import threading
import time
from typing import Optional, List, Callable, Dict, Any, Tuple
from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickMode,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
    JoystickSystemStatus,
    JoystickDirection,
)
from app.modules.actuator_engine.calibration import apply_radial_deadzone
from app.modules.actuator_engine.classifier import classify_joystick_vector
from app.hardware.joystick_service import PhysicalJoystickService

logger = logging.getLogger(__name__)


class ActuatorManager:
    """
    Central controller for actuator inputs.
    Enforces mode exclusivity: either VIRTUAL_SIMULATION or REAL_HARDWARE.
    """
    def __init__(self, physical_service: Optional[PhysicalJoystickService] = None):
        self.physical_service = physical_service or PhysicalJoystickService()
        self.active_mode: JoystickMode = JoystickMode.VIRTUAL_SIMULATION
        self._lock = threading.RLock()

        # Listeners for validated CommonJoystickEvent
        self._subscribers: List[Callable[[CommonJoystickEvent], None]] = []

        # Latest states
        self.last_event: Optional[CommonJoystickEvent] = None
        self.last_event_time: float = 0.0
        self.radial_deadzone: float = 0.08

        # Hook into physical service events
        self.physical_service.register_callback(self._on_physical_joystick_event)

    def start(self) -> None:
        """Starts backend hardware service polling."""
        self.physical_service.start()

    def stop(self) -> None:
        """Stops hardware service and releases resources."""
        self.physical_service.stop()

    def subscribe(self, callback: Callable[[CommonJoystickEvent], None]) -> None:
        """Register subscriber for validated actuator events."""
        with self._lock:
            self._subscribers.append(callback)

    def set_mode(self, mode: JoystickMode, force: bool = False) -> Tuple[bool, str]:
        """
        Explicit, safe mode switching procedure.
        Prevents transitioning to REAL_HARDWARE if no physical hardware is plugged in,
        unless force=True (operator manual override or browser-attached hardware controller).
        """
        with self._lock:
            if mode == JoystickMode.REAL_HARDWARE:
                if not self.physical_service.is_hardware_connected() and not force:
                    msg = "Cannot switch to REAL_HARDWARE mode: No physical USB or Bluetooth joystick detected."
                    logger.warning(msg)
                    return False, msg
                self.active_mode = JoystickMode.REAL_HARDWARE
                device_name = (
                    self.physical_service.metadata[self.physical_service.active_device_index].name
                    if (self.physical_service.active_device_index is not None and 
                        self.physical_service.active_device_index in self.physical_service.metadata)
                    else "Physical Hardware Subsystem (Active)"
                )
                msg = f"Switched to REAL_HARDWARE mode ({device_name})."
                logger.info(msg)
                return True, msg
            else:
                self.active_mode = JoystickMode.VIRTUAL_SIMULATION
                msg = "Switched to VIRTUAL_SIMULATION mode. All events tagged as is_simulation=True."
                logger.info(msg)
                return True, msg

    def get_status(self) -> JoystickSystemStatus:
        """Returns the truthful system status of both modalities."""
        with self._lock:
            devices = self.physical_service.get_connected_devices()
            has_hw = len(devices) > 0
            primary_name = devices[0]["name"] if has_hw else None
            primary_id = devices[0]["device_id"] if has_hw else None

            if self.active_mode == JoystickMode.REAL_HARDWARE:
                conn_status = ConnectionStatus.CONNECTED if has_hw else ConnectionStatus.DISCONNECTED
            else:
                conn_status = ConnectionStatus.CONNECTED

            return JoystickSystemStatus(
                active_mode=self.active_mode,
                physical_hardware_detected=has_hw,
                connected_device_count=len(devices),
                primary_device_name=primary_name,
                primary_device_id=primary_id,
                connection_status=conn_status,
                calibration_status=CalibrationStatus.CALIBRATED if has_hw else CalibrationStatus.DEFAULT,
                last_event=self.last_event,
                error_message=self.physical_service.hardware_error,
            )

    def _on_physical_joystick_event(self, event: CommonJoystickEvent) -> None:
        """Internal handler for incoming physical joystick samples."""
        with self._lock:
            # If in VIRTUAL_SIMULATION mode, auto-engage REAL_HARDWARE upon active physical deflection
            if self.active_mode != JoystickMode.REAL_HARDWARE:
                if event.intensity >= 0.15:
                    self.active_mode = JoystickMode.REAL_HARDWARE
                    logger.info("Auto-engaged REAL_HARDWARE mode upon physical joystick deflection.")
                else:
                    return

            self.last_event = event
            self.last_event_time = event.timestamp

        self._dispatch_event(event)

    def ingest_hardware_input(
        self,
        raw_x: float,
        raw_y: float,
        buttons: Optional[List[bool]] = None,
        device_id: str = "USB-PHYSICAL-CONTROLLER",
        client_timestamp: Optional[float] = None
    ) -> CommonJoystickEvent:
        """
        Ingests a hardware joystick frame (from USB, Bluetooth, or Browser Gamepad API).
        Applies radial deadzone, direction classification, and builds a CommonJoystickEvent
        with is_simulation=False and source=JoystickSource.PHYSICAL_JOYSTICK.
        """
        # Apply radial deadzone filtering
        norm_x, norm_y, intensity = apply_radial_deadzone(raw_x, raw_y, deadzone=self.radial_deadzone)

        # Classify direction
        direction, _ = classify_joystick_vector(
            norm_x,
            norm_y,
            connection_status=ConnectionStatus.CONNECTED,
            data_validity=DataValidity.VALID,
            center_deadzone=self.radial_deadzone
        )

        now_ms = time.time() * 1000.0
        ts = client_timestamp if (client_timestamp and client_timestamp > 1700000000000.0) else now_ms

        event = CommonJoystickEvent(
            source=JoystickSource.PHYSICAL_HARDWARE,
            is_simulation=False,
            device_id=device_id,
            timestamp=ts,
            axis_x=norm_x,
            axis_y=norm_y,
            direction=direction,
            intensity=intensity,
            buttons=buttons or [],
            connection_status=ConnectionStatus.CONNECTED,
            calibration_status=CalibrationStatus.CALIBRATED,
            data_validity=DataValidity.VALID,
        )

        with self._lock:
            self.last_event = event
            self.last_event_time = now_ms

        self._dispatch_event(event)
        return event

    def ingest_virtual_input(
        self,
        raw_x: float,
        raw_y: float,
        buttons: Optional[List[bool]] = None,
        device_id: str = "VIRT-REACT-CANVAS",
        client_timestamp: Optional[float] = None
    ) -> CommonJoystickEvent:
        """
        Ingests a virtual joystick frame from the frontend canvas or keyboard.
        Applies radial deadzone, direction classification, and builds a CommonJoystickEvent.
        """
        with self._lock:
            # Block virtual inputs if in REAL_HARDWARE mode
            if self.active_mode != JoystickMode.VIRTUAL_SIMULATION:
                raise ValueError("Cannot ingest virtual inputs while REAL_HARDWARE mode is active.")

        # Apply radial deadzone filtering
        norm_x, norm_y, intensity = apply_radial_deadzone(raw_x, raw_y, deadzone=self.radial_deadzone)

        # Classify direction
        direction, _ = classify_joystick_vector(
            norm_x,
            norm_y,
            connection_status=ConnectionStatus.CONNECTED,
            data_validity=DataValidity.VALID,
            center_deadzone=self.radial_deadzone
        )

        now_ms = time.time() * 1000.0
        ts = client_timestamp if (client_timestamp and client_timestamp > 1700000000000.0) else now_ms

        # Rule: Virtual joystick events are ALWAYS marked is_simulation=True
        event = CommonJoystickEvent(
            source=JoystickSource.VIRTUAL_SIMULATION,
            is_simulation=True,
            device_id=device_id,
            timestamp=ts,
            axis_x=norm_x,
            axis_y=norm_y,
            direction=direction,
            intensity=intensity,
            buttons=buttons or [],
            connection_status=ConnectionStatus.CONNECTED,
            calibration_status=CalibrationStatus.DEFAULT,
            data_validity=DataValidity.VALID,
        )

        with self._lock:
            self.last_event = event
            self.last_event_time = now_ms

        self._dispatch_event(event)
        return event

    def _dispatch_event(self, event: CommonJoystickEvent) -> None:
        """Dispatches event to all subscribers."""
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"Error in actuator subscriber: {e}")


# Global singleton actuator manager instance
actuator_manager = ActuatorManager()

