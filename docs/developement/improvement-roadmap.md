# Improvement Roadmap

## Purpose

This is the active coordination document for the next maintainability and architecture pass.

The goal is to turn the current strong baseline into three delegation-ready chunks that can be assigned independently without losing control of scope, validation, or file ownership.

Archived assessments and earlier planning notes remain useful context, but active execution should start from this document and the chunk specs linked below.

## Current Baseline

As of `2026-04-21`, the repo is already in a strong state.

- local pytest is green: `2607 passed, 1 skipped`
- local `buildpython --run-steps=6,13,17,19` is green with `Health 100/100`
- production code is mostly under the repo's file-size thresholds
- the remaining headroom is structural: thinner coordinators, more explicit state, and cleaner typed boundaries

That means the next round should optimize for architecture and delegation quality, not for scanner-visible debt alone.

## Execution Model

The work is split into three chunks.

- one owner per chunk
- one hotspot-sized edit round at a time inside each chunk
- preserve public entrypoints and tested facades unless a chunk explicitly says otherwise
- parent-side merged validation remains authoritative even when an agent reports local green results

Recommended agent for all three chunks: `Guided`

The `Guided` agent fits this repo best because the remaining work is hotspot cleanup, protocol narrowing, and boundary extraction rather than broad repo-wide rewrites.

## Chunk Summary

### Chunk A

Spec: [chunk-a-tray-policy-seams.md](chunk-a-tray-policy-seams.md)

Focus:

- tray runtime state explicitness
- tray config-polling policy and classification seams
- lighting-controller boundary cleanup

Primary files:

- `src/tray/app/application.py`
- `src/tray/app/_application_bindings.py`
- `src/tray/protocols.py`
- `src/tray/pollers/config_polling_internal/core.py`
- `src/tray/controllers/lighting_controller.py`

### Chunk B

Spec: [chunk-b-gui-window-cleanup.md](chunk-b-gui-window-cleanup.md)

Focus:

- support-window workflow cleanup
- reactive and uniform window adapter cleanup
- per-key entry-module seam survey

Primary files:

- `src/gui/windows/_support/_support_window_jobs.py`
- `src/gui/windows/reactive_color.py`
- `src/gui/windows/uniform.py`
- selected `src/gui/perkey/` entry modules only when they show the same boundary problem

### Chunk C

Spec: [chunk-c-config-typed-boundaries.md](chunk-c-config-typed-boundaries.md)

Focus:

- typed config and runtime snapshot boundaries
- diagnostics and settings state shaping
- import/bootstrap normalization for dev and packaged runtime paths

Primary files:

- `src/core/config/config.py`
- `src/core/config/_lighting/*`
- `src/core/diagnostics/model.py`
- `src/gui/settings/settings_state.py`
- `src/core/runtime/imports.py`
- launch/bootstrap callers and test bootstrap helpers

## Recommended Order

1. Start Chunk A first. It touches the tray runtime and makes later boundaries easier to reason about.
2. Start Chunk B second. It can overlap with late Chunk A only if file ownership stays clean.
3. Start Chunk C last. It touches shared config and bootstrap contracts and should build on the clearer runtime seams from A and B.

If parallel execution is necessary, keep Chunk C separate until the tray and GUI seam ownership is stable.

## Shared Rules For All Chunks

### Scope control

- do not expand a chunk just because a neighboring file looks messy
- if a change crosses into another chunk's ownership, stop and re-scope before editing
- prefer extraction of small helpers, state models, or adapters over cosmetic file splitting

### Validation

- run the narrowest pytest target for the touched hotspot first
- run `.venv/bin/python -m buildpython --run-steps=13,17,19` when boundary-sensitive code changes
- run `.venv/bin/python -m buildpython --run-steps=6,13,17,19` when import topology, package shape, or scanner-visible structure changes

### Handoff format

Each chunk owner should hand back:

- files changed
- hotspot or boundary reduced
- tests and commands run
- residual risks or follow-up suggestions

## Success Criteria

This plan is succeeding when most of the following become true:

- tray-owned state is easier to see from initialization
- tray and power behavior have cleaner decision-versus-effect seams
- GUI window modules are thinner shells around workflow helpers or adapters
- config and diagnostics logic consume typed views instead of raw nested maps more often
- import/bootstrap behavior is easier for contributors to understand
- the repo stays green on merged validation while the architecture gets easier to extend

## Related Context

Archived reference material:

- [archived/2026-04-21/improvement-roadmap.md](archived/2026-04-21/improvement-roadmap.md)
- [archived/2026-04-19/architecture-and-maintainability-improvement-plan.md](archived/2026-04-19/architecture-and-maintainability-improvement-plan.md)
- [archived/2026-04-19/package-and-gui-boundary-refactor-anchor-plan.md](archived/2026-04-19/package-and-gui-boundary-refactor-anchor-plan.md)
- [archived/2026-04-19/refactor-campaign-progress.md](archived/2026-04-19/refactor-campaign-progress.md)