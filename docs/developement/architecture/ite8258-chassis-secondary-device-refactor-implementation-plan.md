# Implementation Plan: `ite8258-chassis` Secondary Device Architecture Refactor

## Status

Implemented on main as of 2026-06-07. All unit tests pass (2831 passed, 1 skipped).
Hardware validation with `scripts/debug/ite8258-chassis-zone-test.py` is the next step.

### Implemented (matches plan)

- `SharedHidrawTransportManager` with ref-counted proxies and per-backend write locking
- `HidrawTransportProxy` with automatic invalidation on HID errors
- `build_uniform_static_groups_for_leds()` for arbitrary LED-subset static groups
- `Ite8258ChassisZoneDevice` with zone-scoped `set_color` and `turn_off`
- Virtual routes (`logo`, `neon`, `vent`) registered in `SecondaryDeviceRoute`
- Tray context entries include virtual routes when parent backend is available
- Generic uniform-color menu builder fallback for unknown device types
- Software target fan-out includes virtual routes
- One-shot secondary-device actions close acquired devices in `finally`
- Cached software-target devices close on cache invalidation

### Implemented (deviates from revised plan)

- Per-zone brightness sliders are present in v1. The protocol's brightness command is
  global, so each slider controls the same underlying controller brightness. This is
  a UX limitation to validate on real hardware; if per-zone brightness is confirmed
  impossible, the sliders will be removed in a follow-up.
- `supports_independent_brightness` / `shares_primary_brightness` flags were not
  added. The existing `config_brightness_attr` / `config_color_attr` fields are used
  for zone state persistence.
- Zone `turn_off` writes black static groups for the zone LED subset instead of using
  the global `build_turn_off_report()` command, matching the revised plan.

### Not yet done

- Hardware smoke test on Lenovo Legion Pro 7 16IAX10H
- Confirm logo, neon, and vent all respond to independent color commands
- Confirm "All Compatible Devices" software target mirrors to all zones
- Version bump and release as 0.26.0 after hardware validation

## Purpose

This document is the implementation plan for exposing chassis-zone secondary devices from the `ite8258-chassis` backend. It follows `docs/developement/backends/ite8258/ite8258-chassis-correction-plan.md` and must land only after the protocol corrections in that document are complete and hardware-smoke tested.

## Scope

Expose four controllable lighting surfaces from a single `0x048d:0xc197` controller:

| Surface | Route Kind | Control Shape in v1 | Brightness Model |
|---------|------------|---------------------|------------------|
| Keyboard matrix | primary backend | existing keyboard/per-key path | authoritative global brightness |
| Logo | virtual secondary route | uniform color + on/off | shares keyboard/global brightness |
| Neon strip | virtual secondary route | uniform color + on/off | shares keyboard/global brightness |
| Vent groups | virtual secondary route | uniform color + on/off | shares keyboard/global brightness |

## Non-goals for v1

- No separate discovery candidates for logo, neon, or vent.
- No fake per-zone brightness sliders backed by per-zone config values.
- No per-zone hardware-effect surface beyond uniform-color fan-out.
- No multi-controller support. This plan assumes one active `ite8258-chassis` controller per process.

## Hard Constraints

1. One hidraw transport only. Keyboard and all chassis zones must share one transport handle.
2. Keyboard remains authoritative for global brightness and keyboard-only hardware effects.
3. Chassis zones are auxiliary uniform-color routes, not keyboard-like per-key devices.
4. One-shot tray actions must not leak device handles.
5. Cached software-target proxies must invalidate and close stale devices on recoverable failures.

## What Changes From The Earlier Draft

- Per-zone brightness is removed from the first release plan. The current controller protocol only proves global brightness.
- Zone power state is modeled explicitly as `enabled` plus `color`, rather than overloading brightness `0` as "off".
- Device lifetime is now part of the plan. The current secondary-device controller calls `route.get_device()` for one-shot actions and does not close the returned device, which is not acceptable once zone routes acquire shared transports.
- Virtual zone routes use unique route keys, but `get_backend()` still resolves to the real `Ite8258ChassisBackend`.

---

## Architecture Overview

### Current state

```
Tray UI -> selected keyboard backend -> one keyboard device -> one transport
```

Secondary devices already exist in the tray architecture, but they are discovered as separate auxiliary candidates and are treated as independently bright/dimmable uniform devices.

### Target state

```
Tray UI -> selected context
              |
              +-- keyboard -> Ite8258ChassisKeyboardDevice -> shared transport -> 0xc197
              +-- logo     -> Ite8258ChassisZoneDevice     -> shared transport -> 0xc197
              +-- neon     -> Ite8258ChassisZoneDevice     -> shared transport -> 0xc197
              +-- vent     -> Ite8258ChassisZoneDevice     -> shared transport -> 0xc197
```

