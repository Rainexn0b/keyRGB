# Architecture Concerns Plan (2026-08-11)

## Purpose

Track the architecture, correctness, packaging, and operational concerns found
during the 2026-08-11 repository review. This is a bounded confirmation and
remediation campaign: each concern must be inspected against live code and tests
before it is accepted as debt, and each accepted concern must be solved in one
focused pass with its contract preserved by tests.

This document is the campaign tracker, not proof that every reported concern is
valid. Initial entries therefore start as `reported`. A concern moves to
`confirmed` only after a dedicated inspection pass records reproducible evidence
and the intended contract.

## Relationship to prior plans

- Does not supersede
  `docs/I-implementation-plans/2026-07-15/maintainability-debt-paydown-plan.md`.
  That document remains the broad D1-D15 debt inventory.
- Extends D1, D2, D3, D5, D7, D8, D10, D11, D12, and D14 with findings from the
  2026-08-11 architecture review.
- Uses the one-slice workflow established by
  `docs/I-implementation-plans/2026-07-19/0.30.x-maintainability-sprint.md`, but
  permits confirmed bug and security fixes rather than requiring behavior parity.
- Durable architecture decisions produced by this campaign belong under
  `docs/1-src/`; this document records only investigation, sequencing, and
  completion evidence.

## Scope and constraints

### In scope

- Runtime ownership and dependency direction across core, tray, and GUI.
- Backend, capability, geometry, profile, persistence, and diagnostics contracts.
- Test, package-artifact, build-runner, installer, and release controls that
  protect those contracts.
- Small supporting abstractions when they establish a clear long-term owner.

### Constraints

- Work on exactly one inventory item per implementation pass.
- Inspect current implementation and nearby tests before changing code.
- Confirm or reject the report explicitly; do not fix from the review summary
  alone.
- Add the regression or contract test before, or in the same pass as, the fix.
- Prefer the nearest owner over compatibility shims or cross-layer callbacks.
- Preserve public entrypoints and existing user data unless a pass explicitly
  approves a migration.
- Keep hardware access disabled in default tests.
- Do not add device IDs or widen backend claims without hardware evidence.
- Run focused tests plus the smallest applicable buildpython gates. Any pass that
  touches a runtime fallback or Step 19 hotspot must run
  `python -m buildpython --run-steps=19`.
- Parent-side merged validation remains authoritative.

## Conventions

- Priority: `P0` safety/correctness blocker, `P1` high leverage, `P2` phased.
- Effort: `S`, `M`, `L`.
- Status:
  - `reported`: review finding awaiting dedicated inspection;
  - `confirmed`: reproduced and contract recorded;
  - `active`: current single implementation pass;
  - `done`: implementation and required local validation complete;
  - `rejected`: inspection disproved the concern, with evidence recorded;
  - `monitoring`: mitigated but awaiting merged or real-hardware evidence;
  - `blocked`: cannot proceed until the stated dependency is available.

## Inventory

