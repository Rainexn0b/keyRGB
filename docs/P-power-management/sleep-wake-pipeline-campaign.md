# Sleep/wake brightness pipeline campaign

**Started:** 2026-09-03  
**Lane:** `P-power-management`  
**Status:** planned — architecture frozen, no implementation started  
**Hardware validation gate:** inherit [KSW-8](keyboard-sleep-wake-hardening-campaign.md)
plus one-restore-per-wake evidence after the pipeline cutover

## Purpose

Collapse overlapping sleep/wake brightness writers into **one intent pipeline**
so a wake cannot start a second ramp, heal, or effect restart while the first
restore is live.

This is the architectural successor to
[keyboard-sleep-wake-hardening-campaign.md](keyboard-sleep-wake-hardening-campaign.md).
That campaign confirmed real races and stopped them with local guards. Those
guards remain the current contract. They are not the durable shape: the same
poll tuple still means different things in different owners, and wake brightness
still jumps because several ramps can run in one window.

Durable policy stays in [controller-sleep-policy.md](controller-sleep-policy.md).
Durable architecture updates land in `docs/1-src/` at campaign exit, not here.

## Why this campaign exists

On wake, these paths can all write brightness, `is_off`, or restart an effect:

| Writer | Typical wake action |
|---|---|
| Idle restore | start at brightness 1, fade toward configured |
| Firmware / controller-sleep wake | restart effect, sometimes at 1 or dim-temp |
| Hardware-poll recovery | heal a 0-read toward configured |
| Reactive render | 60 fps writes, pulses, step guard `0→8→16…` |
| Engine fade / `start_effect` | another ramp plus token/lock serialization |
| Dim-temp, power-source, scheduler/config | extra policy if they fire in the same window |

`TrayRuntimeCoordinator` already serializes **low-frequency execution**. It does
not reconcile **intent**. FIFO last-writer-wins is how a scheduler persist, a
power-source profile, a poll heal, and an idle restore still fight.

A post-wake “clamp to lowest, then release” is **rejected**. Soft-on at
brightness 1, restore damp, and `MAX_BRIGHTNESS_STEP_PER_FRAME` already hold the
deck low. Another hold would be a thirteenth writer and would fight KSW-11
immediate heal plus typing pulses. If lowest is 0, it recreates the dark gap.

## Decision: integrate “Let the controller sleep”

Yes. `controller_sleep_respect` is a first-class pipeline policy input, not a
side flag sprinkled through pollers.

Config key: `controller_sleep_respect` (`IDLE_DISPLAY`, default `False`).  
GUI: Settings → Screen idle/blanking sync → **Let the controller's own sleep
timeout turn the keyboard off**.

The pipeline has two restore policies over the same state machine:

| Setting | Confirmed native sleep (`brightness=0`, backend sleep signature) |
|---|---|
| **Off (default)** | Unintended blank → one auto-heal commit |
| **On** | Valid dark → `CONTROLLER_SLEEP_DARK` until a legal wake |

Legal wakes when the setting is on, unchanged from
[controller-sleep-policy.md](controller-sleep-policy.md):

1. Non-modifier keyboard `EV_KEY` down
2. Power restore (lid/resume), unless user-off or idle-off still holds
3. Manual **Turn On**
4. Firmware-first race: hardware sees `brightness>0 && !is_off` before evdev;
   one restore commit, the trailing evdev restore is a no-op

Mouse, touchpad, compositor-resume, and modifier-only events stay ignored.
Screen-idle off inherits the same key-only restore rule while the setting is on.
Sleep detection stays backend-owned in
`keyrgb/core/backends/policies/sleep_state.py`. No backend-name checks.

Do not drop, invert, or hide this setting to make the pipeline simpler.

## Target architecture

Two layers, not two queues:

```
sensors / menu / power / config / scheduler / hardware poll
        │  emit Intent (observe only)
        ▼
 SleepWakeDecision  (pure: state + policy + observation → plan)
        │  executed inside TrayRuntimeCoordinator.run / run_if_current
        ▼
 DeckPipeline.commit  (the only low-frequency brightness/off writer)
        │
        ▼
 engine start/stop/fade token + kb_lock
        │
        ▼
 reactive/software render frames   ← outside the pipeline once LIT/RESTORING
```

- **Coordinator** remains the single FIFO for low-frequency transitions and
  stale-observation discard.
- **SleepWakeDecision** is the missing arbiter: one function, called *inside* a
  coordinator transition, owns priority and legal transitions.
- **Hardware polling becomes observe-only.** It may classify and enqueue an
  intent. It may not `start_current_effect`, `stop()`, `turn_off()`, or
  render-heal by itself.
