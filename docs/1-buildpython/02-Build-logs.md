# Build logs

`buildpython` writes per-step logs plus structured summary and debt reports under `buildlog/keyrgb/`.

## Location

All build runner output goes to:

- `buildlog/keyrgb/`

## Always-written outputs

Every selected step writes a standard step log such as:

- `step-01-compile.log`
- `step-18-coverage.log`
- `step-19-exception-transparency.log`

The runner initializes incomplete summaries before executing steps, checkpoints progress, and finalizes the following on completion or stop-on-first-failure:

- `build-summary.json`
- `build-summary.md`
- `debt-index.json`
- `debt-index.md`

`build-summary.*` describes status, duration, all selected step outcomes, skip reasons, run ID, UTC start time, and current report names. JSON schema version 2 removes the aggregate `health_score`; per-step `health` is either null or an object with `label` and `score` (a finding penalty score, independent of pass/fail). Markdown includes the same scores; consumers should read `status`, `counts`, `exit_code`, and `passed` (true only for a complete pass). An incomplete checkpoint has `completed: false` and no final exit code.

`debt-index.*` combines only reports produced in that run (`scope: current_run`). Standalone inventory calls can explicitly list the latest files on disk (`scope: latest_available`); that scope does not imply a single build. Canonical artifacts from older runs remain on disk; use `report_names` and each step's log path in the current build summary to identify current evidence. A lock prevents concurrent writers to this directory.

## Structured report outputs

When their steps run, debt-focused checks write structured reports under the same directory. Current report families include:

- `code-markers.{json,csv,md}`
- `file-size-analysis.{json,csv,md}`
	Contains file-size buckets (`350-399`, `400-499`, `500-599`, `600+`), long import-block hotspots, flat-directory hotspots, middle-man modules, and unreferenced-file candidates.
- `loc-check.{json,csv,md}`
	Contains LOC buckets for non-test Python files (`350-399`, `400-449`, `450-549`, `550+`) and relaxed test-file buckets (`400-449`, `450-499`, `500-600`, `601+`).
- `code-hygiene.{json,csv,md}`
- `architecture-validation.{json,csv,md}`
- `coverage-summary.{json,csv,md}`
- `exception-transparency.{json,csv,md}`

Architecture validation uses lexical AST evidence. It canonicalizes ordinary
`time` and `subprocess` import aliases, but does not infer dynamic object
aliases. The secondary-device rule checks its configured primary receiver
spellings (including `tray.engine` and `self.tray.engine`); generic
`engine` and secondary-target receivers remain outside that rule.

Coverage also maintains internal capture and export artifacts. A new build invalidates the previous capture marker; Step 18 requires successful pytest coverage capture in the same invocation. Run `--run-steps=2,18` when selecting coverage explicitly.

## Step log format

Each step log uses the same plain-text structure:

```text
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

## Summary and debt snapshot behavior

- `build-summary.md` includes a debt snapshot section for reports generated in the current run.
- `debt-index.md` aggregates available sections such as coverage, exception transparency, code hygiene, code markers, LOC, file size, and architecture validation.
- Coverage can report `waiting for pytest coverage capture` if Step `18` runs without fresh coverage data from Step `2`.

If that happens, rerun one of:

```bash
python -m buildpython --run-steps=2,18
python -m buildpython --profile=debt
python -m buildpython --profile=full
```

## What to ask for when debugging

For build runner failures or debt regressions, ask for:

- the failing `step-*.log`
- `build-summary.json` or `build-summary.md`
- `debt-index.json` or `debt-index.md`
- the relevant structured report family if the failure is debt-related
- the exact `python -m buildpython ...` command

That is usually enough to reconstruct the runner state without reproducing the whole environment first.
