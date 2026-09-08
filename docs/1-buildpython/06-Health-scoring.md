# Health scoring

Health bars start at **100%** and deduct points for each reported occurrence,
with a floor of zero. They express finding penalties within the configured scan
scope. They do not measure architectural completeness or determine pass/fail.
A warning can reduce health while a step passes; one architecture error produces
75% and fails the gate. Adding a rule without finding a violation leaves 100%.

The same bars appear in compact and verbose output, locally and in CI.
`build-summary.json` stores each step's `health` (`label`, `score`), or null when
unscored. Markdown includes the same percentage. No aggregate build health is
computed: the build result continues to report actual step outcomes.

## Deductions per occurrence

| Step | Penalty points |
|---|---|
| Ruff | 5 per lint diagnostic |
| Type Check | 10 per mypy error |
| Architecture Validation | 25 per error; 5 per warning |
| Code Markers | 20 per occurrence of a baseline-configured gated marker |
| File Size | File buckets: refactor 3, critical 10, severe 20, extreme 30; import buckets: warning 0.5, critical 4, severe 10; flat directory 2, delegation candidate 5, middleman module 2, unreferenced file 8 |
| LOC Check | Monitor 0.25, refactor 5, critical 12, severe 25 |
| Code Hygiene | 20 for forbidden_api/resource_leak/silent_broad_except/any_type_hint; 8 for forbidden_getattr/hasattr_coupling/runtime_copy_hotspot/test_naming; 4 for other active categories |
| Exception Transparency | Naked except or BaseException catch 30; unlogged broad except 20; logged without traceback 8; logged with traceback 5 |
| Dead Code | 20 per actionable candidate |

These retain the original scanner weights. Fractional deductions are preserved;
every LOC monitor occurrence now counts without the previous ten-point bucket
cap. Ruff and Type Check gain scores from their diagnostic summary counts, which
avoid double-counting source excerpts. A failed gate no longer imposes a separate
49% ceiling: only findings determine the penalty score.

Suppressed/waived findings are excluded where the source report supplies active
counts. Accepted baseline debt still deducts if it remains in those counts.
Skipped checks receive no score. Structured scores use only reports refreshed
by the current step; absent, unreadable, or unusable count data does not default
to 100%. Unrecognized Ruff/mypy output has no score, including startup failures.

Compile, packaging, dependency probes, format checks, and other steps without a
configured finding score retain their outcomes. Pytest reports its actual outcome
counts. Coverage retains its actual measured percentage even if its gate fails;
it is not a penalty score.

Implementation: `buildpython/core/runner_support/health.py`. Regression coverage:
`tests/buildpython/test_buildpython_health_scoring_unit.py` and
`tests/buildpython/test_buildpython_reporting_unit.py`.

## Validation — 2026-09-08

`.venv/bin/python -m buildpython --profile=ci` passed all 18 steps:
4,136 tests passed and 3 skipped. Current scores include Architecture 100%
(24 rules, 611 files, zero findings), File Size 93.5% (13 import warnings), and
LOC 91% (36 monitor findings). All nine scored steps were verified in the JSON
summary, with matching Markdown values.

Isolated real-tool checks with two intentionally introduced findings produced
Ruff 90% and Type Check 80%, both with exit code 1. Regression tests also cover
passing architecture warnings, repeated deductions, the zero floor, fractional
penalties, stale/missing data, and compact/verbose output parity.
