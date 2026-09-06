# Backend limitations

## `ite8291r3` AC unplug blank on some TongFang systems

On some `ite8291r3` laptops, unplugging or replugging AC power causes the
embedded controller to briefly blank or reset keyboard lighting before
userspace can repaint it.

What this looks like:

- AC profile color shows normally
- AC is unplugged
- keyboard briefly goes dark or reports a transient brightness jump
- KeyRGB restores the configured battery or AC profile afterward

What KeyRGB can and cannot do:

- KeyRGB can detect the blank and restore the configured lighting state.
- When the controller reports raw brightness above KeyRGB's stable `0..50`
  range, KeyRGB seeds a render-owned handoff from the normalized physical
  maximum. Subsequent software frames step down toward the active target rather
  than snapping there or waiting for delayed AC policy.
  This controlled frame-by-frame handoff applies to reactive effects; other
  effect classes retain their direct target restore. On an honored native-sleep
  keyboard wake, KeyRGB no longer inserts an explicit off/soft-on cycle before
  that reactive handoff. A successful handoff is latched so repeated raw-high
  polls cannot restart the fade; failed attempts are bounded until a valid-range
  reading re-arms recovery.
- Backends whose per-key mode policy requires reassertion still issue that mode
  command, but at the first guarded handoff step rather than as an earlier
  full-target prime. The affected `ite8291r3` path uses init-once behavior.
- KeyRGB cannot guarantee a perfectly seamless `color A -> color B` transition
  if the controller blanks itself before the USB backend receives a stable
  state again. The initial controller flash can occur before the next hardware
  poll; this correction makes only the remaining interval after detection a
  controlled fade.

Current evidence for this limitation:

- backend: `ite8291r3`
- device family: TongFang / rebrands such as Wootbook
- no kernel `sysfs-leds` backend available on affected systems
- debug logs show raw controller brightness values like `0` and `60` before
  the recovery repaint, which is outside the normal stable UI range

Practical workaround:

- use the same AC and battery color and only change brightness, or
- disable AC/battery per-key profile switching on affected hardware
