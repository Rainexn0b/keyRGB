# Issue 4.1: Continuation after the 0.20.0 retest

Last updated: 2026-04-08

Related issue: https://github.com/Rainexn0b/keyRGB/issues/4

This continuation file now tracks the post-`0.20.0` part of issue `#4` in a
dated session format. It includes the latest reporter reply on `0.21.4`, which
has not been addressed by the maintainer yet.

## Current position

At the end of the main issue-4 batch:

- backdrop modes existed in principle
- one-logical-key-to-many-cells support had landed
- `ite8910` software blinking had positive reporter confirmation
- the guided speed probe had been added for the remaining speed-range question

The continuation starts when the `0.20.0` reporter retest exposed two smaller
follow-up bugs.

## Session 01 — 2026-04-04 — Reporter retest on 0.20.0

Reporter findings:

1. In the per-key colors interface, `No backdrop` hid the keyboard keys rather
   than only removing the optional backdrop image.
2. `Built-in seed` also behaved differently there than in the keymap
   calibrator.
3. Software effects were now much better. No blinking was seen during testing.
4. The guided speed-probe flow appeared to switch to the software
   `Spectrum Cycle` effect instead of the hardware one.

Immediate reading of this reply:

- the large `ite8910` software-effect complaint was no longer the active issue
- the continuation narrowed to one per-key backdrop bug and one speed-probe UX
  bug

## Session 02 — 2026-04-05 — Maintainer reply after the 0.20.0 retest

Maintainer response:

- acknowledged the `No backdrop` behavior as a bug and marked it as fixed
- reworked the support reporting flow to be more logical and user-friendly
- treated the flicker complaint as resolved enough that extra reporting was no
  longer needed for that part

This reply effectively closed the original blinking investigation and left the
continuation focused on:

- per-key backdrop parity
- speed-probe clarity and the remaining hardware-speed-range complaint

## Session 03 — 2026-04-05 — Maintainer planning snapshot for the continuation

The earlier monolithic version of this file captured the follow-up plan as one
large design note. Broken into timeline form, that planning session reads as
follows.

Maintainer decisions for the continuation:

1. Locale-specific legends are valid feedback, but remain deferred.
2. Backdrop handling needs an explicit disabled mode rather than implicit image
   fallback behavior.
3. The keymap model must support one logical key mapping to many physical cells.
4. `ite8910` software rendering needs backend-specific mode-maintenance policy
   rather than a generic renderer assumption.
5. Support Tools should capture structured `ite8910` speed-probe evidence.

Root causes captured in that planning pass:

### Backdrop gap

- The editor supported custom backdrops, reset-to-built-in behavior, and
  transparency, but not a true `no backdrop` mode.
- The per-key and calibrator windows needed to share the same backdrop-loading
  rules instead of each interpreting profile state differently.

### One-key-to-one-cell assumption

- KeyRGB had been assuming `key_id -> one (row, col)` in profile storage,
  calibrator assignment, editor selection, and reactive input lookup.
- That was why keys such as `space` could not fan out to multiple LEDs cleanly.

### ite8910 software blinking

- The generic renderer had been re-entering user mode on every frame.
- That policy is required on `ite8291r3`, but on `ite8910` it triggers
  `enable_user_mode()` and `reset()`, which clears the matrix before the next
  frame.
- The real problem was policy living in the generic renderer instead of on the
  backend/device side.

### ite8910 hardware-speed evidence gap

- After the speed inversion fix, the remaining question was not code discovery.
- It was whether the effective speed range still felt too compressed on the
  reporter's actual device.
- That required structured, saved observations rather than more freeform issue
  comments.

Implementation order captured in that plan:

1. Explicit backdrop disable support
2. One-to-many keymap model migration
3. Backend-specific mode-maintenance policy
4. Guided `ite8910` speed probes in Support Tools
5. Locale/legend cleanup later

## Session 04 — 2026-04-05 to 2026-04-07 — Implementation outcome from that plan

By the end of the follow-up batch described above, the historical plan had been
implemented as follows.

1. Backdrop mode support:
   - landed as explicit `No backdrop`, `Built-in seed`, and `Custom image`
     modes shared by the calibrator and per-key flows.
2. One logical key to many cells:
   - landed across profile storage, calibrator assignment, editor selection,
     and reactive typing.
