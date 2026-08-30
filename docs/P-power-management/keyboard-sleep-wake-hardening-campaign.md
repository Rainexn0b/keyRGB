# Keyboard sleep/wake hardening campaign

**Started:** 2026-08-30  
**Lane:** `P-power-management`  
**Status:** active — investigation and correction campaign  
**Hardware validation gate:** deferred until every workstream has a recorded
disposition and all accepted corrections pass merged validation

## Purpose

Independently investigate the remaining keyboard sleep/wake and computer
suspend/resume concerns identified while diagnosing the ITE 8291r3 controller
sleep race. A reported concern is not automatically a defect. Each workstream
must establish the intended contract, reproduce or reject the suspected
interleaving, and make the smallest owner-local correction only when evidence
shows that one is needed.

After the software campaign is complete, run a new full diagnostic session and
verify both:

1. keyboard-controller sleep and keyboard-input wake; and
2. computer suspend and resume, with the lid open and with normal lid policy.

This tracker records investigation, decisions, implementation evidence, and the
final hardware retest. Durable policy changes belong in
`controller-sleep-policy.md` or the relevant `docs/1-src/` architecture document.

## Baseline incident evidence

Two diagnostic sessions established the current baseline:

- `~/.cache/keyrgb/diagnostic-sessions/20260829T162211.829792Z/`
  exercised controller-native sleep and screen-idle restores but did not include
  a system suspend.
- `~/.cache/keyrgb/diagnostic-sessions/20260829T213638.352322Z/`
  captured a real `s2idle` cycle. During suspend turn-off, KeyRGB called
  `kb.turn_off`, then a non-zero fade sample was misclassified as
  `hardware:controller_sleep_firmware_wake` about 42 ms later. The effect was
  restarted at brightness 10 before the kernel entered suspend.

The immediate forced-off-precedence correction currently touches:

- `keyrgb/tray/pollers/hardware_polling.py`; and
- `tests/tray/pollers/hardware/test_tray_hardware_polling_brightness_unit.py`.

It is locally validated but remains `monitoring` until a post-campaign hardware
session proves that suspend stays dark and resume restores exactly once.

## Campaign rules

1. Work on one inventory item per implementation pass.
2. Begin from current code and nearby tests; do not implement directly from this
   summary.
3. Record one disposition: `confirmed`, `rejected`, `monitoring`, or `blocked`.
4. For a confirmed defect, write a failing regression/contract test before or
   with the correction.
5. Put the correction in the nearest owner. Do not bypass the tray runtime
   coordinator or introduce backend-name policy checks.
6. Preserve the public entrypoints, `backend_caps` model, Linux-first behavior,
   and brightness-only backend validity.
7. Do not weaken `kb_lock`, transition revisions, forced-off ownership, or the
   controller-sleep resume guard to solve a local symptom.
8. Any runtime fallback or exception-boundary change must remain explicit and
   logged and must run `python -m buildpython --run-steps=19`.
9. Worker-side checks are supporting evidence; merged validation in the primary
   worktree is authoritative.
10. Do not begin the final live logging phase while an accepted correction is
    unvalidated or an item remains `active`.

## Conventions

- Priority: `P0` blocks trustworthy hardware testing; `P1` correctness or
  reliability; `P2` defensive hardening.
- Effort: `S`, `M`, or `L`.
- Status:
  - `reported` — awaiting an independent inspection;
  - `confirmed` — evidence establishes a defect and contract;
  - `active` — current investigation or correction pass;
  - `rejected` — suspected defect disproved, with evidence recorded;
  - `monitoring` — corrected locally but awaiting merged or hardware evidence;
  - `done` — correction and required evidence complete;
  - `blocked` — named evidence or dependency is unavailable.

## Inventory

| ID | Concern | Priority | Effort | Status |
|---|---|:---:|:---:|---|
| KSW-0 | Forced-off transition can be mistaken for controller firmware wake | P0 | S | monitoring |
| KSW-1 | Suspending an already controller-sleep-dark deck may wake it to perform a fade | P1 | S | reported |
| KSW-2 | `dbus-monitor` exit or callback failure can permanently end suspend/resume monitoring | P1 | M | reported |
| KSW-3 | A non-reactive software effect may commit one final frame after mode-off is latched | P1 | S | reported |
| KSW-4 | Starting a new effect may not cancel an in-flight brightness fade | P2 | S | reported |
| KSW-5 | Concurrent direct `start_effect()` calls may leave two software workers alive | P2 | M | reported |
| KSW-6 | Disabling power management between suspend and resume may retain stale saved intent | P2 | S | reported |
| KSW-7 | Firmware wake during temporary dim policy may restore the wrong brightness policy | P2 | S | reported |
| KSW-8 | Final merged software validation and live hardware matrix | P0 | M | blocked on KSW-0–KSW-7 |

---

## KSW-0 — Forced-off precedence over firmware wake

