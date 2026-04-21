# Agent Improvement Roadmap

> Archived snapshot from `2026-04-21`. The active coordination docs now live in `docs/developement/improvement-roadmap.md` and the three chunk specs under `docs/developement/chunk-*.md`.

## Purpose

This document was the active roadmap for the `2026-04-21` KeyRGB improvement campaign snapshot.

It is intended to do two things:

1. Capture the main areas where the codebase still has meaningful improvement headroom.
2. Turn those areas into delegation-ready workstreams for future agent rounds.

This roadmap replaces ad hoc planning from chat history. Archived analysis and earlier campaign notes remain useful context under `docs/developement/archived/`, but this file should be treated as the active coordination document for upcoming maintenance and architecture work.

## Current Baseline

The current merged baseline is strong.

- `buildpython` reports a healthy repo state with architecture validation, exception transparency, packaging checks, and coverage all passing.
- The current actionable queue from file-size, architecture, and exception-transparency reports is clear.
- Coverage is already high enough that the next gains should come from better seam coverage, not percentage chasing.
- The project has already completed several focused cleanup waves without breaking public facades.

That means the next campaign should be driven by strategic maintainability and architecture goals, not by waiting for scanner-visible debt to accumulate again.

## What Is Already Strong

- Backend selection is relatively disciplined and intentionally policy-driven.
- Runtime resilience is handled more carefully than in most hardware-facing desktop utilities.
- The test harness is strong, especially around hardware safety and config isolation.
- The repository already uses quality automation as a guardrail rather than a vanity metric.
- The recent refactor waves successfully reduced several boundary leaks without destabilizing public entrypoints.

## Main Improvement Areas

The largest remaining opportunities are structural rather than correctness-driven.

### 1. Thin Coordinator Modules

These files still carry too much orchestration responsibility even after recent cleanup:

- `src/tray/app/application.py`
- `src/tray/pollers/config_polling_internal/core.py`
- `src/core/power/management/manager.py`
- `src/gui/windows/_support/_support_window_jobs.py`
- `src/gui/windows/reactive_color.py`
- `src/gui/windows/uniform.py`

What needs improvement:

- decision-making mixed with side effects
- broad lifecycle ownership in a single facade
- runtime/service wiring mixed with user-facing behavior
- tests that still need wide fake surfaces to exercise narrow behaviors

Target outcome:

- public facades stay stable
- coordination logic moves behind smaller helpers or services
- classification and execution paths are easier to test independently

### 2. Make Tray And GUI Runtime State More Explicit

The tray runtime still relies too much on implicit mutable surfaces and dynamic attribute wiring.

Primary targets:

- `src/tray/app/_application_bindings.py`
- `src/tray/app/application.py`
- `src/tray/protocols.py`
- `src/gui/windows/_support/_support_window_jobs.py`

What needs improvement:

- `setattr()`-driven bootstrap wiring
- runtime state declared after construction rather than owned explicitly
- wide duck-typed collaborator surfaces
- initialization order that is valid but harder to reason about than necessary

Target outcome:

- tray-owned state becomes visible from initialization
- protocols become confirmation of stable boundaries, not compensation for implicit state
- pollers and controllers depend on narrower state contracts

### 3. Expand Typed Config And Snapshot Boundaries

The codebase already uses typed models well in some places, but config and runtime snapshots are still more dict-driven than ideal.

Primary targets:

- `src/core/config/config.py`
- `src/core/config/_lighting/_coercion.py`
- `src/core/config/_lighting/_lighting_accessors.py`
- `src/core/config/_lighting/_secondary_device_accessors.py`
- `src/core/diagnostics/model.py`
- `src/gui/settings/settings_state.py`
- `src/gui/windows/_support/_support_window_jobs.py`

What needs improvement:

- repeated alias and fallback chains
- nested maps such as `effect_speeds` and secondary-device state being manipulated directly at call sites
- runtime state evolution expressed as string-key coordination instead of typed models

Target outcome:

- typed wrappers or snapshot models sit in front of the nested config state
- repeated config-shape logic is centralized
- more code consumes explicit views rather than raw internal maps

