# `ite8258-chassis` Backend Plan (`0x048d:0xc197`)

## Scope

This document is the backend-owner implementation plan for issue `#7`.

It captures:

- the confirmed evidence from the Lenovo Legion Pro 7 Gen10 support report
- the upstream OpenRGB implementation target that matches the report
- the backend-shape decision inside KeyRGB
- the staged implementation plan for `ite8258-chassis`
- the full implementation checklist, using the two validated ITE backends as the reference scope

The relevant reported device model is:

- primary RGB target: `0x048d:0xc197`
- companion USB device: `0x048d:0xc193`
- current KeyRGB runtime coverage: `ite8258` for `0x048d:0xc195` only
- current KeyRGB runtime coverage also includes a keyboard-first experimental `ite8258-chassis` path for `0x048d:0xc197`

The goal is to add support for the `0xc197` path under a dedicated `ite8258-chassis` backend without incorrectly folding it into the existing `ite8258` `0xc195` backend.

## Current repo status

The repo now contains an experimental keyboard-first `ite8258-chassis` backend under `src/core/backends/ite8258_perkey_chassis/`.

Current implemented scope:

- backend naming and registry identity
- hidraw detection for `0x048d:0xc197`
- transport open/close ownership
- Gen10 packet builders translated from the confirmed OpenRGB Lenovo Gen7/8 implementation
- keyboard runtime facade for off, brightness, per-key/static keyboard writes, and firmware effects
- diagnostics-visible probe output that keeps `0x048d:0xc197` ahead of the companion `0x048d:0xc193` device when the experimental backend is disabled
- focused unit coverage for the translated protocol, device, and backend slice

Still intentionally missing:

- neon-zone UI
- logo-zone UI
- vent-zone UI
- companion `0x048d:0xc193` ownership
- chassis-zone modeling

## Source Inputs

This plan is based on:

- GitHub issue `#7` (`Hardware support: Lenovo Legion Pro 7 16IAX10H (048d:c197)`)
- the current KeyRGB `ite8258` backend in `src/core/backends/ite8258/`
- OpenRGB `Controllers/LenovoControllers/LenovoUSBController_Gen7_8/`
- the validated KeyRGB ITE backends:
  - `src/core/backends/ite8291r3/`
  - `src/core/backends/ite8910/`

## Confirmed Evidence

### Reporter evidence

- laptop family: `Lenovo Legion Pro 7 16IAX10H`
- board name: `LNVNB161216`
- distro: `CachyOS`
- kernel: `7.0.10`
- reported USB IDs:
  - `048d:c193` (`Lenovo Lighting`)
  - `048d:c197` (`ITE Device(8258)`)

### Current KeyRGB behavior

- no sysfs keyboard LED path was detected
- no backend was selected
- the existing `ite8258` probe reported `no matching hidraw device`
- this is expected with the current code because `src/core/backends/ite8258/protocol.py` only allows `0xC195`

### Upstream OpenRGB match

OpenRGB already treats `0xC197` as a supported Lenovo Gen10 family device:

- `0xC195` -> `LEGION_5GEN10`
- `0xC197` -> `LEGION_7GEN10`

Important protocol conclusions from the upstream code:

- `0xC195` and `0xC197` share the Lenovo Gen10 HID transport family
- packet size is `960`
- report ID is `0x07`
- Gen10 stores the payload length in bytes `2..3`
- command family includes `0xA1`, `0xC8`, `0xCA`, `0xCB`, `0xCC`, `0xCD`, `0xCE`, `0xD0`, `0xD1`

Important topology conclusion from the upstream zone model:

- `0xC195` is treated as a keyboard-only `4x6` 24-zone device
- `0xC197` is not keyboard-only
- OpenRGB models `0xC197` as a larger Legion 7 Gen10 path with:
  - keyboard matrix
  - neon zone
  - logo zone
  - `18` vent groups

## Planning Conclusions

### What should not happen

Do not add `0xC197` to `src/core/backends/ite8258/protocol.py` `SUPPORTED_PRODUCT_IDS` as a one-line PID extension.

That would reuse the wrong device model:

- wrong zone topology
- wrong UX expectations
- wrong promotion story

### Recommended backend shape

Treat `0xC197` as a separate `ite8258-chassis` backend candidate that happens to share a packet family with the existing `0xC195` work.

That means:

- keep `ite8258` scoped to the already shipped `0xC195` 24-zone keyboard-only path
- add a new backend package named `ite8258-chassis` instead of widening `ite8258`
- keep `0xC193` out of the initial support scope until there is direct protocol evidence for what it controls

