# DCRG Phase 9 – Operational Demonstration Workflow & Script

This document details the exact, step-by-step operational script for presenting the DCRG (Dynamic Command Reliability Graph) verification system.

---

## Preparation & System Startup

### Step 1: Launch FastAPI Backend Server
In PowerShell Terminal 1:
```powershell
Set-Location "DCRG Project\backend"
.\.venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Verify that the API boots at `http://127.0.0.1:8000` and Swagger documentation is live at `/docs`.*

### Step 2: Launch Vite React Frontend
In PowerShell Terminal 2:
```powershell
Set-Location "DCRG Project\frontend"
npm.cmd run dev
```
*Verify that the frontend Vite development server launches at `http://localhost:5173`.*

### Step 3: Open the DCRG Dashboard
Open Google Chrome or Microsoft Edge and navigate to:
```
http://localhost:5173
```
Confirm the header shows:
- System Status: `ONLINE` (Green glowing dot)
- Mode Badge: `SIMULATION` (Amber badge)
- Active Operator: `OPERATOR_01`
- Red E-STOP actuator button is accessible.

---

## Live Demonstration Sequence

### Step 4: System Health Diagnostics Inspection
- Click on the **System Health** tab.
- Walk the audience through the active probe table:
  - *Backend Core*: Status `HEALTHY`, ping $< 5\text{ ms}$.
  - *Frontend Web*: Status `HEALTHY`, WebSocket stream active.
  - *Voice Engine*: Status `HEALTHY`, Microphone device index 1 detected.
  - *Database Engine*: Status `HEALTHY`, SQLite WAL active.
  - *Safety Gateway & Simulator*: Status `HEALTHY`.
- Point out that no subsystems are reporting masked or false healthy states.

### Step 5: Input Device Verification
- Navigate to the **Multi-Modal Monitors** tab.
- **Microphone**: Verify status shows `Microphone Array (Realtek(R) Audio)` is connected and ready.
- **Joystick**: Observe that in the absence of physical USB hardware, the dashboard indicates `NO USB/BT ATTACHED` and provides the hardware troubleshooting guide while the Virtual Joystick Canvas and Browser Gamepad API stand ready.

### Step 6: Interactive Simulation Setup
- Click on the **Robot Simulation** tab.
- Note the initial pose: $(X=0.0\text{ m}, Y=0.0\text{ m}, \text{Heading}=0.0^\circ)$.
- Note the static pylon obstacles: *Barrier Alpha*, *Pylon Beta*, and *Cylinder Gamma*.

---

### Step 7–13: Demonstrate Multi-Modal Agreement (GREEN Authorization)
1. Switch to the **Command Center** tab.
2. In the virtual joystick or on the virtual canvas, drag the control **LEFT** ($X \approx -0.85$).
3. Concurrently speak clearly into the microphone:
   > *"MOVE LEFT"*
4. **Show Live Telemetry**:
   - **Voice Monitor**: Live transcript displays `"MOVE LEFT"`, recognized command is `LEFT`, Whisper confidence $> 0.90$.
   - **Joystick Monitor**: $X$-axis registers negative deflection, direction is classified as `LEFT`, intensity $> 80\%$.
   - **Synchronization Monitor**: Temporal alignment badge displays `SYNCHRONIZED` with $\Delta t \le 50\text{ ms}$.
   - **Fusion & CRS**: Angular difference $\Delta\theta = 0^\circ$, Motor agreement $A_m \approx 1.0$, Composite CRS gauge reaches $> 90.0$.
   - **Safety Authorization**: Evaluated as `GREEN`, Decision: `AUTHORIZED`, permitted command `LEFT`.
   - **Robot Simulation**: The vehicle smoothly turns towards $270^\circ$ and translates along the negative $X$-axis.

---

### Step 14–15: Demonstrate Contradiction Veto (RED Rejection)
1. In the joystick canvas, deflect the stick firmly **RIGHT** ($X \approx +0.85$).
2. Concurrently speak:
   > *"MOVE LEFT"*
3. **Show Live Telemetry**:
   - The Speech intention ($180^\circ$ vector) directly opposes manual control ($0^\circ$ vector), generating an angular delta $\Delta\theta = 180^\circ$.
   - **Contradiction Veto**: The red contradiction badge flashes. The CRS is capped at $\le 30.0$.
   - **Safety Authorization**: State shifts to `RED`, Decision: `REJECTED`, reason: `"Severe motor contradiction detected: Voice LEFT opposes Joystick RIGHT"`.
   - **Robot Simulation**: The robot vehicle **remains completely stationary**, refusing to execute motion.

---

### Step 16: Demonstrate YELLOW State & Human Confirmation Workflow
1. Move the joystick **FORWARD** ($Y \approx +0.80$) with the microphone muted (or speak in a low, muffled voice with confidence $< 0.60$).
2. **Show Live Telemetry**:
   - Evidence completeness factor drops ($E_c \approx 0.50$ due to missing/degraded voice modality).
   - CRS settles into the provisional band ($50.0 \le \text{CRS} < 85.0$).
   - **Safety Authorization**: State displays `YELLOW`, Decision: `HOLD_PENDING_CONFIRMATION`.
   - The robot remains held and stationary.
3. On the dashboard, click the amber **CONFIRM COMMAND** button.
4. The backend verifies the cryptographic decision ID, elevates authorization to `GREEN`, and dispatches forward motion to the simulator.

---

### Step 17: Demonstrate STOP Command Priority
1. With the robot in motion, speak firmly:
   > *"STOP"*
2. Regardless of any residual stick drift, the voice `STOP` command is assigned highest priority.
3. The fusion engine computes an immediate stop agreement, and the simulator decelerates the robot vehicle to $0.0\text{ m/s}$.

---

### Step 18: Demonstrate Global Emergency Stop (E-STOP)
1. Trigger the red **E-STOP** actuator button at the top right of the dashboard.
2. Observe instantaneous reaction:
   - System state locks into `EMERGENCY`.
   - All vehicle linear and angular velocities clamp to $0.0\text{ m/s}$ in $8.3\ \mu\text{s}$.
   - All subsequent voice and joystick inputs are completely ignored and locked out.
3. Click **Reset Emergency**, input the security PIN `1234`, and observe the system transition back to monitored standby.

---

### Step 19: Forensic Audit Log Inspection
1. Navigate to the **Audit Logs** tab.
2. Review the chronological trail in the SQLite forensic table:
   - Voice transcript events.
   - Joystick deflection frames.
   - Synchronization pairings with timestamps.
   - CRS calculations and contradiction vetoes.
   - E-Stop activation and reset entries.
3. Click **Export CSV** and **Export JSON** to demonstrate forensic reporting capabilities.

