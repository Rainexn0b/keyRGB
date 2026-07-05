# Backend naming convention and reference

This document defines the naming convention for KeyRGB backends and serves as
a quick reference for what each backend does and why it is named the way it is.

## Naming convention

```
ITE<chip>_<capability>[_<capability>...][_<oem>]
```

| Position | Meaning | Examples |
|----------|---------|----------|
| `ITE<chip>` | Silicon / controller family driving the LEDs | `ITE8295`, `ITE8258`, `ITE8291` |
| `<capability>` | Lighting abstraction this backend exposes | `perkey`, `zones`, `chassis`, `uniform`, `lightbar` |
| `[<capability>...]` | Optional second capability if one HID interface exposes multiple color targets | `chassis_zones` |
| `[<oem>]` | Manufacturer-specific wiring/quirk variant | `lenovo`, `wootbook` |

Capabilities, when combined, are ordered: **`chassis` > `zones` > `perkey`**.

### Capability definitions

| Suffix | Meaning |
|--------|---------|
| `_perkey` | Every key is individually addressable |
| `_zones` | Keyboard deck has 2+ controllable zones, but not per-key |
| `_uniform` | Entire keyboard is one single color |
| `_chassis` | Non-keyboard lighting (logo, vents, neon strips) |
| `_lightbar` | A separate lightbar strip device |

### Separator policy

All ITE backend names use **underscores** exclusively. Non-ITE backends
(`sysfs-leds`, `sysfs-mouse`, `asusctl-aura`) retain hyphens since they do
not follow the `ITE<chip>` convention.

### Non-ITE backends

Backends that are not ITE-silicon-specific use descriptive tool/subsystem names:

- `sysfs-leds` — generic sysfs LED subsystem backend.
- `sysfs-mouse` — sysfs LED backend for external mice.
- `asusctl-aura` — CLI wrapper around the `asusctl` tool for ASUS Aura.

### One backend vs. two backends

- **Combine** when a single HID interface exposes multiple color targets with
  the same protocol and probe logic.
- **Split** when the capabilities require different protocols, different HID
  interfaces, or different probe behavior.

## Current backend inventory

| Backend name | Directory | Chip | Capability | Stability | Notes |
|---|---|---|---|---|---|
| `asusctl-aura` | `asusctl/` | N/A (CLI) | zones (virtual) | VALIDATED | Wraps `asusctl` CLI; supports virtual per-key via zone bucketing. |
| `ite8291r3_perkey` | `ite8291r3_perkey/` | ITE 8291 rev 0.03 | perkey | VALIDATED | USB control-transfer protocol. |
| `ite8910_perkey` | `ite8910_perkey/` | ITE 8910 | perkey | VALIDATED | Per-key HID backend. |
| `ite8291_perkey` | `ite8291_perkey/` | ITE 8291 | perkey | EXPERIMENTAL | Native HID feature-report variant. |
| `ite8291_zones` | `ite8291_zones/` | ITE 8291 | zones | EXPERIMENTAL | 4-zone variant via tuxedo-drivers protocol. |
| `ite8258_zones` | `ite8258_zones/` | ITE 8258 | zones (24) | EXPERIMENTAL | 24-zone keyboard controller. |
| `ite8258_chassis` | `ite8258_chassis/` | ITE 8258 | chassis | EXPERIMENTAL | Composite chassis lighting (Lenovo Legion Pro 7 Gen10). Exposes logo/neon/vent zones. |
| `ite8295_zones` | `ite8295_zones/` | ITE 8295 | zones (4) | EXPERIMENTAL | Lenovo Legion/IdeaPad 4-zone family. Covers PIDs `0xC955/0xC963/0xC965/0xC973/0xC975/0xC984/0xC985`. |
| `ite8233_lightbar` | `ite8233_lightbar/` | ITE 8233 (HID-reported) | lightbar | EXPERIMENTAL | Clevo lightbar. OpenRGB calls this "ITE 8291 rev 0.03" but the device's own HID descriptor reports "ITE Device(8233)". |
| `ite8297_uniform` | `ite8297_uniform/` | ITE 8297 | uniform | EXPERIMENTAL | Uniform-color sysfs/hidraw backend. |
| `sysfs-leds` | `sysfs/` | N/A (sysfs) | zones/uniform | VALIDATED | Generic sysfs LED subsystem; handles Tuxedo/Clevo/System76 multi-intensity and ITE 8297 channel LEDs. |
| `sysfs-mouse` | `sysfs_mouse/` | N/A (sysfs) | uniform | EXPERIMENTAL | Auxiliary sysfs LED backend for external mice. |

