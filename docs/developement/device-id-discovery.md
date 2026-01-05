# Mining device IDs safely (ITE fallback)

## Goal

Expand KeyRGB’s ITE USB fallback backend support by adding **known-good USB VID:PID pairs** without risking accidental support for incompatible controller families.

Key idea: **USB IDs tell you what device is present, not what protocol it speaks.** Treat IDs as “candidates”, and only promote them to the allowlist when the protocol family is confirmed.

## What we found in this repo (sources of truth)

### 1) Upstream ITE userspace driver (best source)

The vendored `ite8291r3_ctl` module defines the canonical ITE 8291r3 family product IDs.

- Driver constants live in:
  - [vendor/ite8291r3-ctl/ite8291r3_ctl/ite8291r3.py](../../vendor/ite8291r3-ctl/ite8291r3_ctl/ite8291r3.py)

This is the safest place to “mine” IDs from because it is already protocol-scoped.

### 2) KeyRGB backend allowlist + denylist

KeyRGB layers a small allowlist/denylist around the upstream driver to:

- remain compatible with older packaged versions of `ite8291r3_ctl` (fallback IDs)
- **fail closed** on known incompatible controllers (“Fusion 2” family)

- Backend implementation:
   - [src/core/backends/ite8291r3/backend.py](../../src/core/backends/ite8291r3/backend.py)

### 3) Udev rule for non-root USB access

KeyRGB installs a uaccess rule so the active local session can access the USB device without running as root.

- Rule file:
  - [system/udev/99-ite8291-wootbook.rules](../../system/udev/99-ite8291-wootbook.rules)
- Installed by:
  - [install.sh](../../install.sh)

### 4) OEM Windows “Control Center” artifacts (useful, but not for USB IDs)

In the `Control Center/` bundle currently checked into this workspace:

- [Control Center/RGBKeyboard.reg](../../Control%20Center/RGBKeyboard.reg) contains **saved lighting/effect state** (JSON blobs like `*_LastEffect` with palettes and effect parameters).
- The `.inf` driver files we checked contain **ACPI hardware IDs** (e.g., `ACPI\\INOU0000`) but **did not contain USB VID/PID pairs** for the keyboard controller.

So: this particular OEM bundle is a goldmine for **effect/palette schema**, but not (yet) a direct USB-ID source.

## Recommended “safe mining” workflow (repeatable)

### Step A — Prefer protocol-scoped sources first

1. Start from the ITE protocol implementation you actually use:
   - `ite8291r3_ctl` product IDs list
2. Cross-check known supported devices via:
   - existing KeyRGB changelog / issues
   - community tools that explicitly identify ITE 8291r3 vs “Fusion 2” (do not assume all ITE chips are compatible)

Outcome: a short list of IDs with a strong protocol signal.

### Step B — If mining OEM Windows installers, extract then search

When you download OEM software for other models, you’ll usually get an installer (EXE/MSI) containing resources.

1. Extract the installer to a folder (examples):
   - `7z x OEMInstaller.exe -oextracted`
   - `msiextract OEMInstaller.msi -C extracted`

2. Search the extracted tree for VID/PID patterns:
   - `rg -n "VID_[0-9A-Fa-f]{4}|PID_[0-9A-Fa-f]{4}|USB\\\\VID_[0-9A-Fa-f]{4}" extracted/`
   - `rg -n "048d|0x048d|idVendor|idProduct" extracted/`

3. Check driver `.inf` files specifically:
   - Hardware IDs often appear as `USB\\VID_048D&PID_XXXX` or `HID\\VID_...`

4. If IDs aren’t in text files, scan binaries for strings:
   - `strings -a some.dll | rg "VID_[0-9A-Fa-f]{4}|PID_[0-9A-Fa-f]{4}|048d"`

Outcome: a list of candidate IDs + where you found them.

#### Helper script (in this repo)

If you have already extracted OEM installers (e.g. via `innoextract`), you can do a
quick first-pass scan for explicit hardware-ID strings:

- `python tools/oem_mine_scan.py <extracted-root>... > oem-usb-ids.csv`

This is intentionally conservative: it reports only IDs that appear as clear text
(`USB\\VID_....&PID_....`, `VID_....&PID_....`). Many OEM bundles do not ship these
strings in the app payload at all (the IDs may live in separate driver packages or
not be present).

If you want to scan Windows binaries (where strings may be embedded as UTF-16LE), run:

- `python tools/oem_mine_scan.py --include-binaries --utf16le <extracted-root>... > oem-usb-ids.csv`

### Step C — Validate candidates before adding to KeyRGB

An ID should only be added to the allowlist if it’s likely to speak the same protocol family.

Minimum bar (practical):

- Same vendor (often `0x048d`) AND
- Evidence it is an ITE keyboard RGB controller (not a card reader, DVB stick, etc.) AND
- Not in the known-incompatible denylist

Best bar:

- Confirm the device responds correctly to `ite8291r3_ctl` on a test machine (or a contributor’s machine)

## How to land an ID in KeyRGB (checklist)

1. Add the VID/PID to the allowlist in:
   - [src/core/backends/ite8291r3/backend.py](../../src/core/backends/ite8291r3/backend.py)
2. If needed, keep/extend the denylist for incompatible families.
3. Update udev rule coverage in:
   - [system/udev/99-ite8291-wootbook.rules](../../system/udev/99-ite8291-wootbook.rules)
4. Add a small unit test proving probe behavior stays safe:
   - Prefer tests like [src/tests/test_ite_probe_unit.py](../../src/tests/test_ite_probe_unit.py)
5. Update docs/installer messaging if it references a single PID.

## Verifying an ID belongs to the right backend (before submitting)

Before adding a new VID:PID to any backend allowlist, validate the protocol family on the real machine.

### For the IT8291r3 backend

1. Confirm the device is present:
   - `lsusb | rg -i "048d"`
2. Locally (not in a PR yet), add your VID:PID to the fallback list:
   - [src/core/backends/ite8291r3/backend.py](../../src/core/backends/ite8291r3/backend.py) (`_FALLBACK_USB_IDS`)
3. Confirm KeyRGB can open it (permission issues aside):
   - Instantiate `Ite8291r3Backend().get_device()` in a minimal script, or run the tray/app and apply any simple static color.
4. Only once it actually works end-to-end (open + apply), submit a PR that adds:
   - the VID:PID in `_FALLBACK_USB_IDS`
   - a unit test update (probe behavior)
   - a udev rule update (if needed)

If the device is present but `probe()` reports it as "unsupported" (denylisted), do not add it to IT8291r3.

### For the IT8297/8176-family scaffold backend

KeyRGB currently contains an `ite8297` backend scaffold, but it is not implemented. It cannot be used to validate a protocol family yet.
If your device looks like an IT8297/8176-family controller (e.g. `0x048d:0x8297`, `0x048d:0x5702`, `0x048d:0xc966`), please open an issue with:

- `lsusb -v -d 048d:PID` output (redact serial if desired)
- `keyrgb diagnostics` output (if available)
- laptop model + OEM branding

## Context management for bulk mining

When processing many OEM model downloads, keep the process lightweight:

- Store only the **facts** you need (VID/PID pairs + source filename/path + OEM model name/version).
- Avoid committing proprietary binaries into the repo.
- Add IDs in small batches with a note about the source and confidence level.

## Future improvement (optional)

A safe “self-mining” enhancement would be to add diagnostics that:

- logs detected `0x048d:*` USB devices as “seen but not in allowlist”
- does **not** auto-enable support

This helps collect real-world IDs without expanding support blindly.
