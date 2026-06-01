# Secondary-Device Power State Refactor Plan (2026-06)

## Purpose

This note captures a focused cleanup plan for secondary-device power semantics,
starting with lightbar behavior in the tray device-context menu.

## Execution status (2026-06-01)

Implemented in code:

- extracted shared secondary-device power helpers into
  `src/tray/secondary_device_power.py`
- moved current-brightness reads, off-state checks, restore hints, and restore
  target resolution behind that shared helper surface
- updated the tray secondary-device controller to use the shared helper for
  restore behavior
- updated device-context menu building to consume the shared helper for
  `Turn On` / `Turn Off` state
- added direct helper tests plus focused controller, callback, delegate, and
  menu regression coverage
- chose tray-runtime-only restore brightness hints for the current behavior

Still remaining:

- treat persisted secondary-device restore brightness as a future enhancement
  only if users need restore targets to survive app restarts

The immediate bug fix on `0.25.6` restored correct `Turn Off -> Turn On`
behavior by introducing a small tray-local last-nonzero brightness hint for
secondary devices. That fix is intentionally narrow and safe, but it also
confirms a broader maintainability issue:

- the code currently treats brightness as both
  - the current on/off state
  - the restore target after turning a secondary device back on
  - part of the menu/UI state inference surface

That overloading is manageable for a local fix, but it is a fragile long-term
model.

## Problem summary

Today, secondary-device power semantics are spread across a few small seams:

- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/app/callbacks.py`
- `src/tray/app/_delegates.py`
- `src/tray/ui/_menu_sections_device_context.py`
- config-side secondary brightness accessors

The current behavior works, but the design still has these weaknesses:

1. Brightness doubles as power-state truth.
2. The menu infers `Turn On` vs `Turn Off` from persisted brightness alone.
3. Restore behavior depends on implicit state, not an explicit power model.
4. Secondary-device state is coordinated through tray/controller/UI wiring
   rather than through one canonical state seam.

The result is not a huge architecture problem, but it is a coordination-heavy
hotspot where small UI changes can accidentally regress real device behavior.

## Scope estimate

This should stay a moderate refactor, not a broad subsystem rewrite.

Expected hotspot count:

- runtime/controller files: about 4-7
- tray UI and callback files: about 3-5
- config/state helpers: about 2-4
- tests: about 8-12

The priority is to reduce semantic ambiguity, not to split files just because
they are small or to move logic for its own sake.

## Desired target model

### Canonical concepts

Secondary-device runtime state should be modeled using three separate ideas:

1. Current brightness
2. Current power intent
3. Restore brightness

Those concepts should not be inferred from one another more than necessary.

### Recommended behavior rules

#### Rule 1: power state is not just “brightness > 0”

For secondary devices, power intent should be modeled explicitly enough that
the code does not have to guess whether `0` means:

- intentionally off
- temporarily dimmed
- not yet initialized
- missing config data

#### Rule 2: restore brightness must be first-class

Turning a secondary device off should not destroy the only available restore
source.

The system should keep a canonical last-nonzero restore brightness for each
secondary route, even if the currently applied brightness becomes `0`.

#### Rule 3: menu state should read a canonical state seam

The tray menu should not have to reconstruct state from whichever config field
happens to exist for a route.

The menu should ask one helper:

- is this secondary device effectively off right now?
- what action should this menu present?

#### Rule 4: route-aware semantics stay centralized

Any special meaning tied to `lightbar`, `mouse`, or future secondary routes
should live in one secondary-device state layer instead of being spread across
callbacks and menu builders.

## Recommended implementation shape

### State owner

Introduce one small state-oriented helper surface for secondary-device power
semantics, likely still under tray ownership at first.

Potential responsibilities:

- read current secondary brightness
- read or write restore brightness
- decide whether the device is “off” for menu purposes
- compute turn-on target brightness
- cache transient runtime hints if needed

This can start as helper functions in the current controller area and later
graduate into a dedicated module if the surface grows.

### Config model direction

Longer term, the cleanest persisted model would separate:

- `current_brightness`
- `restore_brightness`

for each secondary route.

For the current implementation, restore brightness remains a tray-runtime hint.
That keeps behavior consistent with the keyboard's runtime last-brightness
restore model and avoids adding a config migration for a small menu action.

A staged path is still available later:

1. canonicalize the runtime seam first
2. add persisted restore state only if restart-surviving restore becomes a real
   user need

### UI model direction

The tray device-context menu should become a consumer of the state seam, not a
participant in state inference.

That means:

- menu code chooses labels and callbacks from a helper result
- controller code owns turn-on/turn-off semantics
- callback wiring stays thin

## Suggested refactor slices

### Slice 1: Formalize secondary-device power vocabulary

Goal:

- document the meanings of current brightness, restore brightness, and power
  intent

Primary files:

- this document
- inline comments in `src/tray/controllers/secondary_device_controller.py`

Expected change size:

- docs and tiny comments only

### Slice 2: Extract canonical secondary power-state helpers

Goal:

- move state reads and restore-target decisions behind a small helper seam

Primary files:

- `src/tray/controllers/secondary_device_controller.py`
- possibly a new helper such as
  `src/tray/controllers/_secondary_power_state.py`

Expected outcomes:

- one function to read current brightness
- one function to resolve restore brightness
- one function to decide effective off/on menu state

### Slice 3: Make menu state consume the helper seam

Goal:

- stop duplicating route-aware brightness inference in the menu builder

Primary files:

- `src/tray/ui/_menu_sections_device_context.py`
- `src/tray/ui/menu_sections.py`

Expected outcomes:

- menu code asks for state instead of reading config shape directly
- route fallback logic is not embedded in UI assembly

### Slice 4: Keep callback/delegate wiring thin and uniform

Goal:

- preserve tray app wrappers as pure delegation surfaces

Primary files:

- `src/tray/app/callbacks.py`
- `src/tray/app/_delegates.py`
- `src/tray/app/_runtime_deps.py`

Expected outcomes:

- no secondary power semantics live in delegate wrappers
- callback layer remains dispatch only

### Slice 5: Defer persisted restore state unless evidence requires it

Goal:

- keep secondary-device restore brightness as a tray-runtime hint for now
- avoid config schema changes until restart-surviving restore has clear user
  value

Primary files:

- `src/core/config/_lighting/_secondary_device_accessors.py`
- `src/core/config/_lighting/_lighting_secondary_device_facade.py`
- `src/core/config/defaults.py`

Decision criteria:

- should restore survive app restart?
- should restore survive config reload?
- do we want a schema migration for this behavior?

Current decision:

- no config persistence for secondary-device restore brightness in this release
- revisit only if users expect lightbar restore brightness to survive process
  restart after an explicit off action

### Slice 6: Add seam-level tests rather than only wrapper tests

Goal:

- make future changes safe without relying only on broad tray wrapper coverage

Primary files:

- `tests/tray/controllers/power/test_tray_secondary_device_controller_unit.py`
- tray UI menu tests
- config accessor tests if persistence is added

Tests that should exist after cleanup:

- turning off caches a restore brightness without losing the restore target
- turning on restores the last nonzero brightness
- no saved restore brightness falls back to the canonical default
- menu label selection uses the same state seam as the controller path
- route-specific config fallback behavior is covered once at the seam

## Guardrails

1. Do not combine this cleanup with backend/device support changes.
2. Do not mix this with broader tray power-manager or idle-power refactors.
3. Preserve the current public tray callback surface unless there is a strong
   reason to change it.
4. Keep secondary-device route semantics explicit; do not hide them inside
   generic brightness helpers that really belong to keyboard-only logic.
5. Prefer behavior-preserving refactor slices with seam-level tests after each
   step.

## Validation plan

Minimum validation for the early slices:

- `.venv/bin/python -m pytest -q tests/tray/controllers/power/test_tray_secondary_device_controller_unit.py tests/tray/app/test_tray_callbacks_unit.py tests/tray/app/test_tray_application_unit.py tests/tray/ui/menu/test_menu_sections_unit.py tests/tray/ui/menu/test_tray_menu_capabilities_unit.py`
- `.venv/bin/python -m buildpython --run-steps=1,4`

If config persistence changes:

- add focused config accessor tests
- run a slightly wider tray/config validation slice

## Recommendation

This cleanup is worth doing, but it should stay intentionally scoped.

The current code does not need a dramatic redesign. The right goal is to make
secondary-device power behavior explicit enough that menu changes, callback
wiring changes, and restore logic changes no longer depend on the same
brightness field carrying three meanings at once.

Keep restore brightness as tray-runtime state until there is concrete evidence
that persisted restart-surviving restore behavior is worth the schema cost.
