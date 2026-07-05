# Source Architecture Index

Scope: Linux-first keyboard-lighting architecture.

KeyRGB started with a strong Tongfang / ITE focus, but the app is now built
around modular backends and can support any controller family that fits the
backend contract. Many examples in this series still reference ITE-derived
hardware because that is where most support exists today.

Key principle: keep the tray and GUIs stable while new hardware support,
device types, and diagnostics flows are added behind backend and capability
boundaries.

## Status legend

- **Planned**: approved direction, not implemented
- **In progress**: actively being implemented
- **Done**: shipped + tested

## Documents

1. Backend architecture overview: [01-backend-architecture.md](01-backend-architecture.md)
2. Backend probing and selection: [02-backend-probing-and-selection.md](02-backend-probing-and-selection.md)
3. Sysfs keyboard-backlight backend: [03-sysfs-backend.md](03-sysfs-backend.md)
4. USB and hidraw backends: [04-usb-and-hidraw-backends.md](04-usb-and-hidraw-backends.md)
5. Capabilities-driven UI behavior: [05-capabilities-and-ui.md](05-capabilities-and-ui.md)
6. Diagnostics, discovery, and identity: [06-diagnostics-discovery-and-identity.md](06-diagnostics-discovery-and-identity.md)
7. Battery-saver policy (dimming on AC unplug): [07-battery-saver-policy.md](07-battery-saver-policy.md)
8. Reactive brightness invariants: [08-reactive-brightness-invariants.md](08-reactive-brightness-invariants.md)
9. Physical layouts and canonical slot IDs: [09-physical-layout-and-slot-ids.md](09-physical-layout-and-slot-ids.md)
10. Support Tools and backend discovery: [10-support-tools-and-discovery.md](10-support-tools-and-discovery.md)
11. Multi-device routing and software targets: [11-multi-device-routing-and-targets.md](11-multi-device-routing-and-targets.md)

## Current baseline (already implemented)

- Backend registry exists under src/core/backends.
- Env override supported: `KEYRGB_BACKEND`.
- Capability-gated tray and GUI flows route through the selected backend.
- Current backend mix includes sysfs, multiple ITE hidraw paths, and optional
	controller-specific integrations such as ASUS Aura.
- Support Tools, backend discovery, and support-bundle export are part of the
	shipped support surface.
- Physical-layout selection and canonical slot IDs now sit between the
	reference keyboard model and saved per-key data.

## Current documentation priorities

1. Keep the backend and probing docs aligned with the real backend registry.
2. Keep the support and discovery docs aligned with the tray-first support flow.
3. Keep the layout docs aligned with the slot-ID based editor and calibrator model.
4. Keep multi-device routing docs aligned with auxiliary-device work such as the lightbar path.

## Notes

- The `buildpython` architecture series lives under `docs/architecture/buildpython/`.
- Repository-structure notes live under `docs/architecture/repo/`.