### 4. Separate GUI View Code From Workflow And Backend Routing

The GUI is improving, but public window modules still carry too much mixed responsibility.

Primary targets:

- `src/gui/windows/_support/_support_window_jobs.py`
- `src/gui/windows/reactive_color.py`
- `src/gui/windows/uniform.py`
- selected `src/gui/perkey/` entry modules when they show the same pattern

What needs improvement:

- view code also deciding backend or route selection
- persistence timing and workflow state managed inside Tk-heavy modules
- window facades still acting as adapters, controllers, and views at once

Target outcome:

- public window modules become thinner shells
- backend selection and target resolution stay in bootstrap or adapters
- workflow state becomes easier to test without constructing oversized fake windows

### 5. Separate Policy, Classification, And Side Effects

This remains one of the highest-value design cleanups in the repo.

Primary targets:

- `src/tray/pollers/config_polling_internal/core.py`
- `src/core/power/management/manager.py`
- `src/tray/controllers/lighting_controller.py`

What needs improvement:

- change detection, policy choice, effect application, fallback behavior, and UI refresh all happening in the same flow
- tests needing to assert through side effects instead of through smaller decision seams

Target outcome:

- policy evaluation is testable without exercising the full runtime flow
- side-effect adapters stay narrow and obvious
- new behavior grows by adding strategies or policy units rather than expanding coordinator branches

### 6. Normalize Packaging, Launch, And Import Bootstrap Behavior

The code works, but this area still creates unnecessary contributor friction.

Primary targets:

- `pyproject.toml`
- `keyrgb`
- `src/core/runtime/imports.py`
- `src/tray/ui/gui_launch.py`
- `src/gui/calibrator/launch.py`
- `tests/_paths.py`
- `tests/conftest.py`

What needs improvement:

- the importable `src` package remains unconventional and requires repeated explanation
- checkout-local launcher behavior and installed entrypoint behavior are more different than ideal
- root-discovery and sys.path bootstrap logic exists in several places

Target outcome:

- one clear import/bootstrap story for local development and runtime
- less path manipulation at call sites
- clearer contributor expectations around shipped versus dev-only package boundaries

### 7. Keep Exception Boundaries Intentional By Category

The current scanner baseline is clean, but the long-term goal is still to keep broad runtime boundaries limited to real runtime seams.

Primary targets:

- `src/core/backends/registry.py`
- `src/core/power/management/manager.py`
- `src/tray/pollers/config_polling_internal/core.py`
- `src/tray/controllers/lighting_controller.py`
- selected tray and GUI callback helpers

What needs improvement:

- recurring recoverable-boundary patterns should be easier to audit
- callback or diagnostic glue should not drift toward the same broad handling style as OS or hardware seams

Target outcome:

- runtime resilience stays intact
- broad boundaries remain clearly justified by category
- similar degraded behaviors are centralized where that improves clarity

### 8. Improve Integration Coverage At Runtime Seams

The test suite is already strong. The next step is to improve what it proves.

Primary targets:

- `tests/core/backends/`
- `tests/core/config/`
- `tests/core/power/`
- `tests/tray/`
- selected GUI seam tests where a small integration layer adds value

What needs improvement:

- more runtime-flow coverage around backend selection, config round-tripping, tray lifecycle, and power scenarios
- more reusable fixtures for device families and runtime seams
- clearer distinction between unit-level behavior and seam-level integration checks

Target outcome:

- confidence grows around runtime behavior, not only around local helper functions
- refactors can lean on smaller but more meaningful integration checks

## Workstream Priorities

### P0: Start Here

- thin coordinator modules
- make tray and GUI runtime state explicit
- separate policy, classification, and side effects in tray and power flows

### P1: Start Once The First Seams Are Stable

- expand typed config and snapshot boundaries
- split GUI view code from workflow and backend routing more aggressively
- improve integration coverage at the runtime seams created by the refactors

### P2: Do After The Higher-ROI Structural Work

- normalize packaging and import bootstrap behavior
- continue tightening exception-boundary policy by category where cleanup is still warranted

## Delegation Strategy

Each agent round should stay narrow.

