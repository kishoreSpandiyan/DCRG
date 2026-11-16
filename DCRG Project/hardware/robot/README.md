# Robot Hardware Specifications

## Target Hardware Interfaces
- Serial UART / USB-to-TTL (Baud: 115200)
- CAN Bus (SocketCAN or USB-CAN adapter) where applicable
- Differential drive or 4-wheel omnidirectional mobile base

## Safety Interlocks
- Hardware Heartbeat: 20Hz watchdog ping required; missing heartbeat triggers hardware brake within 100ms.
- Physical E-STOP: NC (normally-closed) relay cut to motor driver power stage.
- Phase Roadmap: Hardware integration unlocks in Phase 9 following simulation sign-off.

