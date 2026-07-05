# Code Hygiene & Static Analysis

KeyRGB enforces strict code hygiene and static analysis in CI and local builds. The build runner includes:

- Defensive conversion checks (e.g., unnecessary int(int(x)))
- Dynamic attribute coupling checks (hasattr/setattr/getattr/delattr on private attributes)
- Excessive `Any` type hint checks
- Forbidden API usage checks (`os.system`, `eval`, `exec`)
- Resource leak checks (`open()` not used in a `with` context or without `.close()`)
- Silent broad exception checks (`except Exception: pass` / bare swallow paths)
- Broad exception debt is split into `silent`, `logged/signaled`, and `fallback` buckets in the report output.
- Test naming and structure checks

Run the hygiene step directly:

```bash
.venv/bin/python -m buildpython --run-steps=16
```

Run the full debt-oriented static sweep:

```bash
.venv/bin/python -m buildpython --profile debt
```

Run the standalone coverage debt step:

```bash
.venv/bin/python -m buildpython --run-steps=18
```

If step 18 reports a missing coverage capture, generate it first:

```bash
.venv/bin/python -m buildpython --run-steps=2,18
```

All new code should pass these checks. See `buildpython/steps/step_code_hygiene.py` for details and thresholds.
Some hygiene categories are currently report-first and do not fail the build until their thresholds are tightened.

The generated reports now include hotspot sections so debt is easier to track over time:

- `buildlog/keyrgb/code-hygiene.md` highlights top files for exception debt, cleanup debt, forbidden APIs, and resource leaks.
- Exception debt is split into silent, logged/signaled, and fallback hotspot tables.
- Code Hygiene now also enforces per-path budgets for selected exception hotspots.
- `buildlog/keyrgb/code-markers.md` highlights top files for `HACK`, `FIXME`, and `TODO` markers.
- `buildlog/keyrgb/coverage-summary.md` tracks total coverage, configured coverage prefixes, and watch-file coverage for debt-heavy areas.
- `buildlog/keyrgb/debt-index.md` combines the current debt signals into one report.
- The Coverage step is a reporting step, not a hidden full-suite test launcher. It summarizes fresh coverage captured by the Pytest step.

Debt baselines are checked in at `buildpython/config/debt_baselines.json`.

- Code Hygiene now reports `baseline` and `delta` per category.
- Code Markers now reports `baseline` and `delta` per marker.
- Regression-gated categories and markers fail the build only when counts rise above the checked-in baseline.
