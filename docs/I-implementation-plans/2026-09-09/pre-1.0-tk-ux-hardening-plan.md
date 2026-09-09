# Pre-1.0 Tk UX hardening plan and tracker

**Created:** 2026-09-09
**Target:** pre-1.0 UX hardening; exact release assignment TBD
**Baseline:** `481ac142` (`main`)
**Lane:** `I-implementation-plans`
**Status:** active
**Source:** the user-approved nine-item UX backlog mapped below, following the
2026-09-09 repository UX review and decision to retain Tkinter

## Purpose

Turn the current UX review into a bounded implementation campaign that improves
the existing Tkinter application without a toolkit migration. The campaign
focuses first on settings information architecture, then removes fragile custom
widget behavior, establishes a small visual and keyboard-accessibility system,
adds stable window lifecycle behavior, and only then revisits the per-key
editor's workflow in a dedicated UX discussion.

The current GUI is functionally strong but visually and behaviorally dense:

- Settings places seven panels in three always-visible columns.
- Basic controls and technical fallback/timing controls have similar visual
  weight.
- Six per-key selectors use a custom `Toplevel`/`Listbox` dropdown that relies on
  `overrideredirect`, a grab, and forced focus.
- Fonts, spacing, focus behavior, and disabled colors are locally specified and
  inconsistent.
- Main windows center themselves on every launch and do not restore user size.
- Standalone GUI subprocesses have no per-window duplicate-instance guard.
- Keyboard shortcuts and focus contracts are incomplete outside the calibrator.
- The per-key editor exposes editing, profiles, keyboard setup, calibration, and
  overlay alignment together; that redesign is intentionally deferred until the
  lower-risk shell improvements have landed and a dedicated UX direction is
  approved.

## Product decision and non-goals

The product decision for this campaign is to **retain Tkinter**. A Qt6, GTK, web,
or other toolkit migration is out of scope. This campaign must not add a second
GUI toolkit or a new required runtime dependency.

Also out of scope unless an individual item is explicitly expanded:

- backend selection, backend capabilities, USB IDs, or hardware protocol work;
- tray menu information-architecture changes;
- config/profile format changes unrelated to bounded UI-only state;
- replacement of `pystray` or consolidation of all windows into one process;
- visual changes to generated keyboard-layout data or calibration mappings;
- a per-key editor workflow redesign before UX-03/UX-04 receive dedicated UX
  approval.

## Guardrails

1. Preserve every public command in `pyproject.toml`, including
   `keyrgb-perkey`, `keyrgb-uniform`, `keyrgb-reactive-color`,
   `keyrgb-calibrate`, and `keyrgb-settings`.
2. Preserve settings' current immediate-save behavior, `Config.batch_update()`
   transaction, time normalization, power-mode value mapping, autostart
   side-effect ordering, and failure rollback unless a separately approved item
   changes that contract.
3. Keep support evidence collection in Support Tools. Settings may link to it
   but must not absorb diagnostics workflows.
4. Keep GUI hardware and OS work behind the existing `tk_async` boundary.
5. Keep `keyrgb/core/**`, tray controllers, and tray pollers free of Tk-specific
   view behavior.
6. Do not reuse the tray/hardware `keyrgb.lock` for GUI duplicate prevention.
7. UI geometry state must not churn the main `config.json` watched by tray
   config polling.
8. Preserve dirty-close confirmation in the per-key editor and calibrator save
   semantics.
9. Add or update focused tests in the same pass as each behavior change. Do not
   weaken architecture, coverage, exception-transparency, or hardware-access
   gates.
10. Do not introduce silent broad exception catches. Any best-effort desktop or
    window-manager boundary must use a narrow exception set and run BuildPython
    Step 19.
11. Validate visual behavior on Linux. KDE Plasma Wayland is the primary manual
    target; also check Plasma X11 where available. Do not claim desktop-session
    validation that was not performed.
12. Work one inventory item at a time and append exact files, commands, and
    results to this document's progress log.

## Conventions

- **Priority:** `P0` blocks acceptable pre-1.0 UX; `P1` high-value hardening;
  `P2` polish or a larger redesign requiring evidence.
- **Effort:** `S`, `M`, or `L` relative to this repository.
- **Status:**
  - `accepted` — approved and waiting for implementation;
  - `active` — the one item currently being implemented;
  - `monitoring` — code is complete but desktop/manual evidence is pending;
  - `done` — implementation and required evidence are complete;
  - `deferred` — intentionally held for the named UX decision or predecessor;
  - `blocked` — cannot proceed until a named dependency is available.

## Requested-outcome traceability

This table is the source-of-truth mapping from the approved backlog to tracker
items. UX-00 is preparatory evidence only and does not add a tenth product
outcome.

| Requested outcome | Tracker item | Initial disposition |
|---|---|---|
| 1. Reorganize Settings into categories or tabs | UX-01 | accepted |
| 2. Separate basic and advanced settings | UX-02 | accepted |
| 3. Simplify the per-key editor's default view | UX-03 | deferred until last, pending dedicated UX discussion |
| 4. Make keyboard setup/calibration a guided workflow | UX-04 | deferred until last, pending dedicated UX discussion |
| 5. Improve spacing, fonts, focus states, and disabled contrast | UX-05 | accepted |
| 6. Persist window geometry | UX-06 | accepted |
| 7. Replace custom dropdown behavior with standard controls | UX-07 | accepted |
| 8. Add accelerators and keyboard interaction | UX-08 | accepted |
| 9. Prevent duplicate instances of the same window | UX-09 | accepted |

## Inventory

| ID | Work item | Priority | Effort | Status | Requires |
|---|---|:---:|:---:|---|---|
| UX-00 | Record the automated/manual UX baseline | P1 | S | done | none |
| UX-01 | Reorganize Settings into clear categories/tabs | P0 | M | done | UX-00 |
| UX-02 | Separate basic and advanced settings | P0 | M | done | UX-01 |
| UX-03 | Simplify the per-key editor's default view | P2 | L | monitoring | UX-01, UX-02, UX-05–UX-09, and dedicated UX discussion |
| UX-04 | Turn keyboard setup and calibration into a guided workflow | P2 | L | deferred | UX-03 direction and dedicated UX discussion |
| UX-05 | Establish consistent spacing, typography, focus, and disabled contrast | P1 | M | done | UX-07 |
| UX-06 | Persist and safely restore main-window geometry | P1 | M | done | UX-09 |
| UX-07 | Replace custom dropdowns with standard Tk controls | P1 | M | done | UX-00 |
| UX-08 | Add accelerators and keyboard-access contracts | P1 | M | done | UX-05 and UX-07 |
| UX-09 | Prevent duplicate instances of the same GUI | P1 | M | done | UX-00 |

## UX-00 — Baseline characterization and review matrix

Before UX-01 or UX-07 changes production behavior, record a reproducible
baseline in this document's progress log. UX-00 moves to `done` only when all
available automated commands and the actual manual environment/results are
recorded, or when the owner explicitly accepts the already-traversed baseline
and that decision is logged. Existing unit tests are extensive but mostly use
widget fakes; they do not replace a desktop walkthrough.

### Automated baseline

Run and record:

```bash
.venv/bin/python -m pytest tests/gui/settings tests/gui/theme_entrypoints -q -o addopts=
.venv/bin/python -m pytest tests/gui/perkey/layout tests/gui/perkey/editor/ui -q -o addopts=
.venv/bin/python -m pytest tests/gui/windows tests/gui/rendering_utils -q -o addopts=
.venv/bin/python -m pytest tests/tray/ui/test_gui_launch_unit.py tests/core/runtime/test_imports_unit.py -q -o addopts=
```

### Manual baseline

Capture screenshots and observations for Settings, Uniform Color, Reactive
Color, Power Mode, Support Tools, Per-key Editor, and Keymap Calibrator under:

