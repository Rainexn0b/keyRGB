# Module Size And Hotspots Assessment

This note documents one maintainability issue in KeyRGB: several production modules have grown large enough that review cost is rising, responsibilities are flattening together, or both.

The evidence here comes from three repo-local sources:

- A current working-tree line-count scan of production Python modules under `src` using `rg --files src -g '*.py' | xargs wc -l | sort -nr`
- The repo's own size-analysis report in [../../buildlog/keyrgb/file-size-analysis.md](../../buildlog/keyrgb/file-size-analysis.md)
- Direct inspection of the relevant modules, especially [../../src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py), [../../src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py), [../../src/gui/windows/uniform.py](../../src/gui/windows/uniform.py), [../../src/tray/ui/menu_sections.py](../../src/tray/ui/menu_sections.py), and [../../src/core/config/_lighting/_lighting_accessors.py](../../src/core/config/_lighting/_lighting_accessors.py)

This assessment intentionally focuses on production code under `src`. Several tests are larger than these files, but the maintainability issue documented here is production review cost and runtime-surface sprawl, not test-file length.

## Why File Size Matters Here

In KeyRGB, file size matters when it becomes a proxy for boundary collapse.

Large files are not automatically bad in this repo. Some modules legitimately need a lot of space because they encode a packet protocol, a storage normalization surface, or a read-only diagnostics collector. What matters more is whether the file stays inside one technical concern or starts mixing layers that change for different reasons.

That distinction matters more than usual in KeyRGB because many modules sit on runtime seams:

- Tk window code and event handlers
- backend capability detection and device acquisition
- config persistence and compatibility fallbacks
- tray callback wiring and state refresh
- filesystem or browser side effects
- best-effort exception boundaries required for non-fatal UX

When those concerns accumulate in one file, a simple feature change stops being local. Reviewers have to reason about UI state, config semantics, capability gating, and fallback behavior at the same time. That increases regression risk even when the code is individually reasonable.

KeyRGB already encodes this intuition in its own tooling. The file-size analysis step defines these thresholds in [../../buildpython/steps/file_size_analysis/constants.py](../../buildpython/steps/file_size_analysis/constants.py):

- `REFACTOR_LINES = 350`
- `CRITICAL_LINES = 400`
- `SEVERE_LINES = 500`
- `EXTREME_LINES = 600`

The point of this note is not to restate that line counts are bad. It is to identify where those thresholds line up with mixed responsibilities and therefore represent high-value refactor targets.

## Current Hotspot Inventory

The current working-tree scan of production modules under `src` ranks the largest files as follows:

| Lines | Repo Bucket | Path | Assessment |
|---:|---|---|---|
| 775 | EXTREME | `src/gui/windows/_support/_support_window_jobs.py` | Highest-value trim target; multiple job/control domains collapsed together |
| 506 | SEVERE now | `src/gui/windows/reactive_color.py` | Single-class GUI/controller file that now crosses the 500-line mark |
| 426 | CRITICAL | `src/gui/windows/uniform.py` | Large window class mixing routing, backend, device, config, and UI concerns |
| 415 | CRITICAL | `src/gui/windows/_support/_support_window_ui.py` | Large, but more layout-focused and less urgent than the jobs module |
| 383 | REFACTOR | `src/gui/calibrator/_app_logic.py` | Large GUI logic module, outside this note's detailed scope |
| 379 | REFACTOR | `src/gui/tcc/profiles.py` | Large GUI/power-profile surface |
| 379 | REFACTOR | `src/core/profile/_profile_storage_ops.py` | Large storage module, but more cohesive than the GUI hotspots |
| 379 | REFACTOR | `src/core/backends/ite8233/protocol.py` | Large protocol module; size is more acceptable because concern is narrow |
| 369 | REFACTOR | `src/tray/ui/menu_sections.py` | Cross-domain tray menu assembly hotspot |
| 366 | REFACTOR | `src/core/config/_lighting/_lighting_accessors.py` | Growing config-schema surface |
| 361 | REFACTOR | `src/tray/pollers/idle_power/_actions.py` | Large policy/action module |
| 358 | REFACTOR | `src/tray/pollers/config_polling_internal/core.py` | Large polling core |
| 358 | REFACTOR | `src/tray/controllers/software_target_controller.py` | Large controller module |
| 356 | REFACTOR | `src/core/effects/engine_support/start.py` | Large engine start/support module |
| 355 | REFACTOR | `src/tray/ui/menu_status.py` | Large tray status module |
| 353 | REFACTOR | `src/core/effects/reactive/input.py` | Large effect input module |
| 351 | REFACTOR | `src/core/diagnostics/_collectors_backends_sysfs.py` | Large collector module, but cohesive |

