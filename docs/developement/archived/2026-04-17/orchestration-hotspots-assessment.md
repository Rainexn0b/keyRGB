# Split Orchestration Hotspots / Reduce Central Coordinator Complexity

## Scope

This note documents one maintainability issue in KeyRGB: several high-level modules have become orchestration hotspots. They do not primarily contain backend algorithms or policy rules. Instead, they sequence many collaborators, own multiple runtime boundaries, and mutate broad shared state surfaces. That makes them expensive to change safely.

The assessment is grounded in the current implementations and representative tests for the following modules:

- [src/tray/app/application.py](../../src/tray/app/application.py)
- [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py)
- [src/core/power/management/manager.py](../../src/core/power/management/manager.py)
- [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)

Representative nearby tests reviewed for this note:

- [tests/tray/app/test_tray_application_unit.py](../../tests/tray/app/test_tray_application_unit.py)
- [tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py)
- [tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py)
- [tests/core/power/manager/test_power_manager_event_handlers_unit.py](../../tests/core/power/manager/test_power_manager_event_handlers_unit.py)
- [tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py](../../tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py)
- [tests/core/power/runtime/test_power_manager_monitoring_unit.py](../../tests/core/power/runtime/test_power_manager_monitoring_unit.py)
- [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py)

This is not an argument to simplify real domain behavior. Linux power monitoring, backend probing, degraded hardware handling, and support evidence capture are legitimate product concerns. The issue here is where that behavior is coordinated and how many unrelated responsibilities have accumulated in the same control modules.

## Why These Hotspots Matter

These modules sit on the paths most likely to change:

- tray startup and shutdown
- tray config application and effect transitions
- power-source, suspend, and lid handling
- support diagnostics and guided evidence capture

When a single module owns sequencing, fallback behavior, user feedback, logging, and direct collaborator calls all at once, small feature work tends to spread into branch-heavy edits. The result is not just larger files. The result is higher change cost:

- more mocks are needed to test one behavior in isolation
- more sequencing assumptions have to be preserved when making unrelated changes
- more runtime seams are crossed inside a single function or class method
- more user-visible regressions are possible from edits that were intended to be structural only

The test surface already reflects this. The representative test files reviewed here are large and branch-oriented because they are pinning coordinator behavior rather than narrow units:

- [tests/tray/app/test_tray_application_unit.py](../../tests/tray/app/test_tray_application_unit.py) is 626 lines.
- [tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py) is 409 lines.
- [tests/core/power/manager/test_power_manager_event_handlers_unit.py](../../tests/core/power/manager/test_power_manager_event_handlers_unit.py) is 398 lines.
- [tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py](../../tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py) is 220 lines.
- [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py) is 1027 lines.

That does not mean the tests are wrong. It means the production modules are central enough that wide tests are currently the safest way to hold behavior in place.

## Hotspot Inventory

| Module | Current shape | Mixed responsibilities | Evidence of change cost |
| --- | --- | --- | --- |
| [src/tray/app/application.py](../../src/tray/app/application.py) | 340 lines, 22 `_on_*` methods | tray composition root, notification fallback, permission messaging, event logging, icon/menu refresh, callback registry, shutdown sequencing | [tests/tray/app/test_tray_application_unit.py](../../tests/tray/app/test_tray_application_unit.py) covers init wiring, run loop, notifications, permission handling, power wrappers, and callback delegation |
| [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py) | 359 lines, 6 top-level defs | config signature building, change classification, forced-off handling, fast paths, effect dispatch, device-unavailable degradation, UI refresh, warning throttling | [tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py) and [tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py) pin many branch combinations |
| [src/core/power/management/manager.py](../../src/core/power/management/manager.py) | 339 lines, 21 methods | thread lifecycle, config gating, AC polling, brightness adaptation, login1/ACPI/sysfs source selection, policy evaluation, keyboard action dispatch | [tests/core/power/manager/test_power_manager_event_handlers_unit.py](../../tests/core/power/manager/test_power_manager_event_handlers_unit.py), [tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py](../../tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py), and [tests/core/power/runtime/test_power_manager_monitoring_unit.py](../../tests/core/power/runtime/test_power_manager_monitoring_unit.py) split the same coordinator across multiple large suites |
| [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py) | 776 lines, 21 top-level defs | Tk dialog layout helpers, background-job orchestration, diagnostics/discovery workflows, supplemental evidence merges, tray-config automation, bundle save, browser/clipboard fallback | [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py) has to fake an entire window surface to cover the job module safely |