## Deprecated aliases

Backends that have been renamed maintain backward-compatible aliases so
existing user config (`KEYRGB_BACKEND`, saved profiles) continues to work.

| Old name | Canonical name |
|---|---|
| `ite8291r3` | `ite8291r3_perkey` |
| `ite8910` | `ite8910_perkey` |
| `ite8291` | `ite8291_perkey` |
| `ite8291-zones` | `ite8291_zones` |
| `ite8258` | `ite8258_zones` |
| `ite8258-chassis` | `ite8258_chassis` |
| `ite8295-zones` | `ite8295_zones` |
| `ite8233` | `ite8233_lightbar` |
| `ite8297` | `ite8297_uniform` |

Aliases are resolved in `registry.py::_BACKEND_NAME_ALIASES`. When a user
sets `KEYRGB_BACKEND=<old_name>`, `select_backend()` transparently resolves
to the canonical backend.

### Adding a new alias

1. Change the backend's `name` attribute to the canonical name.
2. Add `"old_name": "canonical_name"` to `_BACKEND_NAME_ALIASES` in `registry.py`.
3. Update any internal references that check for the old name string.
4. Add a row to the table above.
5. After one release cycle, the alias can be removed if desired.

## Backend-specific clarifications

### ite8233_lightbar — chip identity ambiguity

OpenRGB's `ClevoLightbarController` header says "Driver for Clevo laptop
lightbar (ITE 8291 rev 0.03)". However, the device's own HID descriptor
reports the name as `"ITE Device(8233)"`. KeyRGB uses `ite8233` because the
HID-reported name is concrete evidence. If future hardware diagnostics prove
the chip is actually an ITE 8291 variant, this should be renamed to
`ite8291_lightbar` or `ite8291_lb`.

See `docs/audit/10-ite8233.md` for the full audit.

### ite8233_lightbar — usage page discrepancy

KeyRGB documents `VENDOR_USAGE_PAGE = 0xFF89` (from issue #5 descriptors).
OpenRGB's detector for PID `0x7001` uses `0xFF03`. This does not affect
hidraw matching (which is VID/PID-only) but the probe identifiers may be
misleading. Verify against real descriptors before changing.

### ite8233_lightbar — scan mode unimplemented

`MODE_SCAN = 0x06` is defined because OpenRGB exposes it, but KeyRGB does
not implement a scan effect. The 7-slot color behavior for KeyRGB's
multi-slot protocol is unconfirmed.

### ite8291_perkey vs. ite8291r3_perkey — transport split

Both target ITE 8291-family devices but use different transports:
- `ite8291r3_perkey`: USB control transfers (canonical with `pobrn/ite8291r3-ctl`).
- `ite8291_perkey`: native HID feature reports.

These are kept as separate backends because the probe logic and packet
format differ.

### ite8258_zones vs. ite8258_chassis — capability split

The ITE 8258 chip is used in Lenovo Legion Gen10 laptops with two distinct
lighting targets:
- **Keyboard** (24 zones) → `ite8258_zones`
- **Chassis** (logo/neon/vent) → `ite8258_chassis`

These are split because they use different HID interfaces and probe logic,
even though they share the same chip. The `ite8258_chassis` backend also
exposes secondary device routes for individual chassis zones:
- `ite8258-chassis-logo`
- `ite8258-chassis-neon`
- `ite8258-chassis-vent`

These compound route names retain hyphens because they are zone identifiers,
not backend names.

### sysfs-leds — multi-driver coverage

The `sysfs-leds` backend handles multiple unrelated kernel LED drivers:
- Tuxedo/Clevo `multi_intensity` (RGB multicolor class)
- System76 `color_left/center/right/extra` attributes
- ITE 8297 channel LEDs (`ite_8297:1/2/3`)

This is correct because all use the sysfs LED class interface, but the
backend is more of a "sysfs LED aggregator" than a single-chip driver.

### Shared hidraw modules

Several backends depend on hidraw transport modules from other backends:
- `ite8291_perkey/hidraw.py` — used by `ite8291_zones`, `ite8295_zones`, `ite8258_zones`, `ite8258_chassis`.
- `ite8910_perkey/hidraw.py` — used by `ite8233_lightbar`, `ite8297_uniform`.

These cross-dependencies exist because the hidraw transport logic is
transport-specific (not chip-specific) and was originally implemented in
the first backend that needed it.
