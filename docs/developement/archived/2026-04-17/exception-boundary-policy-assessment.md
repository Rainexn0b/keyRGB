# Exception Boundary Policy Assessment

## Why the policy exists

KeyRGB is not a pure library. It is a long-running Linux tray app that controls real hardware through sysfs, HID transports, subprocess tools, dbus or ACPI monitoring, Tk, pystray, notify-send, and background effect threads. At those seams, the user-facing requirement is usually "keep the tray alive and degrade gracefully" rather than "crash on the first recoverable runtime error". The current exception-boundary style exists because that product requirement is real.

The repo has already moved away from the worst form of broad handling. The current Step 19 build output reports zero active broad-except findings, and the debt-automation tests enforce that literal `except Exception` waivers require an explicit `@quality-exception exception-transparency` explanation. In practice, the codebase now relies more often on wide tuples of recoverable runtime exceptions than on raw `except Exception`.

That is an improvement, but it also creates a new maintainability question. The issue is no longer "broad catches exist". The issue is whether broad recoverable catches are staying at true runtime boundaries, or whether the same boundary style is spreading into logging, serialization, menu glue, and callback plumbing where narrower contracts would be easier to reason about.

## Where it is working well

At real runtime seams, the policy matches the product.

- `src/core/backends/registry.py` treats backend construction and probing as runtime plugin and hardware boundaries. One broken backend can be skipped while other candidates remain selectable.
- `src/tray/controllers/lighting_controller.py` treats effect startup as a recoverable device boundary. It classifies permission-denied and disconnect cases separately instead of collapsing them into a generic failure.
- `src/core/power/management/manager.py` keeps battery-saver, suspend, resume, and lid monitoring alive across sysfs, login1, ACPI, config, and controller failures.
- `src/tray/pollers/config_polling_internal/core.py` protects a long-running reconciliation loop that has to survive device apply failures and even tray UI refresh failures.
- `src/gui/perkey/hardware.py` disables optional per-key hardware features cleanly when backend selection, dimension discovery, or device open fails.
- `src/core/effects/software_targets.py` treats secondary render targets as partial-failure seams so a broken auxiliary device does not stop keyboard rendering.

The tests reinforce that this is not a blanket swallow-everything policy. In the backend registry, lighting controller, config polling, and power manager tests, recoverable runtime failures are contained while unexpected `AssertionError` failures are expected to propagate. That is an important repository contract: runtime seams may degrade, but obvious programming bugs should still surface.

## Where it is becoming costly

The policy is now broad in footprint, not just in local exception tuples.

- Current source counts show 102 `@quality-exception exception-transparency` annotations under `src`.
- Of those, 63 are in `src/tray`, 18 are in power-related code, 15 are in `src/core/effects`, 12 are in `src/core/backends`, and 3 are in `src/gui`.
- The tray subtree now carries most of the review burden for this policy even though not all of those catches are equally critical runtime seams.

The most important maintainability cost is drift between tooling scope and architecture scope. Step 19 now reports an annotation inventory by subtree alongside active broad-except findings, which closes the old blind spot where the build only showed literal broad-catch debt. That helps reviewers see where deliberate runtime seams concentrate. The remaining limitation is semantic rather than structural: the inventory still does not distinguish hardware and OS boundaries from lower-value diagnostic or callback guards.

There is also a categorization problem. Some catches are clearly justified because they sit at hardware, OS, or long-running thread boundaries. Others are protecting event logging, `repr`, throttle bookkeeping, menu-status inspection, or dynamic callback shape mismatches. Using the same exception-boundary vocabulary for both categories makes review harder because it blurs the difference between "the keyboard vanished" and "a diagnostic string conversion failed".

Finally, the local tuples repeat with only minor variation. `AttributeError`, `LookupError`, `OSError`, `RuntimeError`, `TypeError`, and `ValueError` reappear across tray, backend, power, GUI, and effects code. Each tuple is locally defensible, but repeated copies make it difficult to tell whether two catches represent the same policy or just the same house pattern copied into another module.

## Evidence from the codebase

- `src/core/backends/registry.py` uses `_BACKEND_RUNTIME_ERRORS` in both `iter_backends()` and `_probe_backend()`. Broken backend factories and probes are logged and skipped, allowing selection to continue. The paired tests in `tests/core/backends/general/test_backend_registry_unit.py` explicitly check both sides of the contract: `RuntimeError` is contained, while unexpected `AssertionError` still propagates.
- `src/tray/controllers/lighting_controller.py` wraps `start_current_effect()` in `_START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS`, then classifies device disconnects and permission failures before falling back to tray or module logging. `tests/tray/controllers/core/test_tray_lighting_controller_dispatch_unit.py` verifies recoverable logging, notification fallback, mark-device-unavailable fallback, and propagation of unexpected startup or logger bugs.
- `src/tray/pollers/config_polling_internal/core.py` catches recoverable config-apply failures, marks the device unavailable on disconnect, and isolates tray UI refresh from the rest of config application. The config-polling tests include both `test_apply_from_config_once_logs_recoverable_apply_error` and `test_apply_from_config_once_propagates_unexpected_apply_error`, which confirms that the code is intentionally distinguishing runtime degradation from unexpected defects.
- `src/core/power/management/manager.py` catches recoverable exceptions in the battery-saver loop, brightness application, monitor loop, policy evaluation, and controller invocation. `tests/core/power/manager/test_power_manager_brightness_unit.py` and `tests/core/power/runtime/test_power_manager_monitoring_unit.py` show the same pattern: runtime failures are logged, but unexpected `AssertionError` still escapes.
- `src/gui/perkey/hardware.py` performs module-level best-effort backend selection, falls back to reference matrix dimensions, and returns `None` when a device cannot be opened. This is a reasonable optional-capability boundary, but it is also a good example of how far the policy has spread beyond the main tray loops.
- `src/core/effects/software_targets.py` catches per-target render failures so a failing secondary device does not take down the main keyboard render path. This is one of the cleaner uses of the policy because the degraded behavior is obvious and local: keep primary rendering alive, log the auxiliary failure.
- `tests/buildpython/test_buildpython_debt_automation_unit.py` shows what Step 19 is actually enforcing. An explanatory `@quality-exception exception-transparency` comment suppresses findings for literal `except Exception`, and missing explanations do not. That is narrower than the way the annotation is now used in `src`, where it often documents large recoverable tuples rather than scanner-waived `Exception` handlers.
- `buildlog/keyrgb/build-summary.md` now pairs the active broad-except counts with an annotation inventory by subtree. That closes the largest visibility gap, but reviewers still need judgment about which annotations describe high-value runtime seams versus low-value diagnostic guards.
- The repository-memory note named `exception-transparency-scan-scope.md` was not present in the workspace during this assessment, so this document relies on source files, tests, and current build artifacts rather than an additional repo-memory policy note.

