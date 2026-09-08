# Runtime Policy Ownership Follow-up Campaign

**Started:** 2026-09-03
**Baseline:** `~/.cache/keyrgb/diagnostic-sessions/20260903T092201.323445Z`
**Status:** Software-complete and merged-validated; live retest pending

## Purpose

Follow the sleep/wake pipeline campaign with four bounded ownership passes.
Each pass must preserve public facades, keep render frames outside the tray
coordinator, land with focused and full validation, and use live evidence when
changing visual policy.

## Baseline findings

- Four controller sleeps occurred about 605 seconds after the last captured
  keyboard event. The firmware timer is therefore approximately ten minutes,
  not one to three minutes. The shorter intervals in the session are how long
  the keyboard remained dark before typing resumed.
- Each keyboard wake had one restore invocation. The `brightness_change` value
  of 24 or 10 was the hardware poll observing the in-progress fade, not a
  second brightness commit.
- The remaining first-key flash is concrete: in cycle 2, the whole-frame scale
  changes from `0.620` to `1.000` when the first reactive key changes phase to
  `DAMPING`, then the post-start reseed changes it back to `0.620`.
- No suspend/lid cycle occurred. Screen dim tracking was configured for
  600000 ms and remained independent of the controller firmware timeout.

## Operations

| ID | Concern | Evidence / debt | Status |
|---|---|---|---|
| OP-1 | Reactive restore frame and pulse ownership | Evidenced first-key scale discontinuity and duplicate damp seeding | live-accepted |
| OP-2 | `start_current_effect` menu/power callers | Remaining SWP-4 intent-bypass seam; not triggered in baseline | software-complete; live retest pending |
| OP-3 | Layered brightness scheduler/menu deferral | Scheduler drops deferred intent; menu omits unified off-family predicate | software-complete; live retest pending |
| OP-4 | CPU power-mode apply/observation | Apply feedback now separates write success from heuristic observation; EPP failures and mismatches are diagnostic | software-complete; live retest pending |

## OP-1 acceptance

- Queue one reactive restore seed before restart; never create a fresh seed
  after a blocking start returns.
- Whole-frame restore scale is independent of pulse phase and rises
  monotonically from its floor to 1.0 by the configured fade duration.
- The first key cannot cause a whole-deck scale discontinuity.
- A follow-up full diagnostic session shows one restore and no scale reversal.

## OP-2 acceptance

- Manual and power off/restore entrypoints participate in the intent pipeline
  without breaking the valid bare-`is_off` Turn On case.
- A second wake intent cannot restart an effect while restoration is active.
- Public controller and application callback facades remain stable.

## OP-3 acceptance

- Scheduler, power policy, profile, config, and menu brightness use the same
  off-family hardware-deferral rule.
- Deferred scheduler/menu changes persist intent but do not relight the deck.
- Runtime-coordinator revision ordering remains authoritative.

### OP-3 implementation boundary

`hardware_apply_deferred(tray)` is the sole off-family predicate for scheduler
and menu brightness, speed, and effect-selection callbacks.  While it is true,
those paths persist normalized config intent and only update safe software/engine
caches; they do not stop or restart the effect or write the keyboard.  The
scheduler still returns success for a deferred update, so its key advances and
the legal restore transition remains the owner of the physical apply.  A bare
`tray.is_off` without an off-family owner remains the narrow manual-restore
compatibility case and is not folded into this rule.

## OP-4 acceptance

- Successful sysfs/helper application remains independent of heuristic mode
  observation.
- Non-fatal EPP write failures are visible in diagnostics.
- Observation disagreement is diagnostic and does not create a 30-second
  activation retry loop.

## Related ledgers

- `docs/O-optimisations/dim-undim-reactive-typing-review-improvement-plan.md`
- `docs/D-debugging/reactive-typing-flicker-postmortem-2026-04.md`
- `docs/P-power-management/sleep-wake-pipeline-campaign.md`
- `docs/P-power-management/power-mode-verification-refactor-plan.md`

