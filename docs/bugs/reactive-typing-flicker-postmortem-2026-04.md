# Reactive Typing Flicker And Low-Brightness Restore Campaign

Status as of 2026-04-26:

- Latest validation artifact `buildlog/keyrgb/debug-sessions/reactive-flicker-session38.log` is clean for the bug class addressed in this campaign.
- Reporter outcome at close-out: keyboard lighting no longer flickers on dim, and the reactive typing flash appears resolved, pending additional observation.
- This document captures the full campaign so a future maintainer does not have to reconstruct the same debugging line from raw logs.

## Scope

This campaign covered several visually similar but technically different failures in the reactive lighting path:

- startup brightness flashes
- temp-dim and restore flashes
- full idle off -> on wake flashes
- per-key reactive typing flashes on low-brightness backdrops
- reactive typing visibility regressions introduced while suppressing flashes
- tray icon refresh flicker mistaken for keyboard flicker

The work ultimately became a combined render-path, idle-power, and diagnostics campaign rather than a single isolated bug fix.

## Environment used during validation

- OS/session: CachyOS, KDE Plasma, Wayland
- Backend: `ite8291r3`
- Active USB device: `048d:600b`
- Primary effect under investigation: `reactive_ripple`
- Runtime config path: `~/.config/keyrgb/config.json`

Important brightness regimes used during this campaign:

- temp-dim validation baseline:
  - `brightness = 15`
  - `perkey_brightness = 15`
  - `reactive_brightness = 50`
  - `screen_dim_sync_mode = "temp"`
  - `screen_dim_temp_brightness = 5`
- low-brightness reactive typing validation:
  - `brightness = 5`
  - `perkey_brightness = 5`
  - `reactive_brightness` varied during testing, including `50`, to confirm that the reactive slider remained visually effective over a dim base layer

## Why this campaign was hard

Several different failure modes looked almost identical to the reporter:

- whole-keyboard hardware brightness jumps
- software-only per-key pulse contrast bursts
- the reactive idle turn-off fade ladder
- repeated `screen_off=False` turn-off/restore chatter
- tray icon animation and hardware polling refreshes

The other trap was that reactive restore behavior has two separate entry points:

- temp-dim restore uses `apply_restore_brightness()`
- full idle wake uses `restore_from_idle()` -> `start_current_effect_for_idle_restore()`

That distinction mattered late in the campaign, because a fix that worked for temp-dim restore did not automatically cover full off -> on wake.

## Root causes confirmed

The following causes were confirmed during the campaign.

1. Startup flicker: redundant power-policy restore/apply actions could restart reactive output at `brightness=1`.
2. Temp-dim flicker: reactive render could keep writing the old hardware brightness during `dim_to_temp`.
3. Built-in profile mismatch: `dim` previously updated only `perkey_brightness`, leaving reactive steady-state brightness too bright.
4. Last-ripple tail flicker: the renderer could step down through a bright tail frame when the last pulse ended.
5. Keypress-wide brightness flicker: per-key reactive pulses could still send a whole-keyboard hardware brightness lift on per-key hardware.
6. Idle turn-off false positive: reactive per-key idle turn-off used a soft fade ladder that looked like a restore flash.
7. Idle restore chatter: `screen_off=False` turn-off/restore pairs could bounce the control path and reseed restore too aggressively.
8. Tray icon flicker: idle-power and hardware-refresh paths still animated the tray icon even after keyboard brightness was stable.
9. Rough low-brightness restore ramp: `1 -> 5` restores were quantized too early and visibly stepped.
10. Brightness override regression: tray and power-policy brightness overrides stopped syncing `brightness`, `perkey_brightness`, and `reactive_brightness` together.
11. Reactive visibility regression: restore-only visual damp was briefly tied to `_reactive_disable_pulse_hw_lift_until`, which is also seeded on ordinary first keypress activity, so normal low-brightness typing became too dim.
12. Over-correction of low-brightness pulses: an always-on low-brightness contrast-compression path flattened normal per-key reactive intensity until it looked too close to the base layer.
13. Full idle wake bypass: full off -> on wake used `restore_from_idle()` and restarted the effect, while `engine.stop()` cleared restore timers. The restore-only damp therefore never actually engaged on that path.
14. Restore damp duration gap: even after the damp timer was split correctly, the initial visual damp window was shorter than the reporter's real 2-3 second post-undim typing window.

