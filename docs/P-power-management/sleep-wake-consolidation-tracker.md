# Sleep/wake consolidation tracker

Started: 2026-10-22

Status: **software implementation and automated validation complete**.
Live hardware acceptance remains pending.

## Goal

Complete the existing deck pipeline's ownership of sleep/wake state, execution
outcomes, and cancellation. Preserve forced-off precedence, controller-native
wake handoff, temporary dim limits, renderer generations, and `kb_lock`.

## Work items

| ID | Work | Status |
|---|---|---|
| SWC-1 | Prevent observation/no-op polling from cancelling power events | implemented |
| SWC-2 | Propagate restore outcomes and retain failed restore ownership | implemented |
| SWC-3 | Reassert the scene on resume even when suspend-off is disabled | implemented |
| SWC-4 | Share closed-lid eligibility and retain overlapping power causes | implemented |
| SWC-5 | Make deck ownership authoritative; derive compatibility views | implemented |
| SWC-6 | Share restore lifecycle, completion, rollback, and diagnostics | implemented |
| SWC-7 | Move resume/fade waits outside the runtime coordinator | implemented |
| SWC-8 | Bound pre-suspend shutdown and evaluate logind delay inhibition | implemented; inhibition evaluation recorded |
| SWC-9 | Remove unused state/classifiers and duplicate signal parsing | implemented |
| SWC-10 | Replace callback signature/retry compatibility at restore boundaries | implemented |
| SWC-11 | Add end-to-end sequence coverage and update architecture docs | implemented and validated |

## Baseline evidence

- 701 focused power, deck, hardware-polling, and idle-power tests pass.
- Mocked production-path reproductions expose dropped suspend/lid-off actions
  after a queued no-op, consumed failed restores, skipped resume reassertion,
  and different closed-lid eligibility on initial wake versus retry.
- The current coordinator FIFO and stale-observation protection remain required;
  render frames must remain outside that FIFO.

## Validation

Each correction receives a regression at the production orchestration boundary.
Run focused power/tray/effects tests during implementation, then the complete
hardware-disabled suite and applicable BuildPython CI, architecture, and
exception-transparency checks. Record exact commands and results below.

Live acceptance remains a separate evidence gate: native controller sleep,
firmware-first and keyboard-first wake, temporary dim, user-off, lid overlap,
suspend with off disabled, failed-device recovery, and cancellation during fades.

## Implementation and validation ledger

- SWC-1: explicit lighting intent has a revision independent of observation
  FIFO traffic. Production-boundary tests queue a no-op behind suspend/lid-off
  and verify the off still commits. Manual on/off remains superseding intent.
- SWC-2/6: `LightingResult` crosses controller, facade and power-manager seams.
  The shared `RestoreContext` owns snapshots, completion and rollback for manual,
  power, screen-idle and native wake. Tests cover false returns, exceptions,
  asynchronous device failures, duplicate completion and retry backoff.
- SWC-3/4: resume can reassert from `LIT`/`DIM_TEMP`. Initial and retried restore
  use the same physical blockers. Lid-open cannot release suspend; a disabled
  resume restore cannot consume the still-closed lid's original lit intent.
- SWC-5 design refinement: overlapping causes require one typed ownership
  record, not a single exclusive off enum. `deck_state` is now a read-only
  projection of that record and its restore phase; the contradictory cached
  stable enum is gone. Production legacy attributes already proxy the owner.
  Duck-typed bridges remain at the compatibility boundary.
- SWC-7: resume uses a 0.5-second monotonic deadline; engine fades reserve tokens
  synchronously and run outside the FIFO. Restore completion re-enters the
  coordinator. Reactive release follows actual fade completion and renderer
  generation. In-flight restore samples cannot trigger hardware heal/adoption.
  Manual-off and engine-close invalidate stale fade writes.
  Config/menu/scheduler edits coalesce one latest-scene reapply after the fade;
  source classification waits until completion. This prevents edits from
  invalidating the restore token or silently retaining the old brightness.
- SWC-8: power-off is immediate, avoiding fade/flatten work before suspend;
  effect-worker join remains capped at two seconds. Evaluated logind delay
  inhibition: the current text monitor cannot hold the returned Unix FD.
  No inhibitor was added; a future FD-capable monitor needs lifecycle and live
  desktop evidence. Backend I/O retains its own timeout contract.
- SWC-9/10: removed unused saved/deferred/restore-target state and obsolete
  sleep-off helper; live login1 monitoring uses the shared parser. Native and
  idle restore starters receive the declared keywords once, without signature
  inspection or retrying a callback after `TypeError`.
- SWC-11: sequence tests live in
  `tests/tray/pipeline/test_sleep_wake_sequences_unit.py`. Existing event,
  native-wake and controller tests now assert explicit outcomes/deadlines.
  Architecture is recorded in
  [tray runtime ownership](../1-src/13-tray-runtime-state-ownership.md) and
  [effect runtime contracts](../1-src/16-effect-runtime-contracts.md).

### Validation runs

- Focused expanded run: **1,040 passed** (before the final overlap/error/poll
  regressions were added):

  ```bash
  .venv/bin/python -m pytest tests/core/power tests/tray/pipeline \
    tests/tray/controllers/power tests/tray/pollers/hardware \
    tests/tray/pollers/idle_power tests/tray/test_deck_state_unit.py \
    tests/tray/test_lighting_power_pipeline_op2_unit.py \
    tests/core/effects/engine tests/tray/controllers/core -q -o addopts=
  ```

- Follow-up power/sequence run: **175 passed**.
- Final targeted orchestration/config/controller run: **504 passed**:

  ```bash
  .venv/bin/python -m pytest tests/tray/pipeline/test_sleep_wake_sequences_unit.py \
    tests/tray/controllers/core tests/tray/pollers/config \
    tests/tray/controllers/power tests/core/power/manager -q -o addopts=
  ```
