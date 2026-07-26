# Brightness logging

## Full reactive typing investigation (recommended for flash/flicker reports)

```bash
KEYRGB_DEBUG=1 \
KEYRGB_DEBUG_BRIGHTNESS=1 \
KEYRGB_DEBUG_REACTIVE_INPUT=1 \
./keyrgb >> ~/keyrgb-brightness.log 2>&1
```

`KEYRGB_DEBUG_REACTIVE_INPUT=1` adds `reactive_input: key_press …` lines that
pin each flash to an exact keystroke. Stop with Ctrl-C; a libusb assertion
on shutdown (`usbi_mutex_destroy: Assertion … failed`) is a known harmless
teardown race and does not invalidate the captured session.

### What to grep for at the flash timestamp

| Signature | Likely cause | See |
|---|---|---|
| `hardware:stable_zero_brightness_recover` repeated every ~2 s | ITE transient-0 recovery loop | postmortem addendum 2026-07 |
| `hardware:brightness_change new=…` with a large jump | hardware brightness spike | reactive_hw_lift logs |
| `reactive_hw_lift allow=True` on per-key backend | uniform-lift gate misfire | `_render_brightness.py` |
| `reactive_pulse_visual post_restore_damp=1.0` mid-restore-window | damp wiped by unplanned restart | `_reactive_restore_seed.py` |
| `reactive_render_visual combined_scale=…` spike | software per-key composition burst | `render.py` |

Read `reactive_hw_lift`, `reactive_pulse_visual`, and `reactive_render_visual`
together. A flash with `allow=False`, stable `hw=`, and no
`hardware:brightness_change` is NOT a hardware brightness regression.

## Standard brightness logging

```bash
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb >> ./keyrgb-brightness.log 2>&1
```

## Runtime debug

```bash
KEYRGB_DEBUG=1 ./keyrgb
KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb
```
