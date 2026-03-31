# Exception handling debt

## Problem

KeyRGB is intentionally defensive around hardware access, tray startup, and GUI fallbacks. That is the right instinct for a Linux hardware utility, but the repo currently relies on broad exception handling too often, and many handlers silently swallow failures or downgrade behavior without enough signal.

The result is a codebase that is resilient in the short term but expensive to debug when behavior regresses.

## Evidence

- `buildlog/keyrgb/code-hygiene.md` currently reports:
  - `silent_broad_except = 280`
  - `logged_broad_except = 33`
  - `fallback_broad_except = 308`
- Top silent hotspots include:
  - `src/tray/pollers/idle_power/_actions.py`
  - `src/tray/app/application.py`
  - `src/tray/controllers/lighting_controller.py`
  - `src/core/effects/engine_start.py`
- Representative code paths:
  - `src/tray/app/backend.py`
  - `src/tray/app/application.py`
  - `src/tray/controllers/lighting_controller.py`
  - `src/gui/windows/reactive_color.py`
  - `src/core/config/config.py`

## Risks

- Real logic bugs look like harmless degraded mode.
- Permission and device-disconnect failures are inconsistently surfaced.
- Tests can pass while production hides a different failure path.
- New contributors do not know which broad catches are intentional hardware guards and which are just accumulated defensive code.

## Desired end state

- Broad exception handling remains only at true process or hardware boundaries.
- Hot-path `except Exception:` blocks are narrowed to known failure types.
- Every fallback branch either logs once, emits a user-facing signal, or records structured diagnostics.
- The code distinguishes between:
  - hardware unavailable
  - permissions missing
  - optional integration absent
  - internal logic error

## Suggested slices

1. Clean up tray startup and backend introspection first.
   - Target: `src/tray/app/backend.py`, `src/tray/entrypoint.py`, `src/tray/app/application.py`
2. Normalize effect/runtime exception policy.
   - Target: `src/core/effects/engine_start.py`, `src/tray/controllers/lighting_controller.py`
3. Make GUI fallbacks explicit rather than silent.
   - Target: `src/gui/windows/reactive_color.py`, `src/gui/windows/uniform.py`, `src/gui/perkey/editor.py`
4. Replace broad config fallbacks with typed recovery helpers.
   - Target: `src/core/config/config.py`, `src/core/config/_coercion.py`

## Buildpython hooks

- Existing signal:
  - Code Hygiene step 16 already tracks `silent_broad_except`, `logged_broad_except`, and `fallback_broad_except`.
  - Build summaries already surface a debt snapshot from `buildlog/keyrgb/code-hygiene.json`.
- Useful next increment:
  - Add per-path hotspot budgets so regressions in a single module fail earlier than a repo-wide count increase.
- Workflow:

```bash
.venv/bin/python -m buildpython --profile debt
```