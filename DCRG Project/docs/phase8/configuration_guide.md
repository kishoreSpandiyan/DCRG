# DCRG Phase 8 – System Configuration & Runtime Tuning Guide

## 1. Overview & Dynamic Configuration Architecture

The DCRG Runtime Configuration subsystem (`SystemConfigManager`) manages system-wide operational parameters. All parameters are dynamically inspectable, runtime-tunable, strictly validated, and persistently audited.

Configuration changes are performed via `/api/v1/system/config`. Every change is validated against mathematical invariants, persisted to the `config_audit` database table in SQLite, and applied immediately across running managers (`voice_manager`, `actuator_manager`, `sync_manager`, `fusion_manager`, `safety_manager`, and `simulation_manager`).

---

## 2. Configuration Parameter Catalog

| Category | Parameter Name | Type | Default | Allowed Range | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sync** | `sync_window_ms` | `float` | `150.0` | `50.0` – `500.0` ms | Maximum sliding temporal correlation window between voice and joystick events. |
| **Joystick** | `joystick_deadzone` | `float` | `0.10` | `0.0` – `0.50` | Center deadzone radius; deflections below this threshold are mapped to `0.0`. |
| **Voice** | `voice_confidence_threshold` | `float` | `0.60` | `0.10` – `0.99` | Minimum Whisper recognition confidence required to treat speech input as valid. |
| **CRS Weights** | `weight_semantic` ($W_s$) | `float` | `0.30` | `0.0` – `1.0` | Relative weight of speech acoustic and intent reliability in CRS. |
| **CRS Weights** | `weight_motor` ($W_m$) | `float` | `0.40` | `0.0` – `1.0` | Relative weight of vector directional agreement in CRS. |
| **CRS Weights** | `weight_context` ($W_c$) | `float` | `0.15` | `0.0` – `1.0` | Relative weight of mission context and obstacle proximity in CRS. |
| **CRS Weights** | `weight_completeness` ($W_e$) | `float` | `0.15` | `0.0` – `1.0` | Relative weight of multi-modal completeness factor in CRS. |
| **Safety** | `safety_green_min_crs` | `float` | `85.0` | `50.0` – `99.0` | Minimum CRS threshold required for immediate `GREEN` autonomous dispatch. |
| **Safety** | `safety_yellow_min_crs`| `float` | `50.0` | `20.0` – `84.0` | Minimum CRS threshold required for `YELLOW` (operator confirmation) state. |
| **Simulation** | `simulation_speed_scale`| `float` | `1.0` | `0.1` – `5.0` | Movement speed multiplier for the kinematic 2D vehicle simulation. |
| **Simulation** | `collision_margin_m` | `float` | `1.5` | `0.5` – `10.0` m | Safety standoff distance around obstacles for proactive collision stoppage. |
| **Flags** | `allow_single_modality`| `bool` | `True` | `True` / `False` | [Experimental] If True, permits degraded single-modality commands via `YELLOW` review. |
| **Flags** | `enable_stress_penalty` | `bool` | `True` | `True` / `False` | Enables acoustic prosody stress attenuation on speech confidence. |

---

## 3. Strict Validation Invariants

Any configuration update payload submitted to `/api/v1/system/config` must satisfy strict system validation rules. If any check fails, the transaction is rejected with an HTTP 400 error and the current configuration remains untouched:

### 3.1 CRS Weights Sum Invariant
The four CRS component weights must sum to exactly $1.00$ within a floating-point tolerance of $\pm 0.005$:
$$| (W_s + W_m + W_c + W_e) - 1.00 | \le 0.005$$
*Failure Rejection Reason*: `CRS weights must sum to 1.00 (got X.XX)`.

### 3.2 Safety Threshold Hierarchy Invariant
The `YELLOW` minimum CRS threshold must always be strictly less than the `GREEN` minimum CRS threshold:
$$\text{safety\_yellow\_min\_crs} < \text{safety\_green\_min\_crs}$$
*Failure Rejection Reason*: `Yellow safety threshold must be strictly lower than Green threshold`.

### 3.3 Domain Boundary Checks
- `sync_window_ms`: $50.0 \le W_{\text{sync}} \le 500.0$
- `joystick_deadzone`: $0.0 \le \text{deadzone} \le 0.50$
- `voice_confidence_threshold`: $0.10 \le \theta_{\text{voice}} \le 0.99$
- `simulation_speed_scale`: $0.1 \le v_{\text{scale}} \le 5.0$
- `collision_margin_m`: $0.5 \le d_{\text{margin}} \le 10.0$

---

## 4. Resetting to Defaults

Operators can restore factory default configurations at any time:
- **API**: `POST /api/v1/system/config/reset`
- **Dashboard UI**: Click the **Reset Defaults** button in the Configuration Panel header.
- **Audit Impact**: The reset action generates an audit entry in `config_audit` recording the identity of the operator and the timestamp.

---

## 5. Configuration Audit Trail

All parameter updates are captured in the SQLite `config_audit` table:

```sql
CREATE TABLE config_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    parameter_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    updated_by TEXT NOT NULL
);
```

Whenever a setting is modified, the previous value, new value, mutating operator (`OPERATOR_01` or authenticated user), and microsecond-precision timestamp are committed to the forensic log.

