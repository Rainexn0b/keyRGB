# ITE8233 Lightbar Backend Research

## Scope

This document is the backend-owner note for the secondary ITE USB HID device reported in issue `#5`.

It captures:

- the current evidence for the secondary controller
- upstream implementation findings from OpenRGB and tuxedo-drivers
- the staged implementation plan inside keyRGB
- the promotion criteria for moving the backend from `dormant` to `experimental`
- the proposed tray and per-key-editor UX for a keyboard plus lightbar system

The relevant two-device model is:

- Confirmed keyboard controller: `0x048d:0x600b` (`ite8291r3`, already supported)
- Auxiliary controller: `0x048d:0x7001` (`ITE Device(8233)`, likely front lightbar or auxiliary RGB zones)

The goal is to keep the research, implementation plan, scaffold design, UX direction, and promotion criteria in one backend-focused location under `docs/developement/backends/`.

## Source Inputs

This summary is based on:

- `docs/genAI/Lightbar Backend Research for keyRGB.md`
- GitHub issue `#5` (`Hardware support: Support for secondary ITE USB device (048d:7001) – likely lightbar / auxiliary RGB zones`)
- The current backend architecture in `src/core/backends/`
- Upstream OpenRGB `ClevoLightbarController` for `0x048d:0x7001`
- Upstream tuxedo-drivers `ite_8291_lb` driver with explicit `0x7001` handling

## Confirmed Evidence

### Hardware and environment

- Laptop family: MECHREVO YAOSHI Series / Tongfang-derived chassis
- Distro: KDE neon 24.04 base
- Kernel: `6.17.0`
- Existing working backend: `ite8291r3`
- Working keyboard RGB USB ID: `0x048d:0x600b`
- Additional unmanaged USB ID: `0x048d:0x7001`

### USB and HID observations for `0x048d:0x7001`

- Product string: `ITE Device(8233)`
- Driver on Linux: `hid-generic`
- Exposed hidraw node: `/dev/hidraw1` on the reporter's machine
- Interface 0:
  - HID boot keyboard
  - Feature report ID `0x5a`
  - Feature report length `16` bytes
  - Vendor usage page `0xFF89`
- Interface 1:
  - HID interrupt interface
  - IN endpoint `0x81`
  - OUT endpoint `0x02`

### What this strongly suggests

- The lightbar path is not exposed via sysfs LEDs on the affected system.
- The second device has a host-to-device interrupt endpoint, so Linux can almost certainly send commands directly.
- The controller is probably a separate auxiliary RGB path rather than an alternate descriptor for the existing `ite8291r3` keyboard device.

## Upstream Open-Source Findings

The upstream check materially changed the confidence level for a minimal `0x7001` implementation.

### OpenRGB

OpenRGB already contains a dedicated `0x048d:0x7001` controller implementation under its CLEVO lightbar support.

Relevant conclusions:

- `0x7001` is treated as a dedicated lightbar device, not as part of the keyboard matrix.
- The device is controlled with `8`-byte HID feature reports.
- OpenRGB exposes the device as a single lightbar zone.
- OpenRGB supports these mode identifiers:
   - `0x00` off
   - `0x01` direct
   - `0x02` breathing
   - `0x03` wave
   - `0x04` bounce
   - `0x05` marquee
   - `0x06` scan

The concrete packet shapes are especially important:

- static color:
   - `14 00 01 R G B 00 00`
- brightness or mode update:
   - `08 22 MODE SPEED BRIGHTNESS 01 00 00`
- off sequence:
   - `12 00 03 00 00 00 00 00`
   - `08 05 00 00 00 00 00 00`
   - `08 01 00 00 00 00 00 00`
   - `1a 00 00 00 00 00 00 01`

### tuxedo-drivers

tuxedo-drivers also contains explicit `0x7001` support in `ite_8291_lb`.

That driver confirms the safest initial feature scope:

- uniform color
- brightness
- off

It also confirms that `0x7001` belongs to the lightbar family handled separately from the keyboard matrix path.

Important limitation:

- tuxedo-drivers clearly implements the `0x7001` mono-color, brightness, and off path
- its broader effect helpers are not equally clear for `0x7001`; several effect paths are implemented for neighboring PIDs such as `0x6010` or `0x7000`

### TUXEDO Control Center

The TUXEDO Control Center application itself was not the useful implementation source.

The app largely consumes driver-exported sysfs keyboard backlight interfaces. It does not appear to contain a standalone `0x7001` USB lightbar protocol implementation that would be more authoritative than the driver code.

## What Is Still Unknown

The upstream findings close the gap for a minimal lightbar implementation, but they do not answer everything:

1. Why the affected reporter described descriptor facts around report ID `0x5a` and `16`-byte feature data while upstream working implementations use `8`-byte writes.
2. Whether every Tongfang or MECHREVO `0x7001` device accepts the exact same packet framing as the CLEVO-oriented upstream implementations.
3. The real topology:
    - single uniform lightbar
    - multiple logical zones
    - segmented but firmware-collapsed to one zone
