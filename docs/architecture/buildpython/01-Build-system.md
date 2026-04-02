# Build system

`buildpython` is KeyRGB's step-based local and CI build runner. It executes named steps, writes per-step logs, and refreshes summary/debt reports under `buildlog/keyrgb/`.

## Goals

- Keep local validation and CI on the same commands.
- Make checks selectable by profile, name, or step number.
- Write structured outputs that are easy to inspect in CI, reviews, and follow-up cleanup work.

## Quick usage

Stable automation should prefer explicit profiles:

```bash
python -m buildpython --profile=ci
python -m buildpython --profile=debt
python -m buildpython --profile=full --with-black
python -m buildpython --profile=release
```

Useful discovery commands:

```bash
python -m buildpython --list-profiles
python -m buildpython --list-steps
python -m buildpython --run-steps=2,18,19
python -m buildpython --run-steps="Pytest,Coverage,Exception Transparency"
python -m buildpython --skip-steps="AppImage,AppImage Smoke"
python -m buildpython --continue-on-error
python -m buildpython --verbose
```

Bare `python -m buildpython` is not a named profile. It selects the live step registry except `Black`, so it can include packaging steps such as `AppImage` and `AppImage Smoke`. For reproducible automation, use a profile.

## Current profiles

- `ci`: compile, import validation, import scan, pip check, pytest, coverage, exception transparency, architecture validation, and repo validation.
- `debt`: debt-focused checks including code markers, file size, LOC, code hygiene, coverage, exception transparency, architecture validation, and repo validation.
- `quick`: `ci` plus lightweight debt reporting such as code markers and file size.
- `full`: `quick` plus optional lint/type checks and deeper debt checks. `Black` stays opt-in through `--with-black`.
- `release`: `ci` plus `AppImage` and `AppImage Smoke`.

Optional-tool steps auto-skip when their tool is not installed:

- `Ruff`
- `Ruff Format`
- `Type Check`
- `Black`
- `Coverage` when `coverage` or `pytest` is unavailable

## Step coverage

The current registry has steps `1` through `19`. See the exact catalog in `docs/architecture/buildpython/01.1-Build-steps.md`.

The build runner mixes three kinds of work:

- execution checks such as `Compile`, `Pytest`, `Import Validation`, and `Pip Check`
- packaging checks such as `AppImage` and `AppImage Smoke`
- report-oriented debt checks such as `Code Markers`, `Code Hygiene`, `Coverage`, `Architecture Validation`, and `Exception Transparency`

## Typed quality-exception tags

Debt scanners can honor typed inline waivers. The current high-level format is:

```python
# @quality-exception <step-slug>: short reason
```

Example used by the exception transparency scan:

```python
# @quality-exception exception-transparency: optional runtime boundary for startup fallback
```

The step slug scopes the waiver to one checker. A tag for `exception-transparency` does not waive findings for other debt steps.

## Logs and structured reports

All selected steps write logs under `buildlog/keyrgb/`. The runner also refreshes:

- `build-summary.json`
- `build-summary.md`
- `debt-index.json`
- `debt-index.md`

Debt-focused steps write structured reports under the same directory when they run. Current examples include:

- `code-markers.{json,csv,md}`
- `file-size-analysis.{json,csv,md}`
- `loc-check.{json,csv,md}`
- `code-hygiene.{json,csv,md}`
- `architecture-validation.{json,csv,md}`
- `coverage-summary.{json,csv,md}`
- `exception-transparency.{json,csv,md}`

`build-summary.md` includes the overall build state plus a debt snapshot of available structured reports. `debt-index.md` is the combined report index for debt-oriented outputs.

## Related docs

- Step catalog: `docs/architecture/buildpython/01.1-Build-steps.md`
- Extending the runner: `docs/architecture/buildpython/01.2-Extending-buildpython.md`
- Log/report behavior: `docs/architecture/buildpython/02-Build-logs.md`
- CI usage: `docs/architecture/buildpython/03-CI.md`
