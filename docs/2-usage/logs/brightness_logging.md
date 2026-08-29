# Brightness logging

## Diagnostic session (recommended for runtime reports)

For a suspend/resume, flash, flicker, or other runtime report, start the
canonical session first:

```bash
keyrgb --diagnostic-session
```

It writes a timestamped bundle with full runtime logging, diagnostics snapshots,
and best-effort journal slices. See [Diagnostic sessions](diagnostic_sessions.md)
for the workflow, source-checkout command, and privacy guidance.

## Focused reactive typing investigation

Quit any existing KeyRGB tray instance, then run this command from the project
checkout. It launches the installed KeyRGB runtime by default, preserving its
packaged GTK/AppIndicator integration, and writes a fresh `keyrgb-debug.log` in
the current directory:

```bash
keyrgb --capture-runtime-log
```

`KEYRGB_DEBUG_REACTIVE_INPUT=1` adds `reactive_input: key_press …` lines that
pin each flash to an exact keystroke. Stop with Ctrl-C; a libusb assertion
on shutdown (`usbi_mutex_destroy: Assertion … failed`) is a known harmless
teardown race and does not invalidate the captured session.

### Capture modes

```bash
# General runtime and startup diagnostics
keyrgb --capture-runtime-log=debug

# Runtime plus brightness decisions and hardware reads/writes
keyrgb --capture-runtime-log=brightness

# Everything above plus explicit reactive-input tracing (the default)
keyrgb --capture-runtime-log=full
```

Use the source launcher when intentionally testing uninstalled code:

```bash
keyrgb --capture-runtime-log=full --runtime-log-launcher=source
```

The source launcher runs the active Python as `-m keyrgb.tray` from the
checkout. It does **not** exec an installed AppImage: those binaries ignore
`PYTHONPATH` and would log shipped `src.*` code instead of local changes.
The venv must provide the tray dependencies listed in
`docs/2-usage/venv/setup.md`; without PyGObject the Plasma icon may fall back
to XEmbed. Use `--runtime-log-launcher=installed` (the default) when you
intentionally want the packaged runtime.

The previous `buildpython --capture-runtime-log` interface remains as a
compatibility wrapper for contributor workflows. Runtime capture itself is
owned by `keyrgb/core/diagnostics/runtime_capture.py` and does not depend on
`buildpython`.

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
keyrgb --capture-runtime-log=brightness
```

## Runtime debug

```bash
KEYRGB_DEBUG=1 ./keyrgb.sh
KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb.sh
KEYRGB_DEBUG=1 KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb.sh
```