**Question.** Can a poll sampled during suspend/off fade restart a controller
sleep-stopped effect after a forced-off owner has claimed the deck?

**Current evidence.** Confirmed by the second diagnostic session. The poller saw
a non-zero in-flight fade sample while `controller_sleep_off` remained latched
and restarted the effect despite `power_forced_off=True`.

**Correction contract.** User-, power-, and idle-forced off states take
precedence over firmware-wake adoption. A forced-off observation must remain
logically off and must not clear controller-sleep state, stamp resume state, or
restart an effect.

**Existing local evidence.** The focused regression and broader hardware/power
suite pass. Keep this item `monitoring` until KSW-8 confirms the physical deck
turns off before suspend and restores only after resume.

## KSW-1 — Already-dark suspend must not visibly wake to fade

**Question.** When `controller_sleep_off=True` and the physical deck is already
dark, does `power_turn_off_impl()` call `engine.turn_off(fade=True)`, flatten the
per-key frame, re-enter user mode, and visibly light the deck before fading it
back to off?

**Investigation.**

1. Characterize `power_turn_off_impl()` with controller sleep active.
2. Record ITE calls made by `_flatten_perkey_frame_for_fade()`, the brightness
   fade, and final `kb.turn_off()`.
3. Distinguish cached engine brightness from physical controller brightness.
4. Confirm behavior for non-controller-sleep backends remains unchanged.

**Decision rule.** If the already-dark path issues a wake-capable color/mode
write, correct it. Prefer an immediate explicit off without flatten/fade while
retaining the final off command, secondary-target shutdown, forced-off state,
and resume eligibility.

**Required tests.** Already-dark controller sleep uses no wake-capable fade
writes; ordinary on-state suspend still uses the configured fade; secondary
targets still turn off.

## KSW-2 — Suspend/resume monitor lifecycle reliability

**Question.** Can `dbus-monitor` EOF, process failure, malformed output, or a
recoverable callback exception silently terminate power monitoring for the rest
of the tray session?

**Investigation.**

1. Exercise clean EOF, non-zero child exit, callback failure, shutdown, and
   normal true/false `PrepareForSleep` signals.
2. Verify process registration/termination and ensure restart logic cannot busy
   loop during shutdown or repeated process failure.
3. Determine whether recovery belongs in `login1_monitoring.py` or the manager's
   monitor runner; preserve the ACPI fallback contract.
4. Add diagnostic logging that distinguishes signal receipt, policy no-op,
   process exit, and monitor restart where needed.

**Decision rule.** A monitor that exits while `manager.monitoring` remains true
must be restarted with bounded backoff or fail over explicitly. Recoverable
callback failures must be logged without silently removing future monitoring.

**Required tests.** EOF restart, callback failure continuation, bounded backoff,
shutdown termination, and no duplicate callback from one signal.

## KSW-3 — Post-off software-frame commit

**Question.** Can a non-reactive software effect pass its loop stop check, wait
for `kb_lock`, and commit one final frame after `_device_mode_off=True`?

**Investigation.** Compare `software/base.py::render()` with the reactive
hardware-write guard. Reproduce an in-flight render blocked on `kb_lock`, then
turn off or accept controller-native sleep before releasing the frame.

**Decision rule.** If a post-off frame can commit, add the smallest shared
write-eligibility check at the final locked commit boundary. Do not rely solely
on loop exit or a later corrective off.

**Required tests.** Both per-key and uniform software rendering perform no
primary or secondary output after mode-off; ordinary rendering remains intact.

## KSW-4 — In-flight brightness fade versus new effect

**Question.** Can `start_effect()` begin a replacement effect while a prior
brightness fade continues writing brightness with an old token?

**Investigation.** Establish every production caller and whether the tray
coordinator already makes the interleaving impossible. Separately test the
public engine-level lifecycle contract with a blocked fade and direct effect
start.

**Decision rule.** Reject as a production race if all supported callers are
serialized and the engine API is explicitly owner-thread-only. Otherwise cancel
the old fade at a lifecycle boundary without invalidating the replacement
effect's own fade.

**Required tests if corrected.** No old-token brightness writes after effect
start; turn-off's own fade still completes; no new lock-order inversion.

## KSW-5 — Concurrent direct effect starts

**Question.** Can two direct `EffectsEngine.start_effect()` calls both pass
through stop/start and leave two software workers writing serialized but
competing frames?

**Investigation.** Reproduce with controlled barriers around stop and worker
publication. Map every production caller and document whether the engine is
allowed to depend on external tray serialization.

**Decision rule.** If the engine is a supported concurrent facade, serialize
the complete lifecycle or make worker loops generation-aware. If it is strictly
single-owner, record and enforce that contract rather than adding unnecessary
locking.

**Required tests if corrected.** Concurrent starts leave exactly one current
worker; stale workers exit; stop/close timeout behavior and `kb_lock` ordering
remain unchanged.