- KDE Plasma Wayland, dark theme;
- KDE Plasma Wayland, light theme;
- `KEYRGB_TK_SCALING=1.5`;
- a narrow/small screen or constrained window;
- keyboard-only traversal for every non-canvas control.

For each window record initial size, minimum useful size, focus target, close
behavior, duplicate-launch behavior, and any clipped or unreadable control. Use
`assets/screenshots/` as the historical visual reference, but do not overwrite
screenshots until an item is accepted visually.

## UX-01 — Reorganize Settings into categories/tabs

### Evidence

`keyrgb/gui/settings/window.py::_init_layout()` creates three equal columns and
`_init_panels()` places all seven settings panels in those columns. The resulting
window has a 1000×620 minimum and 1320×820 default, yet still presents unrelated
power, scheduler, version, autostart, and backend policy controls with equal
prominence.

### Implementation contract

- Replace the three-column dashboard with category navigation based on standard
  `ttk` widgets; prefer `ttk.Notebook` unless a small prototype demonstrates a
  clearer and equally keyboard-accessible standard-Tk alternative.
- Initial category model:
  - **Lighting & Power:** power management and plugged-in/battery behavior;
  - **Automation:** screen idle/blanking and time-of-day scheduling;
  - **App:** launch and OS autostart behavior;
  - **Advanced:** technical or experimental controls assigned by UX-02;
  - **About & Support:** version information and the existing Support Tools
    entrypoint.
- Keep the save status, actionable hardware hint, and Close action visible
  independently of the selected category.
- Default to the most generally useful category, not Advanced or About.
- Instantiate shared state and each asynchronous probe exactly once. Switching
  categories must not recreate panels, duplicate version checks, or repeat
  hardware probes.
- Preserve all `tk.Variable` values and `_on_toggle()` semantics while moving
  only presentation ownership.
- Each category must remain usable on a 1366×768 work area with scrolling where
  needed.
- UX-01 may add only the minimal Notebook/page styles needed for usable category
  navigation. UX-05 owns the later semantic typography, spacing, focus, and
  contrast system; this deliberate second pass must not reshape Settings again.

### Planned files

- `keyrgb/gui/settings/window.py`
- `keyrgb/gui/settings/_settings_window_constants.py`
- new `keyrgb/gui/settings/navigation.py` for category metadata and page
  construction
- `keyrgb/gui/settings/scrollable_area.py` only if per-page scrolling requires a
  reusable extension
- `keyrgb/gui/settings/panels/_wrap_sync.py` only if page ownership changes its
  parent contract
- `tests/gui/settings/window/test_settings_window_unit.py`
- `tests/gui/settings/window/_settings_window_fakes.py`
- new `tests/gui/settings/test_navigation_unit.py`

### Acceptance criteria

- Tests pin category order, default category, one-time panel/probe construction,
  footer persistence, and category switching.
- Existing settings load/save, autostart rollback, time normalization, enabled
  states, and power-mode mapping tests remain green without semantic changes.
- `ScrollableArea.bind_mousewheel()` routing and the
  `panels._wrap_sync.bind_wraplength_sync()` parent contract work within the
  selected page, with focused coverage in the existing scrollable-area,
  wrap-sync, and settings-window tests.
- Version checking and the footer `tk_async` hardware probe are constructed once
  and are not repeated by `<<NotebookTabChanged>>`.
- No panel content is lost; any control moved to Advanced is tracked in UX-02.
- Manual dark/light screenshots show a clear hierarchy without requiring the
  former 1320-pixel-wide three-column layout.

## UX-02 — Separate basic and advanced settings

### Evidence

The current Settings window gives ordinary power toggles the same prominence as
controller sleep policy, debounce timing, fade tuning, and experimental backend
selection. This increases cognitive load and makes the safe/common path harder
to scan.

### Implementation contract

- Complete a control-by-control classification before moving widgets:
  - **basic:** common outcomes and high-frequency choices;
  - **advanced:** controller-specific policy, timing/debounce tuning,
    experimental backend policy, and other controls requiring technical
    context;
  - **support:** evidence collection or troubleshooting links, which remain in
    Support Tools.
- Record that classification as a table in this UX-02 section or its progress-log
  entry before the first widget moves; each current control must have exactly one
  destination.
- Keep advanced values loaded, enabled/disabled, and saved even while their page
  is not selected.
- Do not silently reset hidden values and do not split the existing full
  `SettingsValues` save transaction into per-page writes.
- Use plain language for advanced labels and retain enough explanation to make
  consequences clear.
- Prefer an explicit Advanced category over a custom animated disclosure widget.
  Add a reusable disclosure widget only if a prototype and keyboard test show it
  is necessary.

### Approved control classification

| Destination | Controls |
|---|---|
| Lighting & Power (basic) | Power-management enable; suspend/resume and lid-close/open behavior; AC/battery lighting enable, brightness, and power mode |
| Automation (basic) | Idle source; idle/blanking sync enable; turn-off versus temporary-brightness outcome; temporary brightness; scheduler enable; day/night start times and brightness values |
| App (basic) | Start lighting on launch; start KeyRGB on login |
| Advanced | Controller firmware sleep behavior; idle turn-off and restore delays; idle fade duration; experimental backend policy |
| About & Support | Installed/latest version, repository link, and Support Tools entrypoint |

The Advanced split is presentational only. All variables remain loaded before
panel construction and continue to participate in the existing full
`SettingsValues` immediate-save transaction even when Advanced is never opened.

### Planned files

- `keyrgb/gui/settings/window.py`
- `keyrgb/gui/settings/panels/dim_sync_panel.py`
- `keyrgb/gui/settings/panels/power_source_panel.py` if power-mode placement is
  reclassified
- `keyrgb/gui/settings/panels/experimental_backends_panel.py`
- `keyrgb/gui/settings/navigation.py` for the approved control-to-category map
- corresponding `tests/gui/settings/panels/` and window tests

### Acceptance criteria

- The default page exposes common lighting, brightness, and power behavior
  without exposing experimental backend policy.
- Advanced values round-trip unchanged when the user never opens Advanced.
- A window-level test constructs Settings, never selects Advanced, triggers a
  basic save, and proves every pre-existing advanced value is unchanged.
- Parent/child disabled-state behavior still follows power-management and
  feature-enable toggles across page boundaries.
- Save success/failure remains visible on every page.
- A manual first-run walkthrough can identify where to control AC/battery
  brightness and where to find technical timing/backend controls without
  searching the entire window.

## UX-07 — Replace custom dropdowns with standard Tk controls

### Evidence

`keyrgb/gui/widgets/dropdown.py::UpwardListboxDropdown` creates an
`overrideredirect` `Toplevel`, forces focus, takes a grab, manually computes
screen position, and supplies only partial keyboard navigation. Six readonly
comboboxes in the per-key editor attach this overlay and intercept mouse click
and Down-arrow behavior.

### Implementation contract

- Use standard readonly `ttk.Combobox` popup behavior for layout, legend pack,
  backdrop, profile, AC profile, and battery profile selectors.
- Preserve existing `<<ComboboxSelected>>` callbacks and persisted values.
- Load one shared profile-name snapshot when the editor opens and refresh all
  three profile-related selectors from one new snapshot after profile create,
  rename/save, or delete operations. Popup opening and AC/battery selection must
  not scan profile storage or perform other avoidable I/O on Tk's event thread.
- Restore native Up/Down/Home/End/Escape and focus behavior; do not replace the
  overlay with another custom popup.
- Remove `UpwardListboxDropdown`, its imports, and its tests only after all six
  call sites have migrated.
- Remove the divergent per-key disabled-color override so the existing shared
  `TCombobox` map applies. UX-05, not UX-07, owns broader shared-theme redesign.

### Planned files

