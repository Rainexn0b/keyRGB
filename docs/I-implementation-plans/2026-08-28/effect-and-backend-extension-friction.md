# Effect and Backend Extension Friction (2026-08-28)

## Purpose

Pre-1.0 maintainability: make **adding a shipped software/reactive effect or a
built-in backend** a registration-plus-test path, without changing user-visible
behaviour.

The app is feature-complete. This campaign does not add effects, does not
enable currently unlisted runners (`breathing`, `fire`, `rain`, `random`), and
does not split packages or adopt a `src/` layout.

## Why this is the work

Backends are already plugin-discovered: a package under
`keyrgb/core/backends/<name>/` exports `BACKEND_REGISTRATION` and
`registry.py` finds it. There is no central import list.

Software and reactive effects are not. A new loop today must be wired in
several places:

| Touch | Role |
|---|---|
| `effects/software/_effects_*.py` or `effects/reactive/` | implementation |
| `effects/software/effects.py` + `__init__.py` | public wrappers |
| `effects/catalog.py` `SOFTWARE_EFFECTS` / `REACTIVE_EFFECTS` | UI + membership |
| `engine_support/methods.py` | engine method shim |
| `engine_support/start.py` `_SW_START_SPECS` | start dispatch |

Tray menus already follow the catalog. If a runner is missing from the catalog
and `_SW_START_SPECS`, it never starts. That is why `run_breathing` /
`run_fire` / `run_rain` / `run_random` exist on disk but are not selectable.

The friction is duplicated dispatch, not package location.

## Non-goals

- No `src/` layout and no new installable packages.
- No move of `keyrgb.core.backends` / `keyrgb.core.effects` to root packages.
- No new user-visible effects, titles, menu order, or start-colour changes.
- No public entrypoint changes in `pyproject.toml`.
- No enabling of unlisted software runners.
- Hardware firmware effects stay backend-owned (`backend.effects()` +
  `hardware_effect_builder()`). `catalog.HW_EFFECTS` remains a generic name
  fallback, not an extension list.

## Target add paths

### Software or reactive effect

1. Implement `run_<name>(engine)` in `keyrgb/core/effects/software/` (or
   `reactive/` for typing effects).
2. Export `EFFECT_REGISTRATION` (or `EFFECT_REGISTRATIONS`) from that module.
3. Add a focused unit test.
4. Catalog names, titles, menu order, and engine start dispatch follow the
   marker. No edits to `catalog.py`, `methods.py`, or `_SW_START_SPECS`.

Optional: re-export `run_<name>` from `software/effects.py` only if callers
need a stable import path. Engine start must not require that wrapper.

### Built-in backend

Unchanged, already the model to copy:

1. Create `keyrgb/core/backends/<package>/`.
2. Export `BACKEND_REGISTRATION` from `__init__.py`.
3. Tests, diagnostics, and USB-ID evidence as today.

This campaign only adds a completeness tripwire: every backend package
directory must export a `BackendRegistration` marker (skip `policies/` and
`_*`).

## Contract

`keyrgb/core/effects/effect_contract.py` owns:

| Field | Meaning |
|---|---|
| `name` | Canonical effect id (catalog key) |
| `kind` | `software` or `reactive` |
| `runner` | `run_<name>(engine)` callable |
| `start_color` | `"current"` or an RGB tuple used for the pre-loop fade |
| `title` | Optional UI label; default titleizes `name` |
| `menu_order` | Stable UI order within `kind` |

`keyrgb/core/effects/registry.py` discovers markers from:

- every `*.py` module directly under `software/` that declares a marker
- every `*.py` module directly under `reactive/` that declares a marker
- any future `software/<pkg>/` package `__init__.py` with a marker

Discovery must not import unmarked reactive helpers (`render.py`, `input.py`,
…) just because they sit in the same directory. Pre-filter on the marker
name in source, then import.

Duplicate `name` values fail discovery loudly. Import errors in marked
modules fail loudly (in-tree effects are not optional plugins).

