# Backend naming convention and reference

This document defines the naming convention for KeyRGB backends and serves as
a quick reference for what each backend does and why it is named the way it is.

## Naming convention

```
ITE<chip>_<keyboard-capability>[_<chassis-lighting>][_<oem-exclusivity>]
```

A backend name must be **self-describing**: two backends that share a chip but
differ in keyboard capability, chassis lighting, or OEM wiring must never
collide on the same name. Names use **underscores only** (never hyphens), so a
name can always be split on `_` unambiguously. The two optional segments are
**omitted when empty** rather than padded with a placeholder:

- `<chassis-lighting>` is omitted when the backend drives no extra chassis
  lighting.
- `<oem-exclusivity>` is omitted when the chip+wiring is multi-OEM / generic.

| Segment | Answers | Token vocabulary | Examples |
|---------|---------|------------------|----------|
| `ITE<chip>` | Which silicon/controller drives the LEDs? | `ite8291`, `ite8258`, `ite8295`, `ite8233`, `ite8910`, `ite8297`, `ite8291r3` | `ite8258` |
| `<keyboard-capability>` | How is the **keyboard deck** driven? | `perkey`, `zones`, `uniform`, `none` (backend drives no keyboard, e.g. a lightbar-only device) | `perkey` |
| `<chassis-lighting>` *(optional)* | Does it also drive **extra chassis lighting**? If so, which surfaces? | `chassis_<surface>[_<surface>...]` where surface ∈ `logo`, `neon`, `vent`, `lightbar`, `ports` | `chassis_logo_neon_vent` |
| `<oem-exclusivity>` *(optional)* | Is this chip+wiring **exclusive to an OEM / model family**? If so, which? | `<oem>_<family>` | `lenovo_legion`, `lenovo_ideapad`, `clevo`, `tongfang` |

Worked example — the Lenovo Legion Pro 7 Gen10 (`0x048d:0xc197`) composite
controller:

```
ite8258_perkey_chassis_logo_neon_vent_lenovo_legion
  ^^^^^^  ^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^
  chip    per-key  logo + neon + vent       exclusive to Lenovo
          keyboard chassis surfaces         Legion Gen10
```

Compare with the same chip on the Legion 5 / Pro 5 Gen10 (`0x048d:0xc195`),
which is a keyboard-only 24-zone part with no chassis lighting:
`ite8258_zones_lenovo_legion` (the empty chassis segment is omitted). Under the
old two-part scheme both collapsed to ambiguous `ite8258_*` names; the expanded
form keeps them distinct.

### Segment definitions

Keyboard capability:

| Token | Meaning |
|-------|---------|
| `perkey` | Every key is individually addressable |
| `zones` | Keyboard deck has 2+ controllable zones, but not per-key |
| `uniform` | Entire keyboard is one single color |
| `none` | Backend drives no keyboard (auxiliary-only device such as a lightbar) |

Chassis lighting (non-keyboard surfaces driven through the same backend). The
whole segment is omitted when there is no extra chassis lighting:

| Token | Meaning |
|-------|---------|
| `chassis_logo` | Lid/logo lighting |
| `chassis_neon` | Neon/accent strip |
| `chassis_vent` | Vent/rear-edge lighting |
| `chassis_lightbar` | A separate lightbar strip |
| `chassis_ports` | I/O-port accent lighting |

Combine multiple surfaces in one token, ordered `logo` > `neon` > `vent` >
`lightbar` > `ports`, e.g. `chassis_logo_neon_vent`.

OEM exclusivity:

| Token | Meaning |
|-------|---------|
| *(omitted)* | Controller+wiring appears across multiple OEMs/rebrands |
| `<oem>_<family>` | Exclusive to one OEM or laptop model family (e.g. `lenovo_legion`, `lenovo_ideapad`, `clevo`, `tongfang`, `wootbook`) |

### Separator policy

- **Underscores only.** All segments and all multi-word tokens inside a segment
  use underscores (e.g. `chassis_logo_neon_vent`, `lenovo_legion`). ITE backend
  names never contain hyphens, so a name can always be split on `_` without
  ambiguity.
- Non-ITE backends (`sysfs-leds`, `sysfs-mouse`, `asusctl-aura`) keep their
  descriptive hyphenated names; they do not follow the `ITE<chip>` convention.

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

The **Identifier** column is the name the code uses everywhere (config,
`KEYRGB_BACKEND`, registry, diagnostics) and follows the convention above. **New
backends must be added under this convention.** Older short identifiers remain
valid via aliases (see *Deprecated aliases*).