The existing size-analysis report in [../../buildlog/keyrgb/file-size-analysis.md](../../buildlog/keyrgb/file-size-analysis.md) is directionally consistent:

- 14 files are already in the refactor bucket or above
- 3 production files are in the critical bucket
- 1 production file is in the extreme bucket
- the report currently records [../../src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py) at 493 lines, while the working-tree scan now shows 506 lines, which means it has crossed from critical into severe since the report was generated

One additional structural hotspot is worth noting even though it is not yet a file-size hotspot: [../../src/tray/app/application.py](../../src/tray/app/application.py) is only 339 lines, but the size-analysis report marks it as the top delegation candidate with score 41. That is a separate smell: facade pressure rather than pure file length.

## Evidence By File

### 1. `src/gui/windows/_support/_support_window_jobs.py`

This is the clearest file-size debt in the repo.

Evidence:

- 775 lines, which is well into the repo's `EXTREME` bucket
- 21 top-level function definitions, plus additional nested callback helpers inside dialog/job functions
- inspected code spans at least four distinct responsibility groups:
  - generic dialog construction and wrap behavior: `_show_probe_message_dialog`, `_ask_probe_choice_dialog`, `_ask_probe_notes_dialog`, `_build_dialog_button_row`
  - backend speed-probe automation and tray-config snapshot/restore: `_probe_config_snapshot`, `_restore_probe_config`, `_auto_run_backend_speed_probe_via_tray_config`, `_complete_backend_speed_probe`
  - asynchronous support jobs: `run_debug`, `run_discovery`, `collect_missing_evidence`, `run_backend_speed_probe`
  - output/export actions: `save_support_bundle`, `open_issue_form`

The most important point is not that the file is long. It is that the file mixes reusable dialog primitives, workflow orchestration, persistence mutation, threaded job callbacks, filesystem output, and browser/clipboard fallback.

That means a reviewer touching the guided backend speed probe also has to reason about generic modal-dialog helpers and issue-bundle export behavior because they live in the same module. The support window has already been partially split into [../../src/gui/windows/support.py](../../src/gui/windows/support.py), [../../src/gui/windows/_support/_support_window_ui.py](../../src/gui/windows/_support/_support_window_ui.py), and this jobs file. The split reduced some pressure, but the jobs file is still acting as a catch-all for everything that is "not layout".

That is the strongest evidence of mixed-responsibility bloat in the current repo.

### 2. `src/gui/windows/reactive_color.py`

This file is now one of the highest-value GUI hotspots.

Evidence:

- 506 lines in the working tree, which crosses the repo's `SEVERE` threshold
- the size-analysis report still records it at 493 lines, showing that it is trending upward rather than shrinking
- 2 classes and about 20 methods concentrated into one window/controller object
- the module has a 26-line import block, which the repo also flags as a warning-level import hotspot

Direct inspection shows that the file does not only define a window. It also owns:

- backend capability probing to determine whether RGB control is available
- config instantiation and persistence decisions
- layout and wrap-sync behavior
- throttled drag-commit logic for color and brightness changes
- manual-color enablement logic
- reactive brightness and reactive trail control semantics
- process-signal and callback-exception behavior for clean shutdown