## Heuristics for acceptable broad catches

- The catch sits at a true runtime seam: hardware I/O, sysfs, HID or USB transport, subprocess probing, login1 or ACPI monitoring, desktop-notification integration, Tk or pystray callback invocation, or effect-thread fanout to secondary devices.
- The fallback is explicit and safe: skip a backend, return `None`, fall back to reference dimensions, mark a device unavailable, keep a thread alive, or keep rendering the primary keyboard while an auxiliary target fails.
- The code classifies important failure families when possible instead of flattening everything into one generic log line. In this repo, permission-denied and device-disconnected cases are especially worth preserving as separate paths.
- The catch is the outer boundary of a user-visible operation or long-running loop, not a repeated wrapper around each internal helper call.
- The degraded behavior is observable through traceback logging, throttled logging, user notification, or explicit state change. Silent suppression should be rare.
- There are tests that prove the intended split between recoverable runtime failure and unexpected defect. The recurring KeyRGB pattern is that `RuntimeError`-style failures are contained but `AssertionError`-style failures remain visible.

## Heuristics for catches that should be narrowed or removed

- The catch is protecting internal data shaping, string conversion, or diagnostic logging rather than a real OS, hardware, or desktop boundary.
- The fallback is effectively just `pass`, with no state repair, no user signal, and no useful diagnostic output.
- `AttributeError`, `TypeError`, or `ValueError` are included mainly because the surrounding interface is loosely typed. If a protocol or helper can make the contract explicit, that is usually preferable to repeatedly widening the catch.
- The same failure is already contained by an outer loop or callback boundary, and the inner catch does not add a distinct degraded outcome.
- The justification comment is generic enough that it could describe dozens of unrelated handlers. In this repo, the strongest comments explain the specific degraded behavior, not just that the code is "best-effort".
- The code now has a better domain exception available, such as `BackendError` or a targeted permission or disconnect classifier, but the higher layer is still catching a broad generic tuple out of habit.

## Recommendations for future review work

- Treat this as boundary taxonomy work, not broad-except cleanup for its own sake. The goal should be to keep broad recoverable catches at real runtime seams and shrink them everywhere else.
- Keep the Step 19 subtree inventory in place and consider extending it with semantic categories. The build now shows where annotated runtime seams cluster, but it still cannot separate hardware and OS boundaries from diagnostic-only guards.
- Review the tray subtree first. It holds most of the annotated boundaries and contains the highest mix of true runtime seams and lower-value diagnostic or callback guards.
- Separate boundaries into a few explicit categories during review: hardware or OS boundary, long-running loop boundary, user-injected callback boundary, optional GUI capability boundary, and diagnostic-only boundary. The diagnostic-only group should be the first candidate for tightening.
- Consolidate repeated fallback helpers for tray logging, notifications, UI refresh, and callback dispatch. Reusing a small number of well-tested wrappers would reduce comment duplication and make the policy easier to audit.
- Continue pushing transport-specific failures downward into domain exceptions near the backend layer. The more upper layers receive `BackendError`, permission-denied, or disconnect signals instead of generic runtime failures, the less they need large catch tuples.
- Keep expanding typed protocols and `safe_attrs` style helpers where they remove the need for `AttributeError` or `TypeError` recovery. Tightening interface shape is usually safer than deleting outer runtime boundaries.
- Preserve the existing tests that assert unexpected `AssertionError` propagation, and add more when narrowing boundaries. Those tests are the main protection against the policy turning into quiet bug suppression.

## Risks of changing this policy too aggressively

- The tray can become brittle if one transient backend, sysfs, or desktop integration failure starts killing the long-running process.
- Background monitoring can regress from "noisy but alive" to "thread died and stopped applying policy", which is worse for users and harder to notice.
- Auxiliary-device failures can start breaking primary keyboard rendering if effect fanout stops being tolerant of partial failure.
- Permission-denied and hot-unplug paths can become user-hostile if the code starts surfacing raw tracebacks instead of preserving the current classified degraded outcomes.
- Removing `AttributeError` or `TypeError` recovery before tightening protocols can turn flexible tray glue into crash paths.
- A cleanup aimed only at Step 19 metrics can miss the real product requirement. KeyRGB is expected to survive recoverable OS and hardware failures while continuing to manage keyboard state.