## KSW-6 — Saved power intent across enable/disable changes

**Question.** Can `PowerEventPolicy._saved_was_off` survive a disabled resume and
incorrectly suppress restore during a later independent suspend cycle?

**Investigation.** Characterize suspend while enabled, resume while disabled,
manual relight, re-enable, then a second suspend/resume. Also cover action flags
being disabled independently of the global management switch.

**Decision rule.** If stale intent crosses into a new ownership epoch, clear it
when management is disabled while preserving normal overlapping lid+suspend
behavior.

**Required tests.** The toggle sequence starts the next cycle from current
intent; ordinary lid+suspend overlap still saves intent once and restores once.

## KSW-7 — Firmware wake under temporary dim policy

**Question.** If firmware wakes while screen dim synchronization owns a temporary
brightness, can the controller-sleep firmware-wake path restart at the configured
full brightness and bypass the temporary target?

**Investigation.** Reproduce controller sleep plus active temporary dim for both
per-key and uniform effects. Define whether keyboard activity should remain dark,
restore to the temporary dim target, or restore normal brightness according to
the current user policy.

**Decision rule.** Correct only after the intended UX is explicit. Do not simply
treat temporary dim as another forced-off flag: it is a brightness policy, not
necessarily an off owner.

**Required tests if corrected.** Firmware-first and evdev-first wake ordering
produce one restore and the same policy-correct brightness.

## KSW-8 — Merged validation and live hardware matrix

### Software exit gate

Before live testing:

- every KSW-0–KSW-7 item is `done`, `rejected`, `monitoring`, or explicitly
  `blocked` with named missing evidence;
- every confirmed item has regression coverage;
- focused Ruff and pytest selections pass;
- the complete power-management, idle-power, hardware-polling, and effects
  lifecycle suites pass;
- `python -m buildpython --run-steps=19` passes for every fallback/runtime
  boundary touched;
- the applicable merged BuildPython profile is green; and
- `git diff --check` passes with only intended files modified.

### Runtime selection

Use the updated checkout explicitly so an installed AppImage cannot obscure
which code is under test:

```bash
./keyrgb.sh --diagnostic-session --diagnostic-mode=full
```

Record session paths and local wall-clock times for each physical observation.
Prefer separate, short sessions for controller sleep and system suspend if that
makes event attribution clearer.

### Live matrix

1. **Controller-native sleep:** allow the firmware timer to darken the keyboard.
   Confirm one `hardware:controller_sleep_off` and no automatic relight while the
   respect setting is enabled.
2. **Input filtering:** verify touchpad/mouse and modifier-only input stay dark;
   verify one non-modifier key restores once.
3. **Screen idle:** verify configured screen-idle off/dim and keyboard restore,
   with no duplicate controller-sleep restore.
4. **Lid-open system suspend:** suspend explicitly with the lid open. Confirm the
   deck is dark before `PM: suspend entry`, remains dark during sleep, and
   restores once after `PM: suspend exit`.
5. **Lid close/open:** verify close and suspend do not double-off or overwrite
   saved intent; verify open/resume do not double-restore.
6. **Pre-suspend native sleep:** let the controller become dark first, then
   suspend. Confirm there is no wake/flash during the suspend transition and the
   configured scene returns after resume.
7. **Manual-off intent:** suspend and resume while manually off; confirm resume
   does not override explicit user intent.

### Hardware acceptance criteria

- No effect or brightness write relights the deck between power turn-off and
  kernel suspend entry.
- No stuck-dark state after an eligible keyboard wake or power resume.
- No duplicate off/restore sequence or visible off-on-off/on-off-on flicker.
- Hardware brightness zero is never persisted as configured user brightness.
- Resume produces either one policy-approved restore or an explicitly logged
  no-op explaining preserved user/idle intent.
- No USB disconnect, hardware polling error, monitor termination, traceback, or
  silent fallback appears in the session.
- `diagnostics-after.json` still selects the expected backend and exposes the
  same device identity as `diagnostics-before.json`.

## Candidate hardening outside the main inventory

Do not widen the campaign automatically for these unless an investigation above
produces evidence:

- coordinator-less test/fallback execution is not a current production path;
- the firmware-wake reducer's benign fall-through may cause redundant UI work
  but has not shown incorrect state;
- `kb_lock` is intentionally an `RLock`; changing it to a non-reentrant lock
  would invalidate nested mode/turn-off helpers and requires a separate design
  review.

## Progress log

### 2026-08-30 — tracker creation and baseline

- Created this tracker from the two diagnostic sessions and the focused
  three-surface concurrency audit.
- Recorded KSW-0 as confirmed and locally corrected, pending post-campaign
  hardware evidence.
- Left KSW-1–KSW-7 as `reported`; the audit is evidence for investigation, not a
  substitute for independent reproduction and contract review.
- Deferred new live logging until every software workstream has a disposition
  and merged validation is green.
- No production behavior was changed by this documentation pass.
