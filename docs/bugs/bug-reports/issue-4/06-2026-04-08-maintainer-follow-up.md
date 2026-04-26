# Issue 4 — 2026-04-08 maintainer follow-up

GitHub issue: https://github.com/Rainexn0b/keyRGB/issues/4

Date: 2026-04-08

This session addressed the parts of the latest `0.21.4` reporter reply that had
clear code-level fixes, while leaving the underlying `ite8910` hardware-speed
range question open pending another reporter retest.

Implemented in this pass:

1. Per-key backdrop loading:
   - `Custom image` now fails closed when the profile has no saved custom
     backdrop file instead of silently falling back to the built-in deck image.
   - This removes an ambiguity in the per-key editor where missing custom
     state could look like `Built-in seed` was still selected.
2. Keymap reassignment semantics:
   - calibrator reassignment now removes the selected physical matrix cell from
     any previous owner before attaching it to the newly selected key.
   - the same write path also collapses stale key-id versus slot-id alias
     entries onto the selected identity so a reassignment does not leave an
     older alias mapping behind.
3. Guided backend speed probe UX:
   - the automatic probe dwell was increased from `1.25s` to `2.5s` per speed
     step, with a slightly longer settle gap.
   - the prompt and in-run message now state the requested speed list and the
     per-step dwell time explicitly.
   - recorded backend-probe evidence now stores the timing metadata used by the
     auto-run.

Validation run for this pass:

- `python -m pytest tests/gui/rendering_utils/test_backdrop_image_cache_unit.py tests/gui/calibrator/test_calibrator_app_logic_unit.py tests/core/diagnostics/support/test_backend_speed_probe_unit.py tests/gui/windows/test_support_window_unit.py -q`
- Result: `64 passed`

What remains open after this pass:

1. Reporter retest on whether the per-key `Built-in seed` path still behaves
   incorrectly on real usage after the custom-mode ambiguity was removed.
2. Reporter retest on whether the slower guided probe is now understandable
   enough to produce better hardware-speed observations.
3. The underlying `ite8910` hardware-speed-range complaint itself.

Important non-change in this pass:

- The `ite8910` hardware speed mapping was not changed here.
- Current evidence was strong enough to justify the probe UX fix, but not yet
  strong enough to justify changing the direct `ui_speed -> raw_speed` mapping
  again without another round of structured reporter feedback.