"""
Pytest Suite for DCRG Actuator Engine (Phase 2).
Tests:
- Axis normalization and inversion
- Radial deadzone filtering
- Direction classification (Cardinals, Diagonals, Center, Unknown)
- Intensity calculation
- CommonJoystickEvent validation rules & rejection of invalid/stale data
- Strict Real vs Simulation separation
- Device disconnection safety guardrails
"""

import time
import pytest
from pydantic import ValidationError

from app.modules.actuator_engine.schemas import (
    CommonJoystickEvent,
    JoystickDirection,
    JoystickSource,
    ConnectionStatus,
    CalibrationStatus,
    DataValidity,
    JoystickMode,
)
from app.modules.actuator_engine.calibration import (
    apply_radial_deadzone,
    calibrate_axis,
    JoystickProfile,
    JoystickProfileRegistry,
)
from app.modules.actuator_engine.classifier import classify_joystick_vector
from app.modules.actuator_engine.manager import ActuatorManager


# ==============================================================================
# 1. Calibration and Deadzone Tests
# ==============================================================================

def test_axis_inversion():
    """Verify that inverted axes flip their sign cleanly."""
    raw_forward = 0.8
    calibrated = calibrate_axis(raw_forward, inverted=True)
    assert calibrated == -0.8

    calibrated_normal = calibrate_axis(raw_forward, inverted=False)
    assert calibrated_normal == 0.8


def test_axis_deadzone():
    """Verify that small deflections within axis deadzone clamp to 0.0."""
    calibrated = calibrate_axis(0.04, deadzone=0.08)
    assert calibrated == 0.0

    # Outside deadzone
    calibrated_active = calibrate_axis(0.5, deadzone=0.08)
    assert calibrated_active > 0.0


def test_radial_deadzone_filtering():
    """Verify radial deadzone zeroes out small 2D deflections and scales smoothly."""
    # Inside radial deadzone of 0.08
    fx, fy, intensity = apply_radial_deadzone(0.03, 0.04, deadzone=0.08)  # r = 0.05
    assert fx == 0.0
    assert fy == 0.0
    assert intensity == 0.0

    # Outside radial deadzone
    fx, fy, intensity = apply_radial_deadzone(0.6, 0.8, deadzone=0.08)  # r = 1.0
    assert intensity == 1.0
    assert fx == 0.6
    assert fy == 0.8


# ==============================================================================
# 2. Direction and Intensity Classification Tests
# ==============================================================================

def test_direction_cardinals():
    """Verify cardinal direction classification."""
    # Forward (+Y)
    dir_fwd, int_fwd = classify_joystick_vector(0.0, 0.9)
    assert dir_fwd == JoystickDirection.FORWARD
    assert int_fwd == 0.9

    # Backward (-Y)
    dir_bwd, int_bwd = classify_joystick_vector(0.0, -0.9)
    assert dir_bwd == JoystickDirection.BACKWARD
    assert int_bwd == 0.9

    # Right (+X)
    dir_rgt, int_rgt = classify_joystick_vector(0.85, 0.0)
    assert dir_rgt == JoystickDirection.RIGHT
    assert int_rgt == 0.85

    # Left (-X)
    dir_lft, int_lft = classify_joystick_vector(-0.85, 0.0)
    assert dir_lft == JoystickDirection.LEFT
    assert int_lft == 0.85


def test_direction_diagonals():
    """Verify diagonal direction classification."""
    # Forward-Right (+X, +Y)
    dir_fr, _ = classify_joystick_vector(0.707, 0.707)
    assert dir_fr == JoystickDirection.FORWARD_RIGHT

    # Forward-Left (-X, +Y)
    dir_fl, _ = classify_joystick_vector(-0.707, 0.707)
    assert dir_fl == JoystickDirection.FORWARD_LEFT

    # Backward-Right (+X, -Y)
    dir_br, _ = classify_joystick_vector(0.707, -0.707)
    assert dir_br == JoystickDirection.BACKWARD_RIGHT

    # Backward-Left (-X, -Y)
    dir_bl, _ = classify_joystick_vector(-0.707, -0.707)
    assert dir_bl == JoystickDirection.BACKWARD_LEFT


def test_center_and_deadzone_classification():
    """Verify that zero/sub-deadzone input is CENTER when connected and valid."""
    dir_ctr, intensity = classify_joystick_vector(0.02, 0.02, center_deadzone=0.08)
    assert dir_ctr == JoystickDirection.CENTER
    assert intensity == 0.0