| ID | Area | Reported concern | Evidence entry points | Priority | Effort | Status | Prior refs |
|---|---|---|---|:---:|:---:|---|---|
| A1 | Profile security | Profile names may resolve to `profiles/` itself or escape to its parent through `.` / `..`, including destructive operations. | `src/core/profile/paths.py` | P0 | S | done | D3 |
| A2 | Tray runtime | Pollers, power monitors, callbacks, and effects mutate one shared tray aggregate without a single serialization owner. | `src/tray/app/application.py`, `src/tray/pollers/`, `src/core/power/management/` | P0 | L | done | D1, D2, D5 |
| A3 | Tray UI | Worker threads can synchronously mutate pystray icon/menu state; thread affinity is not represented as a contract. | `src/tray/pollers/icon_color_polling.py`, `src/tray/ui/refresh.py` | P0 | M | rejected | D1, D5, D11 |
| A4 | Shutdown | Bounded poller joins are not followed by liveness checks before engine/device teardown. | `src/tray/app/lifecycle.py`, power monitor lifecycle | P0 | M | done | D1, D5 |
| A5 | Effect geometry | Software/reactive effects use a fixed 6x21 grid while supported backends expose different dimensions. | `src/core/effects/matrix_layout.py`, backend protocols | P1 | L | done | D2, D3 |
| A6 | Layering | Core profile activation depends behaviorally on private tray callbacks and tray-owned state despite avoiding direct imports. | `src/core/profile/runtime_activation.py` | P1 | M | done | D1, D2, D13 |
| A7 | Profile persistence | Profile JSON and active/default markers do not share config storage's lock, unique-temp, fsync, and merge guarantees. | `src/core/profile/json_storage.py`, `src/core/profile/paths.py`, `src/core/profile/profiles.py` | P1 | M | done | D3 |
| A8 | Capabilities | The capability model is too coarse and missing metadata fails open to full support; method presence can substitute for capability evidence. | `src/core/backends/base.py`, effects and tray gating consumers | P1 | M | done | D3, D4 |
| A9 | Backend diagnostics | Diagnostics duplicate probing/ranking, omit the sysfs safety tier in candidate order, and can describe a policy different from runtime selection. | `src/core/backends/registry.py`, `src/core/diagnostics/collectors/backends.py` | P1 | M | done | D2, D4 |
| A10 | Configuration model | `Config` remains a large mutable dictionary-backed state bag spanning lighting, power, profile, scheduler, layout, and secondary-device concerns. | `src/core/config/config.py`, config accessor packages | P1 | L | done | D3 |
| A11 | Domain units | Brightness normalization differs between primary config, secondary config, and profile payload paths. | config lighting coercion, profile payloads, secondary lighting state | P1 | M | done | D3 |
| A12 | Error semantics | Ordinary config setters can lose persistence failures, while selected boundaries catch programming-shaped exceptions as runtime degradation. | `src/core/config/config.py`, backend registry, effects startup | P1 | M | done | D6 |
| A13 | Effect contracts | Effects mixins, dynamic reactive API injection, closure introspection, and exception-text parsing hide dependencies and payload contracts. | `src/core/effects/engine_support/`, reactive API modules, `hw_payloads.py` | P2 | L | done | D2, D14 |
| A14 | Backend extension | Backend protocol metadata is partial, registration is centralized, and shared controller state is keyed too coarsely for multiple identical devices. | backend base/registry, shared HID manager, chassis backend globals | P2 | L | done | D4 |
| A15 | Diagnostics purity | Some diagnostics instantiate mutable configuration, snapshots are shallowly immutable, and reported environment policy is incomplete. | `src/core/diagnostics/secondary_devices.py`, models, snapshots | P2 | M | done | D3, D6 |
| A16 | GUI responsiveness | Tk callbacks perform synchronous hardware/OS work and the generic Tk worker helper lacks cancellation and generation semantics. | GUI uniform, per-key, power mode, `src/gui/utils/tk_async.py` | P2 | M | done | D2, D11 |
| A17 | View boundaries | Tray menu construction can perform hardware acquisition and direct OS power queries. | `src/tray/ui/_menu_status_devices.py`, `menu_sections.py` | P2 | M | done | D2, D11 |
| A18 | Packaging | Declared package-data patterns may omit nested reference-default JSON; CI does not install and smoke a built wheel/sdist. | `pyproject.toml`, resource loader, CI workflows | P1 | S | done | D8 |
| A19 | Build runner | Continue-on-error summaries can record failure while the runner returns success to the caller. | `buildpython/core/runner.py` | P1 | S | done | D12 |
| A20 | Release inputs | AppImage, dependencies, Actions, checksums, and privileged helper fallbacks are not fully immutable or reproducibly verified. | buildpython AppImage step, workflows, installer libraries | P1 | L | done | D12 |
| A21 | Installer cleanup | Bootstrap uninstall marker matching may leave managed udev rules installed; installer flows lack sandbox end-to-end tests. | `uninstall.sh`, `scripts/uninstall.sh`, udev rules | P1 | M | done | D7, D12 |
| A22 | Validation depth | Unit coverage is strong, but installed-artifact, desktop-session, installer, and genuine multi-component coverage is thinner; hardware tripwire is opt-in. | `tests/`, CI workflows, coverage config | P2 | L | done | D7 |
| A23 | Tool policy | Mypy and dead-code policy are permissive/partial, shell code lacks ShellCheck, and architecture warning rules do not gate regressions. | `pyproject.toml`, buildpython profiles/rules | P2 | M | done | D6, D12 |
| A24 | Documentation | Build/CI documentation and some relative links have drifted from current behavior. | build docs, contributing docs, workflow definitions | P2 | S | done | D10 |

## Preparatory test guardrails

Before implementation passes begin, add passing unit-level characterization for
critical behavior that is not currently protected. Defect-exposing assertions
must land with their corresponding fix rather than leaving the default suite red
or marking permanent expected failures.

| Surface | Preparatory contract | Follow-up defect contract |
|---|---|---|
| Poller lifecycle | shutdown event is used for interruptible waits; signal precedes every join; one join failure does not skip later workers | surviving pollers block teardown and remain observable |
| Build runner | success, fail-fast, continuation, and failed-summary control flow | any continued failure produces a nonzero final exit |
| Profile JSON | serialization/replacement failures preserve the last valid target | writers use unique temporary files, clean failures, lock shared updates, and preserve markers atomically |
| Profile activation | config application precedes runtime and UI callbacks | core service has no tray-private behavioral contract |
| Effect geometry | dimension-aware grid primitive honors explicit dimensions | every software/reactive frame maps exactly to selected backend geometry |
| Resource data | manifest closure exists and every source resource is valid JSON | built wheel contains and can load the complete closure |
| Profile paths | ordinary path-like names remain confined | dot components cannot resolve to root/parent or reach deletion |

## Per-pass workflow

1. Set exactly one inventory item to `active`.
2. Read implementation, callers, tests, and relevant durable architecture docs.
3. Record one of:
   - confirmed defect/debt and its stable contract;
   - rejected finding and the evidence that disproves it;
   - blocked finding and the missing evidence.
4. If confirmed, define the nearest owner and smallest maintainable abstraction.
5. Add or update tests that fail for the confirmed issue.
6. Implement the complete root-cause fix without opportunistic cleanup.
7. Run focused pytest plus applicable Ruff, mypy, architecture, coverage, and
   exception-transparency gates.
8. Update this inventory and append exact files/commands/results to the progress
   log before moving to another concern.

