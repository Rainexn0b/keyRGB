# Diagnostics

Use a diagnostic session for suspend/resume, blanking, flicker, or an effect
that stops. It writes one bundle instead of several ad-hoc logs.

## Session (canonical)

```bash
keyrgb --diagnostic-session
```

From a checkout:

```bash
./keyrgb.sh --diagnostic-session
```

Close an existing tray when prompted, reproduce the issue, then `Ctrl-C`.
`keyrgb-diagnostic-launch` is the same workflow after install. The desktop
**Diagnostic Session** action starts it too.

Output is a timestamped directory under `~/.cache/keyrgb/diagnostic-sessions/`:

- `keyrgb-debug.log`
- `diagnostics-before.json` / `diagnostics-after.json`
- `journal-user.log` / `journal-kernel.log` (best-effort)

Review the bundle before sharing; journals can include host and session details.

## Hardware support bundle

For hardware detection or backend-selection problems, prefer the UI workflow:

1. Open **Settings → Version → Support Tools…**.
2. Run **Run diagnostics** and **Scan devices**.
3. Choose **Save full support bundle…** and attach
   `keyrgb-support-bundle.json` to the hardware-support issue.

The full bundle combines diagnostics, device discovery, supplemental evidence,
and an issue-oriented report.

## Hardware snapshot CLI fallback

If the Support Tools UI cannot be opened, collect a read-only hardware and
backend snapshot from the terminal:

```bash
keyrgb-diagnostics
# Equivalent command that also works directly through the AppImage launcher:
keyrgb --diagnostics
```

Add `--text` for human-readable output or `--no-usb` to skip the general pyusb
USB inventory scan. Backend probes still perform their normal detection.
AppImage installs also create the `keyrgb-diagnostics` forwarding command. This
CLI output is the fallback diagnostics snapshot, not the combined Support Tools
bundle.

## Capture modes

`--diagnostic-mode=` and `--capture-runtime-log=` share the same modes:

| Mode | Flags |
|---|---|
| `debug` | `KEYRGB_DEBUG=1` |
| `brightness` | plus `KEYRGB_DEBUG_BRIGHTNESS=1` |
| `full` (default) | plus `KEYRGB_DEBUG_REACTIVE_INPUT=1` |

```bash
keyrgb --diagnostic-session --diagnostic-mode=debug
keyrgb --diagnostic-session --diagnostic-output-dir DIR
```

## Log only

When you only need the runtime log:

```bash
keyrgb --capture-runtime-log
keyrgb --capture-runtime-log=brightness
keyrgb --capture-runtime-log=full --runtime-log-launcher=source
```

Default launcher is the installed runtime (GTK/AppIndicator). `source` runs
checkout code via `.venv`; it needs the [setup](setup.md) tray deps.

A libusb `usbi_mutex_destroy` assert on shutdown is a known harmless teardown
race.

## Ad-hoc flags

```bash
KEYRGB_DEBUG=1 ./keyrgb.sh
KEYRGB_DEBUG_BRIGHTNESS=1 ./keyrgb.sh
KEYRGB_DEBUG_REACTIVE_INPUT=1 ./keyrgb.sh
```