4. Which built-in effect modes are portable and safe on the affected hardware family.
5. Resume, suspend, and power-loss behavior for the lightbar path.
6. Whether any models require packet sequencing quirks beyond the known off sequence.

So the backend is no longer blocked on total protocol ignorance. It is blocked on deciding the correct first shipped scope.

## Feasibility

### Architectural feasibility: high

The codebase already supports the pieces needed for a safe staged rollout:

- Backends carry stability metadata: `validated`, `experimental`, `dormant`
- Policy already blocks dormant backends from selection
- Diagnostics already report probe metadata and selection reasons
- Hidraw matching utilities already exist for ITE-class backends
- The settings path already supports feature-gated experimental backends for later promotion

### Protocol feasibility: not yet proven

The blocker is no longer raw command discovery for the minimal feature set.

We now have enough upstream evidence to implement a conservative `0x7001` lightbar path for:

- uniform color
- brightness
- off

The remaining caution is about scope control, not about whether any working protocol exists.

## Why A Separate Backend Is Preferred

A new backend is cleaner than extending `ite8291r3` for these reasons:

1. The device is exposed as a distinct USB product ID.
2. The reported interface layout differs from the currently supported `ite8291r3` path.
3. The suspected target is not the main keyboard matrix, but an auxiliary lighting zone.
4. Promotion will likely require separate protocol logic and separate capability flags.

The working assumption is therefore:

- `ite8291r3` continues to own the keyboard
- `ite8233` owns the auxiliary lightbar path

This means keyRGB must handle both device IDs at the same time on affected systems.

## Backend Shape For The First Experimental Release

The current in-tree backend now uses the following conservative experimental design:

### Name

- Backend name: `ite8233`

### Stability metadata

- Stability: `experimental`
- Experimental evidence tag: `reverse_engineered`

Current recommendation:

- keep the shipped scope narrow until real `0x7001` reporters confirm the path on hardware
- do not widen the backend beyond single-zone color / brightness / off until there is model-specific evidence for more

This means:

- It is visible in code and diagnostics
- It is opt-in through the experimental-backends toggle or `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1`
- It can be explicitly selected for testing with `KEYRGB_BACKEND=ite8233`
- It is still not expected to auto-select ahead of validated keyboard backends on affected systems

### Detection behavior

- Match vendor/product `0x048d:0x7001`
- Support a forced hidraw override via `KEYRGB_ITE8233_HIDRAW_PATH`
- Report `experimental disabled` until the user opts into experimental backends
- Report `available=True` once the device is present and the experimental gate is enabled

### Exposed capabilities

The scaffold currently advertises the narrowest plausible future shape:

- `per_key=False`
- `color=True`
- `hardware_effects=False`
- `palette=False`

This remains the right first experimental target.

### Protocol assumptions recorded in code

The backend still records the descriptor-level constants that came from the user report:

- VID `0x048d`
- PID `0x7001`
- feature report ID `0x5a`
- feature report size `16`
- vendor usage page `0xFF89`
- Interface 1 IN/OUT endpoints `0x81` / `0x02`

It also now implements the upstream-backed minimal write set for:

- uniform color
- brightness
- off

It intentionally does not claim segmented writes or firmware effects as supported.

## Revised Implementation Plan

The current best path is a staged promotion, not a large one-shot backend.

### Stage 1: Minimal protocol implementation while still dormant

Implement the known upstream packet path in the `ite8233` backend, but keep selection disabled.

Scope:

- add exact `8`-byte control packet builders for:
  - set uniform color
  - set brightness
  - turn off
- record the known mode constants in the protocol module
- add packet-builder unit tests with exact byte expectations
- add backend tests proving `0x7001` detection still stays blocked while dormant

This stage is complete.

### Stage 2: Promote from dormant to experimental with a narrow feature set

This stage is now complete in-tree. Real-hardware validation is still required before any promotion beyond `experimental`.

Initial experimental feature scope should be:

1. detect `0x7001` reliably
2. expose it as a secondary `lightbar` device
3. support only:
   - off
   - uniform color
   - brightness
4. do not expose firmware effects yet
5. do not claim segmented or per-LED lightbar control

This avoids promising more than upstream has clearly validated for `0x7001`.

### Stage 3: Conditional tray integration for the second device

Once the backend is experimental, the tray should show both detected devices.

Recommended model:

- keep the existing keyboard line
- add a second status line directly underneath it for the auxiliary device
- use explicit types in the labels

Recommended display shape:

- `Keyboard: ITE 8291 (USB) (048d:600b)`
- `Lightbar: ITE 8233 (USB) (048d:7001)`

If the device is detected but the backend is still dormant or disabled, append a short status marker rather than pretending it is usable.

Examples:

- `Lightbar: ITE 8233 (USB) (048d:7001) [experimental disabled]`
- `Lightbar: ITE Device(8233) (048d:7001)`

That gives the user an honest two-device model without implying the lightbar is just part of the keyboard backend.

### Stage 4: Conditional lightbar controls in the tray

After the device line is visible, add lightbar-specific controls only when the lightbar backend is actually active.

Recommended first controls:

- `Lightbar Off`
- `Lightbar Color…`
- `Lightbar Brightness`