- **Render frames stay outside.** 60 fps `set_key_colors` / `set_brightness`
  must not enter the coordinator queue.

## Deck states

`DeckState` is the commit-time authority. Off reasons are not combinable at
commit time. Overlay history (for example “already controller-sleep-dark when
suspend started”) is metadata on `POWER_OFF`, not a second live owner.

| State | Meaning | May write hardware brightness? |
|---|---|---|
| `LIT` | On, configured scene | Render frames only |
| `DIM_TEMP` | `LIT` plus screen-dim cap | Render frames, capped |
| `USER_OFF` | Menu turn-off | No |
| `IDLE_OFF` | Screen-idle / session-idle off | No |
| `POWER_OFF` | Lid/suspend | No |
| `CONTROLLER_SLEEP_DARK` | Honored native sleep | No |
| `RESTORING` | Single in-flight restore | **Yes — the only post-wake writer** |

`DIM_TEMP` is a brightness policy inside `LIT`, not an off state. That is the
KSW-7 rule.

### Restore intent

`RESTORING` carries one `RestoreIntent`:

- `target_brightness`
- `source`: `keyboard_evdev` \| `firmware_wake` \| `power_resume` \| `screen_wake` \| `manual_on` \| `auto_heal`
- `dim_temp_target` if screen-dim still owns the cap
- `revision` from `capture_transition_revision()`
- `guard_until` for the resume/relight guard

No `RESTORING → RESTORING` stacking. A second restore intent while restoring is
either coalesced into the same target or dropped as stale.

### Priority

Highest wins. Lower intents persist as deferred config when they must not light
the deck.

1. **User off / manual on**
2. **Power off / power restore**
3. **Controller-sleep dark** (only if `controller_sleep_respect`) **or idle off**
4. **Dim-temp cap** (inside lit)
5. **Deferred brightness/profile** (scheduler, power-source, config) — persist
   intent, no hardware apply while any off family is active
6. **Poll observations** — never commit

This preserves KSW-0 forced-off precedence, KSW-9/KSW-10 deferred apply, and
KSW-1 already-dark suspend (no wake-capable fade).

## What current writers become

| Current writer | Becomes |
|---|---|
| Hardware poll `_apply_polled_hardware_state` | Observer. Emits `ControllerSleep`, `FirmwareWake`, `StableZero`, `PowerSourceBlank`. |
| Idle `apply_idle_action` / `_maybe_restore_from_controller_sleep` | Observer. Emits `IdleTurnOff`, `DimToTemp`, `ScreenWake`, `KeyboardWake`. |
| Power `power_turn_off_impl` / `power_restore_impl` | Intent via pipeline. Already-dark immediate off stays a `POWER_OFF` commit detail. |
| Power-source / battery-saver brightness and profile | Deferred intent while off-family; consumed by the next `RESTORING` commit. |
| Config apply / time scheduler | Persist config; skip hardware apply while off-family (generalize KSW-9). |
| Menu turn on/off | First pipeline client; still enters through `run_tray_transition`. |
| Render-heal `_reassert_user_mode_while_running_best_effort` | Pipeline action during `RESTORING` or `LIT` auto-heal, not a poller side effect. |
| Reactive render + fade steps | Stay outside. Pipeline seeds restore damp **once** at commit start. |

## Campaign rules

1. One workstream per implementation pass.
2. Begin from current code and nearby tests, not from this summary alone.
3. Preserve `TrayRuntimeCoordinator`, transition revisions, forced-off
   ownership, `kb_lock`, `backend_caps`, Linux-first behavior, and
   brightness-only backend validity.
4. Do not introduce backend-name policy checks. Sleep signatures stay in
   `keyrgb/core/backends/policies/sleep_state.py`.
5. Do not route render frames or per-step fades through the coordinator.
6. Do not add a post-wake brightness clamp or extra hold timer.
7. Do not bypass or invert `controller_sleep_respect`.
8. Public entrypoints stay stable unless a workstream explicitly changes them.
9. Broad exception / runtime-boundary edits run
   `python -m buildpython --run-steps=19`.
10. Worker-side green runs are supporting evidence only. Merged validation in
    the primary worktree is authoritative.
11. Do not start the live matrix while a workstream is `active` or an accepted
    correction is unvalidated.

## Conventions

- Priority: `P0` blocks trustworthy hardware testing; `P1` correctness; `P2`
  defensive / docs.
- Effort: `S`, `M`, or `L`.
- Status: `reported`, `confirmed`, `active`, `rejected`, `monitoring`, `done`,
  `blocked` — same vocabulary as the KSW campaign.

