from __future__ import annotations

from keyrgb.core.power.policies.power_source_loop_policy import PowerSourceLoopInputs


def make_inputs(**overrides) -> PowerSourceLoopInputs:
    values = {
        "on_ac": True,
        "now": 0.0,
        "power_management_enabled": True,
        "current_brightness": 50,
        "is_off": False,
        "active_power_mode": None,
        "active_perkey_profile_name": None,
        "ac_enabled": True,
        "battery_enabled": True,
        "ac_brightness_override": None,
        "battery_brightness_override": None,
        "ac_power_mode": None,
        "battery_power_mode": None,
        "ac_perkey_profile_name": None,
        "battery_perkey_profile_name": None,
        "battery_saver_enabled": False,
        "battery_saver_brightness": 25,
    }
    values.update(overrides)
    return PowerSourceLoopInputs(**values)
