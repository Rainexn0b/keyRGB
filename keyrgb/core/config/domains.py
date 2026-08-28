"""Config domain ownership for the flat on-disk settings map.

The persisted JSON shape stays flat for compatibility. Domain ownership is the
internal architecture that keeps lighting, power, idle/display, scheduler,
layout, and app/session keys from remaining one undifferentiated bag.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType


class ConfigDomain(str, Enum):
    """Logical owner for a group of config keys."""

    LIGHTING = "lighting"
    SECONDARY = "secondary"
    POWER = "power"
    IDLE_DISPLAY = "idle_display"
    SCHEDULER = "scheduler"
    LAYOUT = "layout"
    APP = "app"


# Known keys may include props that have code defaults even when absent from
# DEFAULTS (for example controller sleep respect and idle fade duration).
_DOMAIN_KEY_LISTS: dict[ConfigDomain, tuple[str, ...]] = {
    ConfigDomain.LIGHTING: (
        "effect",
        "speed",
        "brightness",
        "perkey_brightness",
        "color",
        "direction",
        "reactive_use_manual_color",
        "reactive_color",
        "reactive_brightness",
        "reactive_trail_percent",
        "reactive_visual_mode",
        "return_effect_after_effect",
        "per_key_colors",
        "effect_speeds",
        "software_effect_target",
    ),
    ConfigDomain.SECONDARY: (
        "lightbar_brightness",
        "lightbar_color",
        "secondary_device_state",
        "ite8258_chassis_logo_brightness",
        "ite8258_chassis_logo_color",
        "ite8258_chassis_neon_brightness",
        "ite8258_chassis_neon_color",
        "ite8258_chassis_vent_brightness",
        "ite8258_chassis_vent_color",
    ),
    ConfigDomain.POWER: (
        "power_management_enabled",
        "power_off_on_suspend",
        "power_off_on_lid_close",
        "power_restore_on_resume",
        "power_restore_on_lid_open",
        "system_power_extreme_cap_khz",
        "battery_saver_enabled",
        "battery_saver_brightness",
        "ac_lighting_enabled",
        "ac_lighting_brightness",
        "ac_power_mode",
        "ac_perkey_profile_name",
        "battery_lighting_enabled",
        "battery_lighting_brightness",
        "battery_power_mode",
        "battery_perkey_profile_name",
    ),
    ConfigDomain.IDLE_DISPLAY: (
        "screen_dim_sync_enabled",
        "controller_sleep_respect",
        "screen_dim_sync_mode",
        "screen_dim_temp_brightness",
        "idle_dim_debounce_enter_polls",
        "idle_dim_debounce_exit_polls",
        "idle_fade_duration_s",
    ),
    ConfigDomain.SCHEDULER: (
        "time_scheduler_enabled",
        "day_start_time",
        "night_start_time",
        "day_base_brightness",
        "day_reactive_brightness",
        "night_base_brightness",
        "night_reactive_brightness",
    ),
    ConfigDomain.LAYOUT: (
        "physical_layout",
        "layout_legend_pack",
    ),
    ConfigDomain.APP: (
        "autostart",
        "experimental_backends_enabled",
        "os_autostart",
        "tray_device_context",
    ),
}

DOMAIN_KEYS: MappingProxyType[ConfigDomain, frozenset[str]] = MappingProxyType(
    {domain: frozenset(keys) for domain, keys in _DOMAIN_KEY_LISTS.items()}
)

ALL_KNOWN_KEYS: frozenset[str] = frozenset().union(*DOMAIN_KEYS.values())


def project_domain(values: dict[str, object], domain: ConfigDomain) -> dict[str, object]:
    """Return a detached mapping of keys owned by ``domain`` that are present."""

    owned = DOMAIN_KEYS[domain]
    return {key: values[key] for key in owned if key in values}


def project_extras(values: dict[str, object]) -> dict[str, object]:
    """Return detached unknown keys preserved for forward compatibility."""

    return {key: value for key, value in values.items() if key not in ALL_KNOWN_KEYS}
