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
    # Secondary lightbar state for auxiliary single-zone controllers.
    "lightbar_brightness": 25,
    "lightbar_color": [255, 0, 0],
    # Generic secondary-device state for auxiliary routes such as lightbars or
    # future mouse sysfs backends. Kept alongside the legacy lightbar fields so
    # older config consumers continue to work.
    "secondary_device_state": {},
    # Lenovo Gen10 ITE 8258 chassis zone device defaults. These are virtual
    # routes sharing the 0x048d:0xc197 composite controller with the keyboard.
    "ite8258_chassis_logo_brightness": 25,
    "ite8258_chassis_logo_color": [255, 0, 0],
    "ite8258_chassis_neon_brightness": 25,
    "ite8258_chassis_neon_color": [0, 255, 0],
    "ite8258_chassis_vent_brightness": 25,
    "ite8258_chassis_vent_color": [0, 0, 255],
    # Direction for directional effects (wave, snake). None = default direction.
    "direction": None,
    # Manual highlight color for reactive typing effects.
    # When disabled, reactive effects use their built-in coloring.
    "reactive_use_manual_color": False,
    "reactive_color": [255, 255, 255],
    # Reactive typing pulse/highlight intensity (0..50). Kept separate from
    # overall keyboard brightness so power policies can dim the keyboard
    # without overriding the user's reactive intensity preference.
    "reactive_brightness": 25,
    # Reactive typing wave thickness (1..100).
    "reactive_trail_percent": 40,
    # Overall reactive visual style.
    # 'subtle' softens mid-range pulses and reduces ripple saturation;
    # 'vivid' preserves the stronger legacy presentation.
    "reactive_visual_mode": "subtle",
    # When a non-per-key effect is started from a per-key state, we can remember
    # which per-key mode to restore when the user stops the effect.
    # None | 'perkey'
    "return_effect_after_effect": None,
    "autostart": True,
    # Experimental backends remain opt-in until they have broader hardware
    # validation and issue history.
    "experimental_backends_enabled": False,
    # OS session autostart (XDG ~/.config/autostart). When enabled, KeyRGB tray
    # should be started automatically on login.
    "os_autostart": False,
    # Power management (lid/suspend)
    "power_management_enabled": True,
    "power_off_on_suspend": True,
    "power_off_on_lid_close": True,
    "power_restore_on_resume": True,
    "power_restore_on_lid_open": True,
    # Lightweight system power mode tuning.
    # Stored in kHz because cpufreq sysfs uses kHz units.
    "system_power_extreme_cap_khz": 800000,
    # Battery saver (dim on AC unplug)
    "battery_saver_enabled": False,
    # Uses the same brightness scale as `brightness`.
    "battery_saver_brightness": 25,
    # Power-source lighting profiles (AC vs battery)
    # New installs default to a brighter AC setup and a dimmer battery setup.
    # Existing user configs keep their saved values; these defaults only apply
    # when the keys are absent.
    "ac_lighting_enabled": True,
    "ac_lighting_brightness": 40,
    "ac_power_mode": "performance",
    "ac_perkey_profile_name": None,
    "battery_lighting_enabled": True,
    "battery_lighting_brightness": 20,
    "battery_power_mode": "balanced",
    "battery_perkey_profile_name": None,
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
    # Debounce polls for idle-power dimming decisions.
    # Each poll is 0.5s. 6 = 3s, 10 = 5s.
    "idle_dim_debounce_enter_polls": 6,
    "idle_dim_debounce_exit_polls": 10,
    # Time-of-day brightness scheduler.
    # When enabled, automatically adjusts brightness based on local time.
    # During the day, power-source (AC/battery) brightness takes precedence
    # for base brightness, while reactive_brightness still follows the day
    # schedule.
    # At night, these scheduler values always apply.
    "time_scheduler_enabled": False,
    "day_start_time": "08:00",
    "night_start_time": "20:00",
    "day_base_brightness": 40,
    "day_reactive_brightness": 50,
    "night_base_brightness": 20,
    "night_reactive_brightness": 50,
    # Physical keyboard layout for the per-key editor / calibrator overlay.
    # 'auto' probes sysfs conservatively; manual options expose common desktop
    # and laptop physical variants directly in the editor dropdown.
    "physical_layout": "auto",
    # Visible legend-pack for the per-key editor / calibrator overlay.
    # 'auto' keeps the built-in default legends for the active physical family.
    "layout_legend_pack": "auto",
    # Selected tray device-context header row. The tray falls back to
    # 'keyboard' if the saved device is no longer present.
    "tray_device_context": "keyboard",
    # Software-effect routing policy.
    # 'keyboard' keeps looped software effects on the keyboard only.
    # 'all_uniform_capable' mirrors uniformized software frames to compatible
    # auxiliary devices such as the secondary lightbar.
    "software_effect_target": "keyboard",
    # Per-effect speed overrides.  Maps effect name (str) to speed (0-10).
    # When a value is present for the active effect, it overrides the global
    # 'speed' setting.  When absent, the global speed is used.
    "effect_speeds": {},
}
