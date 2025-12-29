# Sysfs Keyboard Backlight Backend

## Goal

Support Tongfang laptops that expose keyboard backlight controls via sysfs (LED class or platform driver) even when no USB ITE controller is present.

## Non-goals

- Per-key support (likely not possible for sysfs LED backlights).
- Hardware firmware effects (unless sysfs exposes them explicitly).

## Detection

Probe for candidate sysfs nodes:

- `/sys/class/leds/*kbd*`
- `/sys/class/leds/*keyboard*`

Some naming patterns seen in the wild (kernel/driver dependent):

- `/sys/class/leds/tuxedo::kbd_backlight/`
- `/sys/class/leds/white:kbd_backlight/`
- `/sys/class/leds/ite_8291_lb:kbd_backlight/`

- Known Tongfang patterns if discovered (document per model)

A backend should record:

- path(s) chosen
- supported attributes detected (brightness only vs RGB)

## Capabilities

Typical sysfs capabilities:

- `per_key = False`
- `hardware_effects = False`
- `palette = False`

The tray should still support:

- off/on
- brightness
- uniform color *only if RGB is exposed* (many sysfs keyboard backlights are white-only)

## Device API mapping

Implement a device class that satisfies the minimal protocol used by KeyRGB:

- `turn_off()` -> write `0` brightness
- `is_off()` -> brightness == 0
- `get_brightness()` -> read brightness
- `set_brightness()` -> write brightness
- `set_color()` -> if RGB supported, write color; otherwise either no-op or raise a clear exception
- `set_key_colors()` -> not supported (should raise)
- `set_effect()` -> not supported (should raise)

## Brightness scale

KeyRGB currently uses a “hardware brightness” scale in some places (0–50) and a UI scale elsewhere.

For sysfs:

- Normalize internally to sysfs `max_brightness`.
- Translate from KeyRGB brightness into sysfs range.

Document the mapping explicitly once a first real sysfs device is confirmed.

## Safety

- Writes to sysfs require correct permissions (udev rules might be needed).
- Avoid running UI as root.
- If permissions are insufficient, backend should probe as “unavailable” with a helpful reason.

## Test strategy

- Unit-test read/write mapping using a temporary directory structure that mimics `/sys/class/leds`.
- Do not require real sysfs in unit tests.
