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

At the end of a run, and also on stop-on-first-failure, the runner refreshes:

- `build-summary.json`
- `build-summary.md`
- `debt-index.json`
- `debt-index.md`

`build-summary.*` describes build status, health score, duration, step outcomes, and a debt snapshot assembled from any structured reports that are available.

`debt-index.*` is the combined index for debt-oriented reports that were produced in that run.

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

Coverage also maintains internal capture and export artifacts used by the coverage summary step.

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

- `build-summary.md` includes a debt snapshot section when structured debt reports exist.
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