The keyboard backend remains the only real hardware backend. Logo, neon, and vent are virtual auxiliary routes layered on top of that backend.

---

## Key Design Decisions

### 1. Shared brightness is a first-class constraint

The safe assumption today is that `SET_BRIGHTNESS` is global on `ite8258-chassis`. Because of that:

- zone routes must not persist their own brightness values
- zone menus must not show an independent brightness submenu
- zone restore logic must use current primary brightness
- zone "off" must be represented by saved route state, not by forcing brightness to zero

If later hardware validation proves per-zone brightness exists, that can be added in a follow-up plan without misleading users in v1.

### 2. Zone off/on must be stateful without mutating keyboard brightness

For lightbar, "off" is currently represented by brightness `0`. That does not work here because zone brightness is not independent.

For `ite8258-chassis` zones, route state must persist:

- `color`
- `enabled`

Turning a zone off writes a black static payload for that zone only, but does not change global brightness. Turning it back on restores the saved color using the current keyboard/global brightness.

### 3. Virtual zone routes use symbolic backend names

The new routes should use unique route identifiers such as:

- `ite8258-chassis-logo`
- `ite8258-chassis-neon`
- `ite8258-chassis-vent`

These are route keys, not backend-registry names. `route.get_backend()` for each of them must still return `Ite8258ChassisBackend()`.

This keeps:

- tray context selection stable
- uniform GUI route resolution stable
- software-target proxy cache keys collision-free

without pretending that there are multiple real backends behind `0xc197`.

### 4. Device lifetime must be explicit

This work should not rely on garbage collection to release HID transports.

- transient controller actions must `close()` their acquired device in `finally`
- cached software-target devices must call `close()` before being discarded
- the shared transport manager must own the underlying hidraw close, never the individual zone facade

---

## Component Design

### 1. Shared HID transport manager

**File:** `src/core/backends/shared_hidraw_transport.py` (new)

Create a small transport manager whose v1 scope is only what `ite8258-chassis` needs:

- open the hidraw transport once
- serialize feature-report writes
- reference-count logical consumers
- invalidate all proxies on terminal errors

Prefer the smallest viable API:

```python
class SharedHidrawTransportManager:
    def acquire(
        self,
        key: str,
        opener: Callable[[], HidrawFeatureOutputTransport],
    ) -> HidrawTransportProxy: ...

    def release(self, key: str, proxy: HidrawTransportProxy) -> None: ...
    def invalidate(self, key: str) -> None: ...
    def is_alive(self, key: str) -> bool: ...


class HidrawTransportProxy:
    def send_feature_report(self, report: bytes) -> int: ...
    def close(self) -> None: ...
    def is_alive(self) -> bool: ...
```

Implementation notes:

- Use `threading.RLock` for manager state and a per-entry `threading.Lock` for write serialization.
- Only expose methods actually used by the current backend. Do not add `write_output_report` until a caller exists.
- In v1, the manager can key by backend name because only one `ite8258-chassis` controller is supported. If multi-controller support appears later, change the key to a stable devnode identity.
- Split transport construction from probe metadata so the manager owns only the transport object, not `(transport, info)` tuples.

### 2. Arbitrary LED-subset static-group helper

**File:** `src/core/backends/ite8258_chassis/protocol.py`

Add a helper that builds static groups for an arbitrary LED subset, not just the keyboard matrix:

```python
def build_uniform_static_groups_for_leds(
    led_ids: Sequence[int],
    color: object,
) -> tuple[Ite8258ChassisGroup, ...]: ...
```

Requirements:

- validate `led_ids` is non-empty
- preserve 16-bit LED IDs
- use the same grouped-profile path as the keyboard static implementation

This helper is the core primitive for all zone writes:

- `set_color(zone, color)` -> save static groups for the zone LED IDs
- `turn_off(zone)` -> save static groups for the zone LED IDs using black

Do not use `build_turn_off_report()` for zones. That command is global and would shut off the whole controller surface.

### 3. `Ite8258ChassisZoneDevice`

**File:** `src/core/backends/ite8258_chassis/device.py`

Add a lightweight uniform-color facade:

```python
class Ite8258ChassisZoneDevice:
    def __init__(
        self,
        *,
        zone_name: str,
        led_ids: tuple[int, ...],
        transport: HidrawTransportProxy,
        profile_id: int = protocol.DEFAULT_PROFILE_ID,
    ) -> None: ...

    def set_color(self, color: tuple[int, int, int], *, brightness: int) -> None: ...
    def turn_off(self) -> None: ...
    def close(self) -> None: ...
```

