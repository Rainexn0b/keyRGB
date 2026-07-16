# Issue #7 Composite Profile Hardening and Validation Plan

## Status

- **Prepared:** 2026-07-15
- **Input:** live-code review of
  `docs/D-bug-reports/issue-7/01-second-review-0.29.1-regression-2026-07-15.md`
- **Decision:** the v0.29.1 dual-seam fix is still the correct immediate fix;
  the residual findings below need different combinations of implementation,
  characterization, documentation, and hardware evidence
- **Implementation state:** Phases 1–5 and Phase 8 debug-script hardening are
  implemented in the working tree as of 2026-07-15 (code + unit/integration
  tests). Phase 0/6/7/8 reporter hardware evidence and shared hidraw descriptor
  filtering remain open.
- **Release state:** reporter hardware revalidation remains the Issue #7 closure
  gate
- **2026-07-16 update:** the reporter confirmed "v0.29.2 is working well" and
  closed the GitHub issue — this closes the primary (v0.29.1 flash-then-dark)
  regression but is **not** the structured Phase 8 per-surface checklist. Phase 6
  is **demoted**: the reporter's v0.28.2 support bundle shows c197 exposes a
  single hidraw node (`hidraw3`), so the multi-interface selection ambiguity
  Phase 6 guards against does not exist on real c197 hardware; additionally the
  bundle's descriptor read for `hidraw3` returned `EINVAL`, so the descriptor
  capture path needs investigation before any re-capture. The backend stays
  `EXPERIMENTAL`; promotion is gated on the Phase 8 checklist, not Phase 6.

This plan treats the Grok review as a hypothesis set. Every concern below was
checked against the current coordinator, device facades, routing table, config
mirror, profile application, software renderer, and tests.

## Executive decision

1. Preserve the dual-seam regression fix and validate it on the reporter's c197
   hardware before broad refactoring.
2. Fix the confirmed desired-off/global-off ambiguity.
3. Add a backend-owned output transaction so one logical c197 frame produces
   one complete physical profile commit.
4. Add the missing cross-layer regression that connects config polling, legacy
   mirror fallback, real c197 facades, and the coordinator.
5. Rename the two misleading `payload_from_config` helpers and document one
   canonical authority contract.
6. Treat process-wide identity, product variants, and generic coordinator
   extraction as evidence-triggered work, not immediate speculative redesign.
7. Keep shared hidraw descriptor filtering separate from the regression fix,
   but complete it before promoting this experimental backend.

## Maintainer disposition of the review

| Review concern | Disposition | Planned response |
|---|---|---|
| 7.1 Hardware remains unproven | Confirmed closure gate | Phase 0 and Phase 8 reporter validation |
| 7.2 Desired-scene/global-off asymmetry | Confirmed behavioral defect | Phase 2 separates desired edits from transient global shutdown |
| 7.3 Process-wide singleton | Bounded current assumption; future risk | Document the one-controller/default-profile contract now; add identity/profile enforcement when Phase 7 is triggered |
| 7.4 Optimistic staged zone state | Accepted logical-state contract with unclear API | Phase 2 adds an explicit commit disposition and documents desired versus observed state |
| 7.5 Strict authoritative mirror gate | Intentional compatibility safety | Keep the strict registered-route gate; Phase 1 names it and Phase 5 tests route expansion |
| 7.6 Cold brightness without primary groups | Existing two-report fallback with hardware-unknown visible result | Characterize exact packets in Phase 2; use reporter observation as the semantic decision gate |
| 7.7 Missing cross-layer mode-change test | Confirmed required coverage gap | Phase 4 adds a real-facade/in-memory-transport integration test |
| 7.8 Silent broad close catches in debug script | Confirmed low-risk support-tool debt | Phase 8 narrows and reports close failures |
| 8.2A Two different helpers with one name | Confirmed maintainability debt | Phase 1 renames both contracts and removes an ignored payload read |
| 8.2B Independent virtual zones | Correct logical routing model | Keep independent routes; the backend/output boundary performs physical batching |
| 8.2B Repeated composite commits | Newly confirmed architecture gap | Phase 3 adds a nested output transaction and one-commit-per-frame tests |
| 8.2C Explicit empty versus default empty | Correct but subtle policy | Phase 5 adds the canonical authority table and route-addition tests |
| 8.2D Issue #7 megathread | Already substantially addressed | Maintain this issue folder and closure matrix; do not create another GitHub issue without an explicit decision |
| 10 Product-variant registry | Evidence-triggered | Do not invent variants; Phase 7 defines the trigger and ownership model |
| 10 Shared hidraw usage filtering | Confirmed pre-existing promotion gap | Phase 6 gathers descriptor evidence and implements shared filtering |
| Generic reusable coordinator | Valuable future abstraction, premature extraction | The current class is now documented as the reference implementation; extract after a second consumer exists |