## Inventory

| ID | Concern | Priority | Effort | Status |
|---|---|:---:|:---:|---|
| SWP-0 | Pure `DeckState` / `SleepWakeDecision` with no behavior change | P0 | S | reported |
| SWP-1 | Hardware poll observe-only; one restore commit owns heal/wake/sleep | P0 | M | reported |
| SWP-2 | Idle and power paths emit intents; unify post-resume suppression | P0 | M | reported |
| SWP-3 | Defer scheduler, config, and power-source hardware applies while off-family | P1 | S | reported |
| SWP-4 | Menu turn on/off cutover; `controller_sleep_respect` read once per decision | P1 | S | reported |
| SWP-5 | Remove dual-write of legacy off flags once `DeckState` is sole owner | P2 | M | reported |
| SWP-6 | Docs/architecture exit plus inherited KSW-8 live matrix | P0 | M | blocked — SWP-0..4 |

---

## SWP-0 — Pure decision table

**Question.** Can legal transitions and `controller_sleep_respect` be expressed
as a pure function with no I/O?

**Correction contract.** Add a tray-local leaf (suggested:
`keyrgb/tray/pollers/idle_power/sleep_wake_decision.py` or
`keyrgb/tray/deck_state.py`) with:

- `DeckState` enum
- intent dataclasses
- `next_state(state, intent, *, respect, now, guards) -> (state, plan)`

Extend `TrayIdlePowerState` with `deck_state` plus deferred brightness/profile
fields. Keep `controller_sleep_off` / forced-off bridges. A thin
`DeckPipeline.enqueue` may call existing apply helpers so behavior is unchanged.

**Required tests.** Exhaustive table for respect on/off, forced-off precedence,
dim-temp vs off, firmware-vs-evdev coalescing, and “no second restore while
`RESTORING`”. No hardware I/O.

**Non-goal.** Do not move commits yet.

## SWP-1 — Hardware poll observe-only

**Question.** Can `_apply_polled_hardware_state()` stop committing?

**Correction contract.** Poll and classify as today. Commit only by enqueueing
intents into the pipeline inside `run_tray_observation_if_current`. Move
engine stop, firmware-wake restart, stable-zero recover, power-source blank
recover, and render-heal into `DeckPipeline.commit`. Keep fast zero-confirm
polling as observation cadence, not as a second healer.

This is where overlapping wake ramps actually die. KSW-11’s immediate
post-restore zero heal becomes one `RESTORING`/`LIT` auto-heal plan, not a
second poller branch.

**Required tests.** Existing hardware polling brightness/loop tests plus
“poller does not call `start_current_effect` / `engine.stop`”.

## SWP-2 — Idle and power intents

**Question.** Can idle restore and power restore share the same `RESTORING`
commit?

**Correction contract.** `compute_idle_action()` stays pure. Runtime emits
intents instead of calling `apply_idle_action` / `restore_from_idle` directly.
`PowerManager` lid/suspend/resume emit `PowerOff` / `PowerResume`. Fold
`POST_RESUME_IDLE_ACTION_SUPPRESSION_S` and
`POWER_SOURCE_POST_RESUME_SUPPRESSION_S` into one pipeline guard. Preserve
soft-on at brightness 1, restore-damp seed-once, and dim-temp cap across
firmware-first vs evdev-first wakes (KSW-7).

**Required tests.** Existing idle runtime / power-state tests rewritten against
intents where they currently assert direct engine calls.

## SWP-3 — Deferred hardware apply

**Question.** Can every config/scheduler/power-source brightness change persist
without lighting an off-family deck?

**Correction contract.** Generalize KSW-9 (`config:skipped_controller_sleep_off`)
and KSW-10 (`defer_hardware_apply` under any forced-off) to all off-family
states. Next `RESTORING` commit consumes the latest deferred brightness and
profile atomically.

**Required tests.** Scheduler persist while `CONTROLLER_SLEEP_DARK`,
power-source profile while `IDLE_OFF`, config apply while `USER_OFF` /
`POWER_OFF`.

## SWP-4 — Menu cutover and single policy read

**Question.** Is `controller_sleep_respect` snapshotted once per decision
instead of via scattered `safe_bool_attr` reads?

**Correction contract.** Menu turn on/off route through `DeckPipeline`.
`SleepWakeDecision` takes `respect: bool` plus `controller_sleep_off` as
explicit inputs. Hardware latch, idle key-only restore, and config-skip all
consume that snapshot.