## Recommended order

1. A1 profile path confinement.
2. A19 build-runner failure exit semantics.
3. A7 profile persistence consistency.
4. A4 poller shutdown liveness.
5. A3 tray UI thread affinity.
6. A2 serialized tray runtime ownership.
7. A9 canonical backend selection report.
8. A8 authoritative capabilities.
9. A5 runtime effect geometry.
10. A6 profile application boundary.
11. A18 built-package resource validation.
12. Remaining P1 items, then P2 items based on evidence and user impact.

The order deliberately addresses bounded safety/correctness issues before larger
state-owner or rendering redesigns. A2 and A5 require an approved architecture
shape in their confirmation pass before implementation begins.

## Campaign completion criteria

- [x] Every inventory item is `done`, `rejected`, `monitoring`, or explicitly
      `blocked` with a named dependency.
- [x] Every confirmed issue has a regression or contract test.
- [x] No new silent broad exception path or architecture-rule waiver was added.
- [x] Public entrypoints and existing profile/config data remain compatible, or
      an explicit migration and rollback path is documented.
- [x] Durable ownership and dependency decisions are reflected in `docs/1-src/`.
- [x] Full parent-side merged validation is green.

## Progress log

### 2026-08-11 - campaign preparation

- Created this campaign tracker and linked every review concern to its first
  inspection surface and prior debt inventory where applicable.
- Mapped existing tests before implementation work.
- Added 19 passing test cases covering cooperative poller shutdown, join ordering,
  build-runner continuation/fail-fast flow, profile JSON target preservation,
  profile activation ordering, explicit effect-grid dimensions, resource-manifest
  closure, ordinary profile-path confinement, and the poller/pystray surface seam.
- Validation:
  - focused pytest selection: `56 passed`;
  - focused Ruff lint and format checks: passed;
  - `python -m buildpython --run-steps=2,10,16,17`: `3469 passed, 1 skipped`;
    repo validation, code hygiene, and architecture validation passed.
- No production code changed. Every inventory finding remains `reported`; none is
  considered confirmed or fixed by this preparatory entry.

### 2026-08-11 - A1 profile path confinement

- **Disposition:** confirmed and fixed.
- Reproduction established that:
  - `safe_profile_name(".")` and `safe_profile_name("..")` preserved the reserved
    components;
  - profile roots consequently resolved to `profiles/` itself or its parent;
  - `delete_profile("..")` entered `shutil.rmtree()` on the parent configuration
    tree, removed contents, and only then failed while removing the terminal
    `..` path;
  - active/default markers could persist the unsafe name; and
  - an existing profile-directory symlink could resolve outside profile storage.
- Contract implemented in `src/core/profile/paths.py`:
  - reserved dot components normalize to the built-in default while supported
    names such as `.gaming`, `gaming.v2`, and `gaming-profile` remain valid;
  - every profile root is checked after filesystem resolution and individual
    profile-directory symlinks are refused;
  - profile creation/migration is revalidated after the filesystem operation;
  - destructive deletion fails closed and preserves external trees;
  - marker files are written only after the target profile root is validated;
  - unsupported directory symlinks are omitted from profile listings.
- Regression coverage in
  `tests/core/profiles/core/test_profile_paths_unit.py` includes dot names,
  ordinary path-like input, deletion sentinels, marker preservation, symlink
  escape, listing behavior, and legacy `light` migration compatibility.
- Validation:
  - focused profile/config/GUI selection: `32 passed`;
  - focused Ruff and mypy: passed;
  - `python -m buildpython --run-steps=2,3,7,13,16,17,19`:
    `3484 passed, 1 skipped`; Ruff, format, type check, code hygiene,
    architecture validation, and exception transparency passed.
- Profile payload/marker locking and unique temporary-file behavior remain
  separately tracked under A7; they were intentionally not widened into A1.

### 2026-08-11 - A19 build-runner aggregate exit semantics

- **Disposition:** confirmed and fixed.
- Reproduction established that `runner.run(..., continue_on_error=True)` ran all
  selected steps and wrote `passed=False`, but returned `0` after one or multiple
  failed steps. The CLI and `python -m buildpython` already propagated the runner
  return value correctly, so the defect was isolated to completed-run aggregation.
- Contract implemented in `buildpython/core/runner.py`:
  - continue-on-error controls execution only; it does not convert failure to
    shell success;
  - after all selected steps run, the first failed step's nonzero exit code is
    returned, matching fail-fast's actionable exit-code behavior;
  - successful and skipped-only completed runs return `0`;
  - summary `passed` and final exit status now derive from the same aggregate
    result, preventing contradictory outputs;
  - a defensive code `1` is used only if a custom step reports `failure` with an
    invalid zero exit code.
- Regression coverage:
  - runner continuation after failure and failed-summary output;
  - first-failure precedence across multiple failures;
  - successful/skipped-only continuation;
  - fail-fast behavior and exit-code preservation;
  - CLI propagation of the runner's nonzero result with `--continue-on-error`.
