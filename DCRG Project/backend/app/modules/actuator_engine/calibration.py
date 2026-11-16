"""
Joystick Calibration, Axis Inversion, and Deadzone Filtering.
Applies mathematical conditioning to raw physical and virtual inputs.
"""

import json
import math
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


class JoystickProfile:
    def __init__(self, data: Dict[str, Any]):
        self.profile_name: str = data.get("profile_name", "Generic Joystick")
        self.vendor_id: str = data.get("vendor_id", "default")
        self.product_id: str = data.get("product_id", "default")
        self.axis_mapping: Dict[str, Dict[str, Any]] = data.get("axis_mapping", {})
        self.button_mapping: Dict[str, int] = data.get("button_mapping", {})
        self.hat_mapping: Dict[str, int] = data.get("hat_mapping", {})
        self.radial_deadzone: float = float(data.get("radial_deadzone", 0.08))

    @classmethod
    def from_file(cls, path: Path) -> "JoystickProfile":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)


def apply_radial_deadzone(x: float, y: float, deadzone: float = 0.08) -> Tuple[float, float, float]:
    """
    Applies radial (circular) deadzone filtering to 2D joystick coordinates.
    Returns: (filtered_x, filtered_y, intensity)
    """
    radius = math.sqrt(x * x + y * y)
    if radius <= deadzone:
        return 0.0, 0.0, 0.0

    # Smooth re-scaling from deadzone boundary to outer limit 1.0
    scaled_mag = (radius - deadzone) / (1.0 - deadzone)
    scaled_mag = min(1.0, max(0.0, scaled_mag))
    
    scale = scaled_mag / radius
    filt_x = round(x * scale, 4)
    filt_y = round(y * scale, 4)
    intensity = round(scaled_mag, 4)

    return filt_x, filt_y, intensity


def calibrate_axis(
    raw_val: float,
    inverted: bool = False,
    deadzone: float = 0.0,
    center: float = 0.0,
    axis_min: float = -1.0,
    axis_max: float = 1.0,
    sensitivity: float = 1.0
) -> float:
    """
    Calibrates a single joystick axis against min/max limits, center offset, and inversion.
    """
    # 1. Apply inversion
    val = -raw_val if inverted else raw_val

    # 2. Subtract center offset
    val = val - center

    # 3. Apply axis-specific deadzone
    if abs(val) <= deadzone:
        return 0.0

    # 4. Normalize by positive or negative range
    if val > 0:
        span = axis_max - center
        norm = (val - deadzone) / (span - deadzone) if span > deadzone else 0.0
    else:
        span = abs(axis_min - center)
        norm = (val + deadzone) / (span - deadzone) if span > deadzone else 0.0

    # 5. Apply sensitivity and clamp
    norm = norm * sensitivity
    norm = max(-1.0, min(1.0, norm))
    return round(norm, 4)


class JoystickProfileRegistry:
    """Registry maintaining loaded hardware configurations from config/joysticks/."""
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default to project root / config / joysticks
            config_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "config" / "joysticks"
        self.config_dir = config_dir
        self.profiles: Dict[str, JoystickProfile] = {}
        self.load_profiles()

    def load_profiles(self) -> None:
        if not self.config_dir.exists():
            return
        for file in self.config_dir.glob("*.json"):
            try:
                prof = JoystickProfile.from_file(file)
                self.profiles[prof.profile_name.lower()] = prof
                if prof.vendor_id != "default":
                    self.profiles[f"{prof.vendor_id}:{prof.product_id}".lower()] = prof
            except Exception:
                continue

    def get_profile_for_device(self, device_name: str, vid: Optional[str] = None, pid: Optional[str] = None) -> JoystickProfile:
        name_key = device_name.lower()
        if "xbox" in name_key:
            for k, prof in self.profiles.items():
                if "xbox" in k:
                    return prof
        if "logitech" in name_key:
            for k, prof in self.profiles.items():
                if "logitech" in k:
                    return prof
        for k, prof in self.profiles.items():
            if k in name_key or name_key in k:
                return prof
        if vid and pid:
            hw_key = f"{vid}:{pid}".lower()
            if hw_key in self.profiles:
                return self.profiles[hw_key]
        return next(
            (p for k, p in self.profiles.items() if "generic" in k or "default" in k),
            JoystickProfile({
                "profile_name": "Fallback Default",
                "axis_mapping": {
                    "x": {"index": 0, "inverted": False, "deadzone": 0.08},
                    "y": {"index": 1, "inverted": True, "deadzone": 0.08}
                },
                "radial_deadzone": 0.08
            })
        )