### Naming decision

Use `ite8258-chassis` as the public backend name for the `0xC197` path.

Why this name:

- it keeps the controller family as the stable root, matching current KeyRGB backend naming
- it distinguishes the composite keyboard-plus-chassis-lighting contract from the existing keyboard-only `ite8258` path
- it avoids binding the backend to one Lenovo marketing name or SKU string
- it avoids opaque numbered variants when the protocol split is already understood well enough to name semantically

This follows the controller-first naming rule documented in [../../B-backend-guides/backend-naming.md](../../B-backend-guides/backend-naming.md).

## Reference Scope From The Validated ITE Backends

The two validated ITE backends already show what a full KeyRGB backend implementation really includes.

### Reference 1: `ite8291r3`

`ite8291r3` is the reference for a fully integrated validated USB backend.

It covers:

- backend probe and selection policy in `src/core/backends/ite8291r3/backend.py`
- transport ownership and open/close behavior in `src/core/backends/ite8291r3/usb.py`
- protocol and device facade in:
  - `src/core/backends/ite8291r3/protocol.py`
  - `src/core/backends/ite8291r3/device.py`
- explicit unsupported-device rejection and variant gating
- backend-specific runtime hints such as speed-policy and per-key-mode-policy metadata
- permission and busy/disconnect translation into typed backend errors
- coverage beyond the backend package itself, including diagnostics, support flows, UI status text, and hardware speed-probe paths

The `0xC197` implementation should copy this level of completeness, not just its probe function.

### Reference 2: `ite8910`

`ite8910` is the reference for a fully integrated validated hidraw backend.

It covers:

- hidraw discovery and transport ownership in `src/core/backends/ite8910/hidraw.py`
- backend surface in `src/core/backends/ite8910/backend.py`
- protocol builders and state handling in:
  - `src/core/backends/ite8910/protocol.py`
  - `src/core/backends/ite8910/_protocol_effects.py`
- device facade in `src/core/backends/ite8910/device.py`
- exact packet-shape tests and translation tests under `tests/core/backends/ite8910/`

The `0xC197` path should use this backend as the reference for:

- hidraw matching
- exact byte-locking of packet builders
- protocol-state tests before broader UI wiring

### Full implementation checklist implied by the validated backends

For `0xC197`, the complete scope is not only `backend.py` plus `protocol.py`.

The real full-scope checklist is:

1. backend package ownership
2. probe and selection policy
3. transport open/close and permission story
4. protocol constants and packet builders
5. device facade and runtime behavior
6. backend registry integration
7. diagnostics and discovery output
8. support-tools / hardware-probe integration when feature scope is stable
9. tray and UI capability behavior
10. focused unit coverage for probe, transport, protocol, device, and integration surfaces
11. README and backend-policy documentation

That is the bar set by `ite8291r3` and `ite8910`.

## Proposed Backend Shape Inside KeyRGB

Recommended package shape:

- `src/core/backends/ite8258_perkey_chassis/__init__.py`
- `src/core/backends/ite8258_perkey_chassis/backend.py`
- `src/core/backends/ite8258_perkey_chassis/protocol.py`
- `src/core/backends/ite8258_perkey_chassis/device.py`
- either:
  - reuse the current shared hidraw-matching pattern from `ite8910` / `ite8291`, or
  - add a small backend-local hidraw helper if the match rules need to differ

Recommended initial runtime assumptions:

- provider: hidraw feature reports
- usage page: `0xFF89`
- usage: `0x07`
- report ID: `0x07`
- packet size: `960`
- payload length in bytes `2..3`

Recommended initial backend capabilities:

- `per_key=True`
- `color=True`
- `hardware_effects=True`
- `palette=False`

The primary keyboard matrix should be the initial runtime owner.

The neon, logo, and vent zones should be treated as staged follow-up scope, not as a requirement for the first keyboard-working milestone.

## Staged Implementation Plan

### Stage 1: Scaffold the backend and lock the protocol

Current status: partially complete.

Scope:

- add the new backend package under `src/core/backends/`
- add detection for `0xC197`
- land the first runtime cut as opt-in experimental so the keyboard path is usable without claiming full chassis parity
- translate the known OpenRGB Gen10 packet family into KeyRGB packet builders for:
  - direct-mode on
  - direct-mode off
  - set brightness
  - get brightness
  - get active profile
  - switch profile
  - save grouped profile payloads
  - direct LED writes
- add exact packet-builder tests before any wider runtime integration

Exit criteria:

- the backend can detect the correct hidraw node
- the packet builders are locked by unit tests
- `0xC197` is no longer invisible to the backend layer and can be exercised behind the experimental-backend policy gate

Completed in the current scaffold:

- backend package ownership
- registry wiring
- experimental policy wiring
- hidraw detection for `0xC197`
- focused scaffold tests
- Gen10 keyboard-first runtime translation

### Stage 2: Keyboard-first experimental runtime path

Scope:

- expose the keyboard matrix as the initial controlled surface
- support:
  - off
  - brightness
  - static color
  - per-key keyboard updates
  - keyboard firmware effects
- wire the backend into the registry and capability flow
- keep the first shipped scope keyboard-first even though the controller owns more than the keyboard

Explicitly defer:

- `0xC193`
- neon-zone UI
- logo-zone UI
- vent-zone UI
- guided backend speed-probe UI

This keeps the first release aligned with the existing experimental-backend policy: narrow feature scope first, broader runtime parity later.

### Stage 3: Validate the effect surface and backend-specific policy

Scope:

- map the confirmed firmware-effect subset from the translated OpenRGB family
- decide and test any backend-specific speed-policy behavior
- decide whether the backend needs a backend-owned runtime hint similar to `ite8291r3` or `ite8910`
- add device tests that prove software and hardware calls use the correct command path

Exit criteria:

- effect payloads are stable
- speed mapping is explicit and tested
- tray hardware-effect routing can rely on the backend metadata

### Stage 4: Diagnostics, support, and documentation parity

Scope:

- surface the backend in diagnostics and discovery output
- ensure unsupported companion paths remain explicit in probe output
- add README backend-table coverage and any backend-specific environment variables
- decide whether a guided speed probe is useful once the hardware-effect surface is verified
- add support wording that tells reporters exactly what to collect if `0xC193` remains present but unmanaged

Reference scope:

- `ite8291r3` is the reference for the support and diagnostics coverage level
- `ite8910` is the reference for the hidraw validation and protocol-test depth

### Stage 5: Decide how to model chassis zones

This is the first intentionally architectural stage.

Open question:

- should neon, logo, and vent groups remain backend-owned extra zones inside one controller surface, or
- should KeyRGB grow a typed secondary-target model for subdevices that are not separate USB controllers?

This should not block keyboard-first support.

But it should block any claim that the first `0xC197` implementation has full Legion chassis-lighting parity.

## Validation Plan

The minimum validation set should mirror the validated backend standards.

### Unit coverage

- probe and hidraw-match tests
- packet-builder exact-byte tests
- device facade tests for:
  - off
  - brightness
  - static writes
  - direct updates
- registry / diagnostics tests if backend selection and discovery output change

### Runtime validation on hardware

One real-hardware pass on an affected `0xC197` laptop should cover:

1. backend detection
2. permission behavior after udev setup
3. turn off / turn on
4. brightness changes across the full UI range
5. static color write
6. direct keyboard update without controller lockup
7. close / restart behavior

### Explicit non-goals for first release

Do not claim first-release support for:

- `0xC193`
- every Legion chassis-lighting zone
- full OpenRGB parity
- promotion beyond `experimental`

## Recommendation

The implemented path now follows this shape:

1. promote the dormant `ite8258-chassis` scaffold into an experimental runtime backend for `0xC197`
2. use `ite8910` as the hidraw/protocol reference
3. use `ite8291r3` as the full-integration reference
4. ship keyboard-first support before attempting full Legion chassis-zone parity

That keeps the first implementation root-cause aligned with the report, preserves the current `ite8258` `0xC195` contract, and follows the same completeness standard already established by KeyRGB's two validated ITE backends.

## External tester checklist

The current repo state is ready for issue-opener validation as an opt-in experimental backend.

Ask the tester to cover this exact path:

1. update to a build that includes the experimental `ite8258-chassis` backend
2. enable Experimental backends in Settings, or launch with `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1`
3. confirm that discovery/probe output identifies `0x048d:0xc197` as `ite8258-chassis`
4. test keyboard-only runtime behavior first:
  - turn off
  - brightness changes
  - uniform static color
  - per-key / sparse key updates
  - at least one translated firmware effect
5. keep the companion `0x048d:0xc193` device in the report if it is still present
6. save the full support bundle after testing, especially if the keyboard responds but any chassis zones remain unmanaged

Success for this stage means the keyboard path is stable and the reporter can confirm that the OpenRGB-backed Lenovo Gen10 packet translation behaves correctly on real `0xc197` hardware.