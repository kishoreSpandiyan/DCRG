# DCRG Phase 7 – Robot Kinematic Simulation Architecture

## 1. Overview & Objective

Phase 7 introduces the **Interactive 2D Robot Simulation Engine** within the Dynamic Command Reliability Graph (DCRG) architecture. The simulation engine acts as the authoritative kinematic testbed, executing verified commands originating from the Phase 6 Tiered Safety Authorization Engine.

In strict compliance with **DCRG Safety Directives**, this system operates **exclusively in software simulation**. Under no circumstances does the simulator actuate physical servos, motors, drones, or robotics hardware.

---

## 2. Environment Coordinates & World Boundaries

The simulation takes place on a standardized continuous 2D Cartesian plane:
- **X Domain:** $[-50.0, +50.0]$ meters (West to East)
- **Y Domain:** $[-50.0, +50.0]$ meters (South to North)
- **Origin $(0.0, 0.0)$:** Neutral coordinate center / default spawn origin.
- **Robot Envelope Radius ($r$):** $1.0\text{ m}$.
- **Safe Working Extents:**
  $$\text{Effective } X \in [-49.0, +49.0]\text{ m},\quad \text{Effective } Y \in [-49.0, +49.0]\text{ m}$$

When the robot envelope contacts any environment boundary:
1. Displacement is clamped strictly to the safe boundary wall ($X = \pm 49.0$ or $Y = \pm 49.0$).
2. Linear velocity is immediately arrested to $0.0\text{ m/s}$.
3. `boundary_hit` diagnostic flag is asserted.
4. Active motion primitive is reset to `STOP`.

---

## 3. Static Environment Obstacles

To validate collision avoidance and safety interlocks, three static obstacles are permanently registered in the world:

| Obstacle ID | Center Coordinates $(X, Y)$ | Collision Radius | Description |
| :--- | :---: | :---: | :--- |
| `obs-alpha` | $(+15.0\text{ m}, +15.0\text{ m})$ | $3.5\text{ m}$ | High-density reinforced barrier |
| `obs-beta` | $(-20.0\text{ m}, +12.0\text{ m})$ | $4.0\text{ m}$ | Cylindrical security pylon |
| `obs-gamma` | $(0.0\text{ m}, -25.0\text{ m})$ | $3.0\text{ m}$ | Static environmental cylinder |

### Collision Detection & Normal Push-Back Algorithm

For each obstacle with center $(x_{obs}, y_{obs})$ and radius $r_{obs}$:
$$d = \sqrt{(x - x_{obs})^2 + (y - y_{obs})^2}$$
$$\text{Safety Distance Limit: } d_{safe} = r_{robot} + r_{obs}$$

If $d \le d_{safe}$:
1. `is_collision` is asserted `True`.
2. `collision_object` is set to the obstacle ID.
3. Linear speed is zeroed: $v = 0.0\text{ m/s}$.
4. The active command transitions to `STOP`.
5. The robot is pushed back along the normal collision vector:
   $$\vec{u} = \frac{(x - x_{obs}, y - y_{obs})}{d},\quad \text{Overlap: } \delta = d_{safe} - d$$
   $$\vec{P}_{corrected} = \vec{P} + \delta \cdot \vec{u}$$

---

## 4. Kinematics & Smooth Angular Alignment

Unlike discrete grid jump models, the DCRG robot simulation features smooth, continuous differential updates:

### Heading Alignment ($\theta$)
Each cardinal primitive corresponds to a target world heading:
- **`FORWARD`**: $0.0^\circ$ (North / $+Y$)
- **`RIGHT`**: $90.0^\circ$ (East / $+X$)
- **`BACKWARD`**: $180.0^\circ$ (South / $-Y$)
- **`LEFT`**: $270.0^\circ$ (West / $-X$)
- **`STOP`**: Heading remains unchanged.

The shortest angular difference across the $0^\circ / 360^\circ$ wrap-around is calculated:
$$\Delta\theta = ((\theta_{target} - \theta + 180^\circ) \pmod{360^\circ}) - 180^\circ$$
$$\theta_{next} = \theta + \text{clamp}\left(\Delta\theta, -\omega_{max} \cdot \Delta t, +\omega_{max} \cdot \Delta t\right)$$
where $\omega_{max} = 120.0^\circ/\text{s}$ (configurable).

### Linear Translation & Acceleration Ramping
- Base velocity: $v_{base} = 3.0\text{ m/s}$.
- Acceleration/Deceleration ramp rate: $8.0\text{ m/s}^2$.
- Displacement per tick $\Delta t$:
  $$\Delta s = v \cdot \Delta t$$

---

## 5. Telemetry & Trajectory Trail

- **Physics Update Rate:** 20 Hz ($\Delta t = 50\text{ ms}$).
- **Trajectory Trail:** Circular breadcrumb buffer capturing position updates every $0.5\text{ m}$ of displacement up to 100 historical points.
- **Telemetry Sync:** Broadcast over dedicated WebSocket (`/ws/simulation/stream`) at 20 Hz to synchronize the UI HTML5 Canvas visualizer.