3. Backend-specific mode-maintenance policy:
   - landed with `ite8291r3` keeping per-frame reassertion and `ite8910` using
     one-time init for per-key software/reactive rendering.
4. Guided speed probes:
   - landed in Support Tools and persisted observation data into the support
     bundle and issue draft.
5. Locale legends:
   - intentionally still deferred.

At that point the continuation looked close to done, but the latest reporter
retest reopened part of the follow-up surface in a smaller, more precise way.

## Session 05 — 2026-04-08 — Reporter retest on 0.21.4

This is the newest reporter reply, and it has not been addressed yet.

Reporter findings on `0.21.4`:

1. `No backdrop` is fixed now.
2. `Built-in seed` and `Custom image` no longer appear to work in the per-key
   colors interface.
3. The redone reporting flow is clearer, but it still takes several attempts to
   understand when the probe is actually running.
4. The timing between speed tests feels too short, and a longer dwell per speed
   may help users evaluate differences.
5. The actual hardware-speed complaint remains: the reporter still does not see
   acceptable speed separation across different hardware effects.
6. Resetting the keymap restores default assignments, but assigning LEDs again
   appears to add the LED to the selected key without clearing the previous
   default owner, leaving the same LED mapped to two keys.
7. The reporter attached screenshots and fresh diagnostics/support output.

Important evidence included in the latest reporter dump:

- the guided probe metadata now explicitly records
  `selection_effect_name = hw:spectrum_cycle`
- the tray path is also present as
  `selection_menu_path = Hardware Effects -> Spectrum Cycle`

That means the original ambiguity from the `0.20.0` retest has been addressed
in the support output. The remaining complaint is now about usability and the
underlying perceived speed range, not about missing hardware-effect selection
metadata.

## Current interpretation after the 0.21.4 reply

The follow-up continuation is no longer a single open item. It has split into
three clearly separate tracks.

### 1. Per-key backdrop regression changed shape

The first continuation bug was:

- `No backdrop` and `Built-in seed` were indexed or interpreted incorrectly in
  the per-key colors window

The newest reporter reply suggests the first fix only solved part of that:

- `No backdrop` now works
- `Built-in seed` and `Custom image` may now both be broken in the same window

So the current issue is no longer a generic backdrop-mode gap. It now looks
like a narrower per-key-editor backdrop selection or image-load regression.

### 2. Speed-probe UX improved, but the hardware-speed complaint remains open

What is now confirmed:

- the support bundle records the forced hardware selection key and tray path
- the earlier `software Spectrum Cycle vs hardware Spectrum Cycle` ambiguity has
  been addressed in the data the reporter returned

What remains open:

- the probe timing may be too short for humans to judge reliably
- the flow may still be too easy to misread on first use
- the reporter still perceives inadequate speed separation on real hardware

### 3. Keymap reassignment semantics need a fresh pass

The newest reply suggests a separate calibrator/keymap problem:

- after resetting to defaults, assigning a LED to a different key appears to
  append ownership instead of replacing or clearing the prior default mapping
- this can leave one physical LED assigned to two logical keys at once

That is distinct from the earlier one-logical-key-to-many-cells feature work.
The earlier feature intentionally allowed one logical key to own many physical
cells. The new complaint is the inverse problem: one physical cell ending up
owned by multiple logical keys.

## Current open items

As of the latest reporter reply, the continuation should be treated as open for
these items:

1. Fix `Built-in seed` and `Custom image` in the per-key colors interface.
2. Revisit guided speed-probe timing and explainability.
3. Continue investigating the real `ite8910` hardware-speed-range complaint
   using the newly returned support data.
4. Fix calibrator/keymap reassignment so a physical LED does not remain mapped
   to both its old default key and the newly selected key unless that behavior
   is explicitly intended.
5. Keep locale-specific legend polish deferred unless it becomes entangled with
   one of the functional fixes above.

## Practical handoff point

The latest reporter reply means issue `#4` is not yet at final closure.

What has positive confirmation:

- row alignment
- wrong-key lighting
- no-backdrop mode itself
- the `ite8910` software-blinking fix
- support output now naming the hardware-effect selection key and tray path

What still needs maintainer response and probably code changes:

- per-key `Built-in seed` / `Custom image`
- guided speed-probe UX duration and clarity
- remaining `ite8910` hardware-speed-range behavior
- duplicate physical LED ownership after keymap reset and reassignment