- `keyrgb/gui/perkey/ui/layout_setup.py`
- `keyrgb/gui/perkey/editor_support/ui.py`
- `keyrgb/gui/perkey/editor_support/bootstrap.py`
- `keyrgb/gui/widgets/dropdown.py` (delete after last caller)
- `tests/gui/perkey/layout/test_layout_setup_unit.py`
- `tests/gui/perkey/editor/ui/`
- `tests/gui/perkey/layout/test_dropdown_unit.py` (delete)
- `tests/gui/perkey/layout/test_dropdown_interaction_unit.py` (delete)
- `tests/gui/perkey/layout/_dropdown_fakes.py` (delete)

### Acceptance criteria

- No production import or reference to `UpwardListboxDropdown` remains.
- All six selectors open and select correctly with mouse and keyboard on Plasma
  Wayland and the available X11 session.
- Dynamic profile lists update without reopening the editor.
- Selection, profile policy persistence, and layout refresh tests remain green.
- No global grab, forced focus, or borderless popup remains in this path.

## UX-05 — Consistent spacing, typography, focus, and disabled contrast

### Evidence

GUI modules hard-code `("Sans", 14, "bold")`, 11-point, 9-point, and 8-point
fonts and use several unrelated outer paddings. Shared theme maps only some
disabled states, while per-key bootstrap maps disabled combobox text to the
normal foreground. Focus indication and initial focus are not a window-level
contract.

### Implementation contract

- Define a small shared Tk visual system using named ttk styles and Tk named
  fonts rather than a replacement theme or third-party styling dependency.
- Establish semantic roles for window title, section title, body, caption,
  status, primary action, and destructive action.
- Establish spacing constants for outer window padding, section gaps, control
  gaps, and compact inline groups. Migrate one window at a time; do not perform
  an unreviewable repository-wide search/replace.
- Respect Tk/system font scaling and `KEYRGB_TK_SCALING`; avoid absolute font
  choices where named-font derivation is sufficient.
- Centralize dark/light disabled foreground and field-state maps for buttons,
  checks, radios, entries, comboboxes, spinboxes, scales, and scrollbars where
  ttk supports them.
- Add a visible keyboard focus treatment and an intentional initial focus target
  to each main window without forcing focus across applications.
- Preserve Support Tools' semantic status palette while removing duplicated
  generic widget-state styling.
- Add a pure relative-luminance/contrast helper used by unit tests. Normal text
  must meet 4.5:1 against its background, large title text 3:1, and disabled text
  a project usability target of 3:1. Disabled controls are not represented as a
  WCAG conformance claim.

### Planned files

- `keyrgb/gui/theme/ttk.py`
- `keyrgb/gui/theme/metrics.py` for semantic spacing/font roles, or an equivalently
  named module chosen and recorded before implementation
- `keyrgb/gui/settings/window.py` and panels
- `keyrgb/gui/windows/` UI builders
- `keyrgb/gui/perkey/editor_support/bootstrap.py` and UI builders
- `keyrgb/gui/calibrator/_app_bootstrap.py`
- `tests/gui/theme_entrypoints/test_theme_ttk_unit.py`
- focused window/panel tests affected in each migration pass

### Acceptance criteria

- Shared semantic styles replace local title/body/caption tuples in every main
  window covered by the campaign.
- Unit-tested color pairs meet the explicit contrast targets above in both
  supported theme modes.
- Keyboard focus is visible on every interactive standard control.
- Scaling does not clip labels or buttons at `KEYRGB_TK_SCALING=1.5`.
- Per-window screenshot review confirms consistent spacing without shrinking
  hit targets or increasing information density.

## UX-09 — Prevent duplicate GUI instances

### Evidence

`keyrgb/tray/ui/gui_launch.py` delegates GUI modules to
`keyrgb/core/runtime/imports.py::launch_module_subprocess()`, which returns a
fire-and-forget `Popen`. Only the tray/hardware owner has a singleton lock.
Repeated tray clicks can create duplicate Settings, Uniform, Reactive, Power
Mode, Support, or Per-key processes, with possible competing state writes.

### Implementation contract

- Add a Linux-first per-GUI advisory lock helper with distinct lock names for
  settings, reactive color, power mode, support, per-key editor, and calibrator.
- Scope Uniform Color locks by target context/device route so valid simultaneous
  keyboard and secondary-device editors are not blocked.
- Use separate `keyrgb-gui-<name>.lock` files under the same XDG/config-root
  resolution policy; never reuse `keyrgb.lock`.
- Acquire the lock before constructing `tk.Tk()` or acquiring hardware. Hold its
  file descriptor for the process lifetime and release it on normal exit. Rely
  on advisory-lock lifetime after a crash rather than treating a leftover path
  as an active process.
- A second launch exits successfully with a concise diagnostic instead of
  opening another window. Cross-process focus/raise is optional and must not be
  simulated with unsafe signals or broad IPC in this item.
- The standalone command path is authoritative. Tray-side process-handle caching
  may avoid needless second spawns but cannot be the only guard.
- Implement the Tk-free lock owner as `keyrgb/gui/single_instance.py`. Reuse
  `keyrgb.core.config.paths.config_dir()` for XDG/`KEYRGB_CONFIG_DIR` resolution
  and mirror the non-blocking `fcntl.flock(LOCK_EX | LOCK_NB)` lifetime contract
  in `keyrgb/core/runtime/hardware_ownership.py`; do not move GUI lifecycle into
  `keyrgb/core/`.

### Planned files

- `keyrgb/gui/single_instance.py`
- `keyrgb/tray/ui/gui_launch.py`
- GUI `main()`/launch modules for settings, windows, per-key, and calibrator
- `tests/tray/ui/test_gui_launch_unit.py`
- new `tests/gui/test_single_instance_unit.py`
- `tests/gui/theme_entrypoints/test_gui_entrypoints_unit.py`

### Acceptance criteria

- Concurrent launches produce one live process per lock identity.
- A process crash does not permanently block the next launch.
- Uniform keyboard and secondary-device contexts use distinct identities where
  simultaneous operation is valid.
- Tests use `KEYRGB_CONFIG_DIR` isolation and prove the hardware/tray lock path is
  untouched.
- Existing entrypoint and launch environment behavior remains unchanged.
- An isolated subprocess/descriptor-lifetime test proves lock exclusion and
  recovery after the holder terminates. Tests must inspect the advisory lock,
  not treat lock-file or PID-text existence as ownership.

## UX-06 — Persist and safely restore main-window geometry

### Evidence

Settings, Uniform, Reactive, Power Mode, Support, Per-key, and Calibrator compute
and apply centered geometry on every launch. Several use delayed second passes to
counter layout inflation or window-manager timing. No main window remembers the
user's last useful size.

### Implementation contract

- Add one UI-state owner for main-window geometry, stored separately from the
  tray-watched `config.json` and profile files, honoring `KEYRGB_CONFIG_DIR` and
  XDG config resolution.
- Use `config_dir()/ui-state.json` plus a distinct `ui-state.lock`. Mirror the
  repository's atomic temporary-write/`os.replace()` and advisory-lock pattern
  rather than importing private config-storage functions or writing in place.
- Store validated width and height for every main window. Store x/y where the
  window manager reports meaningful coordinates, but treat position restoration
  as best-effort on Wayland.
- Clamp restored size to each window's minimum and current screen work area.
  Reject malformed, absurd, or wholly off-screen geometry and fall back to the
  existing centered calculation.
- Debounce configure-event writes by 500 ms and save once more on orderly close,
  before releasing the UX-09 instance lock. Suppress persistence during initial
  programmatic geometry passes.
- Keep probe dialogs transient and centered relative to their owner; do not
  persist every short-lived dialog.
- Introduce the shared helper first, then migrate one main window per focused
  pass, with Settings and Per-key migrated only after simpler windows prove the
  contract.

### Planned files

