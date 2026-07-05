# Hardware Expansion Roadmap (Actionable)

This document turns the Tier research + DOCX notes into an ordered set of **safe**, testable next steps.

## Current repo status (verified)

- **ITE 8291 backend** exists and safely probes by VID/PID without opening the USB device.
  - Additional IDs already included: `0x048d:0x6008`, `0x048d:0x600b`.
- **Sysfs LED backend** exists and supports:
  - broad LED name matching (includes `dell::kbd`, `tpacpi::kbd`, `asus::kbd`, `system76::kbd`, and more)
  - multicolor via `multi_intensity`
  - RGB via `color` attribute (when present)
  - brightness-only fallback

## Tier 3: ITE 8297 / ITE 5702 ("Fusion 2")

### What we know

Research sources mention USB IDs:
- `0x048d:0x8297` (often described as “ITE 8297”, Gigabyte/Tongfang)
- `0x048d:0x5702` (often described as “ITE 5702”, Gigabyte)

### Safety principle

Do **not** add these PIDs to the existing `ite8291r3` backend’s supported PID list until the protocol is confirmed.
If we do, auto-selection could pick the backend and attempt to speak the wrong protocol.

### Immediate actions (safe)

1. **Detect-but-don’t-select**
   - When `0x048d:0x8297` / `0x048d:0x5702` is present, emit a probe result that is *not available*, but includes VID/PID in identifiers.
   - Outcome: users/devs can see “your hardware is detected but unsupported” in debug logs.

2. **Confirm upstream capability**
   - Identify the exact `ite8291r3_ctl` version used by Keyrgb releases.
   - Check whether it supports 8297/5702 (or any “Fusion 2” path).

   Current repo reality (2026-01-02): upstream `pobrn/ite8291r3-ctl` does not reference `0x8297`, `0x5702`, or “Fusion 2”, so assume “no support” until proven otherwise.

3. **If upstream supports it**
   - Add *explicit* support guarded by a flag (e.g., `KEYRGB_EXPERIMENTAL_ITE8297=1`) and a clear warning.
   - Keep probing and selection conservative by default.

4. **If upstream does not support it**
   - Prefer an upstream-first contribution (to reduce maintenance) rather than a bespoke protocol implementation.
   - Only proceed with a new backend when we have:
     - a reliable capture/spec reference
     - a hardware owner for testing
     - a safety plan (fail-closed, no writes during probe)

## Tier 4 notes (future): ASUS Aura / ROG (rog-core)

Research suggests a separate backend targeting ASUS `0x0b05:xxxx` USB devices using a rog-core-like protocol.
This should be treated as a separate effort from sysfs brightness (`asus::kbd*`) support.

## Sysfs patterns (sanity)

Research suggests patterns like `rgb:kbd_backlight`, `dell::kbd_backlight`, `tpacpi::kbd_backlight`, `asus::kbd_backlight`, `system76::kbd_backlight`.
Current sysfs backend matches broadly on substrings like `kbd`/`keyboard`, so these should already be discovered.

