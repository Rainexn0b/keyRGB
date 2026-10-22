# Controller sleep and wake policy

## Scope

Some keyboard controllers implement a firmware inactivity timer that turns the
deck dark independently of KeyRGB. The ITE 8291r3 backend reports this as
`brightness=0` while `is_off=False`. Host-side frame writes do not disable or
re-arm that timer.

Sleep-state detection is backend-owned. The tray consumes the backend-declared
sleep signature and applies one of the two user policies below; it does not
select behavior from a backend-name check.

### Observed timeout and why it can seem earlier

The first 2026-09-03 full diagnostic session on the reported `048d:600b`
controller captured four native sleeps 605.0–607.4 seconds after the last
keyboard event. A second session (`20260903T184044.723987Z`) captured three
more at approximately 604.7, 605.0, and 605.2 seconds. That controller's
measured firmware timeout is therefore approximately ten minutes. This is
hardware evidence for that device, not a universal timeout guarantee for every
controller.

The firmware clock tracks keyboard activity independently of the desktop's
screen-idle clock. Mouse or touchpad activity can keep KDE's ten-minute screen
timeout from advancing without resetting the keyboard controller. For example,
eight minutes of mouse-only use after the last key can make the deck appear to
sleep only two minutes after the user stops all activity, even though its own
keyboard-inactivity timer ran for the full ten minutes.

The second session also distinguishes the owner: each initial dark transition
first appeared as a hardware read of `brightness=0` with `is_off=False` while
screen idle was inactive. KeyRGB issued no off command at those transitions;
the only explicit off commands were the later keyboard-wake re-arm operations.

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

In **Settings → Advanced → Controller sleep and idle timing**, enable **Let
the controller's own sleep timeout turn the keyboard off**. A confirmed native
sleep is then accepted as a valid off state. With **Wake on any input** disabled
(the default):

1. KeyRGB stops the active software effect so render frames do not fight the
   controller's decision.
2. A final in-flight frame is corrected if it lands after the effect stops.
3. Mouse, touchpad, compositor-resume, and modifier-only events leave the deck
   dark.
4. A non-modifier keyboard `EV_KEY` key-down, power restore, or manual **Turn
   On** restores the configured scene.
5. Keyboard and firmware-first wake use the controller-brightness handoff.
   Reactive rendering adopts the physical baseline and descends through its
   frame guard; it does not send another off or soft-on prime. A temporary dim
   target remains authoritative. Failed restarts retain native-sleep ownership
   for retry. Backend-declared settle deadlines defer the restart when needed.

The same default key-only restore rule applies when screen-idle synchronization
turned the deck off while controller-sleep respect was enabled.

Modifier filtering is tray policy, not an ITE protocol requirement. On affected
KDE systems, touchpad gestures can emit synthetic `KEY_LEFTMETA` events through
the physical AT-keyboard evdev node. Requiring a non-modifier key-down prevents
those gestures from being mistaken for intentional typing. A combination such
as Ctrl+C wakes on `C`; pressing Ctrl alone does not.

If firmware itself wakes before the idle-power evdev loop consumes the key,
hardware polling claims the wake and restarts the stopped effect directly. The
idle loop then yields instead of issuing a second off/soft-on transition.

### Wake on any input (opt-in)

Enable **Wake on any input** directly below the controller-sleep checkbox to
also accept modifier keys, mouse movement/clicks/scrolling, and touchpad activity.
The config key is `wake_on_any_input` (`IDLE_DISPLAY`, default `False`); it takes
effect only while `controller_sleep_respect` is enabled. This changes keyboard
lighting wake behavior, not the computer's ability to wake from system suspend.

- Input must occur after the latest active native-sleep or screen-idle off.
  Manual off, suspend/lid/power-off ownership, configured zero brightness, and
  temporary dim limits remain authoritative. Screen-idle restores still obey
  screen state and the existing debounce/power-source guards.
- Evdev accepts timestamped key/button downs and pointer/contact activity using
  an fd-local monotonic event clock. Startup, empty reads, releases, held-key
  repeats, metadata, and dropped-event resynchronization do not count as wake.
- An input-only Wayland listener supplies activity when evdev cannot see a
  device. It requires `ext_idle_notifier_v1` version 2 on both compositor and
  client. Its zero-timeout notification is scoped to the current dark period;
  only a real `idled → resumed` event qualifies. Compositor startup/reconnect,
  a bare active-session status, and idle inhibitors do not trigger a wake.
  Where that protocol is unavailable, readable evdev devices remain the source.
- After the backend's settle interval, the pipeline reads hardware state under
  `kb_lock`. Already-awake firmware retains the native brightness handoff;
  a still-dark device uses the shared idle soft-on restore. Input duplicates
  cannot start a second fade, and failed restores retain ownership for retry.
  A later firmware wake retains its own settle deadline: time spent waiting on
  pointer activity while the controller was dark cannot shorten that interval.

## Diagnostic events

Useful runtime events are:

- `hardware:controller_sleep_off`
- `idle_power:controller_sleep_native_wake_handoff trigger=keyboard_evdev`
- `idle_power:controller_sleep_restore trigger=keyboard_evdev`
- `hardware:controller_sleep_firmware_wake`
- `idle_power:screen_idle_restore trigger=keyboard_evdev`
- `idle_power:screen_idle_restore trigger=any_input`
- `deck:transition` (identity, source, state, outcome and ownership)
  uses `source=input_wake` for a host-driven input restore and
  `source=firmware_wake` when the device was already awake.

While controller sleep is honored, a non-zero brightness register together
with `is_off=True` is valid: an explicit corrective off command may preserve
the register value while the deck remains physically dark.

## Pipeline ownership

Unifying the overlapping wake writers is tracked in
[sleep-wake-pipeline-campaign.md](sleep-wake-pipeline-campaign.md). That
campaign must keep this document's two user policies, default key-only restore
rule, explicit any-input opt-in, and firmware-versus-evdev single-restore race.
It must not replace them with a
post-wake brightness clamp.
