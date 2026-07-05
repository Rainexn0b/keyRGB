# Backend Audit Index

**Goal:** Systematically compare each KeyRGB backend implementation against
publicly available reference implementations (OpenRGB, tuxedo-drivers,
pobrn/ite8291r3-ctl, published protocol docs, etc.) to catch bugs, protocol
discrepancies, and edge cases that could manifest as real hardware issues.

**Methodology:**
1. Read the full KeyRGB backend source.
2. Fetch the corresponding reference implementation(s) from open-source projects.
3. Compare: USB/hidraw protocol (report formats, endpoints, control codes),
   device PID/VID tables, capabilities advertised, error handling, and edge
   cases.
4. Document findings, classify severity, and recommend fixes.

## Backend audit order

| # | Backend | Status | Reference(s) |
|---|---------|--------|--------------|
| 1 | `ite8291r3_perkey` — ITE 8291 rev 0.03 USB (Tongfang) | ✅ Complete | [pobrn/ite8291r3-ctl], [OpenRGB ClevoKeyboardController], [OpenRGB Wiki] |
| 2 | `ite8910_perkey` — ITE 8910 per-key HID | ✅ Complete | [Chocapikk blog post], OpenRGB MR !3236, tuxedo-drivers ite_829x |
| 3 | `sysfs-leds` — Sysfs LED subsystem | ✅ Complete | Kernel docs (leds-class, leds-class-multicolor), tuxedo-drivers, system76_acpi |
| 4 | `ite8291_perkey` — ITE 8291 native HID | ✅ Complete | pobrn/ite8291r3-ctl, OpenRGB ClevoKeyboardController, tuxedo-drivers ite_8291 |
| 5 | `ite8258_zones` — ITE 8258 24-zone | ✅ Complete | OpenRGB Lenovo Gen10, legion-kb-rgb, LenovoLegionToolkit |
| 6 | `ite8258_chassis` — ITE 8258 composite chassis | ✅ Complete | OpenRGB Lenovo Gen10, legion-spectrum-control (83F5), LenovoLegionToolkit |
| 7 | `ite8297_uniform` — ITE 8297 uniform-color | ✅ Complete | tuxedo-drivers ite_8297 |
| 8 | `ite8291_zones` — ITE 8291 4-zone | ✅ Complete | tuxedo-drivers ite_8291 zone path |
| 9 | `ite8295_zones` — ITE 8295 4-zone | ✅ Complete | OpenRGB Lenovo4ZoneUSBController, L5P-Keyboard-RGB |
| 10 | `ite8233_lightbar` — ITE 8233 lightbar | ✅ Complete | OpenRGB ClevoLightbarController, tuxedo-drivers ite_8291_lb (ref only) |
| 11 | `sysfs-mouse` — Sysfs mouse LEDs | ✅ Complete | Kernel LED class docs, OpenRGB mouse controller naming |
| 12 | `asusctl-aura` — ASUS Aura CLI | ✅ Complete | asusctl source (`aura_cli.rs`), OpenRGB Aura controllers (reference only) |

## Backend naming convention

Backend names follow this hierarchy:

```
ITE<chip>_<capability>[_<capability>...][_<oem>]
```

1. **Controller / chip** (`ITE8295`, `ITE8258`, ...) — the silicon family driving the LEDs.
2. **Capability** (`chassis`, `zones`, `perkey`) — the lighting abstraction this backend exposes.
   Multiple capabilities are ordered as `chassis` > `zones` > `perkey`.
3. **OEM-specific variant** (`lenovo`, `wootbook`, ...) — only added when the same chip is
   wired or configured differently for a specific manufacturer.

Examples:
- `ITE8295_zones` — generic 4-zone ITE 8295 implementation.
- `ITE8295_chassis_lenovo` — Lenovo-specific chassis lighting variant.
- `ITE9999_chassis_zones_lenovo` — fully-featured Lenovo backend exposing both chassis and zone control.

This convention keeps the chip visible while making the exposed capability and any OEM quirk clear from the name alone.

[pobrn/ite8291r3-ctl]: https://github.com/pobrn/ite8291r3-ctl
[OpenRGB ClevoKeyboardController]: https://github.com/CalcProgrammer1/OpenRGB/tree/master/Controllers/ClevoKeyboardController
[OpenRGB Wiki]: https://gitlab.com/OpenRGBDevelopers/OpenRGB-Wiki
[Chocapikk blog post]: https://chocapikk.com/posts/2026/reverse-engineering-ite8910-keyboard-rgb/
