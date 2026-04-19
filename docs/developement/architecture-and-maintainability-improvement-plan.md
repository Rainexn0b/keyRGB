# Architecture And Maintainability Improvement Plan

## Purpose

This document consolidates the current architecture and maintainability review into one active plan. The goal is to raise KeyRGB's architecture score from roughly `7.5/10` to `8.5/10+` and its maintainability score from roughly `6.5/10` to `8.0/10+` without reducing hardware support, weakening runtime resilience, or forcing a disruptive rewrite.

This plan is based on direct code review, a green local test run, the repo's own buildpython quality tooling, and the archived assessments under [archived/2026-04-17](archived/2026-04-17).

## Current Baseline

KeyRGB already has several strong foundations.

- The backend abstraction is sound and intentionally small.
- The repo has unusually strong debt automation for an open-source utility app.
- The test suite is large, fast, and currently healthy.
- The project documents its own technical debt honestly.

The scores are held down mainly by boundary management problems rather than by weak engineering discipline.

## What Is Depressing The Scores

The main score depressors are these:

1. Central coordinators own too many responsibilities.
2. Runtime state is still too implicit and duck-typed in key entrypoints.
3. Several GUI modules mix view logic, workflow logic, backend routing, and persistence.
4. Config and runtime snapshots are still more dict-centric than they need to be.
5. Packaging and launch/bootstrap behavior are functional but more unconventional than necessary.
6. Recoverable exception boundaries are mostly justified, but the policy surface is broader than ideal.
7. Testing is strong at the unit and debt-automation levels but thinner at the integration and runtime-flow levels.

## Improvement Targets

To improve architecture and maintainability materially, the codebase should move toward these conditions:

- Public facades stay stable, but their internals become thinner.
- State ownership becomes explicit at tray, power, config, and GUI boundaries.
- Coordinators decide less and delegate more.
- View code stops owning backend acquisition and route-selection policy directly.
- Config aliasing and normalization are encoded once instead of re-expressed across call sites.
- Runtime exception boundaries stay at real OS, hardware, or long-running loop seams.
- Test coverage becomes more meaningful at runtime seams, not just broader in percentage terms.

## Priority Workstreams

## 1. Thin The Main Coordinators

Priority: `P0`

This is the highest-return work. The largest maintainability cost in the repo comes from orchestration hotspots rather than from protocol code or domain rules.

Primary targets:

- [src/tray/app/application.py](../../src/tray/app/application.py)
- [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py)
- [src/core/power/management/manager.py](../../src/core/power/management/manager.py)
- [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)
- [src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py)
- [src/gui/windows/uniform.py](../../src/gui/windows/uniform.py)

What to tackle:

- Keep the current public facades, but move decision-heavy logic behind narrower services.
- Separate classification from execution in config-apply and power-event flows.
- Reduce modules that combine bootstrap, runtime service behavior, logging, notifications, and callback forwarding.
- Move workflow orchestration out of GUI window classes where possible.

What success looks like:

- The largest coordinator modules shrink in responsibility even if some public class names remain the same.
- Tests stop needing full fake tray or full fake window surfaces just to verify one behavior.
- Changes to notifications, power policy, config application, or GUI workflows become more local.

## 2. Make Tray And GUI State Explicit

Priority: `P0`

The tray bootstrap and some GUI workflows still rely too much on dynamic attribute injection and wide mutable surfaces.

Primary targets:

- [src/tray/app/_application_bindings.py](../../src/tray/app/_application_bindings.py)
- [src/tray/app/application.py](../../src/tray/app/application.py)
- [src/tray/protocols.py](../../src/tray/protocols.py)
- [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)

What to tackle:

- Replace tray bootstrap `setattr()` wiring with explicit dependency or state containers.
- Declare tray-owned attributes up front instead of teaching the type system after initialization.
- Narrow wide duck-typed surfaces into smaller protocols or typed state objects.
- Document initialization order and ownership for tray state.

What success looks like:

- Tray collaborators are visible from initialization instead of attached later.
- IDE and static-analysis support improves around tray and GUI runtime state.
- Pollers and controllers stop reaching through implicit mutable surfaces as often.

## 3. Expand Typed Config And Snapshot Boundaries Incrementally

Priority: `P1`

KeyRGB already uses dataclasses and typed snapshots successfully in several places. The next step is to apply that pattern to more of the config and runtime-state boundary without changing the on-disk schema early.

Primary targets:

- [src/core/config/config.py](../../src/core/config/config.py)
- [src/core/config/_lighting/_coercion.py](../../src/core/config/_lighting/_coercion.py)
- [src/core/config/_lighting/_lighting_accessors.py](../../src/core/config/_lighting/_lighting_accessors.py)
- [src/core/config/_lighting/_secondary_device_accessors.py](../../src/core/config/_lighting/_secondary_device_accessors.py)
- [src/core/diagnostics/model.py](../../src/core/diagnostics/model.py)
- [src/gui/settings/settings_state.py](../../src/gui/settings/settings_state.py)
- [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)

