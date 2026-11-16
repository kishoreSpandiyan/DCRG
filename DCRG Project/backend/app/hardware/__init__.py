"""
Hardware Integration Package.
Interfaces directly with physical input controllers and serial/CAN motor layers.
"""

from app.hardware.joystick_service import PhysicalJoystickService, DeviceMetadata

__all__ = ["PhysicalJoystickService", "DeviceMetadata"]
