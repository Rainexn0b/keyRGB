# Tool policy

Status: **Done**

## Purpose

Static gates must fail on real policy regressions. Informational-only scans
cannot protect layering, unused symbols, or installer shell.

## Contract

| Tool | Default gate | Policy |
|---|---|---|
| mypy | yes | `keyrgb/core`, `keyrgb/tray`, `buildpython`, `scripts/release`, `tests/buildpython`, plus a narrow non-Tk GUI baseline. `warn_unused_ignores`, `warn_redundant_casts`, and `no_implicit_optional` are on. Tk-heavy GUI is still excluded. |
| Dead code | yes | vulture findings are reported; unused functions/classes/imports in non-test runtime code fail the step. Unused protocol kwargs stay informational. |
| Architecture rules | yes | Configured warning and error findings both fail Step 17. `keyrgb/gui/perkey/hardware.py` is the per-key hardware bootstrap and is excluded from the backend-selection rule. |
| ShellCheck | yes when installed | Every managed installer/helper script is linted with `shellcheck -x`. CI installs ShellCheck. Local runs skip if the binary is missing. |

## Non-goals

- Typing the full Tk GUI surface
- Treating unused function arguments as dead code
- Requiring ShellCheck in every local developer venv
