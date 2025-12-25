# Build system

KeyRGB includes a lightweight build/check runner implemented in Python under `buildpython/`.

It is inspired by the step-based “enhanced build system” pattern (profiles + step selection + structured logs), but only includes checks that make sense for this repo.

## Goals

- Make it easy to run the same checks locally and in CI
- Keep output readable in the terminal
- Write machine-parsable logs for debugging and PR review

## Quick usage

Run the default steps (same as `--profile=full` behavior may differ depending on optional tools installed):

```bash
python3 -m buildpython
```

Run the CI profile (fast, deterministic):

```bash
python3 -m buildpython --profile=ci
```

List available profiles:

```bash
python3 -m buildpython --list-profiles
```

List steps:

```bash
python3 -m buildpython --list-steps
```

Run specific steps (by number or name):

```bash
python3 -m buildpython --run-steps=1,2
python3 -m buildpython --run-steps="Compile,Pytest"
```

Skip steps:

```bash
python3 -m buildpython --skip-steps="Ruff,Ruff Format"
```

Verbose output (prints stdout/stderr for steps):

```bash
python3 -m buildpython --profile=ci --verbose
```

Continue even if a step fails:

```bash
python3 -m buildpython --profile=full --continue-on-error
```

## Compatibility wrapper

For historical reasons, there is a small wrapper script:

- `scripts/build/keyrgb-build.py`

It delegates to `buildpython` so older docs/aliases continue to work:

```bash
python3 scripts/build/keyrgb-build.py --profile=ci
```

## Profiles

- `ci`: compile + import validation + pip check + import scan + pytest
- `quick`: `ci` plus lightweight analysis steps
- `full`: `quick` plus optional lint/format checks (if installed)

## Steps

Typical steps include:

- **Compile**: `python -m compileall -q src`
- **Import Validation**: imports core modules (catches missing dependencies / import errors)
- **Pytest**: `pytest -q -o addopts=`
- **Ruff** (optional): `ruff check src`
- **Ruff Format** (optional): `ruff format --check src`
- **Pip Check**: `python -m pip check`
- **Import Scan**: parses imports and validates required modules import
- **Code Markers**: scans for TODO/FIXME/HACK/etc. (informational)
- **File Size**: reports very large Python files by line count (informational)

Notes:
- Hardware tests remain opt-in: set `KEYRGB_HW_TESTS=1` if you explicitly want to run them.
- Ruff-based steps auto-skip if `ruff` isn’t installed.

## Logs

Logs are written to:

- `buildlog/keyrgb/`

Each step produces a `.log` file using the standardized format:

```
=== Step Name - 2025-12-25T12:34:56.789Z ===
Command: command-that-was-run
Duration: (X.Xs)
Exit Code: N

=== STDOUT ===
...

=== STDERR ===
...

=== END ===
```

The `buildlog/` directory is ignored by git.

## CI integration

GitHub Actions runs `python -m buildpython --profile=ci` as the single source of truth.

More detail:
- Step descriptions: `docs/architecture/02-Build-steps.md`
- Log format: `docs/architecture/03-Build-logs.md`
- CI overview: `docs/architecture/04-CI.md`