## Current contracts that must not regress

- A default-empty or v0.28.x partial `secondary_device_state` mirror is not an
  explicit all-off scene.
- An active profile component is authoritative even when its `areas` map is
  empty or partial; omitted registered routes are off.
- Materialized config mirrors contain every registered profile-capable route and
  an explicit `enabled` field for each.
- Authority depends on the registered route catalog, not current device
  availability.
- Keyboard, Logo, Neon, and Vents share one c197 group namespace.
- No child-only `SAVE_PROFILE` sequence may be emitted after primary state exists.
- Chassis-zone brightness is primary/controller owned.
- Logical routes remain independent for UI, storage, diagnostics, simulation,
  and software targeting.
- Simulation and unit tests never count as c197 hardware validation.

## Scope

### In scope

- Issue #7 coordinator state and output-transaction hardening.
- Config-mirror authority naming, tests, and documentation.
- One cross-layer flash-then-off regression test.
- Debug-tool exception visibility.
- Evidence-led shared hidraw descriptor filtering for c195/c197.
- Reporter hardware acceptance and release gates.
- Documentation of the reference implementation and future extraction rules.

### Out of scope

- New USB IDs or speculative device variants.
- Moving c197 packet policy into tray or GUI code.
- Treating Logo, Neon, or Vents as keyboard cells.
- Per-zone brightness or per-zone hardware effects without new protocol evidence.
- A process-wide generic coordinator with only one real consumer.
- Opening or closing GitHub issues as part of local implementation.
- Stable promotion before shared hidraw filtering and reporter evidence.

## Phase 0 — Freeze the regression baseline and obtain hardware evidence

### Goal

Prove the current dual-seam fix on the affected Lenovo Legion Pro 7 16IAX10H
before changing coordinator semantics. If it still flashes and turns dark, stop
this plan and debug the actual report stream first.

### Work

1. Build an unreleased AppImage from the exact candidate commit.
2. Record the commit, AppImage SHA-256, config state, backend probe, and support
   bundle in this issue folder.
3. A full reinstall is required only if installer or udev content changed; the
   coordinator-only fix does not itself require reinstalling udev rules.
4. Ask the reporter to run the checklist in Phase 8 and attach:
   - a pass/fail result per surface and transition;
   - `KEYRGB_DEBUG=1` and `KEYRGB_DEBUG_BRIGHTNESS=1` logs for a failure;
   - a fresh support bundle;
   - the exact tested artifact version or hash.
5. Record whether the original v0.28.2 config was reused or a fresh profile was
   materialized.

### Exit criteria

- The candidate is traceable to one commit and artifact hash.
- The reporter confirms either a clean baseline or a reproducible remaining
  failure with logs and support evidence.
- No later phase changes packet behavior while the baseline result is unknown,
  except isolated test/docs work.

## Phase 1 — Name and centralize the secondary-scene authority contract

### Goal

Remove the two-helper naming trap without changing compatibility behavior.

### Files

- `src/tray/controllers/secondary_static_scene.py`
- `src/core/secondary_lighting_state.py`
- `src/tray/pollers/config_polling_internal/helpers.py`
- `src/tray/pollers/config_polling_internal/_apply_callbacks.py`
- `src/tray/controllers/software_target_controller.py`
- matching static-scene, config-polling, and core state tests

### Work

1. Rename the tray classifier:
   - `payload_from_config` -> `authoritative_payload_from_config`
2. Rename the core compatibility builder:
   - `payload_from_config` -> `legacy_snapshot_from_config`
3. Update imports, call sites, `__all__`, test names, and docstrings. These are
   internal symbols; do not retain two ambiguous compatibility aliases.
4. Extract or name the registered route-key check so its contract is visible:
   every registered `supports_profile_state` route must exist with explicit
   `enabled` before the config mirror is authoritative.
5. Remove the dead payload construction in config-poller global turn-off.
   `turn_off_secondary_profile_areas()` now covers every available profile route
   and ignores the payload, so remove the unused parameter and update callers.
6. Do not change the authority check to effective or currently available routes.
   Hardware discovery state must not alter profile meaning.

### Tests