What to tackle now:

- Add typed snapshot models for support-window probe state and diagnostics config state.
- Wrap nested maps such as `effect_speeds` and `secondary_device_state` behind typed helpers.
- Reuse and expand `SettingsValues`-style config views where the model is already coherent.

What to tackle later:

- Add a normalized config model behind `Config` while preserving the flat JSON format initially.
- Formalize more tray/config runtime snapshots after the smaller models prove out.

What success looks like:

- Fewer repeated alias and fallback chains across pollers, GUI code, diagnostics, and power logic.
- Less need to inspect raw dict shape at call sites.
- More runtime-state evolution happens by updating a typed model instead of coordinating string keys manually.

## 4. Split GUI View Code From Workflow And Backend Routing

Priority: `P1`

The GUI layer is not failing because Tk is inherently messy. It is failing where view code also owns workflow state, device selection, backend acquisition, and persistence timing.

Primary targets:

- [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)
- [src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py)
- [src/gui/windows/uniform.py](../../src/gui/windows/uniform.py)

What to tackle:

- Extract support dialog helpers into a smaller dialog library or layout helper module.
- Extract support workflows into a job orchestrator or support-session model.
- Introduce target adapters for uniform/reactive windows so the window stops deciding how to talk to keyboard versus secondary devices.
- Keep the window class as the thin shell for widgets, layout, and user callbacks.

What success looks like:

- Window classes primarily manage widgets and event handling.
- Backend acquisition and route-selection logic move to factories or adapters.
- Support workflows become easier to test without building giant fake window objects.

## 5. Separate Policy, Classification, And Side Effects

Priority: `P1`

Several maintainability problems come from one function or class doing all of these at once: detect change, pick the strategy, perform the side effect, recover from failure, and refresh UI.

Primary targets:

- [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py)
- [src/core/power/management/manager.py](../../src/core/power/management/manager.py)
- [src/tray/controllers/lighting_controller.py](../../src/tray/controllers/lighting_controller.py)

What to tackle:

- Move config-change classification into smaller transition or strategy objects.
- Separate power-event source selection, policy evaluation, and controller invocation.
- Keep degraded outcomes and runtime-boundary behavior, but centralize them at cleaner adapter seams.

What success looks like:

- New effect or power-policy behavior adds a strategy or classifier branch, not another large coordinator branch.
- Tests can focus on decision logic separately from side effects.
- Failure handling remains explicit but is easier to audit.

## 6. Normalize Packaging, Launch, And Import Bootstrap Behavior

Priority: `P2`

The current packaging model works, but it requires repeated reminders that `src` is the import package rather than just a source container. That is a maintenance tax.

Primary targets:

- [pyproject.toml](../../pyproject.toml)
- [keyrgb](../../keyrgb)
- [src/tray/ui/gui_launch.py](../../src/tray/ui/gui_launch.py)
- [src/gui/calibrator/launch.py](../../src/gui/calibrator/launch.py)
- [tests/_paths.py](../../tests/_paths.py)
- [tests/conftest.py](../../tests/conftest.py)

What to tackle now:

- Decide explicitly whether `buildpython` is part of the shipped package boundary.
- Replace fixed path-depth assumptions with structural root-discovery helpers.
- Normalize how entrypoints expose `main`.
- Pick one primary test import-bootstrap strategy.

What to tackle later:

- Re-evaluate whether a conventional `src/keyrgb/` layout is still worth the migration cost after the lower-risk cleanup is done.

What success looks like:

- Fewer runtime import fallbacks and path hacks.
- Clearer contributor expectations around installed commands versus checkout-local wrappers.
- Less coupling between packaging shape and runtime behavior.

## 7. Tighten Exception-Boundary Policy By Category

Priority: `P2`

KeyRGB should stay resilient at hardware, OS, and long-running loop boundaries. That part is correct. The cleanup need is not to remove resilience, but to stop using the same broad boundary style in lower-value diagnostic or callback glue when narrower contracts would do.

Primary targets:

- [src/core/backends/registry.py](../../src/core/backends/registry.py)
- [src/core/power/management/manager.py](../../src/core/power/management/manager.py)
- [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py)
- [src/tray/controllers/lighting_controller.py](../../src/tray/controllers/lighting_controller.py)
- [src/tray](../../src/tray)

What to tackle:

- Keep broad recoverable boundaries at true runtime seams.
- Review tray logging, menu, and callback guards separately from hardware or OS boundaries.
- Consolidate repeated boundary wrappers where the degraded behavior is the same.
- Preserve tests that prove unexpected programmer defects still propagate.

What success looks like:

- The boundary policy becomes easier to audit by category.
- Fewer low-value catches exist around internal glue code.
- Runtime resilience remains intact for real device and OS failures.

## 8. Improve The Test Pyramid And Quality Signals

Priority: `P1` for new integration coverage, `P2` for reporting cleanup

The repo is already strong on unit tests and quality gates. The next maintainability gain comes from adding a few higher-value integration seams and making the coverage signal trustworthy.

