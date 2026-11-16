# DCRG Testing Strategy

## 1. Scope
The testing strategy enforces multi-tier validation across Python backend services, WebSocket communications, and the React frontend.

## 2. Test Tiers
- **Unit Testing**: Pytest for backend logic, schemas, fusion math, and input filters. Oxlint/TypeScript compilation checks for frontend.
- **Contract & API Testing**: FastAPI `TestClient` and HTTPX asynchronous testing for REST endpoints.
- **Stream & WebSocket Testing**: Emulated timestamped packet streams to test pipeline synchronization under jitter and packet loss.
- **Fail-Safe & Edge Case Testing**:
  - Missing voice packets during joystick motion.
  - Joystick disconnected mid-command.
  - Conflicting commands (e.g., vocal "STOP" while joystick pushed forward).
  - High stress prosody with ambiguous direction commands.
  - Immediate E-STOP assertion during maximum velocity authorization.

## 3. Test Rules
- No fabrication of mock hardware responses that mask genuine disconnection errors.
- Real tests only; simulated data must be explicitly labeled.