- Empty mirror -> no authoritative payload.
- Partial v0.28.x mirror -> no authoritative payload.
- Complete registered-route mirror -> authoritative payload.
- Unknown route entries are preserved but do not satisfy known-route completeness.
- Availability changes do not change authority.
- Legacy snapshot construction remains non-persistent.

### Exit criteria

- Repository search finds no ambiguous `payload_from_config` symbol in these two
  secondary-scene roles.
- Existing compatibility behavior is byte-for-byte/state-for-state unchanged.
- Global off performs no unused config-mirror read.

## Phase 2 — Separate desired zone edits from global output suspension

### Goal

Fix the confirmed asymmetry where a positive zone update while globally off is
retained but an explicit zone-off is discarded as cleanup.

### Files

- `src/core/backends/ite8258_perkey_chassis/profile_coordinator.py`
- `src/core/backends/ite8258_perkey_chassis/device.py`
- `src/core/secondary_device_routes.py`
- `src/tray/controllers/secondary_static_scene.py`
- `src/tray/controllers/_power/`
- c197 backend and tray power/static tests

### Design

1. Rename the conceptual state from "globally off" to "output suspended" in the
   coordinator. Suspension affects wire output; it does not erase desired scene.
2. Make both positive and off zone edits update desired state while suspended:
   - positive color -> retain groups, no wire write;
   - off -> retain the zone's black/off groups, no wire write.
3. Stop using child `turn_off()` as transient cleanup after the primary has
   already powered off a shared controller.
4. Add explicit route power ownership, or an equivalent backend-neutral signal,
   for virtual routes whose parent primary owns global output. Global shutdown
   skips redundant child cleanup for those routes while still shutting down
   independent devices.
5. Keep user/profile `turn_off()` as a desired-scene edit. Do not add a boolean
   such as `preserve_scene` whose meaning depends on caller order.
6. Replace the coordinator's boolean return with an explicit disposition, for
   example `COMMITTED`, `STAGED_NO_PRIMARY`, or `STAGED_SUSPENDED`.
7. Document `is_off()` and `get_brightness()` on a zone facade as accepted
   logical state, not hardware readback. KeyRGB has no physical visibility query
   for a staged scene.
8. Decide and document I/O-failure semantics: desired state should remain
   retryable, while an applied revision advances only after the complete report
   sequence succeeds.
9. Preserve the current cold-start brightness packet sequence unless hardware
   evidence disproves it. With no retained primary groups, positive brightness
   sends `SWITCH_PROFILE` followed by `SET_BRIGHTNESS`; it neither replays a
   KeyRGB scene nor proves what becomes visible. Record reporter observation as
   the gate for retaining, replacing, or documenting the visible semantics.

### Required tests

- Global shutdown preserves every retained child color.
- Explicit child-off while suspended changes retained desired state.
- Explicit child-on while suspended changes retained desired state.
- Resume commits the newest desired state, including a child disabled while off.
- An all-compatible software frame cannot relight a route disabled during
  suspension.
- Independent lightbar/mouse routes still receive global-off calls.
- Desired state remains dirty/retryable after an injected mid-commit I/O error.
- No partial child profile is emitted on any staged path.
- Fresh coordinator plus positive brightness emits the documented profile-switch
  and brightness sequence.
- Global off before any primary scene, followed by positive brightness, has an
  exact characterized packet sequence and does not invent primary groups.
- A later child update remains staged until real primary state arrives.

### Exit criteria

- Desired edits are independent of global shutdown call order.
- One explicit API represents output suspension; another represents scene edits.
- Resume has deterministic latest-intent behavior.

## Phase 3 — Add one logical-output transaction for composite controllers

### Goal

Reduce one logical c197 render from up to four complete profile commits to one,
without coupling the effects or tray layers to c197 packet semantics.

### Current failure shape

`src/core/effects/software/base.py` writes the keyboard, then
`src/core/effects/software_targets.py` iterates Logo, Neon, and Vents. Every c197
facade call currently commits the complete retained profile. With all three
zones enabled, one software frame therefore produces four full transactions and
three intermediate scenes. The redundant calls and report volume are proven by
the live call graph; whether they create visible c197 flicker still requires
hardware evidence.

### Files

- `src/core/effects/software/base.py`
- `src/core/effects/software_targets.py`
- `src/core/effects/device.py` or a focused output-transaction helper
- `src/tray/pollers/config_polling_internal/_apply_callbacks.py`
- `src/tray/pollers/config_polling_internal/helpers.py`
- `src/tray/controllers/secondary_static_scene.py`
- c197 coordinator and device files
- software-render, config-polling/static-transition, and c197 backend tests