- new `keyrgb/gui/utils/window_state.py` as the single UI-state owner
- extend existing `keyrgb/gui/utils/window_geometry.py`
- `keyrgb/gui/windows/uniform.py`
- `keyrgb/gui/windows/reactive_color.py` and geometry adapter
- `keyrgb/gui/windows/power_mode.py`
- `keyrgb/gui/windows/support.py` and support geometry helper
- `keyrgb/gui/settings/window.py`
- extend existing `keyrgb/gui/perkey/window_geometry.py` and bootstrap
- `keyrgb/gui/calibrator/_app_bootstrap.py`
- `tests/gui/rendering_utils/test_window_geometry_unit.py`
- focused window geometry/bootstrap tests

### Acceptance criteria

- Resized dimensions survive close/reopen for every main window.
- Corrupt UI-state JSON, removed monitors, smaller work areas, and invalid
  coordinates safely fall back without blocking launch.
- Opening a window does not modify `config.json` or trigger tray config reloads.
- A test records `config.json` digest and mtime before geometry save/restore and
  proves both remain unchanged.
- No continuous disk-write loop occurs while moving/resizing.
- Plasma Wayland evidence distinguishes verified size restoration from
  best-effort or unsupported position restoration.

## UX-08 — Accelerators and keyboard-access contracts

### Evidence

The calibrator has Return, arrows, and Escape bindings, and selected entry fields
commit on Return. Other windows lack a consistent close/save shortcut policy,
mnemonics, initial focus, tested tab order, and keyboard behavior for custom
canvas-adjacent controls. The custom dropdown currently hijacks Down-arrow
behavior.

### Implementation contract

- Define and document a conservative shared policy:
  - `Ctrl+W` closes the current main window;
  - `Escape` closes non-destructive utility windows and dismisses dialogs;
  - `Ctrl+S` saves only in explicit-save surfaces such as the per-key editor,
    calibrator, and Power Mode window;
  - Enter activates the documented default action in modal dialogs;
  - native Tab/Shift+Tab and combobox navigation are preserved.
- Settings remains auto-save; do not add a misleading `Ctrl+S` binding there.
- Route per-key close through its dirty confirmation and retain calibrator probe
  arrow bindings without conflicts.
- Add mnemonics only where labels, focus transfer, and platform behavior can be
  tested consistently. Do not add decorative accelerator text without a working
  binding.
- Keep manual RGB entry as the keyboard alternative to pointer-only color-wheel
  selection; verify that it is reachable and operable.
- Treat full keyboard painting of the per-key canvas as part of the deferred
  UX-03 discussion rather than silently widening this item.

The initial binding map is explicit:

| Window | Close | Save | Escape |
|---|---|---|---|
| Settings | `Ctrl+W` → `_on_close` | none; settings auto-save | `_on_close` |
| Uniform Color | `Ctrl+W` → `_on_close` | none; color commits through existing controls | `_on_close` |
| Reactive Color | `Ctrl+W` → `_on_close` | none; values commit through existing controls | `_on_close` |
| Power Mode | `Ctrl+W` → `_close` | `Ctrl+S` → `_save` | `_close` |
| Support Tools | `Ctrl+W` → normal close/destroy route | none; bundle save remains an explicit button/dialog | normal close route |
| Per-key Editor | `Ctrl+W` → `_on_close` | `Ctrl+S` → `_save_profile` | unchanged pending UX-03 |
| Keymap Calibrator | `Ctrl+W` → `_on_close` | `Ctrl+S` → `_save` | `_on_close`, replacing direct destroy if needed to preserve restoration |

If current code lacks a named normal close route, create one local route and use
it from both the window manager and binding rather than binding directly to
`destroy()`.

### Planned files

- `keyrgb/gui/utils/window_bindings.py` if at least three windows share identical
  installation logic; otherwise keep explicit local bindings
- main window/bootstrap modules under `keyrgb/gui/settings/`, `windows/`,
  `perkey/`, and `calibrator/`
- `keyrgb/gui/widgets/color_wheel/_color_wheel_ui.py`
- focused GUI unit tests for each binding and close/save route

### Acceptance criteria

- Every main window has a documented initial focus and keyboard close route.
- Explicit-save windows invoke the same save method from button and accelerator.
- Dirty-close and modal-dialog protections cannot be bypassed by accelerators.
- A keyboard-only walkthrough reaches and operates every standard form control.
- Native combobox keyboard behavior works after UX-07, with no custom Down-arrow
  interception.

## UX-03 — Simplify the per-key editor's default view

### Status and decision gate

Deferred until UX-01, UX-02, and UX-05–UX-09 are complete or monitoring. This
item requires a dedicated UX discussion using updated screenshots and at least
one low-fidelity layout proposal. No production implementation should begin from
this tracker text alone.

### Discussion scope

- Define the primary jobs: choose profile, paint/select keys, choose color,
  activate/save, and inspect current target.
- Decide which of backdrop controls, AC/battery policy, sample tool, fill/clear,
  keyboard setup, keymap calibration, overlay alignment, optional keys, and
  lighting areas remain in the default view.
- Compare tabs, a task sidebar, compact toolbars, and mode-specific panels using
  the existing minimum-size constraints.
- Define novice and expert paths without removing discoverability.
- Specify status/dirty/default-profile feedback and keyboard expectations.

### Likely owners after approval

- `keyrgb/gui/perkey/editor_support/ui.py`
- `keyrgb/gui/perkey/editor_support/layout.py`
- `keyrgb/gui/perkey/editor_support/layout_state.py`
- `keyrgb/gui/perkey/editor_support/runtime.py`
- `keyrgb/gui/perkey/ui/`
- corresponding per-key layout, UI, dirty-state, and profile tests

### Exit criteria for the discussion

- Approved annotated mockup or wireframe for default, setup, and advanced modes.
- Explicit list of always-visible, contextual, and advanced controls.
- Defined minimum useful resolution and resize behavior.
- Migration/compatibility contract for profiles, selections, setup state, and
  secondary lighting.
- A successor implementation plan or an approved amendment to this item.

## UX-04 — Guided keyboard setup and calibration workflow

### Status and decision gate

Deferred and sequenced last. It depends on the UX-03 editor shell direction and
requires a dedicated discussion of hardware probing, cancellation, save, and
recovery behavior. Existing standalone `keyrgb-calibrate` behavior must remain
available until a replacement workflow has proven parity.

### Discussion scope

- Entry requirements and hardware/backend capability checks.
- Steps for physical layout, legend/optional-key selection, keymap calibration,
  overlay alignment, validation, save, and return to editing.
- Progress indication, Back/Next/Skip semantics, cancellation, dirty state, and
  restoration of the original hardware/config state.
- Recovery after disconnect, unsupported backend, denied permission, or partial
  calibration.
- Relationship between embedded guidance and the standalone calibrator command.

### Likely owners after approval

- `keyrgb/gui/perkey/editor.py`
- `keyrgb/gui/perkey/editor_support/`
- `keyrgb/gui/perkey/ui/layout_setup.py`
- `keyrgb/gui/perkey/ui/layout_slots.py`
- `keyrgb/gui/perkey/overlay/controls.py`
- `keyrgb/gui/calibrator/app.py`
- `keyrgb/gui/calibrator/_app_bootstrap.py`
- `keyrgb/gui/calibrator/_app_logic.py`
- calibrator/per-key integration and state-machine tests

### Exit criteria for the discussion

- Approved step model and interruption/recovery contract.
- Explicit ownership of temporary hardware preview state.
- Compatibility decision for `keyrgb-calibrate` and saved keymaps/layout tweaks.
- Manual reporter-hardware validation plan where real controller behavior is
  involved.
- A successor implementation plan or an approved amendment to this item.

## Recommended implementation order

1. Complete UX-00 and record automated/manual baseline evidence.
2. UX-01 Settings categories/navigation.
3. UX-02 basic/advanced separation.
4. UX-07 native combobox migration and theme deduplication.
5. UX-05 shared visual system, one window at a time.
6. UX-09 per-GUI duplicate prevention.
7. UX-06 geometry persistence, simple windows before Settings and Per-key.
8. UX-08 accelerators, focus, and keyboard walkthrough.
9. Hold the dedicated UX-03 discussion and implement only after approval.
10. Hold the dedicated UX-04 discussion and implement only after UX-03 settles.

