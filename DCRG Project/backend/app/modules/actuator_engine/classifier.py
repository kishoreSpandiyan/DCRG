"""
Direction Classification and Intensity Calculation for Joystick Vectors.
"""

import math
from typing import Tuple
from app.modules.actuator_engine.schemas import (
    JoystickDirection,
    ConnectionStatus,
    DataValidity,
)


def classify_joystick_vector(
    x: float,
    y: float,
    connection_status: ConnectionStatus = ConnectionStatus.CONNECTED,
    data_validity: DataValidity = DataValidity.VALID,
    center_deadzone: float = 0.08,
) -> Tuple[JoystickDirection, float]:
    """
    Classifies a 2D joystick coordinate into polar direction and scalar intensity.
    
    Coordinate convention:
    - axis_x: -1.0 = Left, +1.0 = Right
    - axis_y: -1.0 = Backward, +1.0 = Forward
    
    Returns:
        (JoystickDirection, intensity)
    """
    intensity = min(1.0, max(0.0, math.sqrt(x * x + y * y)))

    # Guard: Disconnected or corrupted joystick MUST NEVER be classified as CENTER
    if connection_status == ConnectionStatus.DISCONNECTED or data_validity != DataValidity.VALID:
        return JoystickDirection.UNKNOWN, round(intensity, 4)

    # Center check
    if intensity <= center_deadzone:
        return JoystickDirection.CENTER, 0.0

    # Calculate angle in degrees:
    # 0 deg = +X (Right)
    # 90 deg = +Y (Forward)
    # 180 deg = -X (Left)
    # 270 deg = -Y (Backward)
    angle_rad = math.atan2(y, x)
    angle_deg = math.degrees(angle_rad)
    if angle_deg < 0:
        angle_deg += 360.0

    # 8-Sector Direction Classification (45 deg sectors centered on axes/diagonals)
    # Right: [337.5, 360) or [0, 22.5)
    # Forward-Right: [22.5, 67.5)
    # Forward: [67.5, 112.5)
    # Forward-Left: [112.5, 157.5)
    # Left: [157.5, 202.5)
    # Backward-Left: [202.5, 247.5)
    # Backward: [247.5, 292.5)
    # Backward-Right: [292.5, 337.5)

    if 67.5 <= angle_deg < 112.5:
        direction = JoystickDirection.FORWARD
    elif 112.5 <= angle_deg < 157.5:
        direction = JoystickDirection.FORWARD_LEFT
    elif 157.5 <= angle_deg < 202.5:
        direction = JoystickDirection.LEFT
    elif 202.5 <= angle_deg < 247.5:
        direction = JoystickDirection.BACKWARD_LEFT
    elif 247.5 <= angle_deg < 292.5:
        direction = JoystickDirection.BACKWARD
    elif 292.5 <= angle_deg < 337.5:
        direction = JoystickDirection.BACKWARD_RIGHT
    elif 22.5 <= angle_deg < 67.5:
        direction = JoystickDirection.FORWARD_RIGHT
    else:
        direction = JoystickDirection.RIGHT

    return direction, round(intensity, 4)