The file has already started to shed some logic into [../../src/gui/windows/_reactive_color_state.py](../../src/gui/windows/_reactive_color_state.py), which is a good sign. The remaining problem is that the window class is still the place where view wiring, controller decisions, and persistence timing rules all meet.

That is a classic review-cost multiplier: the file looks like "one feature" from a product perspective, but it is several technical concerns in one source module.

Tests exist in [../../tests/gui/windows/test_reactive_color_window_unit.py](../../tests/gui/windows/test_reactive_color_window_unit.py), which helps with safety, but the size trend still says the module should be trimmed before more feature work lands there.

### 3. `src/gui/windows/uniform.py`

This file is large for reasons similar to `reactive_color.py`, but with additional backend-routing responsibilities.

Evidence:

- 426 lines, which places it in the repo's `CRITICAL` bucket
- 1 class with about 21 methods
- direct tests exist in [../../tests/gui/windows/test_uniform_color_window_unit.py](../../tests/gui/windows/test_uniform_color_window_unit.py)

Direct inspection shows the file mixing five concerns:

- launch-time target resolution for keyboard versus secondary devices
- backend selection and capability probing
- best-effort device acquisition and device-busy fallback behavior
- Tk layout, geometry, wrapping, and status messaging
- config persistence plus direct hardware apply on release/apply

The secondary-device path makes the file especially important. It is not just a color wheel window anymore. It is also a routing layer that decides whether the action applies to the keyboard, a lightbar, or another device context, and whether to talk directly to hardware or defer to the tray-owned handle.

That makes the file larger in a more concerning way than a pure view module. The likely split is not "make the class smaller" in the abstract. The likely split is "stop making the Tk window own routing and device-apply policy".

### 4. `src/tray/ui/menu_sections.py`

This file is below the critical range, but it is still one of the most valuable refactor candidates because it centralizes unrelated tray-menu domains.

Evidence:

- 369 lines, which is in the repo's `REFACTOR` bucket
- 13 top-level functions
- direct tests exist in [../../tests/tray/ui/menu/test_menu_sections_unit.py](../../tests/tray/ui/menu/test_menu_sections_unit.py) and related tray-menu capability tests

Direct inspection shows one module building or mediating all of the following:

- non-keyboard device context menus
- secondary-device brightness checks and callbacks
- TCC profile menus
- system power mode menus
- per-key profile menus
- callback error logging and menu refresh glue

The issue is not raw size alone. The issue is that each submenu belongs to a different subdomain:

- secondary device routing
- system power state
- TCC integration
- per-key profile persistence

Those domains change for different reasons and are tested for different reasons, but they currently meet inside one menu-construction module. That is a good candidate for a split by submenu domain, with a thin top-level assembler kept in place if needed.

### 5. `src/core/config/_lighting/_lighting_accessors.py`

This file is large, but it is a more nuanced case than the GUI hotspots.

Evidence:

- 366 lines, which puts it in the repo's `REFACTOR` bucket
- 5 top-level helper functions and 1 accessor class
- about 40 methods inside the class
- 14 property/getter pairs and 14 setters
- direct behavior is exercised primarily through [../../tests/core/config/test_config_unit.py](../../tests/core/config/test_config_unit.py) and related config tests rather than a dedicated accessor-focused test module

Direct inspection shows a coherent theme: lighting-related config accessors. The file covers brightness, per-key brightness, reactive brightness, reactive trail, base color, secondary-device state, lightbar state, tray device context, reactive manual color, layout legend pack, and per-key colors.

That is more cohesive than the GUI/controller hotspots. The problem is different: this file has become a schema surface. Every new lighting-related setting is likely to land here as another getter/setter pair plus fallback and normalization logic.

So the concern is not immediate confusion. The concern is accretion pressure:

- compatibility fallback rules
- default-setting lookup behavior
- secondary-device compatibility keys
- layout-related normalization
- per-key serialization entry points

Because the file is still mostly config normalization and persistence, it is less urgent than `support_window_jobs.py`, `reactive_color.py`, or `uniform.py`. But it is clearly the place where lighting schema growth is accumulating.

