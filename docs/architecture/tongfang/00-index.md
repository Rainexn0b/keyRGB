# Tongfang Support Roadmap (Index)

Scope: **Tongfang laptops only**. This roadmap focuses on adding support for more Tongfang chassis without expanding to unrelated vendors.

Key principle: the tray/GUI should stay stable while we add new hardware support behind a backend registry.

## Status legend

- **Planned**: approved direction, not implemented
- **In progress**: actively being implemented
- **Done**: shipped + tested

## Documents

1. Backend architecture overview: [01-backend-architecture.md](01-backend-architecture.md)
2. Backend probing & selection: [02-backend-probing-and-selection.md](02-backend-probing-and-selection.md)
3. Sysfs keyboard-backlight backend: [03-sysfs-backend.md](03-sysfs-backend.md)
4. USB backend variants (ITE + future Tongfang USB): [04-usb-backends.md](04-usb-backends.md)
5. Capabilities-driven UI behavior: [05-capabilities-and-ui.md](05-capabilities-and-ui.md)
6. Diagnostics & identity (Tongfang-focused): [06-diagnostics-and-identity.md](06-diagnostics-and-identity.md)
7. Battery-saver policy (dimming on AC unplug): [07-battery-saver-policy.md](07-battery-saver-policy.md)

## Current baseline (already implemented)

- Backend registry exists under src/core/backends.
- Env override supported: `KEYRGB_BACKEND`.
- Tray dimension loading uses backend selection.
- ITE 8291r3 USB backend is implemented under `src/core/backends/ite8291r3/`.

## Near-term sequencing (recommended)

1. Implement real probing and selection (Doc 02)
2. Add sysfs backend (Doc 03)
3. Add capability-driven UI enable/disable (Doc 05)
4. Expand USB support with variant backends (Doc 04)
5. Add richer diagnostics + a contributor “data capture” flow (Doc 06)
6. Add battery-saver policy only after the above is stable (Doc 07)
