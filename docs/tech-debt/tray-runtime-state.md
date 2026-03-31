# Tray runtime state and orchestration debt

## Problem

The tray runtime currently owns too much mutable state and coordinates too many behaviors directly. `KeyRGBTray` is responsible for startup, backend selection, notification buffering, power state, effect state, UI refreshes, and poller wiring.

That centralization helped the project move quickly, but it now makes the runtime harder to reason about and harder to refactor safely.

## Evidence

- Central state holder:
  - `src/tray/app/application.py`
- High-coupling controller paths:
  - `src/tray/controllers/lighting_controller.py`
  - `src/tray/controllers/_lighting_controller_helpers.py`
  - `src/tray/app/callbacks.py`
- Poller-driven coordination:
  - `src/tray/pollers/config_polling.py`
  - `src/tray/pollers/config_polling_internal/core.py`
  - `src/tray/pollers/idle_power/_actions.py`
  - `src/tray/pollers/idle_power_polling.py`

Examples of state that currently spans multiple concerns:

- `_power_forced_off`
- `_user_forced_off`
- `_idle_forced_off`
- `_dim_temp_active`
- `_dim_temp_target_brightness`
- `_pending_notifications`
- `_permission_notice_sent`

## Risks

- Ordering bugs between pollers, menu actions, and power transitions.
- More private-attribute reads and writes across modules.
- Tests must patch deep runtime behavior instead of isolated services.
- The tray app remains a growth bottleneck for future features.

## Desired end state

- A typed runtime state object, not a loose cluster of private flags.
- Clear separation between:
  - state transitions
  - hardware side effects
  - tray UI refreshes
  - background polling
- Smaller controller surfaces with explicit inputs and outputs.

## Suggested slices

1. Introduce a typed tray state model and migrate the forced-off and dim flags into it.
2. Isolate transition logic into a small coordinator or reducer-style module.
3. Keep `KeyRGBTray` as wiring and lifecycle, not as the main decision engine.
4. Remove remaining private-attribute compatibility shims once the typed state is in place.

## Buildpython hooks

- Existing signals:
  - LOC Check flags large modules.
  - File Size highlights structural hotspots.
  - Code Hygiene already tracks `forbidden_getattr`, `hasattr_coupling`, and cleanup hotspots.
  - Architecture Validation protects some layer boundaries.
- Useful next increment:
  - Add a lightweight architecture rule that prevents new tray UI modules from reading internal tray state directly.