- Validation:
  - pre-fix focused run: `2 failed, 21 passed`, both failures returned `0`
    instead of the first failure code;
  - post-fix focused runner/CLI suite: `24 passed`;
  - focused Ruff and mypy: passed;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3487 passed, 1 skipped`; all eight gates passed.
  - final full Pytest rerun after adding the invalid-zero defensive contract:
    `3488 passed, 1 skipped`.

### 2026-08-11 - A7 profile persistence consistency

- **Disposition:** confirmed and fixed.
- Reproduction established that:
  - concurrent writers shared one fixed `<target>.tmp` path and one writer could
    fail with `FileNotFoundError` after the other replaced it;
  - replacement failure left the fixed temporary file behind;
  - profile writes did not flush file content with `fsync` before replacement;
  - secondary-area updates used an unlocked read-modify-write sequence and raced
    between GUI/tray writers; and
  - active/default markers bypassed the profile atomic writer and could overwrite
    the last valid marker directly.
- Storage contract implemented in `src/core/profile/json_storage.py`:
  - one config-level advisory lock coordinates profile sidecars, profile markers,
    and migrated layout-slot state across processes;
  - readers use shared locks and writers/updates use exclusive locks;
  - each writer owns a unique `mkstemp` file in the target directory;
  - content is flushed and `fsync`ed before `os.replace`;
  - temporary files are cleaned on success and replacement failure;
  - `update_json_atomic` keeps read, mutation, serialization, and replacement in
    one exclusive transaction;
  - forgiving profile reads retain their established `None` fallback, while
    marker readers use the strict locked reader so malformed/I/O cases remain
    diagnostically distinguishable.
- Migrated read-modify-write owners:
  - secondary-lighting area updates in `_profile_storage_ops.py`;
  - backdrop mode/transparency fields in `_backdrop.py`;
  - per-layout slot updates in `core/config/layout_slots.py`.
- Active/default profile markers now use the same atomic writer, validate/create
  the target profile first, and preserve the previous marker on write failure.
- Regression coverage includes fixed-temp collision reproduction, replacement
  cleanup, `fsync`, reader/writer exclusion, concurrent secondary routes,
  concurrent backdrop fields, concurrent physical layouts, marker failure
  preservation, and all prior profile compatibility behavior.
- Validation:
  - pre-fix focused reproduction: `6 failed, 30 passed`;
  - focused persistence/config selection: `79 passed`;
  - focused Ruff and mypy: passed;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3496 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A4 poller shutdown liveness

- **Disposition:** confirmed and fixed.
- Reproduction established that:
  - tray pollers were removed from the lifecycle registry immediately after a
    bounded `join`, without checking whether a worker remained alive;
  - a recoverable join failure was logged but its worker handle was discarded;
  - power-monitor, lid, and battery workers had the same bounded-join assumption;
    and
  - runtime shutdown continued into effects-engine and secondary-device teardown
    after either producer group timed out or raised a recoverable stop error.
- Shutdown contract implemented:
  - `stop_all_polling()` now returns an aggregate quiescence result, checks each
    available `is_alive()` probe after joining, and retains active or
    unverifiable handles for a later retry;
  - `PowerManager.stop_monitoring()` and its core monitor runner now return the
    equivalent aggregate result for all three power workers;
  - one power-worker join failure does not skip bounded joins for the remaining
    workers; and
  - tray shutdown still signals/stops both producer groups, but skips effects
    engine and secondary-target teardown if either group remains active or
    cannot be verified.
- Compatibility:
  - existing callers may continue ignoring the new boolean return values;
  - custom/legacy power managers returning `None` retain their prior synchronous
    stop contract, while implementations that can time out can return `False`.
- Durable ownership guidance was added to
  `docs/1-src/13-tray-runtime-state-ownership.md`.
- Regression coverage includes alive-after-timeout detection, unverifiable
  worker retention, recoverable join continuation, aggregate power-worker
  liveness, and teardown suppression for both producer groups.
- Validation:
  - pre-fix focused reproduction: `6 failed, 21 passed`;
  - final focused lifecycle/power selection: `29 passed`;
  - focused Ruff and mypy: passed;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3502 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A3 tray UI thread affinity

- **Disposition:** rejected after dependency-contract inspection; no production
  change was warranted.
- The reported concern conflated calls to pystray's public properties with
  direct native-toolkit mutation:
  - KeyRGB's worker poller calls the `_update_icon` facade and does not access
    the pystray surface;
  - all KeyRGB assignments to public pystray `Icon.icon` and `Icon.menu`
    properties are centralized in `src/tray/ui/refresh.py`; and
  - no KeyRGB path accesses pystray private/native backend fields.
- The supported pystray contract already owns native thread dispatch:
  - official usage requires `Icon.run()` on the main thread but intentionally
    runs its setup callback in a separate thread;
  - pystray 0.19.5 GTK/AppIndicator update implementations are decorated by a
    dispatcher using `GObject.idle_add`;
  - pystray 0.19.5 Xorg rewrites icon update operations into client messages
    executed by its mainloop thread, synchronously returning failures; and
  - current upstream retains both mechanisms.
- A second KeyRGB lock/dispatcher was rejected because it would duplicate the
  backend contract and can deadlock Xorg if a worker holds that lock while its
  synchronous dispatch waits on a mainloop callback taking the same lock.
- Existing regression coverage already asserts that the icon poller requests
  the facade without touching the pystray surface. Existing refresh tests cover
  the centralized public-property writes and application delegation seam.
- The ownership rule and future-backend trigger were documented in
  `docs/1-src/13-tray-runtime-state-ownership.md`.
- Validation:
  - focused icon-poller/UI/application selection: `69 passed`;
  - focused Ruff and mypy: passed;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3502 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A2 serialized tray runtime ownership confirmation

- **Disposition:** confirmed; production implementation is blocked on the
  architecture approval required by this campaign's A2 design gate.
- Inspection mapped concurrent mutation from config, hardware, idle-power and
  scheduler pollers; battery, login1/ACPI and lid power workers; pystray
  callbacks; lighting controllers; and effect lifecycle operations.
- Existing locks were confirmed to be resource-local. They do not serialize a
  complete check/plan/engine/config/hardware/state transition.
- Deterministic race candidates were identified for stale hardware-off apply,
  config apply versus user turn-off, scheduler brightness versus user turn-off,
  and delayed resume versus newer suspend/lid-close.
- A broad aggregate `RLock` was rejected because complete transitions cross
  blocking USB/sysfs, config, effect join and UI boundaries.
- A naïve actor was also rejected: pystray Xorg can synchronously dispatch a
  public mutation to its mainloop, deadlocking if that mainloop callback is
  waiting for the actor.
- Proposed shape: one tray-owned FIFO `TrayRuntimeCoordinator`, synchronous
  stable facades, reentrant nested execution, transition revisions for stale
  observations, deferred/coalesced UI refresh on the waiting caller, and
  explicit drain/liveness in A4 shutdown order.
- Effect frames and render-local caches remain outside this low-frequency
  transition owner.
- Full proposal, migration boundary, deterministic test plan and approval
  points are recorded in
  `a2-tray-runtime-coordinator-design.md`.

### 2026-08-11 - A2 serialized tray runtime ownership implementation

- **Disposition:** approved architecture implemented; A2 is complete.
- Added a lazy-capable but explicitly production-started FIFO
  `TrayRuntimeCoordinator` with:
  - synchronous result/exception propagation;
  - owner-thread reentrancy for nested stable facades;
  - accepted-command and active-command revisions;
  - revision-gated sensor observations;
  - deferred/coalesced icon and menu intent, preserving `animate=False`; and
  - bounded drain/stop liveness.
- Production ownership migration covers:
  - complete pystray lighting/device/system-power callbacks and profile
    activation;
  - config reload plus apply as one command;
  - scheduler plans and idle sensor actions with stale-observation rejection;
  - hardware snapshots and failures captured before probing and applied only at
    their captured revision;
  - complete power-source iterations, including shared-config reload/classify;
    and
  - suspend/resume and lid events with both event generations and coordinator
    revisions, so delayed restore cannot overtake newer power or manual intent.
- Menu rendering is now presentation-only: it no longer reloads shared config,
  probes/reconnects hardware, or persists selected-context fallback state.
- Startup explicitly starts the coordinator before runtime producers. Autostart
  classification runs inside it and rechecks committed off state.
- Quit shutdown runs outside the pystray callback thread, avoiding Xorg
  mainloop/join inversion. Shutdown drains and verifies the coordinator before
  engine and secondary-device teardown.
- High-frequency effect frames and render-local caches remain outside the owner
  and retain device-local locking, as approved.
- Regression coverage includes coordinator reentrancy, exception transport,
  stale revisions, deferred UI thread/animation behavior, config and scheduler
  versus newer user-off intent, stale hardware state, stale power-source work,
  delayed resume versus power/manual intent, autostart recheck, and shutdown
  liveness/ordering.
- Validation:
  - initial coordinator defect contracts: `5 failed` before implementation;
  - broad focused tray/poller/power/UI selection: `663 passed`;
  - independent blocker re-review: no blockers found;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3517 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A9 canonical backend selection report

- **Disposition:** confirmed and resolved.
- Runtime selected available candidates by kernel/sysfs safety tier, confidence
  and priority. Diagnostics independently probed the same registry backends,
  sorted only by confidence/priority and published the obsolete policy text.
  It could therefore report a candidate order different from the selected
  backend and probed every runtime backend twice.
- Added immutable registry-owned `BackendProbeEvaluation` and
  `BackendSelectionReport` records plus `build_backend_selection_report()`.
  The report owns alias normalization, policy eligibility, one probe result per
  backend, canonical candidate ordering and the selected backend.
- `select_backend()` now returns the report outcome while preserving pytest
  hardware blocking and requested-backend behavior. Explicit runtime selection
  still probes only the requested backend.
- Diagnostics requests one probe-all report, serializes those probe results and
  uses its candidate order and effective request. Policy-disabled backend probes
  remain visible, while diagnostics-only auxiliary probes remain outside the
  runtime candidate list.
- Diagnostics now publishes the actual policy — kernel/sysfs safety tier, then
  confidence, then priority — and exposes each registry probe's selection safety
  tier.
- Regression tests prove sysfs wins consistently despite lower confidence and
  priority, each registry backend is probed once per diagnostics snapshot, and
  unexpected selection-report defects remain transparent.
- Validation:
  - initial contract run: import error because the canonical report did not
    exist;
  - focused registry and diagnostics tests: `79 passed`;
  - broad backend and diagnostics tests: `629 passed, 1 skipped`;
  - independent blocker review: no blockers found;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3519 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A8 authoritative backend capabilities

- **Disposition:** confirmed and resolved.
- Capability normalization previously treated absent metadata and absent fields
  as full support. Hardware-effect mappings and per-key writer methods could
  therefore enable operations without affirmative backend evidence.
- Added explicit `brightness` capability metadata. Every production backend now
  declares it, allowing brightness-only sysfs backends to remain valid without
  implying RGB or per-key support.
- Capability normalization now returns one typed snapshot and fails closed for
  absent or partial fields. Tray startup also stores the normalized snapshot and
  uses an all-false snapshot after recoverable capability lookup failures.
- Hardware-effect enumeration and engine discovery now require
  `hardware_effects=True`; a method or legacy catalog fallback cannot substitute
  for capability evidence.
- Per-key render paths require both declared support and an operational writer.
  The same gate covers persisted startup/config state, power-source transitions,
  hidden-row restoration and standalone editor hardware acquisition.
- The engine refreshes dynamic capabilities on every device ensure and publishes
  changes through a bootstrap-installed callback to the tray's `backend_caps`,
  including ensures initiated internally by effects and brightness operations.
- Primary brightness UI is disabled when unsupported. Uniform/reactive GUI
  capability failures fail closed; backend-absent config-only mode remains
  editable but performs no hardware writes.
- Diagnostics JSON/text now includes the independent brightness capability.
- Regression coverage proves fail-closed normalization, method-presence
  rejection, brightness-only sysfs validity, canonical effect gating, persisted
  per-key fallback, power transition gating, per-key editor refusal and dynamic
  engine-to-tray capability synchronization.
- Initial contract run failed during collection because the authoritative helper
  and brightness metadata did not exist. Broad backend/effects/tray selection
  subsequently passed `1165 passed, 1 skipped`.
- Independent review found and drove closure of persisted transition, GUI,
  standalone editor and stale dynamic snapshot gaps; final review found no
  blockers.
- Final validation:
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3528 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A5 runtime effect geometry confirmation

- **Disposition:** confirmed; blocked on architecture-shape approval.
- Software/reactive/tray-icon paths import fixed `matrix_layout` constants
  (`6×21`). Backend `dimensions()` already diverge: `6×21`, `6×20`, `7×20`,
  `4×6`, and smaller non-matrix shapes.
- Tray bootstrap already captures `_ite_rows/_ite_cols` for config-poller fill,
  but the effects engine does not own or publish matching runtime geometry.
- Preparatory contract exists: `build_full_color_grid()` honors explicit
  dimensions. Live frame construction still hard-codes the reference grid.
- Proposed owner and contracts are recorded in
  `a5-runtime-effect-geometry-design.md`. Production implementation waits for
  explicit approval of that shape.

### 2026-08-11 - A5 runtime effect geometry implementation

- **Disposition:** approved architecture implemented; A5 is complete.
- Added immutable `EffectGridGeometry` with reference helpers. Module
  `NUM_ROWS/NUM_COLS` remain compatibility aliases for the reference fallback
  (now aligned with `REFERENCE_MATRIX_*`).
- `EffectsEngine` owns `effect_geometry` and refreshes it with backend
  capabilities on construction, `set_backend()`, and device ensure.
- Per-key backends supply live rows/cols through `dimensions()`. Non-per-key
  backends keep reference geometry and continue uniform reduction.
- Software, reactive, fade, and tray-icon frame paths consume engine geometry
  instead of hard-coded 6×21.
- `build_full_color_grid()` ignores out-of-range sparse profile cells.
- Tray bootstrap seeds `_ite_rows/_ite_cols` from the engine snapshot so config
  fill and effects share one owner.
- Regression coverage proves 7×20 and 6×20 per-key frames, uniform reference
  fallback, backend-change refresh, and out-of-range cell rejection.
- Validation:
  - focused geometry/effects/icon selection: `492 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3534 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A6 profile application boundary

