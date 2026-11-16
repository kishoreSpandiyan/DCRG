# DCRG Development Guidelines

## 1. Coding Standards
- **Python**: PEP 8 compliance, mandatory type annotations (`typing`), docstrings on all modules/classes/functions, Pydantic for data validation.
- **Frontend**: TypeScript strict mode, functional React components with hooks, Tailwind CSS utility classes, Lucide icons.
- **Error Handling**: Graceful degradation; never let unhandled exceptions crash the telemetry loops or WebSocket connections.

## 2. Hardware and Simulation Separation
- Physical hardware code lives in `backend/app/hardware/` and `hardware/`.
- Simulation code lives in `backend/app/simulation/` and `frontend/src/simulation/`.
- Telemetry schemas MUST contain an `is_simulation: bool` flag.
- Physical hardware cannot be commanded from the frontend directly. All commands route through `backend/app/modules/safety_engine`.

## 3. Prototype Disclaimer
- This project is a university/research prototype demonstrating AI + IoT multi-modal verification concepts.
- It is NOT certified under ISO 13849, IEC 61508, or any industrial functional safety standard. Do not deploy to hazardous machinery.