### Design

1. Define an optional backend-neutral context manager exposed by the primary
   device, such as `output_transaction()`.
2. Provide a no-op adapter for devices without this capability; do not add a
   required method to every backend.
3. Wrap the primary keyboard write and secondary uniform fan-out for one frame
   in the same outer transaction.
4. For c197, entering the outer transaction:
   - acquires the coordinator's re-entrant transaction lock;
   - snapshots desired state;
   - stages primary and child mutations without wire output;
   - records primary brightness once.
5. The outermost successful exit emits exactly one complete profile using the
   primary controller writer. Nested transactions commit only at the outermost
   level.
6. Define exception semantics before implementation. Recommended rule: if an
   exception occurs before commit, restore the pre-transaction desired snapshot;
   if I/O fails during commit, retain the new desired snapshot as dirty and leave
   the applied revision unchanged for retry.
7. Validate that every staged writer/profile belongs to the same physical
   controller and profile namespace.
8. Independent secondary devices continue writing normally inside the optional
   context; only facades sharing the coordinator are batched.
9. Apply the same boundary to static mode/profile transitions where keyboard and
   chassis zones form one logical output operation. Thread the optional generic
   transaction from `_apply_uniform()`/`_apply_perkey()` through secondary static
   reconciliation so both writes share the same outer scope; tray code must not
   branch on c197 or import its coordinator.

### Required tests

- Keyboard plus three c197 zones -> one full commit per software frame.
- Static mode change plus secondary reconciliation -> one final combined commit,
  with no keyboard-only or child-only intermediate profile.
- Independent secondary devices still receive their own output.
- Nested transactions commit once.
- Concurrent frames never interleave.
- A staging exception emits no profile and restores the previous desired scene.
- A commit I/O failure leaves retryable dirty desired state.
- Brightness is emitted at most once and remains primary-owned.

### Optional lower-level follow-up

After the output transaction is proven, consider
`HidrawTransportProxy.send_feature_reports_atomic()` to validate a proxy once and
hold its transport entry lock for the complete report sequence. Preserve
per-report pacing and invalidate consistently on `OSError`.

This lower-level method is reusable hardening, not a prerequisite for current
c197 correctness because the coordinator already serializes its production
report sequence.

### Exit criteria

- One logical composite render produces one physical full-scene commit.
- No c197-specific group or packet knowledge appears in effects/tray code.
- Non-composite backends retain current behavior.

## Phase 4 — Add the missing cross-layer Issue #7 regression

### Goal

Connect the seams whose isolated tests were green while v0.29.1 still failed.

### New test

Create:

`tests/tray/test_secondary_device_issue7_mode_change_integration_unit.py`

### Test construction

1. Enable the hardware test tripwire so real USB/hidraw access is forbidden.
2. Instantiate one real `Ite8258ChassisProfileCoordinator`.
3. Instantiate real c197 keyboard, Logo, Neon, and Vent facades sharing that
   coordinator and an in-memory report writer.
4. Build a tray config with default-empty `secondary_device_state` plus legacy
   route accessors returning distinct enabled colors.
5. Exercise the real config-poller uniform mode callback and secondary
   reconciliation, injecting only effective route inventory and in-memory
   devices.
6. Repeat with a partial v0.28.x mirror and a complete materialized mirror.
7. Decode or construct the expected final report sequence with the production
   protocol builders.

### Assertions

- Default-empty and partial mirrors select legacy fallback.
- Complete materialized state remains authoritative.
- No child path emits a controller-global turn-off report after the primary
  write.
- No child-only `SAVE_PROFILE` starts a replacement group namespace.
- The final commit contains primary plus Logo, Neon, and Vent groups in order.
- Distinct fallback colors survive the mode transition.
- The output-transaction implementation produces one final composite commit.

### Exit criteria

- The test fails when either the old mirror-authority bug or child-only profile
  behavior is reintroduced.
- The test never opens real hardware.
- Existing focused unit tests remain; this test joins rather than replaces them.

## Phase 5 — Lock route-catalog expansion and authority semantics

### Goal

Document and test what happens when a new profile-capable route is registered.

### Decision

Keep the strict authority gate. A previously complete mirror becomes temporary
compatibility state when the registered catalog expands. On normal profile
activation, `Config._merge_secondary_profile_state()` materializes the new route
as `enabled: false`. The profile file does not need to be rewritten merely to
complete the config mirror.

### Work

