# Runtime Policy Ownership Follow-up Campaign

**Started:** 2026-09-03  
**Baseline:** `~/.cache/keyrgb/diagnostic-sessions/20260903T092201.323445Z`  
**Status:** OP-1..2 software-complete; OP-3..4 planned; live retest pending

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
| OP-1 | Reactive restore frame and pulse ownership | Evidenced first-key scale discontinuity and duplicate damp seeding | software-complete; live retest pending |
| OP-2 | `start_current_effect` menu/power callers | Remaining SWP-4 intent-bypass seam; not triggered in baseline | software-complete; live retest pending |
| OP-3 | Layered brightness scheduler/menu deferral | Scheduler drops deferred intent; menu omits unified off-family predicate | planned |
| OP-4 | CPU power-mode apply/observation | Main split landed; EPP failures remain silent and policy can retry heuristic mismatches | planned |

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
