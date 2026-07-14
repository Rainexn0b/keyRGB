# Secondary Lighting Profile Editor, Static Scene, and Simulation Plan

## Status

Code implementation and automated Phase 7 validation completed for v0.29.0 on
2026-07-14. Follow-up review fixes cover authoritative empty/partial scenes,
independent-route editor/profile brightness, and the inline tray hardware-mode
presentation. Issue #7 reporter hardware validation remains explicitly pending;
this status does not claim hardware verification.

Primary support case: [GitHub issue #7](https://github.com/Rainexn0b/keyRGB/issues/7),
Lenovo Legion Pro 7 16IAX10H (`0x048d:0xc197`).

This plan supersedes the UI and profile-state portions of the older secondary-route
plans. The shared transport, virtual routes, software-effect fan-out, and protocol
support are already implemented. This work is primarily profile ownership, runtime
wiring, and UX correction.

## Executive decision

1. Evolve the visible **Per-key Editor** into the **Lighting Profile Editor**.
2. Add secondary routes to that editor as a separate **Lighting areas** panel.
3. Keep auxiliary routes uniform; do not model logo, neon, vents, lightbar, or mouse
   as keyboard cells.
4. Make Static mean the complete active profile: keyboard plus every enabled
   lighting area.
5. Put animated fan-out behind one **Include enabled lighting areas** toggle inside
   **Software Effects**; unchecked remains keyboard-only.
6. Use tray header rows as live device-context selectors while keeping the editor as
   the authoritative whole-profile scene surface.
7. Add a new environment-only simulation mode,
   `KEYRGB_SIMULATE_SECONDARY_DEVICES=1`, so all registered secondary routes can be
   exercised without secondary hardware.

The short design rule is: **integrate the experience, not the device abstraction**.

## Evidence and current diagnosis

The latest issue report says:

> The "Keyboard + enabled lighting areas" option is listed but it doesn't turn on the other
> areas. UPDATE: actually, it does work if I use one of the software effects except
> static.

The attached v0.28.2 support bundle confirms:

- the `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion` parent is available;
- Logo, Neon Strip, and Vents virtual routes are available;
- all three routes support uniform colour and software targeting;
- the saved software target is `all_uniform_capable`;
- per-route colour/brightness state exists in config;
- animated software output can therefore reach the routes.

That separates the remaining problem from backend protocol support. The main gaps are:

1. profiles contain keyboard colours and layout data, but no secondary lighting state;
2. the editor only has lightbar *placement* discovery and cannot enumerate generic
   secondary routes;
3. runtime profile activation loads only keyboard colours;
4. Static restoration is incorrectly gated by the animated-effect target setting;
5. the tray config-polling signature omits `secondary_device_state`, so changes made
   by the editor process may not be observed;
6. virtual routes are used both as tray device contexts and as effect targets, giving
   two selectors unclear and overlapping meanings;
7. the route table and tests have fakes, but there is no safe full-application mode
   that exposes all routes without hardware;
8. the editor has no unified dirty-state/destructive-action guard.

## Scope

### In scope

- A profile-backed Lighting areas panel in the main editor.
- Individual enabled/disabled and colour state for secondary routes.
- Whole-profile Save, New, Activate, default, AC, and battery behaviour.
- Correct Static application and post-animation restoration.
- Enabled-route filtering for animated software effects.
- A shared secondary-route runtime/catalog used by tray, editor, uniform window,
  effects, diagnostics, and simulation.
- Tray terminology and selector cleanup.
- A safe secondary-device simulation mode.
- Forward-compatible storage, compatibility fallback, error isolation, diagnostics,
  focused tests, and manual/hardware acceptance checks.

### Out of scope

- Changing `0xc197` packet formats or LED identifiers without new hardware evidence.
- Treating secondary routes as per-key matrices.
- Per-zone hardware effects.
- Claiming that simulation is hardware validation.
- Adding speculative controller IDs.
- Adding per-zone brightness to shared-brightness chassis zones.
- A separate secondary-device editor window.

## Locked product semantics

### One profile, two rendering layers

The active lighting profile owns:

- the keyboard map or uniform keyboard colour;
- each profile-compatible secondary route's enabled state;
- each profile-compatible secondary route's static colour.

Animated effects temporarily render over that static scene. They do not redefine it.

| Situation | Keyboard | Enabled secondary routes | Disabled secondary routes |
|---|---|---|---|
| Static uniform | Profile uniform colour | Profile static colour | Off |
| Static per-key | Profile per-key map | Profile static colour | Off |
| Software animation, keyboard only | Animated | Profile static colour | Off |
| Software animation, keyboard + areas | Animated | Uniformized animated output | Off |
| Stop software animation | Restore profile | Restore profile static colour | Off |
| Keyboard hardware effect | Hardware effect | Profile static colour | Off |
| Global Turn Off / forced off | Off | Off | Off |
| Resume / Turn On | Restore active profile | Restore active profile | Off |

Static application must not inspect `software_effect_target`. That setting controls
animated software output only.

### Brightness policy

- Logo, Neon Strip, and Vents on the composite ITE 8258 controller share the primary
  keyboard/controller brightness.
- Their profile contract is `enabled + color`; no per-zone brightness control is
  displayed or persisted in profiles.
- A standalone route with an `independent` brightness policy stores brightness in the
  profile and exposes a context-specific tray slider. Turning it off preserves the
  last non-zero profile brightness and changes `enabled`, allowing restart-safe restore.
- Existing brightness values may be used to infer a legacy enabled state, but an
  explicit `enabled` field becomes authoritative.

### Tray controls answer different questions

- **Device context** means which endpoint or lighting area receives the next live,
  device-specific action. The rows remain visible as inventory and selectors when
  secondary routes exist; Keyboard returns to primary controls.
- Selecting a device does not change the active profile. **Lighting Profiles** opens
  the authoritative persistent scene editor.
- The context brightness row is capability-aware: independent routes get a slider,
  shared zones say that they follow Keyboard, and unsupported routes get no fake control.
- **Hardware Mode** contains only actions that route can perform. Current secondary
  routes expose static colour and on/off; keyboard firmware effects remain keyboard-only.
- **Effect Speed** remains global because all software targets share one render clock.
- **Include enabled lighting areas** is a Software Effects toggle controlling where
  animated output is rendered. It does not select active hardware or define Static.
- Static individual-area editing belongs in the Lighting Profile Editor.

### Editor layout

Use the existing bottom-right editor host beside **Lighting profiles**:

```text
Lighting Profile Editor

+------------------------------+-------------------+
| Keyboard canvas              | Keyboard colours  |
|                              | and tools          |
+------------------------------+-------------------+
| Lighting profiles            | Lighting areas       |
| [profile] New Activate Save  | (o) [x] Logo    [■] |
| AC / battery policy          | ( ) [x] Neon    [■] |
|                              | ( ) [ ] Vents   [■] |
+------------------------------+-------------------+
```

- Each row has an explicit selector, display label, enabled checkbox, colour value,
  and preview swatch. Routes with independent brightness also expose a 0–50
  brightness selector; shared-brightness chassis zones do not.
- A Keyboard selector above the rows explicitly returns the shared wheel to per-key
  editing, and area values use the same decimal `RGB: r, g, b` format as the wheel.
- The selected row reuses the editor's colour wheel. The selector makes the current
  target explicit; selecting a keyboard key returns the wheel to keyboard editing.
- Keyboard Setup and Overlay Alignment temporarily replace Lighting areas. Closing
  either setup tool restores Lighting areas; the Setup sidebar also has an explicit
  **Lighting Areas** button for returning to the panel.
- Keep lightbar placement/preview controls under Overlay Alignment. Placement is not
  lightbar lighting state.
- Hide the panel when no profile-compatible secondary route is available.
- In simulation mode, show a persistent banner and `(simulated)` labels.

## Storage contract

Add `secondary_lighting.json` to every profile. Use stable
`SecondaryDeviceRoute.state_key` values, never display labels or devnodes.

Recommended v1 payload:

```json
{
  "version": 1,
  "areas": {
    "ite8258_chassis_logo": {
      "enabled": true,
      "color": [255, 0, 0]
    },
    "ite8258_chassis_neon": {
      "enabled": true,
      "color": [0, 255, 0]
    },
    "ite8258_chassis_vent": {
      "enabled": false,
      "color": [0, 0, 255]
    },
    "lightbar": {
      "enabled": true,
      "color": [255, 128, 0],
      "brightness": 35
    }
  }
}
```

Normalization rules:

- clamp RGB channels to `0..255`;
- normalize `enabled` conservatively from booleans or numeric `0/1`;
- clamp optional independent-route brightness to `0..100`;
- preserve unknown route keys and unknown entry fields when saving;
- distinguish an absent component from an explicitly saved empty `areas` map;
- never create or rewrite the file merely by loading an old profile;
- never discard saved state because a route is temporarily unavailable.

Legacy-profile behaviour:

1. If `secondary_lighting.json` is absent, activation does not create it. Static
   rendering derives an in-memory scene from the existing normalized config and
   compatibility fields so upgraded installations work immediately.
2. The editor seeds its draft from current normalized config for visible routes.
3. The first explicit Save materializes the component.
4. Existing config `brightness > 0` implies enabled only when no explicit enabled
   state exists.
5. Existing lightbar and route-specific compatibility fields remain readable during
   the compatibility period.

The config/profile interpretation rules live in `src/core/secondary_lighting_state.py`.
Tray static rendering, animated target filtering, diagnostics, and the editor must use
that shared boundary rather than reimplementing enabled/colour/brightness fallbacks.

The runtime config remains a mirror used for cross-process observation and legacy
consumers. Extending `Config.apply_perkey_profile_state()` must persist the keyboard
map and normalized secondary enabled/colour/optional independent-brightness state in
one atomic config snapshot while preserving unknown secondary metadata.

## Secondary simulation decision

### Create a new mode

Use:

```bash
KEYRGB_SIMULATE_SECONDARY_DEVICES=1 ./keyrgb
```

Do not reuse existing modes:

- `KEYRGB_DEV=1` only changes exception propagation in one runtime boundary.
- `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1` changes policy but still requires hardware.
- `KEYRGB_ALLOW_HARDWARE` and `KEYRGB_HW_TESTS` explicitly permit real hardware I/O.
- `KEYRGB_DISABLE_USB_SCAN=1` makes routes unavailable.
- `NullKeyboard` is a no-op fallback and does not enumerate secondary routes or expose
  observable route state.
- HID/sysfs path overrides can still open or write their targets and are not safe UX
  simulation.

Reuse the production route descriptors and device protocols, but add a dedicated
runtime provider and simulated device implementation.

### Simulation contract

When the flag is enabled:

- expose every registered uniform secondary route: Lightbar, Mouse, Logo, Neon Strip,
  and Vents;
- synthesize one effective entry per route and deduplicate matching discovery entries;
- mark entries `simulated=True` and `availability_source="simulation"`;
- return an in-memory uniform device supporting colour, brightness, on/off, readback,
  and idempotent close;
- log route state changes under `KEYRGB_DEBUG=1`;
- make unsupported per-key or hardware-effect calls fail explicitly;
- skip all real secondary backend probes and acquisitions;
- never fall through to real secondary hardware after a simulated error;
- leave primary keyboard selection and I/O unchanged;
- inherit the flag into editor and uniform-window subprocesses;
- report simulation explicitly in diagnostics without claiming hardware detection.

For an isolated config/profile session:

```bash
KEYRGB_SIMULATE_SECONDARY_DEVICES=1 \
KEYRGB_CONFIG_DIR=/tmp/keyrgb-secondary-sim \
KEYRGB_DEBUG=1 \
./keyrgb
```

Stop another running tray before this manual flow so two processes do not compete for
the primary keyboard. Simulation suppresses secondary I/O only.

## Architecture boundaries

### Route description

Extend `src/core/secondary_device_routes.py` rather than adding UI-specific route
conditionals.

Required additions:

- `iter_secondary_routes()` for every registered route, not just virtual routes;
- an explicit profile capability, such as `supports_profile_state`;
- an explicit brightness policy, preferably
  `independent | primary_shared | unsupported`;
- retain `parent_backend_name` and `zone_key` for virtual-route identity.

### Route runtime

Add `src/core/secondary_device_runtime.py` as the only effective availability and
acquisition seam. A minimal API is:

```python
def secondary_device_simulation_enabled() -> bool: ...
def iter_effective_secondary_routes(...) -> tuple[EffectiveSecondaryRoute, ...]: ...
def route_is_available(route: SecondaryDeviceRoute) -> bool: ...
def acquire_secondary_device(route: SecondaryDeviceRoute) -> UniformDevice: ...
def backend_for_secondary_route(route: SecondaryDeviceRoute) -> object: ...
```

All effective entries must carry source/simulation metadata. Consumers must stop
calling `route.get_device()` or `route.get_backend()` directly.

Build one route snapshot per refresh and memoize parent availability by
`parent_backend_name`; the three C197 zones must not independently probe the same
parent three times. Deduplicate discovery and virtual/simulated entries by stable
route `state_key`, with deterministic route-table ordering.

Known direct bypasses to migrate:

- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/controllers/_software_target_auxiliary.py`
- `src/tray/ui/_menu_status_devices.py`
- `src/gui/windows/_uniform_color_bootstrap.py`
- `src/core/diagnostics/secondary_devices.py`
- the new Lighting areas editor service

Keep existing shared-transport close and cache-invalidation behaviour intact for real
routes. Add an explicit cached-target `close()`/prune path and invoke it when effective
routes disappear, become disabled, or the tray shuts down. Failure-driven invalidation
alone is not sufficient because a successful cached proxy can otherwise retain an open
transport indefinitely.

### Profile state

Keep normalization and storage under `src/core/profile/`. Keep editor draft/UI logic
under `src/gui/perkey/`. Do not make Tk widgets parse profile JSON or probe backends.

### Static scene application

Introduce a clearly named profile/static operation such as
`apply_secondary_profile_scene()`. Do not continue overloading
`restore_secondary_software_targets()`, whose name and current gating couple it to
animated effects.

The application operation must:

- consume normalized profile/config state and effective routes;
- turn disabled routes off;
- apply colour to enabled routes using the route brightness policy;
- isolate acquisition/write failure per route;
- always close transient devices;
- never block keyboard application because one route failed;
- return per-route outcomes for status/logging/tests.

## Phased implementation

### Phase 0 — Lock the regression and terminology contracts

#### Work

- Add sanitized fixtures representing the issue #7 state: three available virtual
  routes, saved per-route state, and `all_uniform_capable` selected.
- Add regression tests proving the current mismatch:
  - animated uniform fan-out reaches Logo/Neon/Vents;
  - Static is required to restore them independently of the effect-output selection;
  - route inventory produces individual rows;
  - secondary-only config changes must be observable.
- Add the mode table above to test names/comments so later refactors do not conflate
  Static with animated output again.
- Preserve existing backend/protocol and shared-transport tests unchanged.

#### Exit criteria

- The intended semantics have named fixtures and owning test files. Confirm each new
  regression test fails before its fix, but do not commit or hand off a permanently
  failing test suite; land each contract test with the phase that makes it green.
- No backend packet or hardware-ID change is included.

### Phase 1 — Centralize the route runtime and add simulation

#### Work

1. Extend the route metadata and add `iter_secondary_routes()`.
2. Add the central runtime/provider and in-memory simulated backend/device.
3. Migrate every availability, backend, and device acquisition consumer to it.
4. In simulation mode, synthesize all registered route entries and deduplicate by
   stable route `state_key`.
5. Make simulation take precedence over real secondary probing and acquisition.
6. Add subprocess inheritance, visible labels/banner data, debug state logging, and
   diagnostics fields.
7. Expand diagnostics state reporting from virtual routes to all registered routes.
8. Add `KEYRGB_SIMULATE_SECONDARY_DEVICES` to the environment snapshot allow-list.
9. Probe each physical/parent backend once per effective-route snapshot.
10. Add explicit cached-target pruning and tray-shutdown close behaviour.

#### Primary files

- `src/core/secondary_device_routes.py`
- `src/core/secondary_device_runtime.py` (new)
- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/controllers/_software_target_auxiliary.py`
- `src/tray/ui/_menu_status_devices.py`
- `src/gui/windows/_uniform_color_bootstrap.py`
- `src/core/diagnostics/secondary_devices.py`
- `src/core/diagnostics/snapshots.py`

#### Tests

- all-route enumeration and metadata;
- flag normalization;
- simulated state/readback/close behaviour;
- an exploding real probe is never called in simulation;
- an exploding real `get_device()` is never called in simulation;
- five unique simulated routes are produced;
- real/simulated candidates are deduplicated;
- a shared parent is probed once per snapshot and route ordering is stable;
- tray one-shot, uniform-window, and animated target paths use simulation;
- cached targets close on route removal, disable, and shutdown;
- diagnostics distinguish simulation from hardware;
- hardware tripwire proves the simulation test slice performs no secondary I/O.

#### Exit criteria

- A maintainer can launch the real tray/editor and see all secondary routes without
  any secondary hardware.
- Simulation cannot fall through to hardware.
- Real route behaviour remains unchanged when the flag is absent.

### Phase 2 — Add profile and config state for lighting areas

#### Work

1. Add `secondary_lighting` to `ProfilePaths` and the profile test fixture factory.
2. Implement versioned normalization, load, and atomic save operations.
3. Preserve unknown routes/fields and distinguish missing from empty.
4. Add generic secondary `enabled` accessors/facade methods in config.
5. Make explicit enabled authoritative; use brightness only as legacy fallback.
6. Extend `Config.apply_perkey_profile_state()` to merge keyboard and secondary state
   into one saved config snapshot.
7. Extend `ActivatedProfile`, `activate_profile()`, `save_profile()`, and New Profile
   with the secondary draft.
8. Keep lightbar placement in `lightbar_overlay.json`; do not merge it into lighting
   state.

#### Primary files

- `src/core/profile/paths.py`
- `src/core/profile/profiles.py`
- `src/core/profile/_profile_storage_ops.py`
- `src/core/profile/_profile_storage_payloads.py`
- `src/core/config/config.py`
- `src/core/config/_lighting/_secondary_device_accessors.py`
- `src/core/config/_lighting/_lighting_secondary_device_facade.py`
- `src/gui/perkey/profile_management.py`
- `tests/conftest.py`

#### Tests

- missing-file compatibility without an implicit write;
- explicit empty state;
- RGB/enabled normalization;
- unknown-route and unknown-field preservation;
- disconnected-route round trip;
- legacy brightness-to-enabled fallback;
- shared-brightness state does not create per-zone profile brightness;
- atomic config application preserves independent brightness and unknown metadata;
- Save, Activate, and New include the secondary draft.

#### Exit criteria

- Profiles can carry secondary state without changing legacy profiles on read.
- Keyboard-only profiles and installations behave exactly as before.

### Phase 3 — Build the Lighting areas editor surface

#### Work

1. Add focused model/controller and UI modules, preferably:
   - `src/gui/perkey/secondary_lighting.py`
   - `src/gui/perkey/ui/lighting_areas.py`
2. Initialize route inventory and the active-profile draft during editor bootstrap.
3. Replace the lightbar-only discovery assumption with the shared effective-route
   provider. Keep `has_lightbar_device` only for overlay geometry.
4. Mount the default panel in the existing bottom-right `extras_setup` host.
5. Add a row selector, enabled checkbox, display name, colour value, per-row preview,
   and status. Route the shared colour wheel to the selected row and return it to
   keyboard editing when a keyboard key is selected.
6. Hide the panel when empty; show the simulation banner/labels when applicable.
7. Make setup panels replace and then restore the default panel.
8. Rename visible surfaces:
   - window title: `KeyRGB - Lighting Profile Editor`;
   - tray launcher/menu: `Lighting Profile Editor` or `Open Lighting Editor…`.
9. Preview failures must remain local to the route and must not corrupt the draft or
   keyboard state.

#### Primary files

- `src/gui/perkey/editor_support/bootstrap.py`
- `src/gui/perkey/editor_support/ui.py`
- `src/gui/perkey/editor_support/layout.py`
- `src/gui/perkey/editor.py`
- `src/gui/perkey/ui/lighting_areas.py` (new)
- `src/gui/perkey/secondary_lighting.py` (new)
- `src/tray/ui/menu.py`
- `src/tray/ui/_menu_sections_profile_power.py`

#### Tests

- row rendering from injected real and simulated inventories;
- all five simulated routes are visible;
- no panel on a keyboard-only system;
- checkbox and colour draft updates;
- route-specific picker target;
- setup-panel replacement/restoration;
- lightbar placement remains in Overlay Alignment;
- profile activation refreshes every row;
- unavailable saved state is retained;
- one preview failure does not affect other rows or the keyboard.

#### Exit criteria

- Static secondary state can be edited individually from the main profile editor.
- No secondary route is rendered as a keyboard key.

### Phase 4 — Make whole-profile Static authoritative

#### Work

1. Add the static/profile scene application service.
2. Extend runtime profile activation to load and apply secondary state.
3. Update tray menu activation and AC/battery activation call sites.
4. Apply saved state on:
   - startup/default profile activation;
   - editor Activate/Save preview;
   - uniform Static;
   - per-key Static;
   - stop animation;
   - switching away from animated output;
   - global Turn On;
   - resume/lid-open restore;
   - AC/battery profile transition.
5. Remove `software_effect_target` gating from Static application.
6. Filter animated secondary targets to profile-enabled routes.
7. While a software animation is running:
   - keyboard-only leaves enabled areas on their saved static colours;
   - keyboard + areas mirrors output only to enabled areas;
   - disabling a route turns it off and removes it from fan-out;
   - stopping restores saved static colours.
8. While globally forced off, accept profile/config changes but defer hardware I/O
   until restore.
9. Global Turn Off/On and power restore must operate on profile-owned areas regardless
   of the animated Effect output selection.

#### Primary files

- `src/core/profile/runtime_activation.py`
- `src/tray/controllers/effect_selection.py`
- `src/tray/controllers/_lighting_effect_coordination.py`
- `src/tray/controllers/lighting_controller.py`
- `src/tray/controllers/software_target_controller.py`
- `src/tray/controllers/_software_target_auxiliary.py`
- `src/tray/controllers/menu_adapters/__init__.py`
- `src/core/power/management/manager.py`
- relevant idle/suspend restore helpers

#### Tests

- Static applies routes while effect output is `keyboard`;
- uniform and per-key Static have identical secondary semantics;
- disabled routes stay off;
- animated fan-out includes enabled routes only;
- animation stop restores saved colours;
- hardware effects leave enabled areas at saved static colours;
- profile switching and AC/battery switching apply the whole scene;
- forced-off activation performs no hardware writes, then restores the new profile;
- one failing route does not block keyboard or sibling routes;
- transient and cached devices retain close/invalidation guarantees, including cache
  pruning and tray shutdown.

#### Exit criteria

- The issue #7 Static reproduction passes independently of Effect output.
- The active profile is the only Static source of truth.

### Phase 5 — Make editor writes observable to the tray

#### Work

1. Add a normalized immutable secondary-state signature to `ConfigApplyState`.
2. Include it in config-poller comparison/log state.
3. Add a `secondary_only` fast path.
4. In Static, reconcile enabled/colour changes immediately without restarting the
   keyboard mode.
5. During an animation, refresh restore state and target membership without
   unnecessarily restarting the keyboard effect.
6. Turn newly disabled animated routes off immediately.
7. While globally forced off, mark the config state handled without hardware I/O.
8. Treat isolated route failures as handled and throttle/log them so polling does not
   retry every cycle.

#### Primary files

- `src/tray/pollers/config_polling_internal/_config_apply_state.py`
- `src/tray/pollers/config_polling_internal/_fast_path.py`
- `src/tray/pollers/config_polling_internal/_post_fast_path_apply.py`
- `src/tray/pollers/config_polling_internal/core.py`
- `src/tray/pollers/config_polling_internal/helpers.py`

#### Tests

- secondary-only signature changes are detected;
- ordering differences do not change the normalized signature;
- static secondary-only apply does not restart the keyboard;
- animated enable/disable updates target membership correctly;
- forced-off changes produce no write and no retry storm;
- a failed route does not cause endless polling retries.

#### Exit criteria

- Saving a Lighting areas change in the editor process is observed and applied by the
  tray without requiring an unrelated keyboard/config change.

### Phase 6 — Clarify tray context and add editor safety

#### Tray work

1. Keep secondary rows as live device-context selectors, with Keyboard as the explicit
   return path. Do not use them as profile selectors.
2. Build context controls from route capabilities and brightness policy. Independent
   devices receive brightness; shared zones explicitly follow Keyboard.
3. Remove the separate **Software Targets / Effect output** submenu.
4. Add one checkable **Include enabled lighting areas** row at the bottom of
   **Software Effects**, without changing persisted compatibility keys:
   - unchecked = `keyboard`;
   - checked = `all_uniform_capable`.
5. Show the toggle whenever compatible routes exist, even when every area is currently
   disabled. Its placement inside Software Effects makes its scope explicit.
6. Remove the user-visible phrase `All Compatible Devices`.
7. Update diagnostics from `expected_tray_contexts` toward explicit physical context,
   effective route, and expected profile-editor-row reporting.
8. Reorganize the tray into: device selectors; Brightness Override and Lighting
   Profiles; Hardware Mode; Software Effects and global Effect Speed; Power Mode,
   Support Tools and Settings; then global Turn Off, Mode, and Quit.

#### Editor safety work

The editor currently has no dirty-state protection. Add one unified saved snapshot
rather than protecting only new secondary controls. Include:

- keyboard colours;
- keymap/layout state;
- lightbar overlay geometry;
- secondary lighting state.

A lazy comparison before destructive actions is sufficient for v1. Guard:

- activating another profile;
- deleting the active profile;
- closing the editor.

Reset the saved snapshot after Save, Activate, and New. When deleting the active
profile, load and activate the fallback profile rather than changing only the name.

#### Primary files

- `src/tray/ui/menu.py`
- `src/tray/ui/_menu_status_devices.py`
- `src/tray/ui/_menu_callbacks.py`
- `src/tray/controllers/software_target_controller.py`
- `src/core/effects/software_targets.py`
- `src/core/diagnostics/secondary_devices.py`
- `src/gui/perkey/ui/profile_actions.py`
- editor close handler and profile draft helpers

#### Tests

- keyboard-only tray has only the Keyboard context;
- secondary rows select their live-control context without changing the active profile;
- shared and independent brightness policies render different, truthful controls;
- the Software Effects fan-out toggle has correct wording, visibility, and checked state;
- persisted legacy target keys still load;
- dirty Activate/Delete/Close prompt;
- clean actions do not prompt;
- Save/New/Activate reset the baseline;
- deleting the active profile actually activates the fallback scene.

#### Exit criteria

- Every selector has one clear responsibility.
- Static individual control is discoverable in one authoritative surface.

### Phase 7 — Integrated validation and reporter handoff

#### Focused automated lane

Run the existing and new tests covering:

```bash
.venv/bin/python -m pytest -q \
  tests/core/config/test_secondary_device_accessors_unit.py \
  tests/core/diagnostics/devices/test_secondary_devices_snapshot_unit.py \
  tests/core/effects/rendering/test_effects_software_targets_unit.py \
  tests/core/profiles/core/test_profile_runtime_activation_unit.py \
  tests/gui/perkey/editor/core/test_perkey_profile_management_unit.py \
  tests/gui/perkey/editor/core/test_perkey_profile_actions_ui_unit.py \
  tests/tray/controllers/core/test_effect_selection_unit.py \
  tests/tray/controllers/power/test_tray_software_target_virtual_routes_unit.py \
  tests/tray/ui/menu/test_menu_sections_unit.py \
  tests/tray/ui/menu/test_menu_status_virtual_routes_unit.py
```

Add the new profile-storage, simulation-runtime, Lighting areas UI, static-scene, and
config-poller files to this command as they land.

Run simulation tests under the hardware tripwire:

```bash
KEYRGB_TEST_HARDWARE_TRIPWIRE=1 \
.venv/bin/python -m pytest -q -o addopts= \
  tests/core/test_secondary_device_runtime_unit.py \
  tests/gui/perkey/editor/core/test_lighting_areas_unit.py
```

Then run shared validation:

```bash
.venv/bin/python -m buildpython --profile=ci
.venv/bin/python -m buildpython --run-steps 17,19
```

Use `--profile=release` only when preparing a release candidate.

#### Manual simulation checklist

- Start with the simulation flag and confirm the visible warning.
- Confirm Lightbar, Mouse, Logo, Neon Strip, and Vents appear once each.
- Confirm a normal hardware run has no simulation labels.
- Toggle colour and enabled state for each row.
- Open/close Keyboard Setup and Overlay Alignment; confirm Lighting areas returns.
- Save two profiles with distinct area states, activate each, restart, and recheck.
- Assign different AC and battery profiles and exercise the transition.
- In Static, toggle **Include enabled lighting areas** and confirm the static scene does
  not change.
- In animation mode, compare the toggle unchecked and checked.
- Disable one area during animation and confirm only that simulated route turns off.
- Stop animation and confirm saved static colours return.
- Exercise global Turn Off/On and forced-off config changes.
- Generate a support bundle and confirm simulation is explicit and not reported as
  detected hardware.

#### Reporter hardware checklist

After simulation and automated gates pass, ask the issue #7 reporter to:

1. run the full installer for the candidate build;
2. set Logo, Neon Strip, and Vents to distinct static colours;
3. toggle each area independently;
4. save, switch, and reactivate two lighting profiles;
5. verify Static uniform and Static per-key both restore the saved area state;
6. verify **Include enabled lighting areas** unchecked and checked during animation;
7. stop the animation and confirm static colours return;
8. verify Turn Off/On, sleep/resume, and AC/battery profile restoration;
9. attach a fresh support bundle and targeted debug log.

Do not mark the backend or this UX hardware-verified from simulation alone.

#### Documentation to update after implementation

- `docs/1-src/11-multi-device-routing-and-targets.md`
- `docs/1-src/05-capabilities-and-ui.md`
- user-facing tray/editor wording in `README.md`
- issue #7 support/retest notes if a dedicated bug-report document is added
- this plan's status and completed phase checklist

## Test file inventory

Expected new tests:

- `tests/core/test_secondary_device_runtime_unit.py`
- `tests/core/profiles/core/test_profile_storage_secondary_lighting_unit.py`
- `tests/gui/perkey/editor/core/test_secondary_lighting_draft_unit.py`
- focused static-scene tests in the tray controller lane
- `tests/tray/controllers/core/test_secondary_static_scene_unit.py`
- `tests/tray/pollers/config/core/test_secondary_config_polling_unit.py`

Expected extensions:

- `tests/conftest.py`
- `tests/core/config/test_secondary_device_accessors_unit.py`
- `tests/core/diagnostics/devices/test_secondary_devices_snapshot_unit.py`
- `tests/core/effects/rendering/test_effects_software_targets_unit.py`
- `tests/core/profiles/core/test_profile_runtime_activation_unit.py`
- `tests/gui/perkey/editor/core/test_perkey_profile_management_unit.py`
- `tests/gui/perkey/editor/core/test_perkey_profile_actions_ui_unit.py`
- config-polling state-builder and fast-path tests
- `tests/tray/controllers/core/test_effect_selection_unit.py`
- `tests/tray/controllers/power/test_tray_software_target_virtual_routes_unit.py`
- `tests/tray/ui/menu/test_menu_sections_unit.py`
- `tests/tray/ui/menu/test_menu_status_virtual_routes_unit.py`

## Cross-cutting acceptance criteria

The implementation is complete only when all of these are true:

- [x] Keyboard-only systems retain the current editor and runtime behaviour.
- [x] All effective secondary routes come from one shared provider.
- [x] No production consumer bypasses the runtime provider for route acquisition.
- [x] Lighting profiles persist enabled/colour and optional independent-brightness
  state without destructive migration.
- [x] Explicit-empty and partial secondary components turn omitted known routes off
  while preserving unknown future route state.
- [x] Unknown and unavailable route state survives Save.
- [x] Lighting areas are visible in the main editor, not mapped onto keyboard cells.
- [x] Lighting-area rows explicitly select which area the shared colour wheel edits.
- [x] Independent-route brightness is editable in Lighting areas and standalone
  secondary colour actions persist it to the active profile.
- [x] Static applies the whole profile regardless of animated Effect output.
- [x] Animated fan-out includes enabled routes only.
- [x] Stopping an animation restores the profile scene.
- [x] Shared-brightness zones expose no false independent-brightness control.
- [x] Secondary-only editor writes are detected by the tray config poller.
- [x] A failing secondary route does not block the keyboard or sibling routes.
- [x] Virtual zones are not duplicated as physical-controller choices.
- [x] Animated fan-out is one explicit toggle inside Software Effects.
- [x] Simulation exposes all registered routes and cannot touch real secondary hardware.
- [x] Diagnostics clearly distinguish simulated, discovered, and virtual-parent routes.
- [x] Dirty profile actions are guarded.
- [x] Focused tests, CI profile, architecture validation, and exception transparency pass.
- [ ] Real hardware validation is completed separately before release claims.

## Suggested implementation/audit cadence

The implementation agent should deliver one phase at a time with:

1. the exact diff;
2. focused test output;
3. any deviation from this contract;
4. the next phase's dependency status.

The audit pass should review, in order:

1. profile compatibility and data preservation;
2. absence of direct hardware bypasses in simulation;
3. Static/effect-output separation;
4. shared-transport lifetime and error isolation;
5. tray/editor terminology and duplicate selectors;
6. focused and CI validation evidence.