1. Add a canonical table to
   `docs/1-src/11-multi-device-routing-and-targets.md`:

| State | Meaning |
|---|---|
| Active profile component present, even empty or partial | Authoritative; omitted registered routes are off |
| Config mirror has every registered profile route with explicit `enabled` | Materialized authoritative mirror |
| Config mirror is empty, partial, or lacks `enabled` | Legacy source; build a non-persistent compatibility snapshot |
| Unknown route entries | Preserve, but do not count toward known-route completeness |
| Newly registered route | Old mirror is compatibility state until profile activation materializes the route disabled |

2. State explicitly that authority uses registered routes, not effective or
   currently connected routes.
3. Document that reading legacy state does not create or rewrite profile files.
4. Require release notes whenever a new profile-capable route changes the
   materialized mirror catalog.

### Tests

- Simulated new registered route makes an old mirror non-authoritative.
- Applying a profile adds that known route with `enabled: false`.
- Unknown future metadata survives config merge.
- An unavailable registered route still participates in completeness.
- Explicit-empty and partial active profile components stay authoritative.

### Exit criteria

- One architecture table defines the contract for runtime, profiles, support,
  and future route additions.
- Route availability cannot silently change authority.

## Phase 6 — Complete shared hidraw interface filtering

### Goal

Close the existing c195/c197 promotion blocker: VID/PID matching alone may choose
the wrong hidraw interface when a USB device exposes multiple interfaces.

### Evidence gate

Do not guess the correct report descriptor. First capture every hidraw interface
for the reporter's `0x048d:0xc197` controller, including:

- sysfs path and uevent;
- report descriptor size and bytes;
- usage page and usage when derivable;
- the interface that accepts the 960-byte feature report;
- equivalent c195 evidence before changing the shared scanner for both backends.

### Files

- shared hidraw discovery code currently used by c195/c197
- low-level descriptor-reading/parsing support shared with diagnostics
- c195/c197 backend probe code
- hidraw discovery, backend probe, and diagnostics tests
- backend audits for both ITE 8258 variants

### Work

1. Move or expose descriptor reading at a low-level backend-safe boundary so
   backend discovery does not depend on diagnostics presentation code.
2. Add an optional interface predicate/signature to shared hidraw discovery.
3. Select the c197 interface by evidence-backed usage/report characteristics,
   not directory sort order.
4. Preserve a forced hidraw path as an explicit expert override and report that
   descriptor filtering was bypassed.
5. Return useful probe reasons when VID/PID matches but no interface satisfies
   the required descriptor.
6. Include selected interface evidence in diagnostics/support bundles.

### Tests

- Multiple hidraw nodes with identical VID/PID select the matching descriptor.
- Directory order does not affect selection.
- Non-matching descriptors are skipped.
- Descriptor read failures produce a bounded unavailable/diagnostic result.
- Forced path behavior is explicit and tested.
- c195 and c197 signatures remain separate where their framing differs.

### Exit criteria

- The backend no longer relies on the first matching VID/PID node.
- Selection criteria are backed by real descriptors from supported hardware.
- Support bundles explain which interface was selected and why.

## Phase 7 — Controller identity, profiles, variants, and generic extraction

### Status

Trigger-gated. Do not implement this phase solely to make the current class look
generic.

### Trigger

Proceed only when at least one is true:

- two supported physical controllers can coexist in one process;
- a second c197-class product has a different surface/layout definition;
- KeyRGB exposes multiple hardware profiles concurrently;
- another backend needs multiple logical routes over one destructive shared
  scene namespace.

### Work after the trigger

1. Introduce a controller context keyed by stable physical identity, backend
   variant, and hardware profile.
2. Retain desired state when reopening the same controller; discard it when
   identity or variant changes.
3. Bind the transaction writer to that context so a caller cannot commit one
   controller's scene through another controller's proxy.
4. Move product-specific matrix and zone definitions into an evidence-backed
   variant registry.
5. Extract a protocol-neutral retained-scene state machine only after comparing
   both concrete consumers.
6. Keep component order, LED IDs, group types, black-as-off behavior, packet
   builders, and brightness commands in backend adapters.

### Current action

- Document the one-controller/default-profile assumption.
- Add a test that rejects mixed profile IDs if non-default IDs are ever exposed.
- Do not add speculative variants or generic callback plumbing now.

### Exit criteria

- No desired state can cross physical device, variant, or profile boundaries.
- The shared abstraction contains behavior proven common by at least two real
  consumers.

## Phase 8 — Support tool cleanup and reporter acceptance