| Identifier | Directory | Stability | Notes |
|---|---|---|---|
| `asusctl-aura` | `asusctl/` | VALIDATED | Wraps `asusctl` CLI; supports virtual per-key via zone bucketing. |
| `ite8291r3_perkey` | `ite8291r3_perkey/` | VALIDATED | USB control-transfer protocol; multi-OEM Tongfang-class. |
| `ite8910_perkey` | `ite8910_perkey/` | VALIDATED | Per-key HID backend. |
| `ite8291_perkey` | `ite8291_perkey/` | EXPERIMENTAL | Native HID feature-report variant. |
| `ite8291_zones_clevo` | `ite8291_zones_clevo/` | EXPERIMENTAL | 4-zone variant via tuxedo-drivers protocol (Clevo/Tuxedo). |
| `ite8258_zones_lenovo_legion` | `ite8258_zones_lenovo_legion/` | EXPERIMENTAL | 24-zone keyboard controller, Lenovo Legion 5 / Pro 5 Gen10 (`0x048d:0xc195`). |
| `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion` | `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion/` | EXPERIMENTAL | Composite keyboard + chassis lighting (Lenovo Legion Pro 7 Gen10, `0x048d:0xc197`). Exposes logo/neon/vent zones. |
| `ite8295_zones_lenovo_ideapad` | `ite8295_zones_lenovo_ideapad/` | EXPERIMENTAL | Lenovo IdeaPad/Legion 4-zone family. Covers PIDs `0xC955/0xC963/0xC965/0xC973/0xC975/0xC984/0xC985`. |
| `ite8233_none_chassis_lightbar_clevo` | `ite8233_none_chassis_lightbar_clevo/` | EXPERIMENTAL | Clevo lightbar (no keyboard). OpenRGB calls this "ITE 8291 rev 0.03" but the device's own HID descriptor reports "ITE Device(8233)". |
| `ite8297_uniform` | `ite8297_uniform/` | EXPERIMENTAL | Uniform-color sysfs/hidraw backend. |
| `sysfs-leds` | `sysfs/` | VALIDATED | Generic sysfs LED subsystem; handles Tuxedo/Clevo/System76 multi-intensity and ITE 8297 channel LEDs. |
| `sysfs-mouse` | `sysfs_mouse/` | EXPERIMENTAL | Auxiliary sysfs LED backend for external mice. |

## Deprecated aliases

Backends that have been renamed maintain backward-compatible aliases so
existing user config (`KEYRGB_BACKEND`, saved profiles) continues to work.

| Old name | Canonical name |
|---|---|
| `ite8291r3` | `ite8291r3_perkey` |
| `ite8910` | `ite8910_perkey` |
| `ite8291` | `ite8291_perkey` |
| `ite8291-zones` | `ite8291_zones_clevo` |
| `ite8258` | `ite8258_zones_lenovo_legion` |
| `ite8258-chassis` | `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion` |
| `ite8295-zones` | `ite8295_zones_lenovo_ideapad` |
| `ite8233` | `ite8233_none_chassis_lightbar_clevo` |
| `ite8297` | `ite8297_uniform` |
| `ite8291_zones` | `ite8291_zones_clevo` |
| `ite8258_zones` | `ite8258_zones_lenovo_legion` |
| `ite8258_chassis` | `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion` |
| `ite8295_zones` | `ite8295_zones_lenovo_ideapad` |
| `ite8233_lightbar` | `ite8233_none_chassis_lightbar_clevo` |

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

### ite8233_none_chassis_lightbar_clevo — chip identity ambiguity

OpenRGB's `ClevoLightbarController` header says "Driver for Clevo laptop
lightbar (ITE 8291 rev 0.03)". However, the device's own HID descriptor
reports the name as `"ITE Device(8233)"`. KeyRGB uses `ite8233` because the
HID-reported name is concrete evidence. If future hardware diagnostics prove
the chip is actually an ITE 8291 variant, this should be renamed to
`ite8291_lightbar` or `ite8291_lb`.

See `docs/B-backend-audits/10-ite8233.md` for the full audit.

### ite8233_none_chassis_lightbar_clevo — usage page discrepancy

KeyRGB documents `VENDOR_USAGE_PAGE = 0xFF89` (from issue #5 descriptors).
OpenRGB's detector for PID `0x7001` uses `0xFF03`. This does not affect
hidraw matching (which is VID/PID-only) but the probe identifiers may be
misleading. Verify against real descriptors before changing.

### ite8233_none_chassis_lightbar_clevo — scan mode unimplemented

`MODE_SCAN = 0x06` is defined because OpenRGB exposes it, but KeyRGB does
not implement a scan effect. The 7-slot color behavior for KeyRGB's
multi-slot protocol is unconfirmed.

### ite8291_perkey vs. ite8291r3_perkey — transport split

Both target ITE 8291-family devices but use different transports:
- `ite8291r3_perkey`: USB control transfers (canonical with `pobrn/ite8291r3-ctl`).
- `ite8291_perkey`: native HID feature reports.

These are kept as separate backends because the probe logic and packet
format differ.

### ite8258_zones_lenovo_legion vs. ite8258_perkey_chassis_logo_neon_vent_lenovo_legion — same chip, different products

The ITE 8258 chip ships in two different Lenovo Legion Gen10 products with
different keyboard capabilities, chassis lighting, and USB IDs — which is
exactly why the convention keeps their names distinct:

- **Legion 5 / Pro 5 Gen10** (`0x048d:0xc195`) — keyboard-only, 24 zones, no
  chassis lighting → `ite8258_zones_lenovo_legion`.
- **Legion Pro 7 Gen10** (`0x048d:0xc197`) — per-key keyboard *plus* chassis
  lighting (logo / neon / vent) → `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion`.

These are separate backends because they are different products (different
PIDs, protocols, and probe logic), not two views of one laptop. The
`ite8258_perkey_chassis_logo_neon_vent_lenovo_legion` backend is keyboard-first and additionally exposes secondary
device routes for its individual chassis zones:
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
- `ite8291_perkey/hidraw.py` — used by `ite8291_zones_clevo`, `ite8295_zones_lenovo_ideapad`, `ite8258_zones_lenovo_legion`, `ite8258_perkey_chassis_logo_neon_vent_lenovo_legion`.
- `ite8910_perkey/hidraw.py` — used by `ite8233_none_chassis_lightbar_clevo`, `ite8297_uniform`.

These cross-dependencies exist because the hidraw transport logic is
transport-specific (not chip-specific) and was originally implemented in
the first backend that needed it.