Do not mix these into the keyboard effect menus. The lightbar should read as a second controlled device, not as another keyboard effect mode.

### Stage 5: Conditional lightbar UI in the per-key editor

The per-key editor already owns layout and overlay-related visual setup, so it is the right place for a lightbar placement preview.

Recommended first UI:

- render a separate titled frame `Lightbar` underneath `Overlay alignment`
- only show it when a lightbar is detected
- give it its own preview region and transform controls

This should be a visual placement and sizing tool, not a promise of per-segment hardware control.

Recommended first controls:

- visible toggle
- width / length scale
- height / thickness scale
- horizontal offset
- vertical offset
- inset or margin
- reset / save

The important product rule is:

- the lightbar overlay may be resizable in the editor
- the hardware backend still remains single-zone in the first experimental release

In other words, the UI can show where the lightbar lives on the chassis without implying that the backend supports editing separate LEDs inside it.

## Detection And UX Model

This repo now needs to treat the system as a multi-device lighting setup on affected machines.

### Device typing

Discovery, diagnostics, and tray status should distinguish device roles explicitly.

Recommended device types:

- `keyboard`
- `lightbar`

This should appear in:

- backend discovery output
- support bundle payloads
- tray status text
- any future multi-device capability model

### Why this is better than folding it into the keyboard backend label

The user sees two different USB IDs and two different physical lighting surfaces.

Calling both of them just `keyboard` would make debugging harder:

- support logs become ambiguous
- tray status becomes misleading
- future capability gating becomes harder

The explicit `Keyboard` plus `Lightbar` wording is the right product direction.

### Per-key editor positioning

Placing the lightbar UI under `Overlay alignment` is the right direction.

Reasoning:

- `Keyboard Setup` owns what keys exist and how they are labeled
- `Keymap Calibrator` owns mapping keyboard scan positions to keys
- `Overlay alignment` already owns visual placement transforms
- the lightbar is a visual auxiliary overlay, not part of the keymap grid

So the lightbar panel should sit near overlay controls, not near keymap calibration.

## Promotion Path

The old promotion gate required Windows capture before any useful implementation. The upstream check changes that.

### New promotion rule

Promote from `dormant` to `experimental` once the repo has all of the following:

1. exact `0x7001` packet builders for color, brightness, and off based on upstream working implementations
2. unit tests covering the packet builders and off sequence
3. detection tests showing keyboard plus lightbar coexistence
4. one real-hardware validation pass on an affected `0x7001` machine covering:
   - detect
   - set color
   - set brightness
   - turn off
   - restore after relaunch
5. explicit feature gating that keeps lightbar firmware effects disabled

This promotion has now happened in-tree.

### What is no longer required for first promotion

These are still valuable, but they no longer need to block a minimal experimental release:

- Windows traffic capture for basic mono color support
- full segmented topology knowledge
- proof for every firmware effect mode

### What should still block promotion beyond minimal experimental

Do not move beyond the minimal experimental scope until we have evidence for:

1. segmented or per-LED topology
2. safe effect-mode support on Tongfang or MECHREVO-class `0x7001` hardware
3. suspend and resume behavior across repeated cycles
4. no regressions when `0x600b` keyboard and `0x7001` lightbar are both active

## Dumps To Request From The Reporter

Priority order:

1. HID report descriptor
   - `sudo usbhid-dump -d 048d:7001 -e descriptor`
2. Full verbose USB descriptor
   - `lsusb -v -d 048d:7001`
3. Real-hardware confirmation of the upstream packet path
   - static color
   - brightness
   - off
   - relaunch behavior
4. Optional Windows capture while changing lightbar state in the OEM tool
   - especially if we later want firmware effects or segmented behavior
5. Optional feature report probing
   - safe reads around report ID `0x5a`
6. Physical confirmation
   - number of visible LEDs or zones
   - whether the device controls a front lightbar, bottom strip, lid logo, or another auxiliary path

## Risk Notes

### Main technical risk

The biggest risk is over-generalizing the CLEVO-oriented upstream `0x7001` behavior to every Tongfang-derived system without narrowing the feature scope.

### Safety rule

Only the known minimal packet set should currently be enabled.

### Why the experimental gate still matters

The experimental gate still lets the repo:

- ship the upstream-backed minimal path for interested testers
- avoid silently taking over a second device on machines where only the keyboard backend is expected to be active
- keep diagnostics and support flows ahead of broader automatic enablement

## Current Recommendation

Keep `ite8233` experimental and explicitly opt-in while collecting issue-5-style real-hardware confirmation.

Recommended reporter test path:

```bash
KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1 KEYRGB_BACKEND=ite8233 ./keyrgb
```

Ask the reporter to verify this exact first-release scope:

- secondary `lightbar` device detection
- tray status line for the lightbar
- uniform color
- brightness
- off
- conditional lightbar placement UI in the per-key editor

Additional checks worth asking for:

1. relaunch behavior after quitting and reopening the tray
2. suspend / resume behavior if they can test it safely
3. whether the device is a single visible bar or multiple visible zones that still act as one

Do not enable firmware effects or segmented editing in the first experimental release.