UX-07 precedes full keyboard work because it removes bindings that currently
intercept native combobox navigation. UX-09 precedes geometry persistence so two
same-identity processes cannot race UI-state writes. The per-key redesign remains
last so lower-risk consistency work provides a stable baseline rather than being
invalidated by a simultaneous editor rewrite.

## Per-item workflow

1. Set exactly one inventory item to `active`.
2. Re-read current implementation, callers, tests, and this item's evidence.
3. Add or update characterization/contract tests before or with production code.
4. Implement the narrowest complete slice; do not bundle the next inventory item.
5. Run focused tests and static checks for changed files.
6. Run BuildPython Step 19 whenever a best-effort Tk/WM/filesystem boundary was
   added or changed.
7. Perform only the manual desktop checks relevant to the slice and state the
   actual session used.
8. Review `git diff`, update this item/status, and append exact evidence below.

## Validation matrix

### Focused validation

- Settings navigation/basic-advanced:

  ```bash
  .venv/bin/python -m pytest tests/gui/settings tests/gui/theme_entrypoints -q -o addopts=
  ```

- Dropdown and per-key shell:

  ```bash
  .venv/bin/python -m pytest tests/gui/perkey/layout tests/gui/perkey/editor/ui tests/gui/theme_entrypoints -q -o addopts=
  ```

- Geometry and singleton:

  ```bash
  .venv/bin/python -m pytest tests/gui/rendering_utils tests/gui/windows tests/gui/settings/window tests/gui/perkey/editor/window tests/gui/calibrator tests/tray/ui/test_gui_launch_unit.py tests/core/runtime/test_imports_unit.py -q -o addopts=
  ```

- Changed Python files:

  ```bash
  .venv/bin/python -m ruff check <changed-files>
  .venv/bin/python -m black --check <changed-files>
  .venv/bin/python -m mypy <changed-production-files>
  ```

### Campaign validation

After UX-01, UX-02, and UX-05–UX-09 are complete:

```bash
.venv/bin/python -m pytest tests/gui tests/tray/ui tests/core/runtime -q -o addopts=
.venv/bin/python -m buildpython --run-steps=19
.venv/bin/python -m buildpython --profile=ci
git diff --check
```

Hardware access remains disabled in default tests. The campaign does not require
AppImage rebuilding unless a UI-state resource, package-data rule, or launcher
artifact changes, but the final CI profile must retain wheel/resource smoke
coverage.

## Campaign completion criteria

- [ ] UX-01, UX-02, and UX-05–UX-09 are `done` or explicitly `monitoring` with a
      named desktop-session check.
- [ ] UX-03 and UX-04 have approved successor decisions or remain explicitly
      deferred; they are not accidentally implemented as cleanup.
- [ ] Public GUI entrypoints and persisted config/profile data remain compatible.
- [ ] No new non-stdlib GUI dependency or second toolkit was added.
- [ ] Settings presents clear categories and keeps technical controls out of the
      default path.
- [ ] No custom borderless dropdown implementation remains.
- [ ] Every main window has consistent styling, visible keyboard focus, a tested
      keyboard close route, duplicate prevention, and safe geometry restoration.
- [ ] Focused and campaign validation commands are recorded with exact results.
- [ ] Updated screenshots and actual Plasma Wayland/X11 evidence are identified.

## Progress log

### 2026-09-09 — campaign preparation

- Reviewed current screenshots, GUI owners, settings persistence, custom
  dropdown call sites, geometry behavior, entrypoints, subprocess launch paths,
  singleton ownership, theme code, keyboard bindings, and nearby test suites.
- Recorded the decision to retain Tkinter and avoid new runtime dependencies.
- Split the nine requested UX outcomes into independently trackable items with
  dependency order and acceptance criteria.
- Explicitly deferred the per-key default-view and guided calibration redesigns
  until the final dedicated UX discussions.
- No production code changed and no tests were run during this planning pass.

### 2026-09-09 — UX-00 accepted and UX-01 implemented

- The owner confirmed that the baseline UX had already been well traversed and
  approved starting implementation. UX-00 is therefore complete by explicit
  owner acceptance rather than a duplicate screenshot campaign.
- The pre-change automated Settings/theme baseline passed:
  `.venv/bin/python -m pytest tests/gui/settings tests/gui/theme_entrypoints -q -o addopts=`
  reported `176 passed`.
- Added standard `ttk.Notebook` navigation with five stable pages in this order:
  Lighting & Power, Automation, App, Advanced, and About & Support. Lighting &
  Power is the default.
- Moved existing panel instances without changing their variables or save
  behavior. The title and bottom status/hardware-hint/Close bar remain outside
  the pages, and every panel, version check, and footer probe is constructed
  once.
- Extended `ScrollableArea` so independently scrolling pages register additive
  mouse-wheel handlers and only the page underneath the pointer consumes the
  event.
- Reduced Settings minimum geometry from 1000×620 to 680×560 and initially set
  the default to 880×700. The default was subsequently increased to 880×840
  after visual testing showed that the real Lighting & Power rendering still
  needed more vertical room. Persistence remains reserved for UX-06.
- Production files:
  - `keyrgb/gui/settings/navigation.py` (new);
  - `keyrgb/gui/settings/window.py`;
  - `keyrgb/gui/settings/scrollable_area.py`;
  - `keyrgb/gui/settings/_settings_window_constants.py`.
- Test files:
  - `tests/gui/settings/test_navigation_unit.py` (new);
  - `tests/gui/settings/window/test_settings_window_unit.py`;
  - `tests/gui/settings/core/test_scrollable_area_unit.py`.
- Parent-side validation:
  - `.venv/bin/python -m pytest tests/gui/settings tests/gui/theme_entrypoints -q -o addopts=`:
    `182 passed`;
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `811 passed`;
  - focused Ruff, Black, and mypy: passed;
  - `python -m buildpython --run-steps=16,17,19`: `3 passed`; code hygiene,
    architecture validation (`24 rules`, `613 files`, zero findings), and
    exception transparency all passed;
  - `git diff --check`: passed.
- A live smoke on the current KDE Wayland session (`DISPLAY=:0`,
  `WAYLAND_DISPLAY=wayland-0`, 2560×1600) constructed the real Settings window,
  confirmed all five labels and the Lighting & Power default, switched through
  every page, remained viewable at the earlier `880x700` geometry after delayed
  geometry settled, and
  closed normally using an isolated `KEYRGB_CONFIG_DIR`.
- UX-01 is `monitoring`, not `done`, until the reduced geometry and page
  scrolling receive a visual check at a constrained/1366×768 work area. No X11
  or light-theme claim is made by this pass.

### 2026-09-09 — UX-01 compact-default visual correction

- Visual testing showed that the real Lighting & Power rendering could still
  appear vertically clipped/scrollable despite the earlier synthetic geometry
  measurement. The default height is therefore increased from `700` to `840`
  (20% more vertical space), while Automation remains independently scrollable.
- The earlier live measurements (`585px` canvas/`456px` content at normal
  scaling and `586px`/`438px` at `KEYRGB_TK_SCALING=1.5`) are retained as
  diagnostic evidence but are not treated as sufficient visual acceptance.
- Re-run the live smoke and a constrained 1366×768 check before changing UX-01
  from monitoring to done.

### 2026-09-09 — UX-02 basic/advanced separation implemented

- Recorded the approved control classification in UX-02 before moving widgets.
- Kept Automation focused on ordinary outcomes: idle source, sync enable,
  turn-off versus temporary brightness, temporary brightness, and the existing
  time-of-day scheduler.
- Added `IdleTransitionAdvancedPanel` for controller firmware sleep behavior,
  turn-off/restore delays, and fade duration. Experimental backend policy remains
  below it on the Advanced page.
