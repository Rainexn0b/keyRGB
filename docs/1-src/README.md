# 1-src — Source architecture

**Scope:** Source-code architecture for the `keyrgb/` package: backends, tray,
diagnostics, GUI, power management, and support tools. The lane id is `1-src`
and stays put; it is not the Python import root.

## Documents

- `00-index.md` — architecture index
- `01-backend-architecture.md` — backend architecture
- `02-backend-probing-and-selection.md` — backend probing and selection
- `03-sysfs-backend.md` — sysfs backend
- `04-usb-and-hidraw-backends.md` — USB and hidraw backends
- `05-capabilities-and-ui.md` — capabilities and UI
- `06-diagnostics-discovery-and-identity.md` — diagnostics discovery and identity
- `07-battery-saver-policy.md` — battery saver policy
- `08-reactive-brightness-invariants.md` — reactive brightness invariants
- `09-physical-layout-and-slot-ids.md` — physical layout and slot IDs
- `10-support-tools-and-discovery.md` — support tools and discovery
- `11-multi-device-routing-and-targets.md` — multi-device routing and targets
- `12-composite-profile-coordination.md` — reference architecture for logical
  routes that must commit one complete physical-controller profile
- `13-tray-runtime-state-ownership.md` — tray runtime state ownership
- `14-policy-ownership.md` — policy owners, canonical imports, and compatibility facades
- `15-config-domain-model.md` — config domain partitions and extras
- `16-effect-runtime-contracts.md` — effect registration, reactive API, and hardware-effect builders
- `17-backend-extension.md` — package registration and controller identity
- `18-diagnostics-purity.md` — readonly diagnostics config and snapshots
- `19-gui-async-jobs.md` — generation-aware Tk background work
- `20-tray-view-boundaries.md` — menu rendering reads tray-owned snapshots only
- `21-validation-layers.md` — default-suite artifact, session, installer, and tripwire layers
- `22-tool-policy.md` — mypy, dead-code, architecture, and ShellCheck gates
