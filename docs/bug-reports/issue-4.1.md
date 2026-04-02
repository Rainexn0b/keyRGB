# Issue 4.1: Follow-up plan after 0.19.2 retest

Last updated: 2026-04-02

Related issue: https://github.com/Rainexn0b/keyRGB/issues/4

This note turns the latest reporter feedback plus local maintainer review into a
single implementation plan. The goal is to handle the remaining gaps one at a
time, in an order that improves user-visible behavior quickly without locking
KeyRGB into short-term fixes that will become debt.

Update for the end of this version:

- The plan below has been implemented for the functional issue-4 items.
- The remaining materially open complaint is the `ite8910` hardware-speed-range
	question, which now depends on a returned Support Tools bundle containing the
	guided backend-speed probe observations.
- Locale-specific legend polish remains intentionally deferred.

Treat the main body of this document as the historical planning record for the
work that has now landed.

## Current decisions

Maintainer feedback for the next pass:

1. Locale-specific key legends are valid UX feedback, but this is not the next
	item to tackle. Side-line it for now.
2. The backdrop needs an explicit disabled state. The built-in backdrop is only
	a starter reference image, not a permanent required asset.
3. The keymap model must stop assuming one LED per logical key.
4. The remaining `ite8910` software blinking needs the best long-term
	maintainable fix, not a backend-specific hack layered on top of the current
	behavior.
5. The Support Tools flow should gain backend-speed probe support so the next
	diagnostics dump can include evidence for the `ite8910` hardware-speed-range
	complaint.

## Remaining gaps

After the `0.19.2` reporter retest, the meaningful open gaps are:

1. Per-key editor backdrop cannot be disabled entirely.
2. Multiple LEDs can belong to one logical key, but KeyRGB currently only keeps
	one mapping cell per key.
3. `ite8910` software effects still visibly blink.
4. `ite8910` hardware-effect speed may still have a compressed or unclear
	effective range.
5. Locale-specific legends on the visual keyboard remain rough, but this is
	intentionally deferred.

## Root-cause summary

### 1. Backdrop disable gap

The current editor supports:

- per-profile custom backdrops
- reset to the built-in reference image
- transparency adjustment

What it does not support is a true `no backdrop` mode.

Current owner files:

- `src/gui/reference/deck_image.py`
- `src/gui/perkey/canvas_impl/_canvas_drawing.py`
- `src/gui/perkey/editor_ui.py`
- `src/gui/perkey/ui/backdrop.py`

Current behavior always falls back to the built-in reference image when no
custom profile backdrop exists. That matches the reporter complaint: they can
change the image, but they cannot fully turn it off.

### 2. One-key-to-one-cell assumption

KeyRGB still treats the keymap as:

- visual key id -> one `(row, col)` tuple

That assumption currently exists in all major layers:

- profile storage
- calibrator assignment
- per-key editor selection
- reactive key lookup

Current owner files:

- `src/core/profile/profiles.py`
- `src/gui/calibrator/app.py`
- `src/gui/perkey/editor.py`
- `src/core/effects/reactive/input.py`

This is why a logical key such as `space` can only drive one LED at render
time, even if the user has identified multiple physical LEDs that belong to the
same key.

### 3. `ite8910` software blinking

The maintainer note in `issue-4.md` says the generic software renderer now does
one-time mode initialization, but the current tree does not reflect that.

Current behavior in `src/core/effects/software/base.py` still re-enters user
mode on every frame. That behavior is deliberate for `ite8291r3`, because that
controller drifts back to its saved hardware effect unless user mode is
reasserted every frame.

That same policy is a bad fit for `ite8910`, because on `ite8910`
`enable_user_mode()` calls `reset()` and clears the matrix before rendering the
next frame.

Current owner files:

- `src/core/effects/software/base.py`
- `src/core/effects/reactive/_render_runtime.py`
- `src/core/effects/perkey_animation.py`
- `src/core/backends/ite8910/device.py`
- `src/core/backends/ite8291r3/backend.py`

The long-term issue is not just a single bug in one renderer. It is that mode
maintenance policy is backend-specific, but KeyRGB currently hard-codes one
policy into the generic software renderer.