- First CI run: **5,226 passed, 1 skipped**, coverage **89.99%**; compile,
  lint/format, import/dependency, typing, coverage and exception checks passed.
  Code Hygiene identified two new private-attribute `getattr` calls, now
  replaced with typed fields.
- Subsequent full suite: **5,229 passed, 1 skipped**. File-size checks prompted
  consolidating deferred worker startup into the existing engine
  `_start_support.py` and eliminating duplicate fade-call branches.
- Post-extraction focused engine/sequence/controller check: **251 passed**.
- Final static gate command: **11/11 passed**, including architecture,
  exception transparency, typing, hygiene, size/LOC, dead code and repo checks:

  ```bash
  .venv/bin/python -m buildpython --run-steps=3,6,7,12,13,16,17,19,20,21,10
  ```

  No gate baseline or size waiver was added.
- Standalone Architecture Validation passed: **24 rules, 0 errors/warnings**.
  Standalone Dead Code passed. `git diff --check` passed.

### Final verification

```bash
.venv/bin/python -m buildpython --profile=ci
git diff --check
```

**PASS: 18/18 CI steps**, **5,229 tests passed, 1 skipped** with hardware tests
disabled; overall coverage **89.97%**. Architecture: **24 rules, 0 errors and
0 warnings**. Typing, exception transparency, hygiene, dead-code, size/LOC,
formatting, dependency, shell and repository checks all passed.

Full run output: `/tmp/opencode/swc-ci-verified.log`; individual gate logs:
`buildlog/keyrgb/`.

Live acceptance items in the validation section above are deliberately still
open; automated fake-device sequences do not establish physical LED behavior.

## Follow-up lifecycle hardening (2026-10-22)

- Engine close now has a terminal closed state, serialized with effect startup.
  Device acquisition/publication and fade-token checks share `kb_lock`, so a
  delayed or cancelled fade cannot reopen a released keyboard. Deferred fade
  workers are tracked per engine and drained outside engine locks with a shared
  two-second deadline. Jobs queued across close settle without starting.
- Failed/cancelled restore cleanup logs secondary engine errors while retaining
  the original failure, restoring ownership and resolving completion. An
  asynchronous cleanup failure leaves power restore eligible for a later retry;
  transition logging also cannot orphan completion.
- Regressions cover delayed brightness/off fades, cancellation before acquisition,
  queued jobs across close, completion re-entry during drain, the shared drain
  budget, thread-start failure, secondary cleanup failures, cancellation and
  asynchronous retry.
- Focused engine/pipeline/power/idle/app run: **393 passed**.

  ```bash
  .venv/bin/python -m pytest tests/core/effects/engine tests/tray/pipeline \
    tests/tray/controllers/power tests/tray/pollers/idle_power/runtime \
    tests/tray/app -q -o addopts=
  ```
- Full follow-up CI: **18/18 gates passed**, **5,242 passed, 1 skipped**, coverage
  **90.00%**. Architecture: **24 rules, 0 errors/warnings**. Exception transparency,
  typing, hygiene, size/LOC and all remaining CI checks passed. `git diff --check`
  passed. Hardware tests remained disabled.

  ```bash
  .venv/bin/python -m buildpython --profile=ci
  git diff --check
  ```

  Full output: `/tmp/opencode/swc-lifecycle-ci.log`; individual gate logs:
  `buildlog/keyrgb/`. Live hardware acceptance remains pending.

## Follow-up: Wake on any input (2026-10-22)

- Added the default-off `wake_on_any_input` config/diagnostics field and the
  **Settings → Advanced → Controller sleep and idle timing → Wake on any input**
  checkbox. It is available while controller-sleep respect is enabled.
- Added timestamped modifier/button/pointer evdev evidence and a dark-period
  input-only Wayland v2 listener for touchpads/devices unavailable through evdev.
  Startup, reconnect, stale events and ordinary active-session status cannot
  manufacture a wake. Listeners close on policy changes and shutdown.
- Added `INPUT_WAKE` to the existing decision/restore pipeline. It honors the
  latest overlapping off timestamp, manual/power-off precedence, configured zero,
  temporary dim limits, screen-idle gates, and backend settle timing. A locked
  hardware probe chooses native firmware handoff versus host soft-on. Failed
  restores retain ownership; duplicate and stale input cannot start another fade.
- Focused settings/config/idle/pipeline run: **613 passed**:

  ```bash
  .venv/bin/python -m pytest tests/gui/settings tests/core/config \
    tests/tray/pollers/idle_power tests/tray/pipeline \
    tests/tray/test_deck_state_unit.py -q -o addopts=
  ```

  Output: `/tmp/opencode/any-input-focused.log`.
- Follow-up pointer-then-key regression reproduced an early native handoff.
  Firmware settling now keeps its own deadline; elapsed pointer-wake waiting
  cannot substitute for firmware evidence. Focused wake/hardware/idle runtime
  verification: **135 passed**.
- Final CI: **18/18 gates passed**, **5,297 passed, 1 skipped**, coverage
  **90.06%**. Architecture: **24 rules, 0 errors/warnings**. Typing, exception
  transparency, hygiene, formatting and remaining gates passed. `git diff --check`
  passed. Hardware tests remained disabled.

  ```bash
  .venv/bin/python -m buildpython --profile=ci
  git diff --check
  ```

  Full output: `/tmp/opencode/any-input-ci-final.log`; individual gate logs:
  `buildlog/keyrgb/`.
- Live acceptance adds modifier-only, touchpad/mouse-only, no-evdev Wayland,
  firmware-first input wake, repeated input during a fade, and overlapping
  screen-idle/native sleep. These remain pending physical LED evidence.