`catalog.py` derives `SOFTWARE_EFFECTS`, `REACTIVE_EFFECTS`, `SW_EFFECTS`,
`SW_EFFECTS_SET`, and titles from the registry. `HW_EFFECTS` stays a static
fallback list.

`_EngineStart.start_effect` looks up the registration and calls `runner(engine)`
directly. Per-effect `_effect_*` mixins in `methods.py` / `start.py` go away.
Fade / interval / prime helpers stay.

## Guardrails

- Preserve shipped names, titles, menu order, and start colours exactly:

  Software: `rainbow_wave`, `rainbow_swirl`, `spectrum_cycle`, `color_cycle`,
  `chase`, `twinkle`, `strobe`.

  Reactive: `reactive_fade`, `reactive_ripple`.

- Preserve public `run_*` wrappers on `keyrgb.core.effects.software` and
  `keyrgb.core.effects.reactive`.
- Do not register `breathing`, `fire`, `rain`, or `random`.
- `backend_caps` remains the tray capability-gating model.
- No new silent `except Exception` paths. Discovery import failures are not
  swallowed.
- Keep Linux-first assumptions. Prefer sysfs/kernel backends; USB remains
  fallback.

## Waves

| ID | Work | Priority | Effort | Status |
|---|---|:---:|:---:|---|
| W1 | `EffectRegistration` contract + discovery registry + catalog derivation + unit tests | P1 | M | done |
| W2 | Engine start uses registry; remove per-effect method shims | P1 | M | done |
| W3 | Backend package-marker completeness test | P2 | S | done |
| W4 | Living docs: `docs/1-src/16`, effects README, backend extension note | P2 | S | done |

## Validation

Focused (authoritative for this campaign):

```
.venv/bin/python -m pytest -q \
  tests/core/effects/catalog \
  tests/core/effects/engine \
  tests/core/effects/software \
  tests/core/backends/test_backend_registration_discovery_unit.py
```

Release-adjacent:

```
.venv/bin/python -m pytest -q tests/core/effects tests/core/backends tests/tray/controllers
.venv/bin/python -m buildpython --run-steps=13,17,19,20
```

Close the campaign only when `.venv/bin/python -m buildpython --profile=release`
is green.

## Acceptance

- Adding a software effect is: implementation module + `EFFECT_REGISTRATION` +
  test.
- `SOFTWARE_EFFECTS` / `REACTIVE_EFFECTS` / engine start agree with discovered
  markers (one source of truth).
- Shipped selectable effects, titles, order, and start colours are unchanged.
- Unlisted runners stay unlisted.
- Backend add path unchanged except the completeness tripwire.
- Public catalog helpers (`normalize_effect_name`,
  `resolve_effect_name_for_backend`, `hardware_effect_selection_key`, …) keep
  their signatures.

## Progress (2026-08-28)

W1–W4 landed in-tree. Shipped selectable names/titles/order/start colours are
unchanged. `breathing` / `fire` / `rain` / `random` remain implemented but
unregistered. Focused pytest: 130 passed on catalog/engine/software + backend
registration tests; 488 passed on `tests/core/effects` plus tray menu/controller
slices. `ruff` and `mypy` clean on the touched effect modules. The static usage
graph now treats `EFFECT_REGISTRATION` / `EFFECT_REGISTRATIONS` exactly like
backend registration roots, preventing dynamically discovered live effects
from being reported as unreferenced. The full release profile passed with
Health 100/100, 3,639 tests passed and 1 skipped, 90.24% coverage, and AppImage
build/smoke green; all 18 release steps, including ShellCheck, passed.

## Follow-up (out of scope)

- Delete or productize unlisted runners (`breathing` / `fire` / `rain` /
  `random`) — dead-code campaign, not this one.
- Auto-discover hardware effect names into `HW_EFFECTS` — those are
  backend-owned.
- Reactive loops beyond fade/ripple — still need the reactive API facade
  (`docs/1-src/16-effect-runtime-contracts.md`), not just a catalog marker.