### 4. `ite8910` hardware-speed evidence gap

The direct/inverted speed bug is already understood separately from this note.
What remains open is the reporter's claim that the usable speed range still
feels too narrow on `ite8910`.

This is not something code inspection alone can settle. It needs observable
evidence from the affected device.

Current owner files for the support flow:

- `src/gui/windows/support.py`
- `src/core/diagnostics/`
- `src/core/diagnostics/support_reports.py`
- `src/tray/ui/menu.py`

The tray already exposes `Support Tools…`, and the window already has a backend
discovery surface. The next step is to make that surface capable of running and
recording targeted backend speed probes.

## Best path forward

The most maintainable order is:

1. Add explicit backdrop disable support.
2. Migrate the keymap model to support one logical key -> many cells.
3. Introduce backend-specific per-key mode-maintenance policy and use it to fix
	`ite8910` software blinking cleanly.
4. Extend Support Tools to capture hardware-speed probe evidence for `ite8910`.
5. Revisit locale-specific legends after the functional gaps above are closed.

This order keeps visual/UX cleanup first, then fixes the keymap data model,
then fixes the renderer policy with the new model in place, and finally
improves diagnostics for the still-open hardware-speed question.

## Implementation plan by gap

### A. Add true backdrop disable support

Decision:

- treat backdrop state as a mode, not just an image path plus transparency

Target behavior:

- `None` / disabled: no image drawn behind the overlay
- `Built-in`: bundled seed/reference backdrop
- `Custom`: profile image, if present

Recommended implementation:

1. Add an explicit backdrop mode setting at profile scope.
2. Keep existing custom-backdrop storage intact.
3. Change reference-image loading so `disabled` returns no image instead of
	falling back to the built-in asset.
4. Expose a clear UI control in the per-key editor so users can choose:
	`No backdrop`, `Built-in`, or `Custom`.
5. Keep transparency only for modes that actually draw an image.

Why this wins:

- it solves the reporter complaint directly
- it keeps current custom-backdrop behavior working
- it removes ambiguity from the current `Reset Backdrop` meaning
- it avoids overloading transparency as a pseudo-disable flag

Validation target:

- no-backdrop mode persists per profile
- built-in seed image still works
- custom image still works
- reset semantics remain obvious and testable

### B. Move from one-to-one to one-to-many keymaps

Decision:

- the core keymap format must support multiple cells per logical key

Recommended canonical model:

- `key_id -> list[(row, col)]`

Backward compatibility requirement:

- old profiles with one tuple per key must still load without migration tools
- internally normalize them to a one-element list

Recommended implementation shape:

1. Update profile load/save helpers to accept legacy single-cell entries and
	write the new one-to-many shape.
2. Update the calibrator so assigning a probe cell can append to an existing key
	instead of always replacing it.
3. Add explicit calibrator actions for:
	- append current cell to selected key
	- replace selected key mapping
	- remove one assigned cell from selected key
4. Update editor selection so a logical key reads/writes all mapped cells.
5. Update reactive effects so one pressed key fans out to all mapped cells.

Why this wins:

- it reflects the hardware reality of wide keys such as `space`
- it fixes both per-key editor behavior and reactive typing behavior with the
  same model change
- it avoids a second parallel concept such as `aux LEDs` or ad-hoc overrides

Important constraint:

- keep colors stored per physical cell, not per logical key

That preserves current rendering simplicity while letting one logical key drive
many cells.

Validation target:

- legacy profiles continue to load
- new profiles can store multiple cells per key
- `space` can light all mapped LEDs in the per-key editor
- reactive typing can light all mapped LEDs for one pressed logical key

### C. Introduce backend-specific per-key mode-maintenance policy

Decision:

- stop hard-coding one software-render mode policy for all backends

Recommended policy model:

- add a small backend/device capability attribute similar to
  `keyrgb_hw_speed_policy`
- example values:
  - `reassert_every_frame`
  - `init_once`

Expected backend mapping:

- `ite8291r3`: `reassert_every_frame`
- `ite8910`: `init_once`

Recommended implementation:

1. Add a backend/device-facing policy knob for per-key software mode
	maintenance.
2. Update `src/core/effects/software/base.py` to obey that policy instead of
	always calling `enable_user_mode_once()` every frame.
3. Keep the reactive runtime aligned with the same policy model so software and
	reactive effects do not drift into different rulesets.
4. Only fall back to a re-init when brightness changes and the backend cannot do
	a lightweight brightness update.

Why this wins:

- it preserves the required `ite8291r3` behavior
- it removes the `ite8910` reset-per-frame black flash at the root cause
- it gives future backends a clear integration point instead of more renderer
  exceptions

Validation target:

- `ite8291r3` tests still lock in reassert-every-frame behavior
- `ite8910` tests lock in one-time init plus incremental writes
- hardware confirmation from the reporter remains desirable before closing the
  blinking complaint

### D. Add `ite8910` speed probes to Support Tools

Decision:

- the support workflow should gather structured speed evidence rather than rely
  on freeform user comments

Current UI owner:

- `src/gui/windows/support.py`

Recommended product direction:

- keep diagnostics read-only by default
- add a clearly labeled opt-in backend probe action for affected backends
- persist the probe results into the support bundle so the next dump contains
  the relevant evidence automatically

Recommended implementation shape:

1. Add a backend-specific probe section to the Support Tools backend/discovery
	surface.
2. When `ite8910` is the active or discovered backend, expose a guided speed
	probe action.
3. Record probe metadata into the support bundle under a backend-specific field.
4. Include enough structured output to compare UI speed values against the
	user's subjective observation.

Probe scope for the next dump:

- selected backend name
- effect name used for probe
- requested UI speed values tested
- raw payload speed values sent to the backend
- timestamps or measurement notes captured during the probe
- a small user-observation section if the workflow asks the user to confirm
  what they saw

Why this wins:

- it keeps the evidence collection in the existing tray support flow
- it avoids telling users to run ad-hoc shell commands for this specific issue
- it gives future backend investigations a reusable pattern for targeted probes

Open design choice:

- whether the probe should remain strictly read-only or be classified as a
  guided diagnostic action that temporarily exercises hardware effects

For this issue, a guided diagnostic action is acceptable as long as the UI makes
it explicit and the resulting data is saved into the next support bundle.

## Deferred item: locale-specific legends

This remains valid feedback but is intentionally not the next task.

When revisited, the right direction is to decouple:

- physical layout geometry
- key labels shown on the overlay

That should become a later UX pass after the functional gaps above are fixed.

## Suggested execution order for follow-up work

1. Backdrop mode work
2. One-to-many keymap model migration
3. Backend-specific mode-maintenance policy
4. Support Tools speed probes and bundle extension
5. Locale/legend cleanup

## Closure criteria for this follow-up note

This note can be considered complete when:

- per-key editor can truly disable the backdrop
- one logical key can drive multiple cells cleanly
- `ite8910` software blinking is fixed through policy, not workaround layering
- next support bundle can capture structured speed-probe evidence
- locale-specific legends are tracked separately as a later UX task

## Implementation outcome for this version

Status against the plan above:

1. Backdrop disable support:
	- done. The per-key editor and calibrator now support `No backdrop`, `Built-in seed`, and `Custom image` as explicit profile-backed modes.
2. One logical key -> many cells:
	- done. Profile storage, calibrator assignment, editor selection, and reactive typing now support one logical identity driving multiple mapped LEDs.
3. Backend-specific per-key mode-maintenance policy:
	- done. `ite8291r3` keeps per-frame reassertion, while `ite8910` uses one-time init so per-key software/reactive rendering no longer resets the board every frame.
4. Support Tools speed probes:
	- done. Support Tools now exposes the guided `ite8910` backend-speed probe flow and persists the observation data into the support bundle and issue draft.
5. Locale legends:
	- deferred by design. Slot IDs and legend-pack groundwork landed, but reporter-facing locale polish is not part of this closure batch.

That leaves only one issue-4 item still waiting on external input for final closure: the reporter's hardware-speed-range complaint on `ite8910`, which now needs the saved support bundle from the new probe flow.