- Preserved every existing variable, callback, range, immediate-save conversion,
  and enabled-state rule. In particular, controller sleep remains independently
  selectable while delay/fade controls continue to follow the master power
  management state.
- Added a window-level regression proving that a basic Automation save preserves
  controller sleep, both delays, fade duration, and experimental backend policy
  without selecting Advanced.
- Production files:
  - `keyrgb/gui/settings/panels/idle_transition_advanced_panel.py` (new);
  - `keyrgb/gui/settings/panels/dim_sync_panel.py`;
  - `keyrgb/gui/settings/panels/__init__.py`;
  - `keyrgb/gui/settings/navigation.py`;
  - `keyrgb/gui/settings/window.py`.
- Test files:
  - `tests/gui/settings/panels/test_idle_transition_advanced_panel_unit.py`
    (new);
  - `tests/gui/settings/panels/test_dim_sync_panel_unit.py`;
  - `tests/gui/settings/test_navigation_unit.py`;
  - `tests/gui/settings/window/test_settings_window_unit.py`;
  - `tests/gui/settings/window/test_settings_window_toggle_unit.py`.
- Parent-side validation:
  - `.venv/bin/python -m pytest tests/gui/settings tests/gui/theme_entrypoints -q -o addopts=`:
    `190 passed`;
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `819 passed`;
  - focused Ruff, Black, and mypy: passed;
  - `python -m buildpython --run-steps=16,17,19`: `3 passed`; architecture
    validation checked `24 rules` across `614 files` with zero findings;
  - independent review found no blockers or high-severity findings.
- A live KDE Wayland smoke at `880x840` constructed and switched through all
  pages. Measured content/available heights were Lighting & Power `456/725`,
  Automation `617/725`, App `128/725`, Advanced `388/725`, and About & Support
  `191/725`; no page required scrolling in that environment.
- UX-02 is `monitoring` pending owner visual confirmation of the new Advanced
  grouping and title.

### 2026-09-09 — UX-02 visual acceptance; UX-07 started

- The owner confirmed the categorized and basic/advanced Settings UX.
- UX-02 is complete. UX-07 is now the only active implementation item.
- Pre-change UX-07 baseline:
  `.venv/bin/python -m pytest tests/gui/perkey/layout tests/gui/perkey/editor/ui tests/gui/theme_entrypoints -q -o addopts=`
  — `118 passed`.

### 2026-09-09 — UX-07 native combobox migration implemented

- Replaced all six custom per-key dropdown overlays with readonly native
  `ttk.Combobox` behavior: backdrop, lighting profile, AC profile, battery
  profile, physical layout, and legend pack.
- Preserved the existing selection callbacks and persisted values. Profile and
  power-source selectors now use `postcommand` refreshes, while existing profile
  create/delete and power-policy synchronization continue refreshing values
  after changes.
- Removed the per-key instance bindings that intercepted `<Button-1>` and
  `<Down>`, restoring Tk's standard combobox bindings and focus behavior.
- Removed the divergent per-key `TCombobox` state map so the shared disabled
  foreground map applies.
- Deleted `keyrgb/gui/widgets/dropdown.py` and its popup/listbox test support
  after confirming no production or test references remained.
- Production files:
  - `keyrgb/gui/perkey/editor_support/ui.py`;
  - `keyrgb/gui/perkey/ui/layout_setup.py`;
  - `keyrgb/gui/perkey/editor_support/bootstrap.py`;
  - `keyrgb/gui/widgets/dropdown.py` (deleted).
- Test files:
  - `tests/gui/perkey/editor/support/test_editor_bootstrap_unit.py`;
  - `tests/gui/perkey/editor/ui/_editor_ui_fakes.py`;
  - `tests/gui/perkey/editor/ui/test_perkey_editor_ui_unit.py`;
  - `tests/gui/perkey/layout/test_layout_setup_unit.py`;
  - `tests/gui/perkey/layout/_dropdown_fakes.py` (deleted);
  - `tests/gui/perkey/layout/test_dropdown_unit.py` (deleted);
  - `tests/gui/perkey/layout/test_dropdown_interaction_unit.py` (deleted).
- Parent-side validation:
  - focused per-key/theme suite: `103 passed`;
  - all GUI tests: `802 passed`;
  - focused Ruff, Black, and mypy: passed;
  - BuildPython Steps 16, 17, and 19: passed; architecture validation checked
    `24 rules` across `613 files` with zero findings;
  - `git diff --check`: passed;
  - repository search found no remaining `UpwardListboxDropdown`, deleted-module,
    or removed dropdown-attribute references.
- A live smoke on the current KDE Plasma Wayland session constructed the real
  per-key editor with hardware access disabled and isolated configuration. All
  six native popups posted and dismissed successfully; every selector reported
  readonly state, non-empty values, and no instance `<Button-1>` or `<Down>`
  override. No X11 session was available.
- UX-07 is `monitoring` pending an owner-visible mouse and keyboard selection
  walkthrough. No X11 validation claim is made.

### 2026-09-09 — UX-07 visual acceptance; UX-05 started

- The owner confirmed that all six native comboboxes look good.
- UX-07 is complete. UX-05 is now the only active implementation item.

### 2026-09-09 — UX-05 shared visual and focus system implemented

- Added shared semantic ttk styles for title, section, body, caption, status,
  value, primary action, and destructive action roles. The styles use retained
  Tk named fonts on the system-resolved `Sans` alias and preserve the established
  14/11/10/9/8 point hierarchy while continuing to honor Tk scaling.
- Added shared outer/section/control/inline spacing metrics and migrated Settings,
  Uniform Color, Reactive Color, Power Mode, Support Tools, the per-key editor,
  and Keymap Calibrator without changing control order or workflow ownership.
- Added pure WCAG relative-luminance and contrast helpers. Theme tests pin 4.5:1
  normal text, 3:1 large-title text, and the project 3:1 disabled-text usability
  target for supported dark/light palettes.
- Centralized disabled and visible-focus state maps for buttons, checks, radios,
  entries, comboboxes, spinboxes, scales, and scrollbars. Disabled combobox state
  takes precedence over readonly state.
- Added non-forcing initial-focus scheduling that never grabs or calls
  `focus_force`, preserves an already-focused child, and replaces root-only focus
  with the intended first control. Settings targets its notebook; Uniform targets
  Apply or Close when unsupported; Reactive targets Vivid visuals; Power Mode
  targets Save; Support targets the environment-selected Run action; per-key
  targets Backdrop; Calibrator targets Assign.
- Added restrained semantic action emphasis: primary styling for Apply/Save or
  Assign actions and destructive styling for per-key Delete/Clear All. Settings
  and Support retain neutral/custom action treatment where no single primary
  action exists.
- Removed the remaining local per-key ttk overrides and every non-canvas
  `font=("Sans", ...)` tuple under `keyrgb/gui`. Canvas key-label sizing remains
  unchanged and belongs to the rendering/layout contract.
- Shared production files:
  - `keyrgb/gui/theme/contrast.py` (new);
  - `keyrgb/gui/theme/focus.py` (new);
  - `keyrgb/gui/theme/metrics.py` (new);
  - `keyrgb/gui/theme/ttk.py`;
  - `keyrgb/gui/theme/__init__.py`.
- Migrated production owners:
  - Settings window and panels under `keyrgb/gui/settings/`;
  - Uniform, Reactive, Power Mode, and Support UI owners under
    `keyrgb/gui/windows/`;
  - per-key editor chrome/layout controls under `keyrgb/gui/perkey/`;
  - `keyrgb/gui/calibrator/_app_bootstrap.py`.
- Added or updated focused tests under `tests/gui/theme_entrypoints/`,
  `tests/gui/settings/`, `tests/gui/windows/`, `tests/gui/perkey/`, and
  `tests/gui/calibrator/` for semantic roles, spacing, disabled contrast, focus
  maps, initial-focus routing, and no-local-font regressions.
