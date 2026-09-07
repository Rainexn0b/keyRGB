# Tool policy

Status: **Done**

## Purpose

Static gates must fail on real policy regressions. Informational-only scans
cannot protect layering, unused symbols, or installer shell.

## Contract

| Tool | Default gate | Policy |
|---|---|---|
| mypy | yes | `keyrgb/core`, `keyrgb/tray`, `keyrgb/gui`, `buildpython`, `scripts/release`, `tests/buildpython`. Typed against the 3.10 floor. `warn_unused_ignores`, `warn_redundant_casts`, and `no_implicit_optional` are on. Unrelated host stub packages that KeyRGB does not import (`numpy`) are skipped so newer stub syntax cannot fail the gate. |
| Dead code | yes | vulture findings are reported; unused functions/classes/imports in non-test runtime code fail the step. Unused protocol kwargs stay informational. |
| Architecture rules | yes | Configured warning and error findings both fail Step 17. `keyrgb/gui/perkey/hardware.py` is the per-key hardware bootstrap and is excluded from the backend-selection rule. |
| LOC Check | yes | Monitor stays informational. Refactor, critical, and severe fail Step 12. Typed `@quality-exception loc-check:` waivers remain the escape hatch for cohesive ownership units. |
| Code Markers | yes | `TODO`, `FIXME`, and `HACK` fail Step 5 when counts rise above the checked-in baseline. `NOTE` stays informational. |
| ShellCheck | yes when installed | Every managed installer/helper script is linted with `shellcheck -x`. CI installs ShellCheck. Local runs skip if the binary is missing. |

## Non-goals

- Typing the full Tk GUI surface
- Treating unused function arguments as dead code
- Requiring ShellCheck in every local developer venv
