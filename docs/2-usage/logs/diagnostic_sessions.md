# Diagnostic sessions

Use a diagnostic session for a runtime problem such as a failed suspend/resume
restore, unexpected blanking, or an effect that stops responding. It collects
one shareable bundle instead of requiring separate terminal commands.

## Start a session

Installed runtime or AppImage:

```bash
keyrgb --diagnostic-session
```

From a source checkout:

```bash
./keyrgb.sh --diagnostic-session
```

The session auto-selects the checkout runtime when run from a checkout; outside
one it uses the installed runtime. `keyrgb-diagnostic-launch` is an equivalent
dedicated command after installing the current package. The app-menu's
**Diagnostic Session** action opens the same workflow after desktop integration
has been installed or refreshed.

The launcher asks you to close an existing KeyRGB tray, then press Enter. Reproduce
the issue and stop the session with `Ctrl-C`.

## Logging modes and options

All supported capture modes are available through both
`--diagnostic-mode=<mode>` and `--capture-runtime-log=<mode>`:

| Mode | Enabled logging |
| --- | --- |
| `debug` | `KEYRGB_DEBUG=1` |
| `brightness` | `KEYRGB_DEBUG=1`, `KEYRGB_DEBUG_BRIGHTNESS=1` |
| `full` (default) | `KEYRGB_DEBUG=1`, `KEYRGB_DEBUG_BRIGHTNESS=1`, `KEYRGB_DEBUG_REACTIVE_INPUT=1` |

For example, use a smaller session bundle when only startup/backend selection
matters:

```bash
keyrgb --diagnostic-session --diagnostic-mode=debug
```

`--diagnostic-output-dir DIR` chooses the parent directory for session bundles.
`--runtime-log-launcher=source|installed` overrides automatic runtime selection;
normally, leave it automatic. The three environment flags can also be set
directly and independently for ad-hoc developer tracing, but the predefined
modes are the supported shareable-capture combinations.

## Bundle contents

The launcher prints a timestamped directory, normally under
`~/.cache/keyrgb/diagnostic-sessions/`. It contains:

- `keyrgb-debug.log` — full runtime logs, including brightness and reactive-input tracing
- `diagnostics-before.json` and `diagnostics-after.json` — hardware/config snapshots
- `journal-user.log` and `journal-kernel.log` — best-effort journal slices for the session

Review the bundle before sharing it: diagnostics and journals can include host,
device, or user-session details. Attach the relevant files to a bug report rather
than pasting an entire large journal into an issue.

## Focused logging

For a narrower brightness or reactive-effects investigation, see
[brightness logging](brightness_logging.md). The older
`keyrgb --capture-runtime-log` command remains available when only a runtime log
is wanted.
