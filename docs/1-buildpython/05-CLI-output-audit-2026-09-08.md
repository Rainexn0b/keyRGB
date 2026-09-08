# Buildpython CLI output and log audit — 2026-09-08

Scope: buildpython's help/selectors, step catalog, terminal output, per-step logs,
build summaries, debt index, coverage capture, optional tools, and packaging
skip paths. This follows the
[architecture enforcement audit](04-Architecture-enforcement-audit-2026-09-08.md).

Follow-up: the user clarified that health bars are intentional penalty scores.
Per-step bars have been restored and extended to Ruff and Type Check; see
[the scoring contract](06-Health-scoring.md). The removal below records the
initial audit change, which this follow-up supersedes. Current-run filtering,
outcome integrity, and measured coverage remain in place.

## Findings and changes

| Finding | Result |
|---|---|
| “Architecture Health 100%” implied completeness; other scanner scores used arbitrary weights | Removed synthetic step and build health scores/bars. Print configured rules, files, findings, and actual test outcomes instead. |
| Failure caps could display measured 90% coverage as 49% | Coverage retains the measured percentage, independently of gate status. Missing measurement is unavailable, never fabricated as zero. |
| Pytest summary parsing could drop a failed prefix while matching the passed suffix | Extract every outcome count from the final pytest result line, preserving failures, errors, skips, expected failures, deselections, and warnings. |
| Skipped checks could leave a PASS/100 summary | Explicit PASS, FAIL, PARTIAL, NOT RUN, and INCOMPLETE statuses; no percentage. PASS requires every selected step to succeed. |
| Fail-fast summaries counted only attempted steps | Record every selected step; later steps become `not_run` with no exit code or current log link. |
| AppImage smoke and coverage runners returned success for an internal skip | Added `RunResult.skip_reason`; step log, terminal, and build-summary detail agree about the skip. |
| AppImage staging-only could claim a finished build and smoke an old artifact | Staging-only records that no AppImage was built. Smoke is skipped if the preceding selected AppImage build failed or skipped. Smoke-only selection may intentionally test an existing artifact. Dependency-install opt-outs are also printed in the build log/terminal. |
| Old reports could appear in a new build's highlights, summary, and debt index | Track report rewrites per owning step. Aggregate only current report names; expected JSON reports must be freshly produced and readable for a step to pass. |
| Coverage freshness meant only that capture files existed | Clear the capture marker when a new build begins. Step 18 requires a successful pytest coverage capture in the same invocation. |
| An interrupted build could leave the previous PASS summary and successful step log | Checkpoint incomplete status before/after steps. Overwrite the active step log before execution; record traceback on an exception, SystemExit, or KeyboardInterrupt, then re-raise. |
| Concurrent writers could mix report sets | Nonblocking process lock on the shared build-log directory rejects a second writer before it changes summaries or captures. |
| Import Scan silently ignored unreadable or invalid Python | Report source/parse errors and fail the step; describe the actual external top-level import scope. |
| GUI import skips and repository warnings were hidden in compact output | Show checked import counts, GUI omissions, and repository warning notices. |
| Suppressed/waived counts appeared as unexplained parenthesized numbers | Label them explicitly; unused-code output separates all candidates from actionable findings. |
| CLI help/catalog had drifted from commands | Fix single multiword step selectors, reject unknown skip selectors, describe the actual compile/type-check scope, forced hardware-test exclusion, and default full-profile selection. |

Step-17-only output after restoring penalty bars reads, for example:

```text
Architecture Health: [████████████████████] 100% (penalty score)
Rules checked: 24 | Files scanned: 610 | Errors: 0 | Warnings: 0
PASS · 1.5s · 1 selected · 1 passed · 0 failed · 0 skipped · 0 not run
```

No coverage from a previous build is attached to that result.

## Outcome and artifact contract

- `PASS`: all selected steps succeeded. It does not cover unselected checks,
  skipped tests inside pytest, unscanned architectural patterns, or real hardware.
- `PARTIAL`: some selected checks succeeded and others were skipped/not run.
- `NOT RUN`: no selected check succeeded and none failed, including all-skipped
  selection. Optional skips preserve exit code 0 for shell compatibility.
- `FAIL`: at least one selected check failed. Exit status preserves the first
  failure, including `--continue-on-error` runs.
- `INCOMPLETE`: no final result was recorded. Checkpoints contain the last known
  step state; `running` in a checkpoint is not proof that a process is still alive.

`build-summary.json` is now schema version 2. It contains `status`, `passed`,
`counts`, `exit_code`, `completed`, a run ID and UTC start time, all selected
`steps`, and `report_names`. `health_score` was removed. `passed` is true only for
a complete pass; a partial run can have `passed: false` and `exit_code: 0`.
Step summaries retain skip explanations and paths to the logs from attempted
steps. Running/not-run steps have no completed exit code.

Per-step logs explicitly distinguish running, success, failure, skipped, and
aborted states. They preserve returned stdout and stderr; a failure has a log
pointer even when continuing. Unexpected runner exceptions are recorded with a
full traceback and re-raised. The one broad catch is a documented CLI logging
boundary, covered by assertion, SystemExit, and interrupt tests; it does not
convert programming errors into a successful result.

Old standalone reports remain on disk. The current build summary and
`debt-index` include only artifacts produced by this run. Direct inventory calls
without a run filter explicitly use `scope: latest_available`; production build
indexes use `scope: current_run`. Artifact freshness is based on a changed
mtime/size stamp under the exclusive writer lock. This is a build-run ownership
check, not a cryptographic attestation or archive of earlier source revisions.

## Audit boundaries

Reviewed all 21 registered step descriptions and their result paths. Compile
checks `keyrgb/`; Import Scan probes external top-level modules; Type Check uses
its explicit package/script/test roots. Static scanners still enforce their
configured patterns and baselines, not complete absence of defects. Architecture
scanner limits remain in the previous audit.

The runtime-log-capture CLI branch delegates to the diagnostics implementation.
Its launcher, command, working directory, flags, and exit propagation were
reviewed alongside the existing adapter tests; no live hardware capture was
started. Packaging branches were tested with temporary artifacts and mocked
tool availability; this audit did not build or publish a release or run Docker.

## Validation

- Exact user command `.venv/bin/python -m buildpython`: 18/18 selected steps
  passed; 4,091 tests passed, 1 skipped at the first complete validation.
- Standalone Step 17: factual counts, no health percentage or stale coverage.
- Standalone Step 18 without same-run pytest: exit 1 and coverage unavailable.
- Final focused buildpython suite: **392 passed**.
- Final CI profile: **18/18 steps passed; 4,095 tests passed, 1 skipped**.
- Inspected final JSON/Markdown: schema v2 status/counts agree, eight current-run
  report families, no synthetic health field or stale report contributions.
- `git diff --check`: passed.

Regression cases exercise mixed pytest outcomes; failure-independent coverage;
partial/all-skipped builds; fail-fast and continue-on-error; stale/missing
reports; abnormal termination; concurrent writers; capture invalidation;
AppImage skip/staging behavior; source-read failures; and CLI selectors.

Reproduce:

```bash
.venv/bin/python -m pytest -q -o addopts= tests/buildpython
.venv/bin/python -m buildpython
.venv/bin/python -m buildpython --profile=ci
git diff --check
```