### Debug script hardening

Update `scripts/debug/ite8258-chassis-zone-test.py`:

1. Add a labeled close helper.
2. Catch only expected cleanup failures such as `OSError`, `RuntimeError`, and
   `ValueError`.
3. Print cleanup failures to stderr with the affected surface name.
4. Preserve the original test result while making cleanup failures visible.
5. Do not copy a silent broad catch into production code.

### Reporter checklist

Using the exact candidate artifact:

1. Establish a static keyboard color.
2. Set Logo, Neon, and Vents to distinct colors.
3. Switch repeatedly among Static, per-key, every supported hardware effect,
   keyboard-only software effects, and all-compatible software effects.
4. Confirm no mode change flashes and then leaves all surfaces dark.
5. Confirm later keyboard updates preserve every enabled child color.
6. Disable each child individually, change keyboard modes, and confirm it stays
   disabled.
7. Turn the whole controller off and on; confirm the latest desired scene
   returns.
8. Change a child while globally off, both on and off, then resume.
9. Change keyboard brightness through its full supported range; confirm child
   zones follow without an independent-brightness claim.
10. Exercise suspend/resume and lid close/open when configured.
11. Run rapid all-compatible animation long enough to expose report pacing or
    flicker issues.
12. Attach a fresh support bundle and debug log for any failure.

### Exit criteria

- Cleanup failures from the evidence tool are visible.
- Every reporter check has a recorded pass/fail result.
- The tested artifact hash and hardware identity are recorded.

## Phase 9 — Final validation and release gate

### Focused automated lane

Run with the hardware tripwire:

```bash
KEYRGB_TEST_HARDWARE_TRIPWIRE=1 .venv/bin/python -m pytest -q -o addopts= \
  tests/core/backends/ite/test_ite8258_chassis_backend_unit.py \
  tests/core/backends/test_shared_hidraw_transport_unit.py \
  tests/core/test_secondary_lighting_state_unit.py \
  tests/core/profiles/core/test_profile_storage_apply_profile_unit.py \
  tests/tray/controllers/core/test_secondary_static_scene_unit.py \
  tests/tray/pollers/config/core/test_secondary_config_polling_unit.py \
  tests/tray/test_secondary_device_issue7_regression_unit.py \
  tests/tray/test_secondary_device_issue7_mode_change_integration_unit.py
```

Run named quality steps while iterating so step-number changes cannot make the
handoff stale:

```bash
.venv/bin/python -m buildpython --run-steps="Ruff,Ruff Format,Type Check,Architecture Validation,Exception Transparency"
```

Run the full CI profile before any merge decision:

```bash
.venv/bin/python -m buildpython --profile=ci
```

Run the release profile only when an exact release is requested:

```bash
.venv/bin/python -m buildpython --profile=release
```

### Merge gates

- All focused and CI validation passes in the merged parent worktree.
- The cross-layer test proves both regression seams together.
- One composite frame produces one physical c197 commit.
- Global off/resume preserves latest desired intent.
- Descriptor filtering is evidence-backed before stable promotion.
- Docs, changelog, and backend audit match actual behavior.
- No release claims hardware closure before reporter evidence is recorded.

### Rollback plan

Keep phases in reviewable commits. If hardware regresses:

1. retain the config-mirror compatibility fix and its tests;
2. disable or revert output batching independently from scene-state fixes;
3. restore the last hardware-verified coordinator semantics;
4. capture the failing report sequence before attempting another refactor;
5. do not weaken the strict authority gate to mask a backend transaction bug.

## Definition of done

This plan is complete only when:

- every accepted concern in the disposition table is implemented, tested, or
  explicitly closed as an evidence-triggered contract;
- the Issue #7 cross-layer regression remains green under the hardware tripwire;
- the reporter validates the affected hardware transitions;
- shared hidraw selection no longer depends only on VID/PID directory order;
- current architecture docs identify the coordinator as a backend-local
  reference, not a generic shared API;
- Issue #7's index records the tested release/artifact and closure evidence.

## Related documents

- [Issue #7 index](../D-bug-reports/issue-7/issue-7.md)
- [Grok second review](../D-bug-reports/issue-7/01-second-review-0.29.1-regression-2026-07-15.md)
- [Composite coordination reference](../1-src/12-composite-profile-coordination.md)
- [ITE 8258 chassis backend audit](../B-backend-audits/06-ite8258-chassis.md)
- [Secondary lighting profile plan](secondary-lighting-profile-editor-and-simulation-plan.md)