- Parent-side merged validation:
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `883 passed`;
  - Ruff across the affected GUI/test owners: passed;
  - Black across all `61` changed or new Python files: passed;
  - mypy across `141` GUI source files: passed;
  - `python -m buildpython --run-steps=16,17,19`: `3 passed`; architecture
    validation checked `24 rules` across `616 files` with zero findings;
  - `git diff --check`: passed;
  - two independent final reviews found no blocker, high-, or medium-severity
    findings after the theme/font-cache and Support-focus corrections.
- Real-Tk checks on the current KDE Plasma Wayland session applied both dark and
  light themes at `KEYRGB_TK_SCALING=1.5`, created every mapped widget type and
  semantic style, confirmed named-font availability and focus state maps, and
  constructed all seven migrated main windows using isolated configuration with
  hardware access disabled.
- UX-05 is `monitoring` pending owner-visible dark/light and scaling review. No
  X11 validation claim is made.

### 2026-09-09 — UX-05 visual acceptance; UX-07 responsiveness follow-up

- The owner confirmed that all changed UX surfaces work and look good. UX-05 is
  complete.
- Testing found that the three profile-related native comboboxes are slow to
  populate and generally unresponsive. UX-07 is temporarily active again for a
  focused responsiveness fix and aggressive removal of obsolete campaign code.

### 2026-09-09 — UX-07 responsiveness fix and campaign-code pruning

- Removed all profile-selector `postcommand` callbacks. The editor now scans
  profile storage once during construction, stores an immutable profile-name
  snapshot, and opens the Lighting profile, Use on AC, and Use on battery native
  popups without filesystem work.
- AC/battery selection reuses the cached snapshot and batches its two config
  property updates into one persistence transaction. Profile save/new/delete
  refresh all three selectors from one shared post-operation scan while retaining
  configured-but-missing policy names.
- Added regressions proving one construction scan, no popup callback, no scan on
  policy selection, one shared CRUD refresh scan, and current native selection
  callbacks.
- Aggressively removed obsolete campaign scaffolding: no-op theme flags and their
  call plumbing, private focus aliases used only as monkeypatch seams, the unused
  Support focus exception parameter, the old Settings default-page alias, and
  four dead per-key bootstrap dependency parameters/protocols.
- Parent-side merged validation:
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `884 passed`;
  - `.venv/bin/python -m buildpython --run-steps=3,7`: Ruff and Ruff Format
    passed after formatting two changed tests;
  - Black across all `68` changed or new Python files: passed;
  - `.venv/bin/python -m buildpython --run-steps=13`: passed;
  - `.venv/bin/python -m buildpython --run-steps=1,4,16,17,19,20`: `6 passed`;
    compile and all `8/8` import probes passed;
    architecture validation checked `24 rules` across `616 files` with zero
    findings and Dead Code reported zero actionable candidates;
  - `git diff --check`: passed.
- The repository-wide Black gate still reports pre-existing formatting drift in
  unrelated `keyrgb/core/` and `buildpython/` files; no unrelated production file
  was reformatted in this UX pass.
- UX-07 is `monitoring` pending the owner's responsiveness confirmation on the
  three profile selectors. No new X11 validation claim is made.

### 2026-09-09 — UX-07 remaining focus-churn root cause corrected

- Owner testing found virtually no perceived improvement from removing the
  profile-list popup scans, so the first responsiveness diagnosis was incomplete.
- The remaining stall came from the editor's toplevel `<FocusIn>` binding. Tk
  dispatches toplevel bindings for descendant focus events, and dismissing a
  native combobox popdown also returns focus through the editor root. Each event
  synchronously reopened and locked `keymap.json`, sanitized the full keymap, and
  redrew the complete keyboard canvas on Tk's event thread.
- Removed the generic focus-driven reload. The calibrator launcher now returns
  its subprocess handle; the editor polls that process every 250 ms and reloads
  the keymap exactly once when the calibrator exits. This preserves the original
  calibrator-return purpose without coupling ordinary widget focus to storage and
  canvas work.
- No-op keymap reloads no longer redraw the keyboard canvas when the loaded map is
  unchanged.
- Calibrator polling stops cleanly if the editor has already been destroyed,
  with narrow, debug-logged Tk teardown handling.
- Added regressions for no per-key `<FocusIn>` binding, calibrator process polling
  and one completion reload, returned subprocess ownership, and no redraw for an
  unchanged keymap.
- Parent-side validation:
  - focused calibrator/keymap/editor transition tests: `12 passed`;
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `885 passed`;
  - Ruff and Ruff Format across `keyrgb/gui` and `tests/gui`: passed;
  - Black across all `75` changed or new Python files: passed;
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; all `8/8` import probes passed, architecture checked `24`
    rules across `616` files with zero findings, and Dead Code reported zero
    actionable candidates;
  - `git diff --check`: passed.
- A real-Tk KDE Wayland smoke with isolated config and hardware disabled posted
  and dismissed all three profile selectors in `2.73`, `3.97`, and `5.50` ms,
  with no `<FocusIn>` binding and zero keymap reloads. These programmatic timings
  do not replace the owner's interaction check. No X11 validation claim is made.
- UX-07 remains `monitoring` pending a fresh editor restart and owner confirmation.

### 2026-09-09 — UX-07 responsiveness accepted; UX-09 started

- The owner confirmed after a fresh restart that the three profile comboboxes
  are now instant and responsive.
- UX-07 is complete. UX-09 duplicate-instance prevention is now the only active
  implementation item.

### 2026-09-09 — UX-09 duplicate-instance prevention implemented

- Added Tk-free `keyrgb/gui/single_instance.py` with validated per-window lock
  identities, Linux non-blocking advisory `flock`, process-lifetime descriptor
  ownership, PID diagnostics, `atexit` cleanup, and clean duplicate exit code 0.
  Lock paths use `config_dir()/keyrgb-gui-<identity>.lock`; the tray/hardware
  `keyrgb.lock` is untouched.
- Added lock-first guards before Tk construction or hardware acquisition for
  Settings, Reactive Color, Power Mode, Support Tools, Per-key Editor, Keymap
  Calibrator, and Uniform Color.
- Uniform Color uses route-scoped identities so keyboard, lightbar, mouse, logo,
  neon, and vent editors do not incorrectly block different valid targets.
- Tests cover identity/path validation, XDG/config isolation, real exclusion and
  release, stale-path recovery, forced subprocess death, missing-`fcntl`
  fail-open behavior, all entrypoint ordering/duplicate exits, and Uniform route
  resolution.
- Validation:
  - pre-change focused baseline: `7 passed`;
  - focused lock/entrypoint/tray suite: `77 passed`;
  - `.venv/bin/python -m pytest tests/gui tests/tray/ui/test_gui_launch_unit.py -q -o addopts=`:
    `959 passed`;
  - Ruff and Ruff Format across `keyrgb/gui`, `tests/gui`, and the tray-launch
    test: passed (`279` files formatted);
  - Black across all `10` changed or new Python files: passed;
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; all `8/8` import probes passed, architecture checked `24` rules
    across `616` files with zero findings, and Dead Code reported zero actionable
    candidates;
  - `git diff --check`: passed;
  - independent final review found no blocker, high-, or medium-severity issue.
- A live subprocess smoke held each lock and launched every guarded module. All
  eight cases (including keyboard and logo Uniform identities) emitted the
  duplicate diagnostic and exited 0 before constructing a window.
- UX-09 is complete. UX-06 geometry persistence is now the only active item.

### 2026-09-09 — UX-06 geometry persistence implemented

- Added the Tk-free `keyrgb/gui/utils/window_state.py` owner for
  `config_dir()/ui-state.json`, with a distinct `ui-state.lock`, blocking
  advisory locks, atomic read-modify-write replacement, sibling-state
  preservation, validated geometry, screen/minimum clamping, and malformed or
  wholly off-screen fallback.
- Window coordinates are persisted on coordinate-capable sessions and omitted
  on Wayland, where size restoration remains the reliable contract. Configure
  events ignore descendant widgets and debounce writes by 500 ms.