- **Disposition:** confirmed and resolved.
- Core `activate_perkey_profile_runtime` previously resolved private tray methods
  (`_start_current_effect`, `_update_icon`, `_update_menu`,
  `_apply_power_source_perkey_profile_transition`) and tray-owned attributes
  (`_power_forced_off`, power-source transition stamps, active secondary
  lighting) by name despite avoiding tray imports.
- Core activation now takes only explicit hooks for config load/apply, power-off
  gating, runtime transition/effect start, UI refresh, secondary storage, and
  power-source transition markers. It returns a typed `ProfileActivationResult`.
- Tray menu activation wires those hooks in
  `src/tray/controllers/profile_activation.py`. Power-source activation supplies
  duck-typed hooks from the tray object without importing tray packages into
  core.
- Config application still precedes runtime lighting and UI refresh.
- Regression coverage proves callback order, power-forced-off skip, secondary
  payload handling, menu refresh gating, and that core source no longer contains
  private tray attribute/method contracts.
- Validation:
  - focused activation/power/menu selection: `29 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3535 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A18 built-package resource validation

- **Disposition:** confirmed and resolved.
- Pre-fix wheel contents included top-level `src/core/resources/*.json` only.
  Nested `reference_defaults_specs/**/*.json` (including `per_key_tweaks/`) were
  absent, so installed packages could not load split starter defaults. Editable
  installs masked the gap by reading the checkout tree.
- `[tool.setuptools.package-data]` now uses recursive `**/*.json` and `**/*.png`
  under the `src` package.
- Tests cover source manifest closure, package-data pattern coverage of every
  resource data file, and an isolated wheel build/install smoke that loads ANSI
  reference defaults from the installed distribution.
- CI quality job adds a matching built-wheel resource smoke step.
- Validation:
  - focused packaged resources: `4 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3538 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A11 brightness domain units