def test_disconnected_joystick_never_center():
    """Rule: Do not classify an invalid or disconnected joystick as CENTER."""
    dir_disc, _ = classify_joystick_vector(
        0.0, 0.0, connection_status=ConnectionStatus.DISCONNECTED
    )
    assert dir_disc == JoystickDirection.UNKNOWN
    assert dir_disc != JoystickDirection.CENTER

    dir_corrupt, _ = classify_joystick_vector(
        0.0, 0.0, data_validity=DataValidity.CORRUPTED
    )
    assert dir_corrupt == JoystickDirection.UNKNOWN


# ==============================================================================
# 3. CommonJoystickEvent Schema Validation Tests
# ==============================================================================

def test_valid_virtual_joystick_event():
    """Verify clean instantiation of a virtual simulation joystick event."""
    event = CommonJoystickEvent(
        source=JoystickSource.VIRTUAL_SIMULATION,
        is_simulation=True,
        device_id="VIRT-CANVAS-01",
        axis_x=0.0,
        axis_y=0.85,
        direction=JoystickDirection.FORWARD,
        intensity=0.85,
        buttons=[False, True],
    )
    assert event.is_simulation is True
    assert event.source == JoystickSource.VIRTUAL_SIMULATION
    assert event.intensity == 0.85


def test_valid_physical_joystick_event():
    """Verify clean instantiation of a physical hardware joystick event."""
    event = CommonJoystickEvent(
        source=JoystickSource.PHYSICAL_HARDWARE,
        is_simulation=False,
        device_id="USB-Logitech-0",
        axis_x=-0.75,
        axis_y=0.0,
        direction=JoystickDirection.LEFT,
        intensity=0.75,
        buttons=[True, False, False],
    )
    assert event.is_simulation is False
    assert event.source == JoystickSource.PHYSICAL_HARDWARE


def test_rejection_of_simulation_confusion():
    """Rule: Never label simulated input as physical hardware or vice-versa."""
    # Virtual source with is_simulation=False MUST FAIL
    with pytest.raises(ValidationError):
        CommonJoystickEvent(
            source=JoystickSource.VIRTUAL_SIMULATION,
            is_simulation=False,  # Contradiction!
            device_id="FAKE-DEVICE",
            axis_x=0.0,
            axis_y=0.5,
            direction=JoystickDirection.FORWARD,
            intensity=0.5,
        )

    # Physical source with is_simulation=True MUST FAIL
    with pytest.raises(ValidationError):
        CommonJoystickEvent(
            source=JoystickSource.PHYSICAL_HARDWARE,
            is_simulation=True,  # Contradiction!
            device_id="USB-DEVICE",
            axis_x=0.0,
            axis_y=0.5,
            direction=JoystickDirection.FORWARD,
            intensity=0.5,
        )


def test_rejection_of_out_of_range_axes():
    """Verify rejection of axis values exceeding [-1.0, +1.0]."""
    with pytest.raises(ValidationError):
        CommonJoystickEvent(
            source=JoystickSource.VIRTUAL_SIMULATION,
            is_simulation=True,
            device_id="VIRT-01",
            axis_x=1.45,  # Out of range
            axis_y=0.0,
            direction=JoystickDirection.RIGHT,
            intensity=1.0,
        )


def test_rejection_of_invalid_timestamp():
    """Verify rejection of stale or corrupted timestamps (e.g., year 1970)."""
    with pytest.raises(ValidationError):
        CommonJoystickEvent(
            source=JoystickSource.VIRTUAL_SIMULATION,
            is_simulation=True,
            device_id="VIRT-01",
            timestamp=1000.0,  # Corrupted Unix epoch from 1970
            axis_x=0.0,
            axis_y=0.0,
            direction=JoystickDirection.CENTER,
            intensity=0.0,
        )


# ==============================================================================
# 4. ActuatorManager Mode Separation & Ingestion Tests
# ==============================================================================

def test_actuator_manager_mode_separation():
    """Verify that ActuatorManager blocks virtual input when in REAL_HARDWARE mode."""
    mgr = ActuatorManager()
    assert mgr.active_mode == JoystickMode.VIRTUAL_SIMULATION

    # Ingesting virtual in simulation mode works
    ev = mgr.ingest_virtual_input(0.0, 0.75)
    assert ev.is_simulation is True
    assert ev.direction == JoystickDirection.FORWARD

    # Switching to REAL_HARDWARE should fail if no hardware is connected
    success, msg = mgr.set_mode(JoystickMode.REAL_HARDWARE)
    assert success is False
    assert "No physical" in msg
    assert mgr.active_mode == JoystickMode.VIRTUAL_SIMULATION

