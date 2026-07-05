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
- KeyRGB cannot guarantee a perfectly seamless `color A -> color B` transition
  if the controller blanks itself before the USB backend receives a stable
  state again.

Current evidence for this limitation:

- backend: `ite8291r3`
- device family: TongFang / rebrands such as Wootbook
- no kernel `sysfs-leds` backend available on affected systems
- debug logs show raw controller brightness values like `0` and `60` before
  the recovery repaint, which is outside the normal stable UI range

Practical workaround:

- use the same AC and battery color and only change brightness, or
- disable AC/battery per-key profile switching on affected hardware