Primary targets:

- [tests/conftest.py](../../tests/conftest.py)
- [tests/core/backends](../../tests/core/backends)
- [tests/core/config](../../tests/core/config)
- [tests/core/power](../../tests/core/power)
- [tests/tray](../../tests/tray)
- [buildpython](../../buildpython)
- [htmlcov/index.html](../../htmlcov/index.html)

What to tackle:

- Add higher-value integration tests for backend selection, config round-tripping, effects pipeline, tray lifecycle, and power scenarios.
- Build reusable mock-device fixtures for backend families.
- Add pytest markers for integration, GUI, and slower suites.
- Make coverage reporting current and decision-useful before using it as a stronger governance metric.

What success looks like:

- More confidence around runtime flows, not just around local helpers.
- Fewer wide coordinator tests are needed to pin behavior indirectly.
- Coverage discussions focus on meaningful seam coverage rather than stale or misleading percentages.

## 9. Strengthen Architecture Governance With Lightweight Rules

Priority: `P3`

The repo already has useful architecture and debt automation. Once the structural cleanup starts, the next step is to use lightweight rules to keep the gains from eroding.

Primary targets:

- [buildpython/config/architecture_rules.json](../../buildpython/config/architecture_rules.json)
- [buildpython](../../buildpython)
- [docs/developement](.)

What to tackle:

- Add or tighten architecture rules only after the target boundaries are stable.
- Keep active roadmap documentation separate from archived assessments.
- Use file-size, exception-boundary, and package-structure checks as backstops, not as the design process itself.

What success looks like:

- New boundary mistakes are caught earlier.
- The repo has one active plan and several archived rationale docs instead of many disconnected notes.

## Recommended Sequencing

## Phase 1: Highest ROI, Lowest Structural Risk

Focus here first.

- Thin `KeyRGBTray` without changing its public role.
- Replace dynamic tray dependency injection with explicit state or dependency containers.
- Start splitting config-polling decision logic from execution logic.
- Add typed support and diagnostics snapshots.
- Add typed wrappers for nested config maps.
- Clean up packaging boundary documentation, root discovery, and entrypoint consistency.
- Add the first higher-value integration tests for config persistence and tray/runtime seams.

## Phase 2: Broader Boundary Cleanup

Take this on once phase 1 seams are proven.

- Split power-manager responsibilities more aggressively.
- Split support-window workflows from Tk layout helpers.
- Move uniform/reactive backend routing behind adapters.
- Tighten exception-boundary categories in tray and support glue.
- Expand integration tests around power, backend selection, and effect flows.

## Phase 3: Structural Changes Only If Still Justified

Do this only after earlier improvements land and stabilize.

- Introduce a normalized config core behind `Config`.
- Formalize tray state ownership further through protocols or typed containers.
- Re-evaluate a package-layout migration away from the current importable `src` model.

## What Not To Do Yet

These are tempting but should not lead the effort.

- Do not start with a repo-wide package rename.
- Do not replace `Config._settings` everywhere in one pass.
- Do not remove broad recoverable exception boundaries at true runtime seams before replacing them with better-placed boundaries.
- Do not chase raw coverage percentage before adding higher-value integration seams and refreshing the reporting path.
- Do not mechanically split files by line count alone; split by responsibility and boundary.

## Definition Of Done

This plan is working when most of these statements are true:

- The tray app is a thinner orchestrator with explicit dependencies.
- Config-apply and power-event logic have clearer decision-versus-execution seams.
- Support, reactive, and uniform windows are visibly thinner and less coupled to backend-routing policy.
- Key config aliases and nested maps are normalized behind typed helpers instead of repeated dict access.
- Package/bootstrap behavior is easier to explain and less path-fragile.
- Runtime exception boundaries are easier to classify and audit.
- Integration tests exist for the runtime seams that matter most to users.
- The archived assessments still explain the rationale, and this file remains the active roadmap.

## Related Assessments

- [Split Orchestration Hotspots / Reduce Central Coordinator Complexity](archived/2026-04-17/orchestration-hotspots-assessment.md)
- [Typed Config And State Models Assessment](archived/2026-04-17/typed-config-and-state-models-assessment.md)
- [Package Structure Assessment: Normalizing the Python Packaging Layout](archived/2026-04-17/package-structure-assessment.md)
- [Exception Boundary Policy Assessment](archived/2026-04-17/exception-boundary-policy-assessment.md)

## Active Campaign Notes

- [Package And GUI Boundary Refactor Anchor Plan](package-and-gui-boundary-refactor-anchor-plan.md)
- [Refactor Campaign Progress](refactor-campaign-progress.md)

## Short Version

If the project only tackles a small number of things, the best order is:

1. Thin the coordinators.
2. Make runtime state explicit.
3. Expand typed config and snapshot boundaries.
4. Split GUI workflow from view code.
5. Add integration tests at the runtime seams created by those refactors.

That sequence will improve both architecture and maintainability more than any single rewrite or metric-driven cleanup pass.