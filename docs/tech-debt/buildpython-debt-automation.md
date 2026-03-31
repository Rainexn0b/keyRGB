# Using buildpython to track debt and exception cleanup

## What buildpython already gives us

The repo already has a good foundation for debt tracking:

- Step 5: Code Markers
- Step 6: File Size
- Step 12: LOC Check
- Step 16: Code Hygiene
- Step 17: Architecture Validation
- `buildlog/keyrgb/build-summary.md` includes a debt snapshot built from the report outputs.
- `buildpython/config/debt_baselines.json` stores checked-in baselines for marker and hygiene categories.

The most relevant existing signal for the March 2026 review is step 16, because it already breaks broad exception handling into:

- `silent_broad_except`
- `logged_broad_except`
- `fallback_broad_except`

## Recommended workflow

Use the debt-focused buildpython profile for quick local sweeps:

```bash
.venv/bin/python -m buildpython --profile debt
```

That should be the default command when working on:

- exception cleanup
- state-model cleanup
- large-file splits
- architecture boundary work

The `Coverage` step now expects a fresh capture from the `Pytest` step instead of silently launching the whole suite on its own. This keeps `--run-steps=18` predictable and makes long test runs explicit in the selected profile.

Use the full profile before landing larger refactors:

```bash
.venv/bin/python -m buildpython --profile full
```

## What the current reports are good at

- Counting broad exception debt and highlighting hotspots.
- Tracking cleanup markers and legacy shims.
- Flagging large files and growth trends.
- Catching architecture boundary regressions.
- Showing a concise debt snapshot after a build run.

## Current state after the March 2026 automation pass

1. Coverage debt is now tracked in buildpython.
   - The Coverage step writes `coverage-summary.json`, `coverage-summary.csv`, and `coverage-summary.md`.
   - The Pytest step reuses coverage capture when coverage.py is available, so default runs do not need to execute the test suite twice.
2. Exception baselines are now tracked both repo-wide and per-path.
   - Code Hygiene still enforces category baselines, and now also supports per-path exception budgets for selected hotspot modules.
3. A combined debt index now exists.
   - `buildlog/keyrgb/debt-index.json` and `buildlog/keyrgb/debt-index.md` merge the main debt signals into one artifact.

## Recommended next increments

1. Keep baselines strict for new regressions.
   - Existing debt can remain report-first, but new debt should not grow unnoticed.
2. Expand coverage tracking beyond total and prefix-level signals.
   - The next good increment is backend-family or subsystem-specific coverage gates once the current baselines settle.
3. Add debt-ID mapping if desired.
   - The current index aggregates report signals, but it does not yet attach them to specific `docs/tech-debt/*.md` backlog IDs.

## Practical mapping from debt docs to buildpython

| Debt area | Current buildpython signal | Best next step |
|---|---|---|
| Broad exception debt | Code Hygiene step 16 | Per-path budgets |
| Tray state sprawl | LOC Check, File Size, forbidden private-attr access | Add more boundary rules |
| Backend confidence | Pytest only | Add coverage step |
| Backend duplication | File Size, LOC, Architecture Validation | Add shared-layer boundary rule |
| Polling complexity | File Size, LOC, exception hotspots | Track poller growth in summary |