- One hotspot per agent, or one tightly coupled file pair.
- Preserve tested and public facades unless the round explicitly includes a contract change.
- Prefer root-cause boundary cleanup over file splitting for its own sake.
- Use parent-side merged validation as authoritative.
- Refresh queueing from current reports after each merged round, but do not confuse a clear scanner queue with “no further improvement work.”

## Validation Rules

Use the smallest validation that proves the hotspot, then rerun merged checks in the parent context.

- Focused pytest targets for touched areas.
- `.venv/bin/python -m buildpython --run-steps=13,17,19` for boundary-sensitive work.
- `.venv/bin/python -m buildpython --run-steps=6,13,17,19` when a round changes package shape, import topology, or debt-scanner-visible structure.

Parent-side merged validation remains the source of truth even when an agent reports green local results.

## Delegation Queue Template

For each future round, fill in this structure before dispatching agents:

- queue source
- hotspot
- allowed files
- protected public or tested facades
- exact validation commands
- expected handoff format

Recommended handoff format:

- files changed
- debt or risk reduced
- tests or commands run and results
- residual risks or follow-up suggestions

## Campaign Progress Snapshot (2026-04-21)

The scanner-visible queue is clear and several roadmap hotspots are already complete.

### Completed in this campaign

- `src/core/power/management/manager.py` coordinator thinning and policy/classification seam extraction
- `src/gui/windows/reactive_color.py` state/settings adapter extraction
- `src/gui/windows/uniform.py` bootstrap adapter extraction
- targeted seam coverage expansions in power and GUI window boundaries
- flat-directory scanner follow-up and allowlist alignment for peer-level test roots

### Remaining work

- tray runtime state explicitness and protocol narrowing (`src/tray/app/application.py`, `src/tray/app/_application_bindings.py`, `src/tray/protocols.py`)
- tray policy/classification seam hardening and boundary audit (`src/tray/pollers/config_polling_internal/core.py`, `src/tray/controllers/lighting_controller.py`)
- support-window private re-export surface cleanup (`src/gui/windows/_support/_support_window_jobs.py`) and perkey entry-module survey
- typed config and snapshot boundary cleanup (`src/core/config/_lighting/*`, `src/core/diagnostics/model.py`, `src/gui/settings/settings_state.py`)
- packaging/import bootstrap normalization follow-through (`src/core/runtime/imports.py`, launcher/test bootstrap callers)

## Current Chunk Execution Plan

The roadmap is now executed through three bounded chunk documents under `docs/developement/`.

### Chunk A (P0): Tray policy and classification seams

- spec: `docs/developement/chunk-a-tray-policy-seams.md`
- focus: tray config-polling state seams and controller boundary auditing

### Chunk B (P1): GUI window cleanup

- spec: `docs/developement/chunk-b-gui-window-cleanup.md`
- focus: support-window boundary cleanup and perkey entry-module seam survey

### Chunk C (P1/P2): Typed config boundaries and bootstrap cleanup

- spec: `docs/developement/chunk-c-config-typed-boundaries.md`
- focus: typed config/snapshot shaping and import-bootstrap normalization

Execution order:

1. Chunk A
2. Chunk B
3. Chunk C

Validation rule for each chunk remains unchanged: run focused tests first, then parent-side merged `buildpython` validation.

## Success Criteria

This roadmap is succeeding when most of the following become true:

- the tray app is visibly thinner and owns explicit state
- power and config flows have clearer decision-versus-effect seams
- GUI windows are slimmer and less responsible for backend routing
- config and runtime state are accessed through more typed boundaries
- packaging and import bootstrap behavior are simpler for contributors to understand
- integration tests cover the runtime seams that matter most to users
- the repo stays green on merged validation while the architecture becomes easier to reason about

## Related Context

See these archived notes for prior reasoning and earlier campaign history:

- `docs/developement/archived/2026-04-19/architecture-and-maintainability-improvement-plan.md`
- `docs/developement/archived/2026-04-19/package-and-gui-boundary-refactor-anchor-plan.md`
- `docs/developement/archived/2026-04-19/refactor-campaign-progress.md`

If this roadmap and the archived notes diverge, prefer this file for upcoming delegation rounds.
