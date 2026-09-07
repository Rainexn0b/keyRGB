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
