# Extending buildpython

This document explains how to add new build steps and profiles.

## Add a new step

1) Implement a runner that returns `RunResult`.
- For external commands, prefer `buildpython.utils.subproc.run()`.
- For internal analysis steps, construct a `RunResult` directly.

2) Add the step definition in `buildpython/steps/step_defs.py`.
- Assign a unique `number`
- Choose a stable `name` (used by `--run-steps=Name`)
- Pick a log filename under `buildlog/keyrgb/`

3) Decide whether the step is optional.
- If it depends on an optional tool, make it auto-skip in `buildpython/core/runner.py`.

## Add/update a profile

Profiles are in `buildpython/core/profiles.py`.

- Keep `ci` fast and deterministic.
- Put expensive or developer-only checks in `full`.

## Make steps non-flaky

Rules of thumb:
- Don’t require real hardware in the default profiles.
- Don’t depend on network access.
- Prefer analysis that works from the repo contents.

## Logs

All steps should write logs in the standard format under `buildlog/keyrgb/`.

When changing log output, keep it:
- Plain text
- Machine-parsable
- Without ANSI color codes
