# Build steps

This document describes the individual steps used by `buildpython`.

List steps:

```bash
python3 -m buildpython --list-steps
```

Run a single step:

```bash
python3 -m buildpython --run-steps=Compile
python3 -m buildpython --run-steps=2
```

## Step catalog

### 1) Compile
- Command: `python -m compileall -q src`
- Purpose: fast syntax check over the project sources.

### 2) Pytest
- Command: `pytest -q -o addopts=`
- Purpose: run tests without forcing coverage output.
- Notes: hardware tests remain opt-in via `KEYRGB_HW_TESTS=1`.

### 3) Ruff (optional)
- Command: `ruff check src`
- Purpose: linting.
- Behavior: auto-skips if `ruff` is not installed.

### 4) Import Validation
- Purpose: imports key “entry” modules to catch import-time errors.
- Currently imports:
  - `src.tray.entrypoint`
  - `src.gui.perkey`
  - `src.gui.calibrator`

### 5) Code Markers
- Purpose: informational scan for TODO/FIXME/HACK/etc.
- Does not fail the build by default.
- Reports:
  - `buildlog/keyrgb/code-markers.json`
  - `buildlog/keyrgb/code-markers.csv`
  - `buildlog/keyrgb/code-markers.md`

### 6) File Size
- Purpose: informational report of unusually large Python files.
- Thresholds are in `buildpython/steps/step_size.py`.
- Reports:
  - `buildlog/keyrgb/file-size-analysis.json`
  - `buildlog/keyrgb/file-size-analysis.csv`
  - `buildlog/keyrgb/file-size-analysis.md`

### 7) Ruff Format (optional)
- Command: `ruff format --check src`
- Purpose: formatting consistency.
- Behavior: auto-skips if `ruff` is not installed.

### 8) Pip Check
- Command: `python -m pip check`
- Purpose: detect broken/mismatched installed dependencies.

### 9) Import Scan
- Purpose: parse Python files for imports and attempt to import them.
- Behavior:
  - Treats `PyQt6` as optional.
  - Excludes `src/tests/` so integration/hardware tests don’t break CI.
  - Treats legacy Tuxedo-only modules as optional (e.g. `backlight_control`).
  - Treats other missing third-party imports as failures.
  - Adds repo root and vendored `ite8291r3-ctl/` to `sys.path` to match runtime.

### 10) Repo Validation
- Purpose: quick sanity checks for a “public repo” baseline.
- Checks (non-exhaustive):
  - required top-level files exist (`README.md`, `LICENSE`, `install.sh`, `pyproject.toml`, `requirements.txt`)
  - `requirements.txt` does not hard-require `PyQt6` (it should remain optional)
  - `pyproject.toml` has expected metadata (optional `qt` extra, project URL pointing to Rainexn0b/keyRGB)
  - `install.sh` appears to set up autostart
- Behavior:
  - Errors fail the step.
  - Warnings are informational.