Behavior:

- `set_color()` writes zone-scoped static groups and then sends the global brightness command using the supplied effective brightness.
- `turn_off()` writes zone-scoped black static groups only. It does not send global brightness `0`.
- `close()` releases the proxy back to the shared manager.

Intentionally omit a public `set_brightness()` from the first release. That prevents accidental controller wiring from treating zones as independently dimmable.

### 4. Route model extension

**File:** `src/core/secondary_device_routes.py`

Extend `SecondaryDeviceRoute` with explicit virtual-route and brightness semantics:

```python
@dataclass(frozen=True)
class SecondaryDeviceRoute:
    device_type: str
    backend_name: str
    display_name: str
    state_key: str
    get_backend: Callable[[], Any]
    get_device: Callable[[], Any]
    config_brightness_attr: str | None = None
    config_color_attr: str | None = None
    supports_uniform_color: bool = False
    supports_software_target: bool = False
    parent_backend_name: str | None = None
    zone_key: str | None = None
    supports_independent_brightness: bool = True
    shares_primary_brightness: bool = False
```

New zone routes:

```python
SecondaryDeviceRoute(
    device_type="logo",
    backend_name="ite8258-chassis-logo",
    display_name="Logo",
    state_key="ite8258_chassis_logo",
    get_backend=_get_ite8258_chassis_backend,
    get_device=_acquire_ite8258_chassis_logo,
    supports_uniform_color=True,
    supports_software_target=True,
    parent_backend_name="ite8258-chassis",
    zone_key="logo",
    supports_independent_brightness=False,
    shares_primary_brightness=True,
)
```

Notes:

- Leave `config_brightness_attr=None` and `config_color_attr=None` for the new zones. They should use `secondary_device_state` only; there is no legacy compatibility key to preserve.
- Existing lightbar and mouse routes keep their current behavior with the default `supports_independent_brightness=True`.

### 5. Secondary-device state model

**Files:** `src/core/config/_lighting/_secondary_device_accessors.py`, `src/tray/secondary_device_power.py`

Extend the generic secondary-device state entry to support `enabled`:

```python
{
    "secondary_device_state": {
        "ite8258_chassis_logo": {
            "enabled": true,
            "color": [255, 0, 0],
        }
    }
}
```

Add helpers:

- `get_secondary_device_enabled(...)`
- `set_secondary_device_enabled(...)`

Semantics:

- For routes with `supports_independent_brightness=True`, existing brightness-driven logic stays authoritative.
- For routes with `shares_primary_brightness=True`, `enabled` is authoritative for on/off and `config.brightness` is the effective brightness source.

No config migration is required. Old routes continue to work because:

- lightbar and mouse still use brightness
- zone routes are new state keys

### 6. Virtual route availability in tray context entries

**File:** `src/tray/ui/_menu_status_devices.py`

Continue to build keyboard and discovered auxiliary entries as today, then append virtual zone entries when the parent backend is available:

```python
for route in iter_virtual_routes():
    if _virtual_parent_available(route):
        entries.append(
            {
                "key": route.backend_name,
                "device_type": route.device_type,
                "backend_name": route.backend_name,
                "status": "supported",
                "text": f"{route.display_name}: Lenovo Chassis Zone",
            }
        )
```

Requirements:

- cache parent availability by `parent_backend_name` for the duration of one `device_context_entries()` call
- do not add duplicate entries
- if the selected context points at a virtual route that is no longer available, existing `selected_device_context_key()` fallback behavior should return the user to keyboard

### 7. Menu builder semantics

**File:** `src/tray/ui/_menu_sections_device_context.py`

Keep the generic uniform-device fallback, but only render the brightness submenu when the route truly supports it:

- if `route.supports_uniform_color` and `route.supports_independent_brightness` -> show `Color`, `Brightness`, `Turn On/Off`
- if `route.supports_uniform_color` and not `route.supports_independent_brightness` -> show `Color`, `Turn On/Off`

This is required so logo/neon/vent do not advertise a brightness model the hardware does not currently provide.

### 8. Transient controller device lifetime

**File:** `src/tray/controllers/secondary_device_controller.py`

This is a required robustness fix, not optional cleanup.

Change the one-shot path so it closes a transient device after use:

```python
def _with_secondary_device(...):
    device = route.get_device()
    try:
        operation(device)
    finally:
        close = getattr(device, "close", None)
        if callable(close):
            close()
```