**Required tests.** Respect enabled/disabled matrix covering latch, key-only
idle restore, firmware wake coalescing, and deferred scheduler persist.

## SWP-5 — Legacy flag collapse

**Question.** After SWP-0..4, can `_user/_idle/_power_forced_off` and
`controller_sleep_off` become derived views of `DeckState`?

**Correction contract.** Keep the public tray attribute seam until tests and
fakes migrate. Then derive the bools from `DeckState` so a future flag cannot
drift. Optional; do not start before SWP-4 is `monitoring`.

## SWP-6 — Exit gate

Software exit:

- SWP-0..4 `done` or `monitoring`
- focused hardware/idle/power/config tests plus Ruff
- `python -m buildpython --run-steps=19` if exception boundaries moved
- authoritative `PYTHONPATH="/tmp/opencode/keyrgb-pyusb${PYTHONPATH:+:$PYTHONPATH}" python -m buildpython --run-steps=2`
- `git diff --check`
- patch [controller-sleep-policy.md](controller-sleep-policy.md) only for
  pipeline-owned wording (scheduler/power-source defer, single restore commit)
- patch `docs/1-src/13-tray-runtime-state-ownership.md` and, if needed,
  `docs/1-src/08-reactive-brightness-invariants.md`

Live matrix: inherit KSW-8, plus:

- exactly one `RESTORING` commit per wake (no duplicate
  `controller_sleep_firmware_wake` + idle restore)
- typing after controller-sleep wake stays continuously lit (KSW-11)
- AC unplug/replug while idle-off does not strand the deck (KSW-10)
- scheduler brightness change while respected-sleep stays dark (KSW-9)

Runtime capture:

```bash
./keyrgb.sh --diagnostic-session --diagnostic-mode=full
```

## Non-goals

- Clamp-to-lowest-then-release, extra post-wake hold timers, or a second
  brightness queue beside `TrayRuntimeCoordinator`
- Routing reactive/software frames through the coordinator
- Changing pulse visual shape, GUI panel layout, or the
  `controller_sleep_respect` config schema
- New ITE USB IDs, backend-name branches, or treating dim-temp as an off flag
- Replacing evdev / `InputIdleTracker`
- Reopening KSW-0..11 as new defects without new evidence
- Implementing `docs/O-optimisations/dim-undim-reactive-typing-review-improvement-plan.md`
  Items 1–9 (thread-safety, constant extraction). Consume them if already
  landed; do not re-implement them here

## Residual risks

- ITE can report a non-zero register while physically dark. The pipeline still
  cannot sense LED current. Keep the lightweight auto-heal; do not add a
  forceful `off → soft-on` strategy without new hardware evidence.
- Evdev can miss the first key. Firmware-wake fallback must remain a *single*
  coalesced restore, not a second ramp.
- Fade steps that sleep on the coordinator owner already stall the FIFO.
  Pipeline commits must not add more owner-thread sleeps.
- `ConfigPersistenceError` rollback must also roll back deferred pipeline
  intent, or the next restore uses a stale target.
- Help text currently says only a keypress restores lighting; power restore and
  manual Turn On also restore. Fix copy only if a later pass touches the panel.

## Related documents

- [controller-sleep-policy.md](controller-sleep-policy.md) — durable sleep/wake
  contract; this campaign must satisfy it
- [keyboard-sleep-wake-hardening-campaign.md](keyboard-sleep-wake-hardening-campaign.md)
  — predecessor defect tracker; cite KSW IDs, do not copy evidence tables
- [power-mode-verification-refactor-plan.md](power-mode-verification-refactor-plan.md)
  — apply vs observation split for power *modes* (not keyboard brightness)
- `docs/1-src/13-tray-runtime-state-ownership.md` — coordinator / revision rules
- `docs/1-src/14-policy-ownership.md` — sleep signatures stay backend-owned
- `docs/1-src/08-reactive-brightness-invariants.md` — temp-dim ceiling, no
  per-key global brightness bump, `SET_BRIGHTNESS` is a frame commit
- `docs/1-src/16-effect-runtime-contracts.md` — engine start/stop/fade
- `docs/O-optimisations/dim-undim-reactive-typing-review-improvement-plan.md` —
  adjacent render-state work, not this campaign
- `docs/I-implementation-plans/2026-08-11/a2-tray-runtime-coordinator-design.md`
  — coordinator must not own effect frames

## Progress log

### 2026-09-03 — campaign opened

- Confirmed overlapping wake writers and rejected clamp-to-lowest.
- Froze `controller_sleep_respect` as a first-class pipeline policy input.
- No code changes in this pass.
