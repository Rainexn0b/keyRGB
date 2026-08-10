# Controller sleep and wake policy

## Scope

Some keyboard controllers implement a firmware inactivity timer that turns the
deck dark independently of KeyRGB. The ITE 8291r3 backend reports this as
`brightness=0` while `is_off=False`. Host-side frame writes do not disable or
re-arm that timer.

Sleep-state detection is backend-owned. The tray consumes the backend-declared
sleep signature and applies one of the two user policies below; it does not
select behavior from a backend-name check.

## Automatic recovery (default)

When **Let the controller's own sleep timeout turn the keyboard off** is
disabled, KeyRGB treats a confirmed stable zero as an unintended blank and
restores the configured scene automatically.

- A single zero read is not enough: hardware polling performs a fast stable-zero
  confirmation first.
- A running software or reactive effect heals through its render loop by
  invalidating the hardware-brightness cache. The poller does not issue a
  competing brightness write or restart the effect.
- A short post-resume guard prevents a transient zero from undoing a successful
  idle, power, or manual restore.
- Zero brightness reported by hardware is never persisted as user intent.

This lightweight path is intentionally retained. Hardware registers can report
non-zero even when an ITE deck is physically held dark by a stale firmware
latch, and KeyRGB has no sensor for physical LED output. A backend-declared
`off -> soft-on` recovery strategy would be more forceful but could turn a
persistent harmless zero into an avoidable visible transition. Add such a
strategy only with automatic-mode hardware evidence; do not add a backend-name
special case.

## Respect controller sleep (opt-in)

When the setting is enabled, a confirmed native sleep is accepted as a valid
off state:

1. KeyRGB stops the active software effect so render frames do not fight the
   controller's decision.
2. A final in-flight frame is corrected if it lands after the effect stops.
3. Mouse, touchpad, compositor-resume, and modifier-only events leave the deck
   dark.
4. A non-modifier keyboard `EV_KEY` key-down, power restore, or manual **Turn
   On** restores the configured scene.
5. Keyboard restore sends an explicit off command before soft-on. This clears
   the observed ITE stale-off latch, then primes user mode at brightness 1 and
   fades to the configured level.

The same key-only restore rule applies when screen-idle synchronization turned
the deck off while this setting was enabled.

Modifier filtering is tray policy, not an ITE protocol requirement. On affected
KDE systems, touchpad gestures can emit synthetic `KEY_LEFTMETA` events through
the physical AT-keyboard evdev node. Requiring a non-modifier key-down prevents
those gestures from being mistaken for intentional typing. A combination such
as Ctrl+C wakes on `C`; pressing Ctrl alone does not.

If firmware itself wakes before the idle-power evdev loop consumes the key,
hardware polling claims the wake and restarts the stopped effect directly. The
idle loop then yields instead of issuing a second off/soft-on transition.

## Diagnostic events

Useful runtime events are:

- `hardware:controller_sleep_off`
- `idle_power:controller_sleep_rearm trigger=keyboard_evdev`
- `idle_power:controller_sleep_restore trigger=keyboard_evdev`
- `hardware:controller_sleep_firmware_wake`
- `idle_power:screen_idle_restore trigger=keyboard_evdev`

While controller sleep is honored, a non-zero brightness register together
with `is_off=True` is valid: an explicit corrective off command may preserve
the register value while the deck remains physically dark.
