# V1 Release Sprint (Maintainability + Tests)

This checklist is for the “final v1” stabilization pass.

## Goals

- Reliable install on Fedora/Nobara (KDE) and Fedora Workstation (GNOME)
- No regressions in “no keyboard device present” startup
- Clear separation between unit tests (CI-safe) and hardware/integration tests (manual)
- Fewer silent failures and easier debugging

## Maintainability Sprint

### P0 (must-do)

- Standardize vendored dependency handling
  - Only one mechanism should exist for `ite8291r3-ctl`:
    - `install.sh` installs upstream and applies the one-line `0x600B` patch
    - RPM spec downloads upstream as `Source1` and applies the patch
  - Code should not assume `vendor/` exists at runtime.

- Reduce “swallow errors” patterns
  - Replace `except Exception: pass` in hot paths with narrow exceptions + a single log line.
  - Ensure tray polling threads log failures once, then keep running.

- Logging consistency
  - Prefer `logging.getLogger(__name__)` everywhere.
  - Avoid `print()` for errors in runtime code.

### P1 (nice-to-have)

- Centralize “import fallback / repo root sys.path injection” into one helper module.
- Simplify config polling (debounce / less frequent polling).
- Add clearer user-facing error messages for missing tray backend requirements.

## Test Sprint

### CI unit tests (must pass)

- `pytest` runs in GitHub Actions.
- Hardware tests are skipped by default.

Acceptance:

- `pytest -q` passes on Python 3.10/3.11/3.12.

### Hardware / manual tests (run before tagging v1)

Run with real hardware on Fedora/Nobara:

- Install (fresh user) using `./install.sh`
- Verify tray icon appears
  - KDE Plasma: should appear
  - GNOME: ensure AppIndicator extension installed/enabled
- Verify “no device present” behavior
  - Unplug or boot without keyboard device
  - App should start and show a “device not detected” warning, without crashing
- Verify effects
  - Set brightness, set static color, start/stop an effect
- Verify per-key
  - Run calibrator and save a profile
  - Apply per-key colors
- Verify power management (optional)
  - Lid close/open and suspend/resume do not crash the app
- Verify TCC integration (optional)
  - If `tccd` exists: list profiles, activate temporarily
  - CRUD: create/rename/edit/delete custom profiles (expect pkexec/sudo prompt)

### Release tagging checklist

- Update `pyproject.toml` version to the new v1 scheme (decide exact version string).
- Ensure README + docs point to the simplified `./install.sh` path.
- Confirm RPM build instructions match the spec.