Apply route-aware power semantics:

- brightness actions are valid only for `supports_independent_brightness=True`
- `turn_off` for shared-brightness routes sets `enabled=False` and writes zone-black
- `turn_on` for shared-brightness routes sets `enabled=True` and restores saved color using current primary brightness

Do not synthesize or persist a fake zone brightness value.

### 9. Cached software-target lifetime and invalidation

**Files:** `src/tray/controllers/_software_target_auxiliary.py`, `src/tray/controllers/software_target_controller.py`

`_CachedSecondarySoftwareTarget` currently invalidates its cached device by dropping the reference. That is not enough once the cached device owns a shared-transport proxy.

Required changes:

- add a `_close_cached_device()` helper
- call it on recoverable device failures before clearing `_device`
- expose a `close()` method so the cache can be pruned cleanly when routes disappear or the tray shuts down

Restore semantics for zone routes:

- if `enabled=False`, keep the zone off
- if `enabled=True`, restore saved color using current primary brightness
- if primary brightness is `0`, do not auto-bump it; keep the state enabled and dark

### 10. Uniform color GUI state helpers

**Files:** `src/gui/windows/_uniform_color_state.py`, `src/gui/windows/_uniform_color_bootstrap.py`

The uniform GUI is already target-aware, but its secondary-device brightness helpers assume a route owns its own brightness value. That is not safe for the new zones.

Required behavior for `shares_primary_brightness=True` routes:

- `current_brightness()` returns `config.brightness`
- `store_brightness()` becomes a no-op for the secondary route
- `ensure_brightness_nonzero()` must not silently raise keyboard brightness just because a zone color was edited

Preferred UX:

- if primary brightness is `0`, still persist the zone color
- show a status message that the zone uses keyboard/global brightness and will appear when the keyboard brightness is raised

### 11. Backend integration

**File:** `src/core/backends/ite8258_chassis/backend.py`

Add:

- a module-level shared transport manager accessor
- `get_zone_device(zone_key: str) -> Ite8258ChassisZoneDevice`
- keyboard `get_device()` path updated to acquire a managed proxy instead of opening a standalone transport

Important:

- both keyboard and zone devices must participate in the same manager
- backend probe/discovery behavior should remain unchanged
- `get_backend()` for virtual zone routes returns `Ite8258ChassisBackend()`, not a fake backend object

### 12. Diagnostics

**File:** none required in v1

Do not change discovery output for the initial implementation. The device-discovery snapshot should continue to show one `ite8258-chassis` candidate.

Possible follow-up after validation:

- add a `zones` field to the backend diagnostics report so support bundles can say `keyboard + logo + neon + vent`

---

## Implementation Phases

### Phase 1: transport and protocol primitives

Scope:

- add `SharedHidrawTransportManager`
- add arbitrary-LED static-group helper
- add focused unit tests for transport lifetime and zone packet generation

Exit criteria:

- multiple logical consumers can share the same transport
- invalidation closes the underlying transport exactly once
- zone static-group helper emits the exact LED IDs and packet framing expected

### Phase 2: route and state model

Scope:

- extend `SecondaryDeviceRoute`
- add `enabled` accessors to secondary-device state
- add virtual route iteration helpers

Exit criteria:

- existing lightbar/mouse tests stay green
- zone routes can persist color and enabled state without any brightness key

### Phase 3: controller lifetime and GUI-state fixes

Scope:

- close transient devices in `secondary_device_controller`
- close cached devices in `_CachedSecondarySoftwareTarget`
- update uniform GUI brightness helpers for shared-brightness routes

Exit criteria:

- no one-shot action leaks a device handle
- cached software targets release stale devices on recoverable failure
- zone GUI color edits do not silently modify keyboard brightness

### Phase 4: zone device and backend wiring

Scope:

- add `Ite8258ChassisZoneDevice`
- add `get_zone_device()` to `Ite8258ChassisBackend`
- move keyboard `get_device()` onto the shared manager

Exit criteria:

- keyboard and zones can coexist on the same transport
- closing one zone facade does not disrupt other active consumers

### Phase 5: tray, software-target, and power integration

Scope:

- surface virtual routes in tray context entries
- render correct per-route menus
- restore enabled zones correctly after software-target fan-out and power events

Exit criteria:

- logo/neon/vent appear only when the parent backend is available
- zone menus do not show brightness
- software-target restore honors `enabled` plus current primary brightness

### Phase 6: hardware validation

Scope:

- validate protocol-only zone writes first
- validate tray contexts second
- validate software-target and suspend/resume last

Exit criteria:

- independent zone color control works
- zone off/on does not shut off the keyboard
- no stale-handle or transport-corruption failures appear in repeated toggling

---

## Detailed Test Plan

### Core backend tests

**File:** `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py`

Add coverage for:

- `build_uniform_static_groups_for_leds()` on logo, neon, and vent LED IDs
- zone-device `set_color()` packet sequence
- zone-device `turn_off()` using zone-scoped black static groups
- shared transport manager ref counting and invalidation
- keyboard and zone devices sharing one managed transport

### Route and state tests

**Files:** `tests/core/config/test_secondary_device_accessors_unit.py`, `tests/tray/test_secondary_device_routes_unit.py` (new)

Add coverage for:

- `enabled` persistence for secondary-device state
- legacy brightness-driven routes remaining unchanged
- virtual route lookup by symbolic backend name
- `iter_virtual_routes()` returning only routes with `parent_backend_name`

### Tray and controller tests

**Files:** `tests/tray/ui/menu/test_menu_sections_unit.py`, `tests/tray/controllers/power/test_tray_secondary_device_controller_unit.py`, `tests/tray/controllers/power/test_tray_software_target_controller_unit.py`

Add coverage for:

- virtual routes appearing only when parent available
- zone menu items omitting `Brightness`
- transient controller actions calling `close()` exactly once
- shared-brightness route on/off using `enabled` instead of brightness
- cached secondary targets closing stale devices on invalidation
- restore logic using current primary brightness for enabled zones

### Uniform GUI tests

**File:** `tests/gui/windows/test_uniform_color_window_unit.py`

Add coverage for:

- secondary route resolution for symbolic zone backend names
- shared-brightness routes reading primary brightness
- zone color apply not writing a secondary brightness value
- `ensure_brightness_nonzero()` not auto-bumping keyboard brightness for shared-brightness routes

---

## Hardware Validation Order

### Step 1: protocol-only smoke test

Run a small script against `Ite8258ChassisBackend().get_zone_device(...)`:

1. set logo red
2. set neon green
3. set vent blue
4. turn each zone off individually
5. verify keyboard remains on throughout

Do this before any tray/UI validation.

### Step 2: tray context validation

1. open tray
2. confirm `Logo`, `Neon`, and `Vent` contexts appear only when `ite8258-chassis` is available
3. confirm each shows `Color` and `Turn On/Off`, but no `Brightness`
4. confirm turning one zone off does not darken the keyboard

### Step 3: software-target validation

1. enable `All Compatible Devices`
2. run a uniform software effect
3. confirm all enabled zones mirror the keyboard's representative color
4. switch back to keyboard-only target
5. confirm each enabled zone restores its saved color

### Step 4: power lifecycle validation

1. suspend/resume
2. lid-close event if available
3. AC/battery transitions if those paths are active on the test machine

Verify:

- enabled zones restore
- disabled zones stay off
- keyboard brightness remains authoritative

---

## Risks And Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Pretending brightness is per-zone when it is global | confusing UI and broken restore behavior | do not ship per-zone brightness in v1 |
| One-shot controller actions leak device handles | ref-count never returns to zero; stale transports persist | close transient devices in `finally` |
| Cached software targets drop devices without closing them | shared transport ref-count leak | close cached device on invalidation and cache pruning |
| Zone off/on uses global turn-off command | keyboard unexpectedly powers off | use zone-scoped black static groups only |
| Virtual routes collide with future route names | wrong target or cache reuse | use unique symbolic `backend_name` keys per zone |
| Primary brightness is zero when a zone is re-enabled | user sees no visible change and thinks restore failed | persist enabled state and color, but do not auto-bump brightness; surface a clear status message in GUI where possible |
| Future multi-controller support arrives | backend-name keyed transport manager becomes ambiguous | document the single-controller assumption and switch to devnode-keyed manager if needed |

---

## Release Guidance

Do not lock the version number in this plan. Cut the release only after hardware validation passes end to end. Update:

- `README.md`
- `AGENTS.md`
- backend support docs under `docs/developement/backends/ite8258/`

only after the zone names and shared-brightness behavior are confirmed on real hardware.

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-07 | Do not ship per-zone brightness in v1 | The live protocol only proves global brightness, and brightness-driven zone state would break restore/power semantics |
| 2026-06-07 | Model zone power as `enabled` plus `color` | Zone off/on must not mutate keyboard brightness |
| 2026-06-07 | Close every transient secondary device explicitly | Shared transports make lifetime leaks materially risky |
| 2026-06-07 | Use symbolic route backend names for virtual zones | Needed for stable tray contexts and uniform GUI targeting without inventing fake registry backends |
