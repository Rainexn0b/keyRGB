"""Default configuration values.

Split out from `src.core.config` to keep that module small and focused.
"""

from __future__ import annotations

DEFAULTS: dict = {
    "effect": "rainbow",
    "speed": 4,  # 0-10 UI scale (10 = fastest)
    # Effect/uniform brightness (0-50 hardware scale).
    "brightness": 25,
    # Per-key mode brightness (0-50 hardware scale). Kept separate so per-key
    # edits don't overwrite the effect brightness (and vice versa).
    "perkey_brightness": 25,
    "color": [255, 0, 0],  # RGB for static/custom effects
    # Manual highlight color for reactive typing effects.
    # When disabled, reactive effects use their built-in coloring.
    "reactive_use_manual_color": False,
    "reactive_color": [255, 255, 255],
    # When a non-per-key effect is started from a per-key state, we can remember
    # which per-key mode to restore when the user stops the effect.
    # None | 'perkey'
    "return_effect_after_effect": None,
    "autostart": True,
    # OS session autostart (XDG ~/.config/autostart). When enabled, KeyRGB tray
    # should be started automatically on login.
    "os_autostart": False,
    # Power management (lid/suspend)
    "power_management_enabled": True,
    "power_off_on_suspend": True,
    "power_off_on_lid_close": True,
    "power_restore_on_resume": True,
    "power_restore_on_lid_open": True,
    # Battery saver (dim on AC unplug)
    "battery_saver_enabled": False,
    # Uses the same brightness scale as `brightness`.
    "battery_saver_brightness": 25,
    # Power-source lighting profiles (AC vs battery)
    # These default to "enabled" with no brightness override (None).
    # When brightness is None, KeyRGB will keep using the current brightness
    # (and can optionally fall back to battery_saver_* behavior on battery).
    "ac_lighting_enabled": True,
    "ac_lighting_brightness": None,
    "battery_lighting_enabled": True,
    "battery_lighting_brightness": None,
    # Per-key colors stored as {"row,col": [r,g,b]}
    "per_key_colors": {},
    # Screen dim sync (best-effort, DE-specific). When enabled, KeyRGB will
    # react to desktop-driven display dimming/brightness changes (usually via
    # /sys/class/backlight, plus DPMS screen-off detection) by either turning
    # keyboard LEDs off, or dimming them to a temporary brightness.
    "screen_dim_sync_enabled": True,
    # 'off' | 'temp'
    "screen_dim_sync_mode": "off",
    # 1-50 (same brightness scale as `brightness`). Used when mode == 'temp'.
    "screen_dim_temp_brightness": 5,
}
