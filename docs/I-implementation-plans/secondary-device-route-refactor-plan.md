# Secondary Device Route Refactor Plan — Virtual Zone Routes

## Status

Draft — awaiting review before implementation.

## Context

The `ite8258-chassis` backend (`0x048d:0xc197`, Lenovo Legion Pro 7 Gen10) controls four independent lighting surfaces through a single USB controller:

| Surface | LED IDs | Count |
|---------|---------|-------|
| Keyboard matrix | `KEYBOARD_LED_IDS` | 101 |
| Logo | `LOGO_LED_IDS` (0xDD) | 1 |
| Neon strip | `NEON_LED_IDS` (0xF5–0xFE) | 10 |
| Vent groups | `VENT_LED_IDS` (0xE9–0xFA) | 18 |

KeyRGB's secondary-device architecture (`SecondaryDeviceRoute`) currently assumes **one backend = one physical USB device**. The `ite8233` lightbar is the reference implementation, and it is a completely separate USB controller (`0x048d:0x7000/0x7001`). There is no mechanism for a single backend to vend multiple zone-level secondary devices.

This document is the implementation plan for refactoring the route table and related layers to support **virtual subdevice routes** — multiple tray-selectable, config-persisted, software-target-routable devices that share a single backend transport.

## Goals

1. **Backward compatibility** — existing `ite8233` lightbar and `sysfs-mouse` routes must continue to work unchanged
2. **Hardware safety** — shared transport must be reference-counted, thread-safe, and fail consistently across all zone devices
3. **Incremental delivery** — each phase lands independently and is testable without full chassis-zone parity
4. **No discovery rework (initially)** — virtual routes appear in the tray based on static registration + runtime backend availability, not USB discovery

## Non-Goals

- Renaming the existing `99-ite8291-wootbook.rules` udev file (deferred to 1.0)
- Adding per-zone software effects (each zone receives uniform color only, same as lightbar today)
- Adding hardware effects for chassis zones
- Supporting non-ITE backends in the shared-transport manager (keep it scoped to hidraw for now)

---

## Current State Analysis (from agent surveys)

### Route table (`src/core/secondary_device_routes.py`)

- `SecondaryDeviceRoute` has 10 fields: `device_type`, `backend_name`, `display_name`, `state_key`, `get_backend`, `get_device`, `config_brightness_attr`, `config_color_attr`, `supports_uniform_color`, `supports_software_target`
- Static `_ROUTES` tuple of exactly 2 entries: `lightbar` → `ite8233`, `mouse` → `sysfs-mouse`
- Looked up by `device_type`, `backend_name`, or `context_entry`
- Consumed by: tray menu builders, software target controller, secondary device controller, config accessors, GUI bootstrap, power management, effect engine fan-out

### Transport ownership

- Every `get_device()` call opens a **fresh** OS file descriptor
- **No thread safety** around HID writes (`fcntl.ioctl` / `os.write` are unguarded)
- Device facades store `transport` only for `close()`; runtime I/O goes through injected callables
- `ite8233` lightbar opens its own hidraw node — **not** a shared-transport model

### Discovery

- `DEVICE_TYPES_BY_USB_KEY` maps one `(vid, pid)` → one `device_type`
- One backend probe → one discovery candidate
- Tray renders one "keyboard" header + non-keyboard candidates from discovery
- No mechanism for a single USB device to surface as multiple tray contexts

### Menu builders

- `_DEVICE_CONTEXT_MENU_BUILDERS` is a `dict[str, _DeviceContextMenuBuilder]` keyed by `device_type`
- Only `"lightbar"` and `"mouse"` have registered builders
- Unknown device types get a disabled generic placeholder

---

## Proposed Architecture

### Design decision: extend `SecondaryDeviceRoute` with an optional parent marker

Rather than replacing the route table, we extend it with two optional fields:

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
    # NEW:
    parent_backend_name: str | None = None
    zone_key: str | None = None
