# Refactor plan (proposed PR slices)

This document proposes **small, reviewable PRs** to reduce risk while improving maintainability.

Principles:

- Prefer **extracting modules** over rewriting behavior.
- Keep public behavior stable.
- Add/extend unit tests where it’s cheap and high value.

## 1) `src/core/diagnostics.py`

**Problem**

- One file contains: sysfs readers, /proc scanning, command execution, backend probing, config snapshotting, formatting, plus the dataclass model.

**Proposed split**

- `src/core/diagnostics/__init__.py`: `collect_diagnostics`, `Diagnostics` model export.
- `src/core/diagnostics/model.py`: `Diagnostics` dataclass + typing helpers.
- `src/core/diagnostics/collectors/`
  - `dmi.py`, `leds.py`, `power_supply.py`, `usb.py`, `process.py`, `env.py`, `app_versions.py`, `backend_probe.py`, `config_snapshot.py`
- `src/core/diagnostics/formatting.py`: `format_diagnostics_text`

**PR slices**

1. Move `format_diagnostics_text` into a new module; keep imports stable via re-export.
2. Move USB-related helpers (`_usb_devices_snapshot`, `_proc_open_holders`, sysfs roots) into `collectors/usb.py`.
3. Move config snapshot into `collectors/config_snapshot.py`.

**Acceptance**

- No change to output schema (unless explicitly documented).
- Existing diagnostics tests still pass.

## 2) `src/gui/power.py` (Settings window)

**Problem**

- Contains layout, scroll mechanics, config persistence, diagnostics worker threads, status UI, clipboard + browser integration.

**Proposed split**

- `src/gui/settings/` package
  - `window.py`: `SettingsWindow` top-level / layout
  - `state.py`: load/save config values, variable binding
  - `diagnostics_panel.py`: diagnostics UI + worker
  - `widgets/scrollframe.py`: reusable scrollable frame/canvas logic

**PR slices**

1. Extract scrollable canvas behavior into a reusable widget (`ScrollFrame`).
2. Extract diagnostics panel to a separate class.
3. Keep `src/gui/power.py` as a thin wrapper for backward compatibility (imports `SettingsWindow`).

**Acceptance**

- UI looks the same and functions the same.
- Still safe to launch as a subprocess from the tray.

## 3) Power management (`src/core/power_management/manager.py`)

**Problem**

- “Policy decisions” (what to do on AC/battery, suspend/resume, lid close/open) are interleaved with threads, polling, and hardware calls.

**Proposed refactor**

- Introduce a pure, unit-testable policy object for power-source transitions, similar to `BatterySaverPolicy`.
- Keep OS integration (dbus-monitor, sysfs lid monitoring) in `PowerManager`.

Note: `src/core/power.py` remains as a thin compatibility wrapper exporting `PowerManager`.

**PR slices**

1. Extract an `AcBatteryPolicy` with a method like `update(on_ac, desired_profile, now, is_off, current_brightness) -> actions`.
2. Add unit tests for the new policy.
3. Keep `PowerManager` loop minimal (read inputs → policy → apply actions).

## 4) Legacy surface area

**Problem**

- Legacy modules (`src/legacy/*`) still contain large logic that can confuse contributors.

**Pragmatic approach**

- Add documentation about what is legacy vs current.
- Over time, move active code paths behind `src/core/*` and keep legacy modules stable.

