"""Power-management and power-source lighting config accessors."""

from __future__ import annotations

from typing import Any

from ._lighting import _props as _config_props


class PowerConfigAccessors:
    """Power and power-source preference accessors for ``Config``."""

    _settings: dict[str, Any]

    def _save(self) -> None: ...

    power_management_enabled = _config_props.bool_prop("power_management_enabled", default=True)
    power_off_on_suspend = _config_props.bool_prop("power_off_on_suspend", default=True)
    power_off_on_lid_close = _config_props.bool_prop("power_off_on_lid_close", default=True)
    power_restore_on_resume = _config_props.bool_prop("power_restore_on_resume", default=True)
    power_restore_on_lid_open = _config_props.bool_prop("power_restore_on_lid_open", default=True)
    system_power_extreme_cap_khz = _config_props.int_prop(
        "system_power_extreme_cap_khz",
        default=800000,
        min_v=400000,
        max_v=5000000,
    )

    # Battery saver (legacy)
    battery_saver_enabled = _config_props.bool_prop("battery_saver_enabled", default=False)
    battery_saver_brightness = _config_props.int_prop("battery_saver_brightness", default=25, min_v=0, max_v=50)

    # Power-source lighting and optional power-mode selection
    ac_lighting_enabled = _config_props.bool_prop("ac_lighting_enabled", default=True)
    battery_lighting_enabled = _config_props.bool_prop("battery_lighting_enabled", default=True)
    ac_power_mode = _config_props.optional_str_prop("ac_power_mode")
    battery_power_mode = _config_props.optional_str_prop("battery_power_mode")
    ac_perkey_profile_name = _config_props.optional_str_prop("ac_perkey_profile_name")
    battery_perkey_profile_name = _config_props.optional_str_prop("battery_perkey_profile_name")

    ac_lighting_brightness = _config_props.optional_brightness_prop("ac_lighting_brightness")
    battery_lighting_brightness = _config_props.optional_brightness_prop("battery_lighting_brightness")