```

- `parent_backend_name` indicates this route is a **virtual zone route** that shares transport with the named parent backend
- `zone_key` is an opaque identifier passed to the parent backend's zone-device factory
- Existing routes (`lightbar`, `mouse`) leave both as `None` — no behavioral change

### Design decision: introduce `SharedHidrawTransportManager`

A new module `src/core/backends/shared_hidraw_transport.py` provides:

```python
class SharedHidrawTransportManager:
    """Reference-counted, thread-safe hidraw transport sharing."""

    def acquire(self, backend_name: str, opener: Callable[[], HidrawFeatureOutputTransport]) -> _LockedTransportProxy:
        """Return a proxy for this backend's transport, opening it if needed. Increment ref-count."""

    def release(self, backend_name: str) -> None:
        """Decrement ref-count. Close transport when count hits zero."""

    def invalidate(self, backend_name: str) -> None:
        """Force-close transport and reset state (used on disconnect/permission errors)."""
```

- One manager instance per process (singleton or owned by the effects engine)
- `acquire()` is called by zone-route `get_device()` factories
- `release()` is called by zone device `close()` (which becomes a no-op close of the actual transport, just decrements the ref)
- A `threading.Lock` wraps `send_feature_report` / `write_output_report` on the proxy
- If any write fails with `ENODEV` or permission error, `invalidate()` marks the transport dead for all consumers

### Design decision: backend exposes a zone-device factory

The `ite8258-chassis` backend gains:

```python
def get_zone_device(self, zone_key: str, transport_proxy: _LockedTransportProxy) -> UniformColorDeviceProtocol:
    if zone_key == "logo":
        return Ite8258ChassisZoneDevice(
            transport_proxy.send_feature_report,
            led_ids=protocol.LOGO_LED_IDS,
            transport=transport_proxy,
        )
    elif zone_key == "neon":
        ...
    elif zone_key == "vent":
        ...
    else:
        raise ValueError(f"Unknown zone: {zone_key}")
