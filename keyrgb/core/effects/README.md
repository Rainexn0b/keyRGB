# Effects extension

Adding a selectable software or reactive effect should not require editing
`catalog.py` or the effects engine start mixin.

## Software / reactive effect

1. Implement `run_<name>(engine)` in `keyrgb/core/effects/software/` (or
   `reactive/` for typing effects).
2. Export a module-level marker:

   ```python
   from keyrgb.core.effects.effect_contract import CURRENT_COLOR, EffectKind, EffectRegistration

   EFFECT_REGISTRATION = EffectRegistration(
       name="example_wave",
       kind=EffectKind.SOFTWARE,
       runner=run_example_wave,
       start_color=(255, 0, 0),  # or CURRENT_COLOR
       title="Example Wave",  # optional; default titleizes the name
       menu_order=75,
   )
   ```

   Multiple effects in one module may export `EFFECT_REGISTRATIONS = (...)`.
3. Add a focused unit test.

Catalog names, tray menu order, titles, and engine start dispatch are derived
from those markers. Unmarked runners are not user-selectable.

Optional: re-export `run_<name>` from `software/effects.py` only if callers need
a stable import path. Engine start does not require that wrapper.

Unprefixed names that also exist as firmware effects (`breathing`, `rain`,
`random`) select the software loop. The matching controller effect is stored
and started as `hw:<name>`.

## Hardware firmware effects

Do not add names to `catalog.HW_EFFECTS` to ship a new firmware effect. Expose
it from `backend.effects()` with `hardware_effect_builder()` metadata. See
`docs/1-src/16-effect-runtime-contracts.md` and
`docs/1-src/17-backend-extension.md`.

## Backends

Built-in backends are discovered the same way: export `BACKEND_REGISTRATION`
from `keyrgb/core/backends/<package>/__init__.py`.