- **Disposition:** confirmed and resolved.
- Primary keyboard brightness correctly uses the persisted `0..50` 5-step grid,
  but independent secondary brightness was inconsistently normalized:
  profile payloads / secondary state / config profile-merge used `0..100`, while
  config secondary accessors re-applied the primary keyboard normalizer and
  snapped values (for example `17 -> 15`, `75 -> 50`).
- Added canonical `normalize_secondary_brightness_value` (`0..100`, no snap) in
  lighting coercion and routed profile storage, secondary lighting state,
  secondary runtime clamps, tray secondary profile updates, and config secondary
  accessors through that single unit.
- Primary and precise brightness normalizers remain unchanged.
- Durable docs now state the three brightness domain units explicitly.
- Validation:
  - focused brightness/secondary selection: `60 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3542 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A12 error semantics

- **Disposition:** confirmed for config persistence and resolved; programming-
  shaped catches at backend registry / effect-thread seams kept under the
  existing runtime-boundary policy (recoverable tuples + AssertionError
  propagation already covered by tests).
- Ordinary `Config._save()` discarded `_persist_changes()` boolean failures, so
  property setters and profile-apply helpers could leave a dirty in-memory view
  with no exception. Only `batch_update()` raised `ConfigPersistenceError`.
- `_save()` now raises `ConfigPersistenceError` after restoring `_settings` from
  the last persisted snapshot when a non-batch write fails. Batch transactions
  keep snapshot rollback on final-write failure.
- Durable policy docs record the config persistence error contract.
- Validation:
  - focused config selection: `107 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3544 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A21 installer cleanup / udev uninstall matching