## Software validation ledger

- OP-1: BuildPython Step 2 passed with 3767 tests and 1 skip.
- OP-2: Step 19 passed; BuildPython Step 2 passed with 3781 tests and 1 skip.
- OP-3: Step 19 passed; BuildPython Step 2 passed with 3788 tests and 1 skip.
- OP-4: focused power/tray validation passed with 303 tests; targeted Ruff,
  `git diff --check`, and Step 19 passed; BuildPython Step 2 passed with 3799
  tests and 1 skip.

The remaining gate is the rest of the live hardware matrix: temporary dim wake,
key-event filtering, manual-off suspend/resume intent, AC unplug/replug while
dark, and continuous-lit typing.

## 2026-09-03 live retest

Session `~/.cache/keyrgb/diagnostic-sessions/20260903T184044.723987Z`
partially accepts the live gate:

- Three native sleeps were detected at monotonic times `580171.665`,
  `585007.955`, and `590284.095`, approximately 604.7, 605.0, and 605.2
  seconds after the last captured keyboard event.
- Every initial transition was observed from hardware as `brightness=0` with
  `is_off=False`; KeyRGB did not issue an off command. The only `kb.turn_off`
  operations occurred later as part of the documented keyboard-wake re-arm.
- Screen idle was false at each initial transition, excluding screen-idle
  policy as the owner. The apparently variable delay after the user stops all
  activity is explained by the firmware tracking keyboard inactivity while
  mouse/touchpad activity independently resets desktop idle.
- Each wake had one re-arm and one restore completion.
- OP-1 is live-accepted: during first-key typing, the restore envelope continued
  monotonically (for example `0.708 -> 0.729 -> 0.749`) rather than reversing
  from `0.62 -> 1.0 -> 0.62`.

The session did not exercise suspend/lid, temporary dim, AC unplug/replug while
dark, or continuous-lit typing, so those live matrix rows remain open.

## 2026-09-04 failed suspend/lid restore

Session `~/.cache/keyrgb/diagnostic-sessions/20260903T231854.539789Z`
exercised the previously open controller-sleep-to-system-suspend path and found
an overlapping-event race:

- The controller entered native sleep at `t=596661.872`; KeyRGB detected
  `brightness=0` with `is_off=False` and correctly retained controller-sleep
  ownership.
- At `t=623886.670`, the system-suspend route issued the expected explicit off.
- Resume/open notifications then overlapped; the debug log contains back-to-back
  sysfs and polling lid-open observations. The outcome matches the older restore
  consuming saved lit intent before its generation/revision guard ran, followed
  by a newer event superseding that plan but finding no remaining intent. No
  restore was invoked, and hardware polls remained `brightness=0` with
  `is_off=True`.

The correction makes restore intent two-phase: policy evaluation marks it
pending, and only a current restore action consumes it after execution. A stale
resume therefore leaves the same intent available to the replacement lid-open
event. A newer suspend still replaces a pending restore with current user
intent, preserving manual-off precedence. Focused merged validation passed with
355 power/tray tests, targeted Ruff and Step 19 passed, and BuildPython Step 2
passed with 3803 tests and 1 skip. Another live suspend/lid retest is required
before this matrix row can be accepted.

## 2026-09-04 maximum-brightness flash follow-up

Session `~/.cache/keyrgb/diagnostic-sessions/20260904T141303.659334Z`
contains one maximum observation during an AC transition:

- At `t=656243.427`, the controller reported raw brightness `60`; hardware
  polling normalized this out-of-range value to KeyRGB's UI maximum `50`.
- KeyRGB did not write brightness `50`. The next AC-profile correction began
  roughly 1.5 seconds later and wrote `18 -> 26 -> 34 -> 40`.
- The active render cache still held the prior target `10`, so normal frames
  skipped a brightness write while the hardware remained at its firmware value.