```

`Ite8258ChassisZoneDevice` is a lightweight facade implementing:
- `set_color(color, *, brightness)` → builds `build_uniform_static_groups()` with its own `led_ids`
- `turn_off()` → sends off packet for its LED set
- `set_brightness(brightness)` → sends brightness report
- `close()` → calls `transport_proxy.release()` (decrements ref, does NOT close underlying fd)

### Design decision: static virtual routes, no discovery changes

Virtual routes are registered statically in `secondary_device_routes.py`:

```python
SecondaryDeviceRoute(
    device_type="logo",
    backend_name="ite8258-chassis-logo",
    display_name="Logo",
    state_key="ite8258_chassis_logo",
    get_backend=_get_ite8258_chassis_backend,
    get_device=_acquire_ite8258_chassis_logo,
    config_brightness_attr="ite8258_chassis_logo_brightness",
    config_color_attr="ite8258_chassis_logo_color",
    supports_uniform_color=True,
    supports_software_target=True,
    parent_backend_name="ite8258-chassis",
    zone_key="logo",
)
```

The tray's `device_context_entries()` is updated to:
1. Always include the static "keyboard" entry
2. Append discovery candidates (unchanged)
3. **NEW:** Append virtual routes whose `parent_backend_name` backend is available (probe returns `available=True`)

This avoids touching the discovery pipeline entirely.

### Design decision: generic uniform-color menu builder

Instead of adding builders for `"logo"`, `"neon"`, `"vent"`, we generalize the existing uniform builder:

```python
_DEVICE_CONTEXT_MENU_BUILDERS: dict[str, _DeviceContextMenuBuilder] = {
    "lightbar": _build_lightbar_context_menu_items,
    "mouse": _build_uniform_secondary_context_menu_items,
    # NEW — catch-all for any uniform-color secondary device:
    "_uniform": _build_uniform_secondary_context_menu_items,
}
```

The dispatcher falls back to `"_uniform"` when `route.supports_uniform_color` is True and no specific builder is registered.

---

## Implementation Phases

### Phase 1: Shared transport manager (no tray changes)

**Scope:**
- Create `src/core/backends/shared_hidraw_transport.py` with `SharedHidrawTransportManager` and `_LockedTransportProxy`
- Add unit tests: acquire/release ref-counting, thread-safe concurrent writes, invalidation on error, idempotent close
- No consumers yet — the module is dormant

**Validation:**
- `python -m buildpython --profile=release` passes
- New unit tests cover ref-count edge cases (acquire twice, release twice, invalidate while held)

### Phase 2: Backend zone-device factory + protocol variants

**Scope:**
- Add `Ite8258ChassisZoneDevice` to `src/core/backends/ite8258_chassis/device.py`
- Add `get_zone_device()` to `Ite8258ChassisBackend`
- Extend protocol builders to accept arbitrary `led_ids` instead of hardcoding `KEYBOARD_LED_IDS`:
  - `build_uniform_static_groups_for_leds(led_ids, color)`
  - `build_turn_off_report_for_leds(led_ids, profile_id=...)`
- Add unit tests for zone packet builders and zone device facade

**Validation:**
- Packet-builder tests prove logo/neon/vent LED IDs produce correct bytes
- Zone device tests prove `set_color` / `turn_off` send the right packets

### Phase 3: Route table extension + static virtual routes

**Scope:**
- Add `parent_backend_name` and `zone_key` to `SecondaryDeviceRoute` (optional, defaults `None`)
- Register static virtual routes for `ite8258-chassis-logo`, `ite8258-chassis-neon`, `ite8258-chassis-vent`
- Implement `_acquire_ite8258_chassis_logo()` etc. using `SharedHidrawTransportManager`
- Update `device_context_entries()` to include available virtual routes
- Update menu builder dispatcher to fall back to generic uniform builder
- Add config defaults for new `state_key`s

**Validation:**
- Existing lightbar/mouse tests still pass unchanged
- New tests verify virtual routes appear in tray entries when parent backend is available
- New tests verify virtual routes are absent when parent backend is unavailable

### Phase 4: Software target + power integration

**Scope:**
- Verify `_CachedSecondarySoftwareTarget` works with virtual routes (it should — `route.get_device()` is the only interface it uses)
- Verify power turn-off / restore paths handle virtual routes correctly
- Verify "All Compatible Devices" mode fans out uniform color to logo/neon/vent
- Add integration tests for software-target fan-out with virtual routes

**Validation:**
- Software target controller tests cover virtual route proxies
- Power management tests verify all zones turn off on lid close / suspend

### Phase 5: Hardware validation on Legion Pro 7

**Scope:**
- Ask the issue reporter to test each zone independently:
  - Logo: set to red, confirm lid logo lights up
  - Neon: set to green, confirm front strip lights up
  - Vent: set to blue, confirm side/rear vents light up
- Collect fresh diagnostics bundle
- Verify no transport corruption when switching between zones rapidly

**Exit criteria:**
- All four surfaces are independently controllable from the tray
- "All Compatible Devices" mode applies uniform color to all surfaces
- No regressions in keyboard-only mode

---

## Files to Modify (by phase)

### Phase 1
- `src/core/backends/shared_hidraw_transport.py` **(new)**
- `tests/core/backends/test_shared_hidraw_transport_unit.py` **(new)**

### Phase 2
- `src/core/backends/ite8258_chassis/device.py`
- `src/core/backends/ite8258_chassis/backend.py`
- `src/core/backends/ite8258_chassis/protocol.py`
- `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py`

### Phase 3
- `src/core/secondary_device_routes.py`
- `src/tray/ui/_menu_status_devices.py`
- `src/tray/ui/_menu_sections_device_context.py`
- `src/core/config/defaults.py`
- `tests/tray/ui/menu/test_menu_sections_unit.py`
- `tests/tray/test_secondary_device_routes_unit.py` **(new)**

### Phase 4
- `src/tray/controllers/software_target_controller.py` *(verify, likely no changes needed)*
- `src/tray/controllers/_software_target_auxiliary.py` *(verify)*
- `src/tray/controllers/secondary_device_controller.py` *(verify)*
- `tests/tray/controllers/power/test_tray_software_target_controller_unit.py`
- `tests/tray/controllers/power/test_tray_secondary_device_controller_unit.py`

### Phase 5
- No code changes — validation only
- Update `../../Z-legacy/implementation plans/ite8258-chassis-backend-plan.md` with findings

---

## Test Plan

| Layer | What to test | Where |
|-------|-------------|-------|
| Transport manager | Ref-counting, thread safety, invalidation, idempotent close | `tests/core/backends/test_shared_hidraw_transport_unit.py` |
| Protocol | Zone-specific packet builders produce correct bytes for logo/neon/vent LED IDs | `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py` |
| Device facade | Zone device `set_color`, `turn_off`, `set_brightness` send expected reports | `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py` |
| Route table | Existing routes unchanged; virtual routes resolve correctly | `tests/tray/test_secondary_device_routes_unit.py` |
| Tray entries | Virtual routes appear when parent available; absent when unavailable | `tests/tray/ui/menu/test_menu_sections_unit.py` |
| Menu builders | Generic uniform builder renders Color/Brightness/Turn Off for unknown device types | `tests/tray/ui/menu/test_menu_sections_unit.py` |
| Software targets | Virtual routes receive uniform color in "All Compatible Devices" mode | `tests/tray/controllers/power/test_tray_software_target_controller_unit.py` |
| Power management | All zones turn off on lid close / suspend; restore on resume | `tests/tray/controllers/power/test_tray_secondary_device_controller_unit.py` |
| Config | Brightness/color persistence for new state keys | `tests/core/config/test_secondary_device_accessors_unit.py` |
| Integration | Full buildpython release profile passes | CI / local `buildpython --profile=release` |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Thread-safety bugs in shared transport** | Corrupt HID packets, controller lockup | Lock around every `send_feature_report`; add stress tests with concurrent writes |
| **Transport leak** | Zombie file descriptors, unable to reopen device | Strict ref-counting with `weakref` finalizer fallback; audit all `close()` paths |
| **Backward compatibility break** | Lightbar/mouse stop working | Existing routes use `parent_backend_name=None` and bypass the manager entirely; extensive regression tests |
| ** premature transport close** | One zone's `close()` kills transport for all zones | Zone devices call `proxy.release()`, not `transport.close()`; only manager closes the fd |
| **Discovery confusion** | Diagnostics show duplicate `0xc197` entries | Virtual routes bypass discovery; only one candidate per PID in diagnostics |
| **Config migration** | Old installs lack new state keys | Config defaults handle missing keys gracefully; no migration needed |
| **Hardware damage** | Sending wrong packets to `0xc197` bricks the controller | Protocol builders already validated against OpenRGB; unit tests lock packet shapes |

---

## Open Questions

1. **LED ID overlap:** `VENT_LED_IDS` and `NEON_LED_IDS` overlap at `0xF5–0xFA`. Is this correct upstream, or do we need to reconcile with OpenRGB source?
2. **Brightness model:** Does the `0xc197` controller have per-zone brightness, or is brightness global (one brightness register for all LEDs)? If global, zone-specific brightness sliders would need to be software-scaled color values.
3. **Vent grouping:** Are the 18 vent LEDs independently addressable, or are they grouped into fewer logical zones? The current constants treat them as 18 individual LEDs.
4. **`0xc193` companion device:** Should we eventually model this as a separate backend, or does `0xc197` truly control all surfaces?

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-03 | Extend `SecondaryDeviceRoute` rather than replace | Minimizes blast radius; existing lightbar/mouse routes work unchanged |
| 2026-06-03 | Static virtual routes, no discovery changes | Discovery pipeline is USB-device-centric; refactoring it is high-risk and unnecessary for first milestone |
| 2026-06-03 | Shared transport manager as singleton | All zone routes for one backend share one fd; prevents fd exhaustion and concurrent-write corruption |
| 2026-06-03 | Generic uniform menu builder fallback | Avoids N menu builders for N zone types; any uniform-color route gets Color/Brightness/On/Off automatically |