- **Disposition:** confirmed and resolved.
- Uninstall identified managed udev rules with stale comment markers that no
  longer appear in current rule headers (`Allow user access to ITE 8291 USB
  device.`, `Reactive Typing effects`). Bootstrap curl uninstalls also lack the
  `system/udev` source tree, so `cmp` matching fails and marker-only matching is
  required; managed rules could be left installed.
- Added stable `KEYRGB_MANAGED_UDEV_RULE=...` markers to the three managed rule
  files, extracted match helpers to `scripts/lib/uninstall_match.sh` (with
  legacy-header fallbacks), wired `scripts/uninstall.sh` and bootstrap
  `uninstall.sh` to that library, and added sandbox installer tests covering
  current/legacy/foreign rules without sudo.
- Validation:
  - focused installer selection: `4 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3548 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A20 release input immutability

- **Disposition:** confirmed and resolved for the highest-impact release inputs;
  residual installer `main` fallbacks for optional helper/udev bootstrap assets
  remain documented compatibility paths.
- AppImage packaging downloaded mutable
  `AppImageKit/.../continuous/appimagetool` with no digest check.
- Pinned `appimagetool` to versioned `AppImage/appimagetool@1.9.1` with embedded
  SHA-256 and `download_verified()` fail-closed reuse/mismatch handling.
- Pinned CI/release GitHub Actions to immutable commit SHAs.
- Installer checksum verification gained opt-in fail-closed mode via
  `KEYRGB_REQUIRE_CHECKSUM=1`.
- Validation:
  - focused appimage/release-input selection: `10 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3553 passed, 1 skipped`; all eight gates passed.

### 2026-08-11 - A10 configuration domain model

- **Disposition:** confirmed and resolved.
- `Config` still exposed one flat mutable `_settings` bag spanning lighting,
  secondary, power, idle/display, scheduler, layout, and app/session concerns,
  with non-lighting property definitions piled into `config.py`.
- Introduced domain ownership (`ConfigDomain` + key partition), `ConfigDocument`
  for live settings identity and readonly domain/extras projections, and split
  power/scheduler/app accessor mixins out of the facade. Public properties and
  flat on-disk JSON remain compatible; unknown keys are preserved as extras.
- Durable architecture: `docs/1-src/15-config-domain-model.md`.
- Validation:
  - focused config suite: `112 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3558 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A13 explicit effect runtime contracts

- **Disposition:** confirmed and resolved.
- Reactive effects injected a large dependency map into module globals and then
  recovered that module through `sys.modules` casts. Hardware payload building
  discovered accepted fields through callable closure internals and retried by
  parsing `ValueError` text. Engine mixins declared shared state separately but
  had no construction-time completeness check.
- Added a frozen `ReactiveApiFacade` passed directly to fade/ripple loops,
  `HardwareEffectBuilder` metadata plus structured
  `UnsupportedHardwareEffectArgument`, and an explicit engine-support contract
  validated when `EffectsEngine` is constructed. All in-tree hardware-effect
  builder backends now publish accepted payload fields.