## What landed

### 1. Better diagnostics and log separation

The late-stage investigation became reliable only after separating hardware brightness decisions from software-side per-key composition.

New high-value logs:

- `reactive_hw_lift`
  - explains whether hardware pulse lifts are allowed, blocked by cooldown, gated by backend type, or simply inactive
- `reactive_pulse_visual`
  - reports resolved pulse scale, restore-only holdoff state, and restore-only damp state
- `reactive_render_visual`
  - reports the final per-frame visual scale actually used by the renderer

The practical debugging rule that emerged was:

- inspect the latest completed restore window first
- inspect the later flash tail separately
- do not blame restore if the completed restore slice has no `hardware:brightness_change` and no move toward `brightness=50`

### 2. Reactive render and pulse behavior fixes

The reactive render path now follows these rules:

- startup and restore brightness transitions are owned by guarded render-time brightness resolution
- per-key backends keep hardware brightness fixed and express pulse intensity through the per-key color map
- uniform-only backends may still use pulse-time hardware brightness lifts because they have no per-key output path
- low-brightness restore ramps smooth the final written frame between integer hardware steps
- normal low-brightness typing uses direct reactive slider scaling again
- any extra suppression is scoped only to explicit restore windows, not to ordinary typing

### 3. Idle-power and wake-path fixes

The idle-power path now distinguishes between several cases that were previously conflated:

- reactive per-key idle turn-off skips the soft fade ladder
- short post-turn-off restore suppression prevents obvious `screen_off=False` chatter from immediately reseeding restore
- idle-power and hardware-refresh UI paths can refresh without tray icon animation
- temp-dim restore seeds a short hardware-lift cooldown and a longer restore-only visual damp window
- full off -> on idle wake reseeds those same restore windows after `start_effect()` returns, because the restart clears engine timer state via `stop()`

That final point was the crucial late-campaign fix.

### 4. Brightness override and policy sync fixes

During the same campaign, a regression surfaced where reactive brightness overrides stopped working correctly.

That was fixed by keeping all reactive brightness fields in sync when the user or power policy changes brightness:

- `brightness`
- `perkey_brightness`
- `reactive_brightness`

Without that sync, reactive typing could look wrong even if the render logic itself was otherwise correct.

## Final clean evidence

The final close-out artifact was:

- `buildlog/keyrgb/debug-sessions/reactive-flicker-session38.log`

Key lines from the final clean restore window:

- `14596`: `EVENT idle_power:restore ...`
- `14597`: `EVENT idle_power:restore_start_policy ... brightness_override=1 fade_in=True fade_in_duration_s=0.42`
- `14633`: `engine.set_brightness: prev=5 new=5 apply_to_hardware=False`
- `14635`: first post-restore `reactive_pulse_visual` line with:
  - `holdoff_remaining_s=4.00`
  - `post_restore_damp=0.350`

What was absent from the final log:

- no `hardware:brightness_change`
- no `brightness=50` outside `reactive_hw_lift`
- no restore-time whole-keyboard hardware brightness bump

Late-frame behavior in the same log also stayed clean for the fixed bug class:

- last `reactive_hw_lift` line kept `allow=False` and `hw=5`
- last `reactive_render_visual` line ended at `pulse_mix=0.000`
- tail frames remained steady `kb.set_key_colors ... brightness=5`

Interpretation:

- the full-off wake path finally seeded restore damp correctly
- hardware brightness stayed pinned at the steady-state target
- the old restore-time flash signatures were gone

## High-value artifacts from the campaign

Earlier validated artifacts:

- `buildlog/keyrgb/debug-sessions/reactive-flicker-session20-icon-poller-holdoff.log`
  - completed restore slices were clean; remaining visible noise came from the turn-off fade tail and tray refresh paths
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session21-idle-hardoff.log`
  - repeated `screen_off=False` turn-off/restore pairs shifted blame toward software dim-state chatter
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session22-idle-restore-guard.log`
  - first clean run after the post-turn-off restore suppression guard
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session23-tray-hw-refresh.log`
  - tray hardware-refresh cleanup pass; no remaining visible flashing was reported at that stage

Late-stage artifacts that closed the remaining line of work:

- `buildlog/keyrgb/debug-sessions/reactive-flicker-session35.log`
  - confirmed reactive brightness values were resolving correctly, but normal typing still used a compressed pulse scale that made the reactive layer too dim
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session36.log`
  - proved a later flash had no `hardware:brightness_change` and no restore-time move toward `brightness=50`; the remaining issue was software-side per-key composition
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session37.log`
  - exposed that full idle wake was bypassing restore-only damp entirely; no post-restore damp state ever appeared in the log
- `buildlog/keyrgb/debug-sessions/reactive-flicker-session38.log`
  - final clean artifact after reseeding restore timers on the full-off wake path after effect restart

## Files that own the current behavior

- `src/core/power_policies/power_source_loop_policy.py`
  - suppresses redundant initial AC/battery restore/apply actions
- `src/core/profile/profiles.py`
  - keeps built-in profile brightness baselines coherent
- `src/core/effects/reactive/render.py`
  - owns pulse scale resolution, restore-only damp blending, and per-key vs uniform behavior
- `src/core/effects/reactive/_render_brightness.py`
  - owns hardware brightness resolution and pulse-time hardware-lift gating
- `src/core/effects/reactive/_render_brightness_support.py`
  - owns the brightness decision and visual-scale debug logs
- `src/core/effects/reactive/_render_runtime.py`
  - owns render-time visual scaling of written per-key frames
- `src/core/effects/reactive/effects.py`
  - owns live pulse-mix rise/decay behavior
- `src/core/effects/reactive/_ripple_helpers.py`
  - owns per-key pulse mixing against the backdrop
- `src/tray/pollers/idle_power/_transition_actions.py`
  - seeds temp-dim restore state, restore-only damp windows, and the full-off wake post-restart timers
- `src/tray/pollers/idle_power/_actions.py`
  - owns the full idle wake control path
- `src/tray/pollers/icon_color_polling.py`
  - owns resume-related icon refresh holdoff
- `src/tray/controllers/_lighting_menu_handlers.py`
  - owns tray brightness override sync
- `src/tray/controllers/_power/_lighting_power_policy.py`
  - owns power-policy brightness sync

## Regression coverage and validation used during the campaign

Focused reactive coverage used repeatedly:

- `tests/core/effects/reactive/rendering/test_reactive_pulse_brightness_unit.py`
- `tests/core/effects/reactive/rendering/test_reactive_render_brightness_policy_unit.py`
- `tests/core/effects/reactive/core/test_reactive_backdrop_brightness_scaling_unit.py`
- `tests/tray/pollers/hardware/test_brightness_stability_guard_unit.py`

Focused idle-power coverage used repeatedly:

- `tests/tray/pollers/idle_power/core/test_idle_power_polling_apply_action_unit.py`
- `tests/tray/pollers/idle_power/runtime/test_tray_idle_power_polling_more_unit.py`

Other validation completed during the overall line of work:

- the full `buildpython` pipeline was brought back to green after the brightness override fixes and related cleanup work
- latest focused restore validation after the final full-off wake fix: `47 passed`
- latest focused reactive validation after the direct-slider restore: `30 passed`

## Lessons to preserve

1. Do not reuse `_reactive_disable_pulse_hw_lift_until` for visual damp. It is also set on ordinary first keypress activity.
2. Full idle wake and temp-dim restore are different control paths. Fix both or the bug will appear to "come back" on only one path.
3. `engine.start_effect()` calls `stop()`, which clears reactive restore timers. Any full-off wake timer seed done before restart will be lost.
4. Read `reactive_hw_lift`, `reactive_pulse_visual`, and `reactive_render_visual` together.
5. Inspect the completed restore slice and the later flash tail separately. Do not merge them mentally into one event.
6. A later flash with `allow=False`, `hw=5`, and no `hardware:brightness_change` is not a hardware brightness regression.
7. Low-brightness typing visibility and low-brightness flash suppression pull in opposite directions. Keep those controls separate.

## Remaining watch items

- The reporter's final outcome is positive, but longer observation is still warranted.
- If a future flash is reported, start with a fresh debug capture and verify whether it is:
  - a restore-time hardware brightness jump
  - a software-side per-key pulse burst
  - a tray/UI refresh artifact
  - or a different regression entirely

## Related references

- `docs/architecture/src/08-reactive-brightness-invariants.md`
- `.github/agents/ReactiveTypingFlickerDebug.agent.md`
