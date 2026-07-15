# Multi-device Routing and Effect Output

## Goal

Support auxiliary lighting devices without forcing them into keyboard-only tray,
GUI, or effects abstractions.

## Why this exists

KeyRGB started with a single keyboard-focused surface. Auxiliary devices such as
an ITE lightbar need their own state, menu actions, and software-effect routing
without destabilizing keyboard behavior.

## Current owner modules

- `src/core/secondary_device_routes.py` — declarative route/capability registry
- `src/core/secondary_device_runtime.py` — availability, acquisition, and simulation
- `src/core/secondary_lighting_state.py` — shared profile/config state interpretation
- `src/core/profile/` — persistent whole-scene profile component
- `src/tray/ui/menu_status.py`
- `src/tray/ui/menu.py`
- `src/tray/controllers/secondary_device_controller.py`
- `src/tray/controllers/secondary_static_scene.py`
- `src/tray/controllers/software_target_controller.py`
- `src/core/diagnostics/secondary_devices.py`
- `src/gui/perkey/secondary_lighting.py`
- `src/gui/windows/uniform.py`

## Architecture flow

```text
route registry
    -> effective runtime inventory (real or simulated)
        -> tray selectors / editor rows / diagnostics

profile storage <-> normalized config mirror
        -> shared secondary state interpretation
            -> static scene renderer
            -> animated target filter and restore
            -> per-device live controls
```

The route registry describes what a device can do; it never owns mutable state.
The runtime inventory decides what is currently available; it never decides profile
policy. Profiles own the persistent scene, while config is the cross-process mirror
and backward-compatibility source. Static and animated renderers consume the same
state interpretation but remain separate output paths.

## Current model

1. Device discovery can surface auxiliary devices separately from the keyboard.
2. The rows at the top of the tray select a live-control device context. They are
   not a second profile selector: profiles remain whole-scene state in the editor.
3. The Lighting Profile Editor is the authoritative surface for profile-owned
   secondary state. Each lighting-area row can explicitly take ownership of the
   shared colour wheel; selecting a keyboard key returns it to per-key editing.
   The editor remains available for uniform or zoned primary keyboards when an
   available profile-compatible secondary route exists.
4. The Software Effects menu has an **Include enabled lighting areas** toggle;
   unchecked renders to the keyboard only, while checked also fans out to enabled areas.
5. Static profile state remains distinct from animated output selection.
6. Brightness routing is explicit: standalone devices may be independent, composite
   chassis zones follow the keyboard/controller brightness, and software effect speed
   remains one global render setting.
7. `src/core/secondary_lighting_state.py` owns interpretation of profile/config area
    state, including legacy brightness-to-enabled fallback. Runtime consumers must not
    duplicate those coercion rules.

## Secondary scene authority

Two helpers with different jobs must not be confused:

| Helper | Module | Role |
|---|---|---|
| `authoritative_payload_from_config` | `secondary_static_scene` | Is the config mirror a complete explicit profile scene? |
| `legacy_snapshot_from_config` | `secondary_lighting_state` | Build a non-persistent compatibility snapshot from legacy accessors |

Authority uses the **registered** profile-capable route catalog, not current device
availability. Reading legacy state never creates or rewrites profile files.

| State | Meaning |
|---|---|
| Active profile component present, even empty or partial | Authoritative; omitted registered routes are off |
| Config mirror has every registered profile route with explicit `enabled` | Materialized authoritative mirror |
| Config mirror is empty, partial, or lacks `enabled` | Legacy source; build a non-persistent compatibility snapshot |
| Unknown route entries | Preserve, but do not count toward known-route completeness |
| Newly registered route | Old mirror is compatibility state until profile activation materializes the route disabled |

When a new profile-capable route is registered, release notes must mention that older
mirrors become temporary compatibility state until the next profile activation merges
the new route as `enabled: false`.

## Design rules

1. Keyboard logic stays authoritative for keyboard-only features.

Per-key editing, keymaps, and input-reactive behavior should not be diluted by
secondary-device concerns.

2. Auxiliary devices should plug in through explicit routing points.

Menu sections, controller handlers, and software-effect targets should be
selected by device type rather than ad-hoc conditionals spread through the main
keyboard path.

3. Uniform output is the default cross-device bridge.

Software effects may mirror a representative uniform output to compatible
auxiliary devices, but they should not force auxiliary devices into the
keyboard's per-key engine model.

## Current example

The lightbar path is the first auxiliary-device architecture consumer:

- tray status and diagnostics inventory
- independent lightbar brightness and color config
- dedicated uniform-color target routing
- Lighting Profile Editor lightbar placement and Lighting areas state

## Testing

- Tray tests for context selection and per-context menu rendering
- Controller tests for lightbar actions and software-target policy
- GUI tests for target-aware uniform windows and lightbar placement controls

## Composite controllers

Some logical routes are independent in the product model but share one physical
profile namespace. The Lenovo c197 Keyboard, Logo, Neon, and Vent routes are the
first example. Their logical route model remains unchanged; a backend-local
coordinator translates the independent updates into complete physical commits.

See [Composite Controller Profile Coordination](12-composite-profile-coordination.md)
for the reference invariants, current limitations, and extraction rule.
