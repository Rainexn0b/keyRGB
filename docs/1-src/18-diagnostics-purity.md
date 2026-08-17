# Diagnostics purity

Status: **Done**

## Purpose

Diagnostics collection is a read-only support surface. It must not construct
live mutable application state, and the snapshot handed to formatters or saved
JSON must be detached from collector internals.

## Contracts

1. **No live `Config`.** Secondary-device diagnostics load settings through
   `load_config_settings()` into `ReadonlyDiagnosticsConfig`. That view never
   saves, coerces-to-disk, or shares identity with the tray/GUI config object.
2. **Deep-frozen snapshots.** `Diagnostics` and secondary-device snapshots freeze
   nested mappings and sequences. Callers cannot mutate the snapshot, and later
   mutation of the collector's input dicts does not change it.
3. **JSON remains ordinary data.** `Diagnostics.to_dict()` unfreezes to plain
   `dict`/`list` values for serialization.
4. **Environment policy is prefix-complete.** `env_snapshot()` reports every
   present `KEYRGB_*` variable plus the desktop-session keys
   `XDG_CURRENT_DESKTOP`, `DESKTOP_SESSION`, and `XDG_SESSION_TYPE`. New KeyRGB
   policy knobs appear automatically. Unrelated process environment is omitted.

## Owners

| Surface | Module |
|---|---|
| Freeze/unfreeze | `src/core/diagnostics/model.py` |
| Environment snapshot | `src/core/diagnostics/snapshots.py` |
| Secondary-device snapshot | `src/core/diagnostics/secondary_devices.py` |

## Non-goals

- Uploading diagnostics
- Changing the on-disk config schema
- Dumping the entire process environment
