# Hardware Joystick Specifications

## Supported Devices
- Standard USB HID Joysticks / Gamepads (Logitech Extreme 3D Pro, Xbox Controller, DualShock/DualSense via USB)
- Bluetooth HID Gamepads supported under Windows DirectInput / XInput
- Browser Gamepad API compliant controllers

## Integration Architecture
- Backend: Integrated via `pygame.joystick` (via `pygame-ce`) in `backend/app/hardware/`
- Frontend: Web Gamepad API polling in `frontend/src/hooks/useGamepad.ts`
- Calibration: Deadzone thresholding (default 0.08), min/max axis scaling \([-1.0, +1.0]\)