## What Kinds Of Size Are Acceptable Versus Concerning In This Repo

The repo evidence suggests three broad categories.

### Acceptable Large: single-domain dense logic

Some files are large because the domain itself is dense, but the responsibility stays narrow.

Examples inspected for this note:

- [../../src/core/backends/ite8233/protocol.py](../../src/core/backends/ite8233/protocol.py) at 379 lines: this file is heavy on constants, product-ID variants, clamping helpers, and packet builders for one protocol family. It is large, but the mental model stays inside "ITE8233 lightbar protocol encoding".
- [../../src/core/diagnostics/_collectors_backends_sysfs.py](../../src/core/diagnostics/_collectors_backends_sysfs.py) at 351 lines: this is a read-only collector module. It is long, but the functions stay inside sysfs diagnostics gathering and error snapshotting.
- [../../src/core/profile/_profile_storage_ops.py](../../src/core/profile/_profile_storage_ops.py) at 379 lines: the inspected content stays inside profile-storage normalization and persistence helpers rather than crossing into UI or runtime device control.

Those files may still deserve cleanup, but their size is easier to justify because they are not flattening unrelated responsibilities together.

### Borderline But Manageable: cohesive layout or schema modules

Some large files are still mostly one concern, but they show growth pressure.

Examples:

- [../../src/gui/windows/_support/_support_window_ui.py](../../src/gui/windows/_support/_support_window_ui.py): large, but mostly concerned with styles, wrap syncing, action-row construction, and section layout. That is much more coherent than the companion jobs module.
- [../../src/core/config/_lighting/_lighting_accessors.py](../../src/core/config/_lighting/_lighting_accessors.py): cohesive as a lighting-config accessor surface, but vulnerable to endless property accretion.

These are not the first files to split if effort is limited, but they should not keep growing unchecked.

### Concerning Large: mixed runtime layers in one file

The high-value hotspots share a stronger smell than simple length:

- Tk UI and backend/device logic in one module
- config persistence and direct side effects in one module
- unrelated submenu domains assembled in one module
- reusable primitives and workflow orchestration living together

That pattern describes [../../src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py), [../../src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py), [../../src/gui/windows/uniform.py](../../src/gui/windows/uniform.py), and [../../src/tray/ui/menu_sections.py](../../src/tray/ui/menu_sections.py) much more than it describes the protocol and collector files.

## Refactor Candidates

The highest-value candidates are not just the biggest files. They are the files where size and boundary mixing overlap.

### Candidate 1: `src/gui/windows/_support/_support_window_jobs.py`

Suggested split direction:

- `support_window_dialogs`: generic modal-dialog helpers and wrap logic
- `support_window_probe_automation`: config snapshot/restore and tray-driven probe automation
- `support_window_tasks`: async debug/discovery/evidence jobs
- `support_window_export`: bundle save and issue-form/browser actions

Why first:

- already extreme
- already partly split from the main window class, so further extraction has a natural seam
- highest mixed-responsibility density in the repo sample inspected here

### Candidate 2: `src/gui/windows/reactive_color.py`

Suggested split direction:

- keep a thin `ReactiveColorGUI` view/orchestration class
- move more persistence and slider/drag timing policy into a controller/helper module next to `_reactive_color_state.py`
- isolate startup/runtime concerns such as backend capability probing and signal setup

Why second:

- current scan shows the file has crossed into severe territory
- extraction work has already started, so there is an obvious continuation path
- likely to keep growing if future reactive controls are added in place

### Candidate 3: `src/gui/windows/uniform.py`

Suggested split direction:

- extract target resolution and backend/device acquisition into a service/helper layer
- keep the Tk window focused on view state and user interaction
- isolate direct apply/deferred apply behavior into a small apply pipeline

Why third:

- same GUI-controller fusion pattern as `reactive_color.py`
- extra routing logic for secondary devices makes future changes expensive

