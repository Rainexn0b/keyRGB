# Exception transparency quality gate

## Problem statement

KeyRGB has a real broad-exception debt problem today.

The repo is intentionally defensive around hardware access, tray startup, optional integrations, GUI fallback paths, and config recovery. That is appropriate for a Linux hardware utility. The current implementation problem is that broad `except Exception:` handlers are widespread, and many of them still hide the failure reason or degrade behavior without a traceback.

That means a runtime path can look "stable" while actually masking:

- permission failures
- HID disconnects
- missing sysfs nodes
- optional integration breakage
- normal application bugs

The result is silent or weakly-signaled failure instead of diagnosable failure.

## Reality check as of 2026-03-31

The Gemini summary is directionally correct, but the precise repo state is:

- Broad `except Exception:` handlers are widespread across `src/`.
- Naked `except:` is not currently the main problem in `src/`; it appears to be rare or absent in current application code.
- Existing buildpython automation already tracks broad-exception debt indirectly in `Code Hygiene`, but it does not express the policy clearly enough for an operational quality gate.

Initial buildpython scan from 2026-03-31:

- `broad_except_total = 638`
- `broad_except_unlogged = 591`
- `broad_except_logged_no_traceback = 13`
- `broad_except_traceback_logged = 20`
- `naked_except = 0`
- `baseexception_catch = 0`
- top current unlogged hotspot: `src/tray/pollers/idle_power/_actions.py` with 19 findings

The practical conclusion is:

- the immediate debt to track is broad-catch transparency
- naked except should still be tracked so it does not enter the repo later

## Policy

### Rule A: No naked except

Ban `except:`.

Reason:

- it catches `KeyboardInterrupt`
- it catches `SystemExit`
- it makes CLI and interactive shutdown harder to reason about

### Rule B: Broad catch requires a diagnostic footprint

If a hot path must use `except Exception:` to prevent a user-facing crash, it must record a traceback.

Preferred signal:

```python
logger.exception("descriptive message")
```

Equivalent traceback-preserving patterns are acceptable, for example:

```python
logger.error("descriptive message", exc_info=True)
```

Non-traceback signals like `logger.warning(...)`, `print(...)`, or GUI notifications are better than silence, but they do not satisfy the long-term bar because they do not preserve the causal stack.

### Rule C: Specificity over generality

Prefer typed recovery where the code actually knows the expected failure mode.

Examples:

- `PermissionError`
- `FileNotFoundError`
- `OSError`
- backend-specific USB or HID exceptions

Broad catches should remain only at genuine process, hardware, or optional-integration boundaries.

## Best implementation approach

Ruff alone is not enough for this policy.

What Ruff can do well:

- `E722` can catch naked `except:`
- `BLE001` can catch blind `except Exception`

What Ruff cannot express cleanly for KeyRGB today:

- allow a broad catch only when it records a traceback
- separate broad catches that log a traceback from broad catches that only warn, print, or silently fallback
- introduce the gate as report-only first and ratchet it later against checked-in baselines

Because of that, the best near-term implementation is a custom buildpython AST scan.

## Buildpython implementation

Buildpython now includes a dedicated report-only step:

- Step 19: `Exception Transparency`

Artifacts:

- `buildlog/keyrgb/exception-transparency.json`
- `buildlog/keyrgb/exception-transparency.csv`
- `buildlog/keyrgb/exception-transparency.md`

Current tracked categories:

- `naked_except`
- `baseexception_catch`
- `broad_except_total`
- `broad_except_traceback_logged`
- `broad_except_logged_no_traceback`
- `broad_except_unlogged`

Waivers:

- Broad-handler findings may be waived for a single handler with `@quality-exception exception-transparency: ...` when the comment includes an explanation.
- Accepted forms are either a same-line comment on `except ...:` or a single immediately preceding comment line aligned with the `except` handler.
- An indented comment inside the `try` body does not waive the following handler.
- A bare marker or a missing explanation does nothing. `# @quality-exception exception-transparency` does not suppress findings.
- Intended use is narrow: legitimate runtime boundaries, process-boundary cleanup, or known scanner false positives that still need a short reason in code.

Example same-line waiver:

```python
except Exception:  # @quality-exception exception-transparency: optional shutdown cleanup boundary
    cleanup_best_effort()
```

Example preceding-line waiver:

```python
# @quality-exception exception-transparency: plugin hook boundary; host must stay alive
except Exception:
    return None
```

Interpretation:

- `broad_except_total` is the total inventory of broad handlers
- `broad_except_traceback_logged` is the current best broad-catch bucket
- `broad_except_logged_no_traceback` still needs improvement because the traceback is missing
- `broad_except_unlogged` is the main silent-failure debt bucket

## Why this is informational first

The repo already carries a large backlog of broad catches, so an immediate fail-on-sight gate would create churn without helping delivery.

The correct sequence is:

1. measure the current inventory
2. publish the hotspots in build artifacts
3. freeze the baseline
4. ratchet targeted categories until new debt cannot land

That is why the step is report-only today, but its JSON structure already supports regression gating later.

## Recommended ratchet order

1. Keep `naked_except` at zero and promote it to fail as soon as the baseline is confirmed.
2. Promote `baseexception_catch` to fail next unless a handler has a very explicit process-boundary justification.
3. Freeze `broad_except_unlogged` and ratchet it downward by hotspot.
4. After that, ratchet `broad_except_logged_no_traceback` downward until broad catches either become typed or traceback-logged.
5. Only after those counts stabilize should Ruff `BLE001` be considered as an always-on fail gate.

## Operational commands

Default debt sweep:

```bash
.venv/bin/python -m buildpython --profile debt
```

Focused run for the exception gate only:

```bash
.venv/bin/python -m buildpython --run-steps=19
```

Combined local review with the existing hygiene and architecture signals:

```bash
.venv/bin/python -m buildpython --run-steps=16,17,19 --continue-on-error
```

## Expected cleanup behavior

The goal is not to crash more often.

The goal is to make failure observable and attributable:

- name the exception when the code knows the failure mode
- log a traceback when the code must absorb a broad failure at runtime
- stop merging code that hides hardware or logic failures behind silent `pass` or fallback branches

## Related docs

- `docs/tech-debt/exception-handling-debt.md`
- `docs/tech-debt/buildpython-debt-automation.md`