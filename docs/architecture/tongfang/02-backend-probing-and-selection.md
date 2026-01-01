# Backend Probing & Selection

## Goal

Make `KEYRGB_BACKEND=auto` pick the correct backend on Tongfang machines by probing for real availability, not just “importable Python module”.

## Why this matters

- Many future backends will be importable on all machines, but only usable on some.
- Probing needs to be fast and safe so the tray can start instantly.

## Design requirements

- Probes must be **read-only** (no writes, no “set color” during probe).
- Probes must be **fast**: target < 100ms total in the common case.
- Probes must not spam logs; log details only at DEBUG or via throttling.

## Proposed interface changes

Keep the existing `KeyboardBackend` shape but tighten semantics:

- `is_available()` becomes a true probe:
  - returns True only if the backend can plausibly operate on this machine
  - should not require root
  - may check for sysfs nodes, USB VID/PID presence, or driver availability

Optional (recommended) extension:

- Add `probe()` method returning a structured result:

```text
ProbeResult {
  available: bool
  reason: str
  confidence: int  # 0..100
  identifiers: dict[str, str]  # vid/pid, sysfs paths, dmi strings, etc
}
```

This makes selection explainable and easier to debug.

## Auto-selection algorithm (recommended)

1. Build a list of backends (registry).
2. For each backend:
   - run probe
   - keep only `available=True`
3. Choose winner by:
   - highest `confidence`, then
   - highest `priority`

## Env override behavior

- `KEYRGB_BACKEND=<name>`:
  - if backend exists and is available: use it
  - if backend exists but probe fails: return None (and log why)
  - if backend name unknown: return None

This preserves “power user” control and avoids silently picking something else.

## What to log

At INFO (once at startup):

- selected backend name

At DEBUG:

- per-backend probe outcome and reason

Example:

```text
Selected backend: sysfs-leds (confidence 90)
ite8291r3: unavailable (no matching USB device)
sysfs-leds: available (found /sys/class/leds/tongfang::kbd_backlight)
```

## Unit tests

- Auto-selection chooses highest confidence
- Env override respected
- Unknown override returns None
- “No backends available” returns None

Probes should be monkeypatchable so tests don’t touch the real system.