- Hardware polling now routes raw values above `50` through the deck pipeline.
  A running effect records the observed value in its hardware-mode cache and
  seeds a normalized physical baseline of `50`. The normal eight-step frame
  guard then renders `42 -> 34 -> 26 -> 18 -> 10` for a target of `10`, without
  a competing poller write. This handoff remains stepped during temporary dim;
  ordinary intentional dim transitions retain their existing immediate apply.
  Stopped/static effects remain with the existing power-profile correction
  rather than claiming a cache-only recovery succeeded.
- Explicit hardware-off observations never enter this heal, and persistent
  invalid readings cannot restart a successful fade. Failed publication is
  limited to three attempts until a valid-range hardware observation re-arms
  recovery. The handoff also forces the frame guard for uniform-effect pulse
  tails, preventing that backend path from bypassing the controlled descent.
- This cannot prevent the embedded controller's initial full-brightness startup
  before polling detects it; a live AC/resume retest must confirm that the
  remaining max-to-target transition reads as an intentional fade.

## 2026-09-05 native keyboard-wake flash follow-up

Session `~/.cache/keyrgb/diagnostic-sessions/20260905T070406.529305Z`
showed that the final visible flash was not the earlier raw-high polling path:

- Native controller sleep was accepted at log lines `92674-92680` with raw
  brightness `0` and `is_off=False`.
- The keyboard event-driven wake at lines `95779-95953` issued `kb.turn_off`,
  then deliberately restored `1 -> ... -> 40` over 0.60 seconds. No raw `60`
  poll occurred in that final wake window because the evdev path reacted before
  the next hardware poll.
- Combined with live observation that the keyboard naturally wakes at full
  brightness while KeyRGB is closed, the visible sequence was therefore most
  likely firmware-full -> KeyRGB forced-off -> software fade-up. The individual
  software ramp was monotonic, but the forced dark reset made the whole physical
  transition look like a flash.
- Keyboard-event wake now keeps the already-lit native controller on and starts
  reactive rendering with a physical baseline of `50`. It performs no explicit
  `turn_off` and no pre-render target prime; the first frames descend through the
  existing guard (for target `40`, `50 -> 42 -> 40`). Firmware-poll-first wake
  uses the observed normalized brightness as the same handoff baseline.
- Failed effect restart keeps controller-sleep ownership latched for retry.
  Legacy start callbacks remain callable without the new handoff keyword, and
  tray state/UI finalization occurs only after successful restart.
- This correction is reactive-effect-specific. Static, ordinary software, and
  hardware effects continue to restore directly to their target rather than
  claiming a frame-guarded descent.

## 2026-09-05 software-idle reactive release follow-up

Session `~/.cache/keyrgb/diagnostic-sessions/20260905T220953.129561Z`
isolated a separate visual discontinuity after an otherwise valid software-idle
restore:

- The software-owned hardware restore was monotonic from `1 -> ... -> 10`; no
  controller-native wake, raw `60`, forced-off re-arm, or brightness guard
  recovery occurred.
- While the global fade owned rendering, effective reactive brightness remained
  capped at `10` and the damped pulse scale was approximately `0.070`. Clearing
  the follow-global cap released the configured reactive target directly to
  `50`, selecting the contrast-preserving branch at approximately `0.480`.
- The restore path now seeds a second, render-owned release from the completed
  global target to the active reactive/per-key target. Pulse scaling blends over
  that release by elapsed time, so crossing the base-brightness boundary cannot
  create the prior one-frame step. The final scale is calculated from the actual
  reactive target and only an active per-key base map.
- Release publication and follow-global cleanup are generation-checked under the
  engine lifecycle lock, so a replacement effect cannot receive stale release
  state from a superseded fade.
- Focused reactive/controller validation passed with 413 tests. Targeted Ruff,
  `git diff --check`, and Step 19 passed; BuildPython Step 2 passed with 3833
  tests and 1 skip. A live software-idle wake retest remains required to accept
  the visual transition.