- Durable architecture: `docs/1-src/16-effect-runtime-contracts.md`.
- Validation:
  - focused effects/backend suite: `676 passed, 1 skipped`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3567 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A14 backend extension and per-controller identity

- **Disposition:** confirmed and resolved.
- Built-in backends were registered only through a hardcoded `_default_specs()`
  import list. Static provider/tier/safety data was inferred from name prefixes,
  and `sysfs-mouse` was imported as a diagnostics special case. ITE 8258 chassis
  transport and profile-coordinator state were process-global and keyed only by
  backend name.
- Package-owned `BACKEND_REGISTRATION` markers plus `BackendMetadata` now drive
  discovery, primary-versus-auxiliary role, provider, and safety tier.
  Shared HID/coordinator state is keyed by `controller_identity(backend, hidraw)`.
- Durable architecture: `docs/1-src/17-backend-extension.md`.
- Validation:
  - focused backend/diagnostics selection: `150 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3574 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A15 diagnostics purity

- **Disposition:** confirmed and resolved.
- Secondary-device diagnostics constructed a live `Config()`, snapshots only
  froze the top-level mapping, and `env_snapshot()` used a stale KEYRGB allowlist
  that omitted current policy variables.
- Diagnostics now load a detached `ReadonlyDiagnosticsConfig`, deep-freeze
  snapshot graphs, serialize through `to_dict()` as ordinary JSON data, and
  report every present `KEYRGB_*` variable plus desktop-session keys.
- Durable architecture: `docs/1-src/18-diagnostics-purity.md`.
- Validation:
  - focused diagnostics/export suite: `149 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3577 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A16 GUI async jobs

- **Disposition:** confirmed and resolved.
- `run_in_thread()` had no cancel or generation, so stale workers could still
  deliver UI updates. Uniform apply/release, per-key commit, and power-mode
  preview/save ran blocking hardware or sysfs work on the Tk callback.
- Added `TkAsyncJob` / `TkAsyncCoordinator` and routed those production paths
  through `submit_gui_work()`. Tests without a coordinator remain synchronous.
- Durable architecture: `docs/1-src/19-gui-async-jobs.md`.
- Validation:
  - focused GUI async/uniform/power/perkey selection: `390 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3580 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A17 tray view boundaries

- **Disposition:** confirmed and resolved.
- A2 already stopped primary-device ensure during menu build, but construction
  still called live `get_status()` (cpufreq sysfs, including checked callbacks)
  and `iter_effective_secondary_routes()` (backend probe / `is_available`).
- Added tray-owned snapshots in `src/tray/controllers/view_snapshots.py`.
  Runtime start captures them; power-mode apply refreshes the power snapshot;
  menu builders only read stored state.
- Durable architecture: `docs/1-src/20-tray-view-boundaries.md`.
- Validation:
  - focused tray menu/snapshot/application selection: `109 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3589 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A22 validation layers

- **Disposition:** confirmed and resolved.
- Unit coverage was already strong. Remaining gaps: the hardware tripwire was
  opt-in because a USB-import ban broke backend unit tests; sdist install was
  untested; desktop XDG roots were not isolated; installer desktop integration
  had no sandbox.
- Default suite now refuses real `/sys` writes and `/dev/bus/usb` opens, isolates
  `XDG_*` roots, smokes sdist resources, and sandboxes desktop launcher/autostart
  install. USB-import and LED-snapshot tripwires stay opt-in.
- Durable architecture: `docs/1-src/21-validation-layers.md`.
- Validation:
  - focused validation/sysfs/installer/session/resource selection: `13 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19`:
    `3596 passed, 1 skipped`; all eight gates passed.

### 2026-08-17 - A23 tool policy

- **Disposition:** confirmed and resolved.
- Mypy stayed a narrow runtime/GUI-baseline gate but now enables
  `warn_redundant_casts` and `no_implicit_optional`. Dead-code was
  informational; unused functions/classes/imports in runtime code now fail.
  Architecture warning findings did not fail the step; they do now, after
  excluding the per-key hardware bootstrap from the backend-selection rule.
  Installer shell had no ShellCheck step.
- Added Step 21 ShellCheck, CI shellcheck install, and `vulture` to dev extras.
- Durable architecture: `docs/1-src/22-tool-policy.md`.
- Validation:
  - focused buildpython tool-policy selection: `16 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19,20,21`:
    `3600 passed, 1 skipped`; all ten gates passed.

### 2026-08-17 - A24 build/CI documentation drift

- **Disposition:** confirmed and resolved.
- Build-system docs still said steps `1–19` and understated the `ci` profile.
  CI docs described a nonexistent AppImage CI job. CONTRIBUTING pointed at
  `docs/developement/backends/` and told contributors to register backends only
  in `registry.py`.
- Updated buildpython, CI, contributing, and architecture-index docs. Added a
  contract test so the step catalog, profiles, and contributor links cannot
  drift silently.
- Validation:
  - focused build-docs selection: `4 passed`;
  - `python -m buildpython --run-steps=2,3,7,10,13,16,17,19,20,21`:
    `3604 passed, 1 skipped`; all ten gates passed.

### 2026-08-17 - campaign complete

- Every inventory item is `done` or `rejected` (A3 rejected).
- No remaining `reported`, `active`, `monitoring`, or `blocked` items.