- Integrated route-scoped Uniform, Reactive Color, Power Mode, Support Tools,
  Settings, Per-key Editor, and Keymap Calibrator geometry. Existing centered
  behavior remains the fallback, startup geometry passes run before tracking,
  and orderly close saves before teardown. Calibrator Escape now shares its
  orderly close path instead of bypassing hardware restoration.
- Added focused coverage for locked/atomic persistence, corruption and screen
  changes, negative Tk coordinates, Wayland size-only state, write debouncing,
  dynamic Uniform identities, all seven restore/fallback paths, close ordering,
  and proof that `config.json` digest and mtime remain unchanged.
- Validation:
  - focused UX-06 suite: `117 passed`;
  - `.venv/bin/python -m pytest tests/gui tests/tray/ui/test_gui_launch_unit.py -q -o addopts=`:
    `1056 passed`;
  - Ruff and Ruff Format across `keyrgb/gui` and `tests/gui`: passed (`285`
    files formatted);
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; all `8/8` import probes passed, architecture checked `24` rules
    across `618` files with zero findings, and Dead Code reported zero
    actionable candidates;
  - `git diff --check`: passed;
  - independent final review found no blocker-, high-, or medium-severity issue.
- UX-06 is `monitoring` pending a Plasma Wayland close/reopen walkthrough that
  confirms size restoration for all seven windows and records position behavior
  as best-effort. UX-08 keyboard access is now the only active implementation
  item.

### 2026-09-09 — UX-08 keyboard access implemented

- Added the Tk-free `install_window_bindings` helper with additive Ctrl+W,
  optional Escape, and explicit-save-only Ctrl+S routes. The helper does not
  bind Tab, Shift+Tab, Return, arrows, or combobox events, preserving native
  traversal and UX-07 combobox navigation.
- Settings, Uniform Color, Reactive Color, Power Mode, Support Tools, Per-key
  Editor, and Keymap Calibrator now share their existing orderly close routes.
  Power Mode, Per-key, and Calibrator Ctrl+S bindings invoke the exact methods
  used by their Save buttons; Settings remains auto-save. Per-key intentionally
  leaves Escape unbound and Ctrl+W still passes through dirty confirmation.
- Calibrator Return/KP Enter assignment and Left/Right probe navigation remain
  intact. Its Escape route is no longer separately implemented.
- Support probe dialogs now use additive Escape cancellation and documented
  Enter defaults. Choice-dialog Enter honors the focused button, close routes
  are idempotent, and the notes dialog deliberately leaves Return/KP Enter to
  ScrolledText. Manual RGB fields also accept keypad Enter.
- Automated validation:
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `1085 passed`;
  - Ruff and Ruff Format across `keyrgb/gui` and `tests/gui`: passed (`291`
    files formatted);
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; all `8/8` import probes passed, architecture checked `24` rules
    across `619` files with zero findings, and Dead Code reported zero
    actionable candidates;
  - `git diff --check`: passed;
  - independent final review found no blocker- or high-severity issue; its two
    medium dialog findings were corrected with idempotent close and
    focused-choice routing.
- UX-08 is `monitoring` pending a keyboard-only desktop walkthrough of every
  standard form control and native combobox popup behavior. No implementation
  item is activated next: UX-03 and UX-04 remain deferred at their required
  dedicated UX discussion gate.

### 2026-09-09 — UX-06 and UX-08 owner acceptance

- The owner opened all main windows after the geometry and keyboard-access
  changes and reported that they work correctly.
- This owner walkthrough closes the remaining desktop acceptance gate for
  UX-06 and UX-08; both items are now `done`.
- No X11-specific position-restoration claim is added. Wayland position remains
  explicitly best-effort, while persisted size and orderly shortcut routes are
  the supported contracts.
- The campaign is now at the UX-03 dedicated design-discussion gate. Production
  implementation remains deferred until an updated per-key editor screenshot
  and a low-fidelity default/setup/advanced layout direction are approved.

### 2026-09-09 — UX-03 layout direction approved

- The owner supplied an updated screenshot of the current Lighting Profile
  Editor and approved the proposed default layout.
- The canvas and compact paint rail remain always visible. The lower editor area
  becomes a full-width native Notebook with Profiles, Setup, and Advanced tabs.
- Profiles owns profile actions, default selection, and AC/battery policy. Setup
  owns layout, legends, optional keys, and calibrator launch. Advanced owns
  overlay alignment, lightbar/lighting areas, and backdrop image/transparency;
  backdrop mode remains in the paint rail.
- A visible unsaved indicator is approved. Save remains in Profiles with Ctrl+S
  available globally. Existing profile formats, secondary-device routing,
  selection state, and standalone calibration behavior remain unchanged.
- The owner also reported size-only restores opening top-left. Commit `8cd8e0b0`
  now centers validated/clamped size-only state while retaining explicit saved
  coordinates where supported.
- UX-03 became `active`; UX-04 remained deferred until the editor shell settled.

### 2026-09-09 — UX-03 approved editor shell implemented

- Replaced the competing bottom profile/setup regions and numbered right-rail
  launchers with a full-width native Profiles, Setup, and Advanced notebook.
  The keyboard canvas and compact paint rail remain visible while switching
  tasks.
- Profiles retains profile actions, default selection, and AC/battery policy.
  Setup contains physical layout, legends, optional keys, and the existing
  calibrator launch route. Advanced contains backdrop image/transparency,
  overlay alignment, optional lightbar controls, and lighting areas.
- Native tab clicks refresh layout, overlay, and lightbar state. Conditional
  lighting areas retain their grid placement across profile activation, and the
  Advanced tab expands to full width when no secondary areas are available.
- Added a `Saved` / `● Unsaved` indicator driven by the existing in-memory dirty
  snapshot. No profile fields or formats changed; immediately persisted backdrop
  and AC/battery policy state remain outside that snapshot.
- Geometry keeps the existing 0.92 screen cap and now includes notebook space in
  its resize floor. Advanced content uses two columns to reduce vertical demand
  at the approved screenshot resolution.
- Validation:
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `1108 passed`;
  - Ruff and Ruff Format across the edited per-key sources/tests: passed (`112`
    files formatted);
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; architecture checked `24` rules across `619` files with zero
    findings;
  - `git diff --check`: passed;
  - independent final review found no blocker-, high-, or medium-severity issue
    after notebook synchronization and conditional-layout corrections.
- UX-03 is `monitoring` pending an owner-visible restart and tab/resizing check.
  UX-04 remains deferred until this shell is accepted.

### 2026-09-09 — UX-03 owner review prompted two-column refinement

- The owner confirmed that the redesigned editor window works, but the
  full-width notebook controls looked excessively stretched at the normal
  desktop width shown in the acceptance screenshot.
- The approved refinement keeps the notebook full-width while arranging each
  tab's task groups side-by-side: profile management and automatic selection;
  keyboard layout and optional keys/calibrator; backdrop and advanced alignment
  or lighting controls.
- The tab groups fall back to a vertical stack below a narrow-width threshold.
  This changes presentation only; existing callbacks and persisted profile,
  layout, and device-routing state remain unchanged.
- The Advanced tab uses stable cells whether lighting areas are currently
  available or not, so a later device refresh cannot place lighting controls on
  top of overlay controls. Hidden panels also retain the correct placement for
  the current responsive mode.
- Validation:
  - `.venv/bin/python -m pytest tests/gui -q -o addopts=`: `1119 passed`;
  - Ruff and Ruff Format across per-key sources/tests: passed (`115` files
    formatted);
  - `.venv/bin/python -m buildpython --run-steps=1,4,13,16,17,19,20`:
    `7 passed`; architecture checked `24` rules across `620` files with zero
    findings;
  - `git diff --check`: passed.
- UX-03 remains `monitoring` pending owner confirmation of the refined
  side-by-side presentation. UX-04 remains deferred.
