# Package And GUI Boundary Refactor Anchor Plan

## Purpose

This note anchors the current package-boundary and GUI-boundary refactor campaign. It complements the active roadmap in [architecture-and-maintainability-improvement-plan.md](architecture-and-maintainability-improvement-plan.md) and the earlier package-layout assessment in [archived/2026-04-17/package-structure-assessment.md](archived/2026-04-17/package-structure-assessment.md).

The goal for the current version is internal boundary cleanup inside the existing package model. It is not a repo-wide package rename campaign.

## Current Package Model Stays Stable

For now, the top-level application ownership model remains `src/core`, `src/gui`, and `src/tray` inside the importable `src` package.

- Do not treat this campaign as a move away from the current `src` import model.
- Do not expand this work into a repo-wide rename such as `src/keyrgb/...`.
- Keep existing public entrypoints, package roots, and tested facades stable unless a specific round explicitly says otherwise.

That keeps the current package contract intact while the internal seams are cleaned up.

## Internal Refactor Anchor

The anchor for this campaign is feature-first internal packaging with explicit `view`, `workflow`, and `adapter` seams.

| Seam | Responsibility |
|---|---|
| `view` | Tk widgets, layout, event binding, and display-only state |
| `workflow` | feature state, orchestration, persistence timing, and async sequencing |
| `adapter` | backend acquisition, target resolution, tray or app callbacks, and runtime-boundary I/O |

The important point is scope. This is an internal seam cleanup inside the existing package roots, not a repo-wide package rename.

- Prefer feature-first subpackages under the existing roots when a hotspot needs to split.
- Keep the top-level window or menu facade in place when it is already public or tested.
- Move routing, backend selection, and storage or callback boundaries out of Tk-heavy modules first.

## Why `gui/windows`, `gui/perkey`, And `tray/ui` Are First

These packages are the first campaign targets because the current reports show boundary leakage there already.

- `src/gui/windows` mixes view code with backend acquisition, target routing, and workflow orchestration. `uniform.py`, `reactive_color.py`, and the support-window helpers are the clearest examples.
- `src/gui/perkey` is already a feature-dense package root, and [../../buildlog/keyrgb/architecture-validation.md](../../buildlog/keyrgb/architecture-validation.md) currently flags `src/gui/perkey/hardware.py` for direct backend-selection coupling.
- `src/tray/ui` is where menu-building code still reaches into profile storage and private tray runtime hooks. The current first-wave warnings point directly at `_menu_sections_profile_power.py`, `menu_sections.py`, and `menu_status.py`.

This is the highest-return boundary work because it reduces coupling without changing the repo's top-level package model.

## Buildpython Safety Net And Queue Sources

Use `buildpython` as the campaign safety net.

- Step `13`: type check
- Step `17`: architecture validation
- Step `19`: exception transparency

Use the current reports under `buildlog/keyrgb/` as queue sources and backstops:

- [../../buildlog/keyrgb/architecture-validation.md](../../buildlog/keyrgb/architecture-validation.md)
- [../../buildlog/keyrgb/exception-transparency.md](../../buildlog/keyrgb/exception-transparency.md)
- [../../buildlog/keyrgb/file-size-analysis.md](../../buildlog/keyrgb/file-size-analysis.md)

`file-size-analysis.md` is a hotspot signal, not a command to split files mechanically. Use it to find pressure, then split by responsibility and boundary.

Parent-side merged validation will be rerun later and is authoritative.

## Delegation Rules For Future Rounds

- Delegate one hotspot per agent.
- Preserve tested and public facades unless the round explicitly allows a contract change.
- Make the smallest root-cause boundary move that actually reduces coupling.
- Treat parent-side merged validation as authoritative even when local checks are green.
- Tune architecture or debt scanners only when a specific finding is proven to be a false positive.
- Do not relax a scanner just to hide a real boundary problem.

## Wave-Based Sequencing For The Upcoming Version

### Wave 1: Clear The Current Boundary Warnings

Start with the current queue from [../../buildlog/keyrgb/architecture-validation.md](../../buildlog/keyrgb/architecture-validation.md).

- `src/gui/perkey/hardware.py`
- `src/gui/windows/uniform.py`
- `src/tray/ui/_menu_sections_profile_power.py`
- `src/tray/ui/menu_sections.py`
- `src/tray/ui/menu_status.py`

Goal: move backend selection, route resolution, storage access, and private runtime hooks behind explicit adapters or callbacks while leaving the current facades intact.

### Wave 2: Trim The First Delegation Hotspot

Take the first delegation candidate from [../../buildlog/keyrgb/file-size-analysis.md](../../buildlog/keyrgb/file-size-analysis.md).

- `src/gui/windows/_support_window_runtime_deps.py`

Goal: reduce import and dependency pressure by isolating runtime dependencies from Tk view code and support-window workflow helpers.

### Wave 3: Propagate Proven Seams Inside The Same Roots

After waves 1 and 2 land, extend the same seam pattern inside `src/gui/windows`, `src/gui/perkey`, and `src/tray/ui`.

- Prefer repeating the same `view` or `workflow` or `adapter` split pattern.
- Avoid creating new top-level package families for one-off extractions.
- Keep queue selection tied to the refreshed `buildlog/keyrgb/*.md` reports.

### Wave 4: Re-evaluate Packaging Cleanup Only If Still Needed

Once the internal seams are cleaner, revisit the packaging and bootstrap work described in [architecture-and-maintainability-improvement-plan.md](architecture-and-maintainability-improvement-plan.md).

- Re-evaluate package-surface cleanup inside the current `src` model.
- Re-evaluate whether a repo-wide package-layout migration is still worth the cost.

That last step is explicitly later. It is not the anchor for the current refactor campaign.