## Evidence by Module

### [src/tray/app/application.py](../../src/tray/app/application.py)

Observed responsibilities:

- `KeyRGBTray.__init__` loads dependencies, config, backend selection, discovery snapshot, engine creation, permission callback installation, software target setup, power monitoring, polling startup, and effect autostart.
- `_notify` and `_notify_permission_issue` own user-facing notification fallbacks and permission-specific messaging.
- `_log_event` implements throttled event logging with its own internal state.
- `_update_icon`, `_update_menu`, `_refresh_ui`, `_start_current_effect`, `turn_off`, `restore`, and `apply_brightness_from_power_policy` are runtime adapters.
- The class also exposes 22 `_on_*` methods that mostly forward tray-menu actions into the callback layer.
- `run` creates the pystray icon, builds the menu, flushes queued notifications, and enters the tray loop.

Why this is an orchestration hotspot:

- The class is acting as both composition root and long-lived runtime service object.
- It owns state for power, UI, backend capability gating, notification queuing, and event throttling on the same object.
- The callback wrapper count is a strong signal that the tray object is also serving as an action registry rather than only as application state.
- Module-level aliases pull startup, backend selection, refresh, lifecycle, controller, and dependency-loading functions into one class vocabulary. That keeps call sites short, but it also makes the tray application the convergence point for many unrelated seams.

Representative test evidence:

- [tests/tray/app/test_tray_application_unit.py](../../tests/tray/app/test_tray_application_unit.py) verifies startup wiring, run-loop construction, notification queueing and fallback behavior, permission reporting, callback wrapper delegation, and shutdown behavior.
- The breadth of that test file shows that even simple structural edits to the tray app can disturb wiring, user messaging, or menu behavior at the same time.

What is justified domain complexity here:

- There must be a tray composition root somewhere.
- Capability-driven UI gating and permission surfacing are legitimate user-facing concerns.

What is not justified orchestration complexity:

- The same class does not need to be the notification adapter, throttled event logger, callback registry, and bootstrap sequence owner all at once.

### [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py)

Observed responsibilities:

- `compute_config_apply_state` converts config state into a normalized apply signature, including effect name normalization, reactive settings, per-key signatures, and software target selection.
- `maybe_apply_fast_path` decides whether a target-only change, reactive-only change, or software-effect brightness-only change can bypass a full effect restart.
- `apply_from_config_once` then sequences the whole apply flow: compute current state, normalize persisted effect names, sync software target policy, handle forced-off state, run fast paths, log the change, turn off on zero brightness, sync reactive fields, choose per-key vs uniform vs effect application, degrade cleanly on device disconnect, and refresh tray UI.
- The same function also throttles warnings and owns several runtime boundaries around config reads, engine/hardware writes, and UI refresh.

Why this is an orchestration hotspot:

- The core logic is not just applying config. It is classifying changes, selecting the execution path, handling degraded hardware behavior, and deciding how logging and UI refresh should happen.
- Even though helper functions already exist for `_apply_effect`, `_apply_perkey`, `_apply_uniform`, `_handle_forced_off`, `_sync_reactive`, and `_sync_software_target_policy`, the central sequencing logic is still concentrated in one place.
- That means the file has already started splitting leaf work out, but the change-cost driver remains: one coordinator still owns the main branch structure.

Representative test evidence:

- [tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py) covers unchanged state early return, signature failures, zero-brightness turn-off behavior, per-key fallbacks, uniform and effect dispatch, device-unavailable handling, fast-path fallback, and UI-refresh throttling.
- [tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_fastpath_unit.py) separately pins the fast-path matrix for reactive settings, brightness changes, and software target changes.
- That split test surface exists because one refactor-safe unit does not currently exist below the public polling entrypoints.

What is justified domain complexity here:

- Effect-specific behavior, forced-off rules, and degraded-hardware handling are real product behavior.
- Normalizing backend-specific effect names and preserving software effect targets are legitimate parts of the tray/runtime contract.

What is not justified orchestration complexity:

- A single apply coordinator should not need to both derive state differences and execute all side effects while also deciding throttling and recovery policy.

### [src/core/power/management/manager.py](../../src/core/power/management/manager.py)

Observed responsibilities:

- `start_monitoring` and `stop_monitoring` manage thread lifecycle.
- `_battery_saver_loop` polls AC state, rebuilds power-source inputs, evaluates policy, and applies controller actions.
- `_apply_brightness_policy` adapts a power-policy brightness decision into controller calls and config mirroring.
- `_monitor_loop` chooses login1 monitoring first, falls back to ACPI, and starts lid monitoring.
- `_handle_power_event`, `_evaluate_power_event_policy`, and `_invoke_keyboard_method` adapt policy outputs into keyboard controller actions.
- `_on_suspend`, `_on_resume`, `_on_lid_close`, and `_on_lid_open` are event-specific entrypoints layered on top.

Why this is an orchestration hotspot:

- This class mixes lifecycle, monitor-source selection, controller adaptation, config gating, and power-event policy dispatch.
- The number of runtime seams is high: sysfs reads, login1 monitoring, ACPI fallback, thread control, config reloads, and controller callbacks are all crossed from one class.
- The codebase has already extracted meaningful domain pieces into `PowerEventPolicy`, `PowerSourceLoopPolicy`, and manager helper functions. That is a good boundary. The remaining hotspot is the coordinator that still owns when and how those pieces are stitched together.

Representative test evidence:

- [tests/core/power/runtime/test_power_manager_monitoring_unit.py](../../tests/core/power/runtime/test_power_manager_monitoring_unit.py) covers daemon-thread startup and login1-to-ACPI fallback wiring.
- [tests/core/power/manager/test_power_manager_event_handlers_unit.py](../../tests/core/power/manager/test_power_manager_event_handlers_unit.py) covers enablement, action gating, policy evaluation, and error handling for suspend/lid events.
- [tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py](../../tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py) covers power-source polling, policy-action application, exception boundaries, and profile-specific override behavior.
- The need for separate suites for threads, event handlers, and battery saving is another sign that one coordinator is wearing several hats.

What is justified domain complexity here:

- Linux power monitoring genuinely requires multiple sources and best-effort fallbacks.
- Non-fatal runtime boundaries are appropriate in monitor threads.

What is not justified orchestration complexity:

- The same class does not need to own thread startup, power-source loop execution, event source selection, and controller adaptation as one undifferentiated responsibility.

### [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py)

Observed responsibilities:

- Dialog-specific helpers such as `_probe_dialog_dimensions`, `_bind_dialog_prompt_wrap`, `_show_probe_message_dialog`, `_ask_probe_choice_dialog`, and `_ask_probe_notes_dialog` manage Tk layout details.
- Config snapshot and restore helpers support temporary tray automation for the backend speed probe.
- `run_debug`, `run_discovery`, `collect_missing_evidence`, and `run_backend_speed_probe` orchestrate threaded work, prompt flows, widget state updates, and follow-up actions.
- `_complete_backend_speed_probe` merges user observations back into the support evidence bundle.
- `save_support_bundle` and `open_issue_form` add persistence and browser/clipboard fallbacks.

Why this is an orchestration hotspot:

- Presentation details, workflow state transitions, evidence-model mutation, and I/O side effects all live in one module.
- The functions mutate a broad duck-typed `window` surface directly: button enablement, text widgets, status labels, `_diagnostics_json`, `_discovery_json`, `_supplemental_evidence`, `_issue_report`, and follow-up prompt hooks.
- The backend speed probe flow is especially mixed. It includes dialog presentation, tray-process preconditions, config snapshot/restore, timed automation, user observation capture, and evidence merging in one module.
- This is the clearest case where the maintainability problem is not domain complexity. The support workflows are inherently multi-step, but the same file currently owns both the support-session state and the widget-level choreography.

Representative test evidence:

- [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py) builds a fake window surface and then exercises discovery, diagnostics, missing evidence capture, backend speed probing, saving, and browser fallback behavior.
- The test file is 1027 lines because the production job module works against many implicit `window` attributes instead of a smaller explicit session model.

What is justified domain complexity here:

- Guided support capture naturally involves user prompts, asynchronous work, and evidence aggregation.
- Preserving issue-report state across discovery and supplemental evidence collection is a valid product requirement.

What is not justified orchestration complexity:

- One module does not need to own dialog layout helpers, evidence workflow control, tray-config automation, and browser/file fallbacks as a single blended responsibility.

## Common Patterns Driving Complexity

Across the four hotspots, the same maintainability patterns recur.

- The coordinator both decides what should happen and performs the side effects directly.
- Runtime-boundary handling is interleaved with normal control flow instead of being isolated at adapter seams.
- Wide mutable objects are passed around implicitly. `KeyRGBTray` and the support `window` object both carry state for many unrelated concerns.
- Tests often need to mock the entire collaborator surface because the production code does not expose smaller contracts.
- Some extraction has already happened in the repo. Policy objects and helper modules exist, but the central branch logic remains concentrated in the top-level coordinator.
- A recurring contract is already present in tests: expected runtime failures should degrade gracefully, while unexpected programmer errors should still surface. Any structural refactor has to preserve that distinction.

This last point matters. These files are not just large. They also encode exception-boundary policy. Splitting them safely means moving those boundaries to better seams, not deleting them or broadening them further.

## Refactor Directions

The right direction is incremental separation by responsibility, not mechanical file splitting.

### 1. Keep the public facades, thin the internals

`KeyRGBTray`, `PowerManager`, and the support-window public methods are already entrypoints used across the app and tests. Preserve those facades first. Move work behind them into narrower services or workflow objects while keeping public behavior stable.

### 2. Separate classification from execution

The config-polling core is the clearest candidate.

- One layer should compute a transition or apply plan from old state plus new state.
- A second layer should execute that plan against the engine, config, and tray UI.

That reduces change cost because effect-selection rules and runtime side effects stop changing in the same function.

The same idea applies to power management.

- One component decides which power action should happen.
- Another component handles monitor-thread plumbing and controller invocation.

### 3. Turn implicit mutable state into explicit workflow state

The support UI would benefit most from this.

- Support-session data such as diagnostics JSON, discovery JSON, supplemental evidence, and issue-report state should be represented explicitly.
- Tk-facing job functions should update widgets from that session state rather than mutate many `window` attributes directly.
- Backend speed probe automation should become a dedicated workflow object with clear phases: snapshot, auto-run, observation capture, merge result.

This reduces coupling without changing the user-visible flow.

### 4. Isolate runtime adapters

Notification fallback, browser/clipboard fallback, pystray creation, power-monitor source selection, and controller adaptation are all legitimate adapter concerns. They should live near their runtime seam instead of inside broader coordinators.

Examples:

- tray notifications can move behind a dedicated notifier object
- event-log throttling can move behind a logger helper instead of living on the tray state object
- power monitor source selection can move behind a monitor runner or monitor strategy object
- support-window file and browser actions can move behind thin service functions that return typed results