### Candidate 4: `src/tray/ui/menu_sections.py`

Suggested split direction:

- secondary-device context menus
- power and TCC menus
- per-key profile menus
- shared menu logging helpers kept in a small common module if needed

Why fourth:

- still under 400 lines, but already clearly split across multiple domains
- direct tests exist, which lowers refactor risk
- aligns with the existing tray UI package structure rather than fighting it

### Candidate 5: `src/core/config/_lighting/_lighting_accessors.py`

Suggested split direction:

- base brightness and core color accessors
- reactive accessors
- secondary-device and lightbar accessors
- layout/per-key accessors

Why fifth:

- the file is still cohesive enough that an early split is optional
- the risk is future accretion more than current confusion
- changes here affect persistence compatibility, so this should follow the higher-value GUI and tray splits

## Suggested Thresholds Or Review Heuristics

The repo's existing thresholds are a good baseline, but they work best when combined with responsibility checks.

Recommended interpretation for KeyRGB:

- Below 350 lines: usually acceptable unless the module mixes UI, hardware, config, and filesystem/browser side effects or is flagged as a strong delegation candidate.
- 350-399 lines (`REFACTOR`): acceptable only if the file still reads as one concern. Protocol encoders, collectors, and normalization modules can live here temporarily. Cross-domain GUI or tray files should usually start splitting here.
- 400-499 lines (`CRITICAL`): should trigger an explicit split plan for GUI/controller or menu-assembly modules. New features should avoid adding more unrelated responsibilities.
- 500-599 lines (`SEVERE`): no further feature growth without extracting at least one responsibility slice first.
- 600+ lines (`EXTREME`): active maintainability debt. Treat as a structural issue, not a cosmetic one.

Additional review heuristics that are more valuable than raw LOC in this repo:

- If one file contains Tk widgets, config writes, backend probing, and device-handle logic, it is already carrying too many reasons to change.
- If a tray UI module assembles menus for unrelated subsystems, split by submenu domain even if total lines are still in the refactor bucket.
- If a config module keeps growing through property-pair accretion, split by state domain before compatibility fallback logic becomes hard to review.
- If the file-size report flags a module as a delegation candidate, treat that as early-warning debt even when line count is still below 350.
- Large import blocks matter more when they correspond to facade behavior, not just legitimate dependency breadth.

## Recommended Sequencing

If this issue is worked down incrementally, the order should be based on maintainability return, not just on raw line count.

1. Split [../../src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py).
   This is the biggest file and the clearest mixed-responsibility hotspot. It also already sits behind an existing support-window split, so it has natural extraction seams.

2. Continue trimming [../../src/gui/windows/reactive_color.py](../../src/gui/windows/reactive_color.py).
   It has crossed into severe territory, and the file is already partway through an extraction pattern via `_reactive_color_state.py`.

3. Apply the same separation pattern to [../../src/gui/windows/uniform.py](../../src/gui/windows/uniform.py).
   The likely reuse is architectural, not literal: keep the window thin and move routing/apply policy outward.

4. Split [../../src/tray/ui/menu_sections.py](../../src/tray/ui/menu_sections.py) by submenu domain.
   This should be relatively safe because the behavior already has direct menu tests.

5. Stabilize and then segment [../../src/core/config/_lighting/_lighting_accessors.py](../../src/core/config/_lighting/_lighting_accessors.py).
   This should happen after the higher-pressure GUI/tray hotspots, because config accessors are more cohesive and more compatibility-sensitive.

6. Keep watching near-threshold structural hotspots such as [../../src/tray/app/application.py](../../src/tray/app/application.py).
   It is not yet a file-size hotspot, but the delegation score says it could become the next maintainability problem even without crossing 350 lines.

The highest-value conclusion is straightforward: KeyRGB's large-file problem is not primarily about long protocol or collector modules. The stronger debt signal is large GUI and tray modules that combine UI wiring, config policy, runtime fallback, and side effects in one place. Those are the files most worth trimming first.
