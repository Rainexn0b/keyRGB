# Audit: `ite8295_zones` — Lenovo 4-zone keyboard (ITE 8295)

**Audit date:** 2026-07-04  
**Backend source:** `src/core/backends/ite8295_zones/` (4 files, ~620 LOC)  
**Test file:** `tests/core/backends/ite/test_ite8295_zones_backend_unit.py` (20 tests)  
**Stability:** `EXPERIMENTAL`  
**Evidence level:** `REVERSE_ENGINEERED`  
**Priority:** 97

## References

1. **OpenRGB** `Controllers/LenovoControllers/Lenovo4ZoneUSBController/` — primary C++ reference.
   - `LenovoDevices4Zone.h` — constants and LED/zone definitions
   - `Lenovo4ZoneUSBController.h` / `.cpp` — packet builder and HID transport
   - `Lenovo4ZoneUSBControllerDetect.cpp` — USB detection
   - `RGBController_Lenovo4ZoneUSB.cpp` — mode/effect definitions
2. **L5P-Keyboard-RGB** (`4JX/L5P-Keyboard-RGB`, 515★) — independent Rust reference.
   - `driver/src/lib.rs` — known device table and payload builder

## Summary

**No protocol bugs found.** Every protocol constant — VID/PID, usage page/usage, packet size,
header bytes, effect IDs, brightness levels, speed range, 4-zone layout, wave direction flags,
and even zone name strings — is a byte-for-byte match with both OpenRGB and L5P-Keyboard-RGB.

One minor copy-paste error was fixed: the `open_matching_hidraw_transport` error message said
"ITE 8291 IDs" instead of "ITE 8295 4-zone IDs".

The main actionable finding is that KeyRGB only supports PID `0xC963`, while both public
references confirm the same protocol works across **8–11 PIDs** in the Lenovo Legion/Ideapad
4-zone keyboard family.

## Detailed Comparison

### 1. Protocol constants

| Constant | KeyRGB | OpenRGB | L5P-KB-RGB | Match |
|----------|--------|---------|------------|-------|
| `VENDOR_ID` | `0x048D` | `ITE_VID = 0x048D` | `0x048d` | ✅ |
| `USAGE_PAGE` | `0xFF89` | `LENOVO_PAGE = 0xFF89` | `0xff89` | ✅ |
| `USAGE` | `0x00CC` | `LENOVO_USAGE = 0xCC` | `0x00cc` | ✅ |
| `PACKET_SIZE` | `33` | `LENOVO_4_ZONE_HID_PACKET_SIZE = 33` | `[u8; 33]` | ✅ |
| `HEADER_0` | `0xCC` | `header[0] = 0xCC` | `payload[0] = 0xcc` | ✅ |
| `HEADER_1` | `0x16` | `header[1] = 0x16` | `payload[1] = 0x16` | ✅ |
| `EFFECT_STATIC` | `0x01` | `1` | `0x01` | ✅ |
| `EFFECT_BREATHING` | `0x03` | `3` | `0x03` | ✅ |
| `EFFECT_WAVE` | `0x04` | `4` | `0x04` | ✅ |
| `EFFECT_SMOOTH` | `0x06` | `6` | `0x06` | ✅ |
| `RAW_BRIGHTNESS_LOW` | `0x01` | `1` | `1` | ✅ |
| `RAW_BRIGHTNESS_HIGH` | `0x02` | `2` | `2` | ✅ |
| `RAW_SPEED_MIN` | `0x01` | `1` | `1` | ✅ |
| `RAW_SPEED_MAX` | `0x04` | `4` | `4` | ✅ |
| `NUM_ZONES` | `4` | `4` | `4` | ✅ |

---

### 2. Packet layout

**KeyRGB `build_report()`:**
```
[0]  0xCC          header
[1]  0x16          header
[2]  effect        (0x01/0x03/0x04/0x06)
[3]  speed         (1-4)
[4]  brightness    (1=low, 2=high)
[5..7]   Zone 0 RGB
[8..10]  Zone 1 RGB
[11..13] Zone 2 RGB
[14..16] Zone 3 RGB
[17] 0x00
[18] wave_ltr flag
[19] wave_rtl flag
[20..32] padding (zeros)
```

**OpenRGB `Lenovo4ZoneUSBController.cpp::setMode()`:** identical layout.

**L5P-KB-RGB `build_payload()`:** identical layout.

**Finding:** ✅ Byte-for-byte match across all three implementations.

---

### 3. Wave direction flags

| Direction | KeyRGB | L5P-KB-RGB | Match |
|-----------|--------|------------|-------|
| Left / RTL | `(wave_ltr=0, wave_rtl=1)` → byte[19]=1 | `LeftWave` → `payload[19] = 0x1` | ✅ |
| Right / LTR (default) | `(wave_ltr=1, wave_rtl=0)` → byte[18]=1 | `RightWave` → `payload[18] = 0x1` | ✅ |