### 5. Reduce wrapper fan-out where wrappers are only routing

The 22 `_on_*` tray callback wrappers are individually small, but they increase the apparent responsibility of the tray application object. If the menu layer can bind through a smaller action map or action registry object, the tray class can stop being the catch-all callback namespace.

This should be a late cleanup, not the first move.

### 6. Prefer structural extraction over line-count extraction

The goal is not to create more files that still share the same mutable god object. The goal is to reduce the number of reasons one module changes.

Signs of a good extraction:

- a new unit has one kind of state to manage
- exception handling aligns with a real runtime seam
- tests for one behavior no longer need to fake unrelated collaborators
- existing facade methods become thinner and more obvious

## Recommended Order of Attack

1. Start with [src/gui/windows/_support/_support_window_jobs.py](../../src/gui/windows/_support/_support_window_jobs.py).
   It is the largest hotspot, it is mostly UI/workflow orchestration rather than hardware control, and it offers the clearest opportunity to introduce explicit session state without destabilizing backend behavior.

2. Thin [src/tray/app/application.py](../../src/tray/app/application.py) next.
   Startup/bootstrap, notification delivery, and event logging can move behind smaller services while preserving `KeyRGBTray` as the stable tray facade.

3. Split [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py) into change classification and execution phases.
   This area has strong characterization tests already, and it is a good place to reduce central branch density once the lower-risk UI/tray extractions have established a pattern.

4. Refactor internals of [src/core/power/management/manager.py](../../src/core/power/management/manager.py) last.
   It has the highest concentration of thread and external-runtime behavior. The public `PowerManager` facade should likely remain, while monitoring, event handling, and power-source loop execution are split behind it.

This order favors early maintainability wins on lower-risk coordination code before touching the most runtime-sensitive hardware and monitoring path.

## Validation Concerns During Refactor

Several constraints should govern any future refactor of these hotspots.

- Preserve sequencing contracts. Startup order, poller startup, power-monitor start/stop, UI refresh timing, and backend speed-probe flow ordering are user-visible even when no explicit UI text changes.
- Preserve the existing expected-vs-unexpected exception contract. Many tests intentionally allow recoverable runtime errors while still surfacing `AssertionError` or other unexpected failures.
- Keep hardware and policy behavior stable while extracting structure. Do not combine coordinator refactors with backend behavior changes.
- Preserve degradation semantics such as permission notifications, device-unavailable marking, login1-to-ACPI fallback, and browser-to-clipboard fallback.
- Use the current large tests as characterization tests before reducing them. In particular, keep [tests/tray/app/test_tray_application_unit.py](../../tests/tray/app/test_tray_application_unit.py), [tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py](../../tests/tray/pollers/config/core/test_tray_config_polling_apply_misc_unit.py), [tests/core/power/manager/test_power_manager_event_handlers_unit.py](../../tests/core/power/manager/test_power_manager_event_handlers_unit.py), [tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py](../../tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py), [tests/core/power/runtime/test_power_manager_monitoring_unit.py](../../tests/core/power/runtime/test_power_manager_monitoring_unit.py), and [tests/gui/windows/test_support_window_unit.py](../../tests/gui/windows/test_support_window_unit.py) green while extracting smaller seams.
- Add narrower tests at the new seam, not only after the old coordinator has been dismantled. Otherwise the refactor can create a coverage gap while still passing broad wrapper tests.
- When touching exception-heavy areas such as [src/tray/pollers/config_polling_internal/core.py](../../src/tray/pollers/config_polling_internal/core.py) and [src/core/power/management/manager.py](../../src/core/power/management/manager.py), keep the repo's exception-transparency constraints in mind and run the corresponding quality checks, including `python -m buildpython --run-steps=19`.

The main point is simple: these modules should not be split just because they are long. They should be split because they currently centralize too many control decisions, too many runtime seams, and too many reasons to change. The refactor target is lower coordination density, not fewer lines by itself.