**Finding:** ✅ Exact match.

---

### 4. Zone names

KeyRGB: `("Left side", "Left center", "Right center", "Right side")`
OpenRGB: identical strings in `lenovo_4_zone_leds[]`.

**Finding:** ✅ Verbatim match.

---

### 5. USB PID coverage

| Source | PIDs |
|--------|------|
| **KeyRGB** | `0xC963` only |
| OpenRGB | `0xC955`, `0xC965`, `0xC963`, `0xC973`, `0xC975`, `0xC984`, `0xC985` |
| L5P-KB-RGB | `0xC955`, `0xC963`, `0xC965`, `0xC973`, `0xC975`, `0xC983`, `0xC984`, `0xC985`, `0xC993`, `0xC994`, `0xC995` |

**Finding:** KeyRGB's PID coverage is now aligned with OpenRGB's Lenovo 4-zone family.
The protocol is identical across all listed PIDs — same VID, same usage page/usage,
same 33-byte packet format. Both public references treat them as one device family.

**Action taken:** `SUPPORTED_PRODUCT_IDS` expanded to
`0xC955, 0xC963, 0xC965, 0xC973, 0xC975, 0xC984, 0xC985`, and udev rules updated.

**Risk:** Low. These PIDs are explicitly listed in OpenRGB's detection table; the
alternative is users with Legion 5 2022 (`0xC975`), 2023 (`0xC984`/`0xC985`), or
newer models seeing "no matching hidraw device" despite compatible hardware.

---

### 6. Copy-paste error in error message (fixed)

**Original** (`backend.py` line 53):
```python
"No hidraw device found for supported ITE 8291 IDs: "
```

**Fixed:**
```python
"No hidraw device found for supported ITE 8295 4-zone IDs: "
```

This was a copy-paste from the `ite8291` backend template. The error message is only shown
when no device is found, so it would not have caused functional issues, but it would confuse
users reading the error.

---

### 7. Brightness model

The hardware supports only 2 brightness levels: `1` (low) and `2` (high). KeyRGB maps its
UI 0–50 scale to these two levels via `raw_brightness_from_ui()`, with the midpoint at 25.

This is a reasonable UI policy. OpenRGB and L5P-KB-RGB expose the same two-level hardware
range.

**Finding:** ✅ Correct.

---

### 8. Capabilities

```python
BackendCapabilities(per_key=False, color=True, hardware_effects=True, palette=False)
```

This is correct: the 4-zone device supports per-zone color and hardware effects (breathing,
wave, smooth/spectrum_cycle), but not per-key control.

---

### 9. Naming note

"ITE 8295" is KeyRGB-internal terminology. Public sources (OpenRGB, L5P-KB-RGB) call this the
"Lenovo Legion/Ideapad 4-zone keyboard." The VID `0x048d` is ITE Tech Inc., so an ITE part is
implied, but no public source documents the chip model number as "8295."

This does not affect functionality but may impact user-facing discoverability.

---

## Test Coverage

| Area | Tests | Coverage |
|------|-------|----------|
| Static report bytes | 1 | ✅ |
| Breathing report bytes | 1 | ✅ |
| Wave report with direction | 1 | ✅ |
| Turn-off report bytes | 1 | ✅ |
| `set_color` single report | 1 | ✅ |
| `set_key_colors` zone indices | 1 | ✅ |
| `set_key_colors` average fallback | 1 | ✅ |
| Turn-off device behavior | 1 | ✅ |
| `set_effect` wave with direction | 1 | ✅ |
| `set_brightness` reapplies last effect | 1 | ✅ |
| Experimental metadata | 1 | ✅ |
| Forced hidraw path | 1 | ✅ |
| Probe unavailable/disabled/opt-in | 4 | ✅ |
| Transport open error wrapping | 4 | ✅ |
| Device type and report | 1 | ✅ |
| Fixed dimensions/effects/colors | 1 | ✅ |
| `is_available` reflects probe | 1 | ✅ |

Total: **20 tests** — comprehensive coverage.

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | Fix copy-paste error message ("ITE 8291" → "ITE 8295 4-zone") | Code | Low | ✅ Done |
| 2 | Widen `SUPPORTED_PRODUCT_IDS` to include OpenRGB-confirmed Lenovo 4-zone family | Code | Medium | ✅ Done |
| 3 | Update udev rules for new ITE8295 4-zone PIDs | Rules | Medium | ✅ Done |
| 4 | Consider referencing "Lenovo Legion 4-zone" in user-facing docs for discoverability | Docs | Low | ⏳ Follow-up |

**Overall: VALIDATED AS EXPERIMENTAL** — byte-for-byte protocol match with OpenRGB and
L5P-Keyboard-RGB. PID coverage is the main improvement opportunity.
