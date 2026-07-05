# Audit: `ite8291_zones` — ITE 8291 4-zone CE00 bcdDevice=0x0002 backend

**Audit date:** 2026-07-04  
**Backend source:** `src/core/backends/ite8291_zones/` (4 files, ~440 LOC)  
**Test file:** `tests/core/backends/ite/test_ite8291_zones_backend_unit.py` (18 tests)  
**Stability:** `EXPERIMENTAL`  
**Evidence level:** `REVERSE_ENGINEERED`  
**Priority:** 96

## References

1. **tuxedo-drivers** `src/ite_8291/ite_8291.c` — the canonical kernel driver. The zone-mode
   functions (`ite8291_zones_write_on`, `ite8291_zones_write_off`,
   `ite8291_zones_write_state`) and the firmware split logic
   (`hdev->product == 0xce00 && driver_data->bcd_device == 0x0002`) are the sole public
   protocol reference.

## Summary

**No protocol bugs found.** Every report — zone enable, zone color define, commit/apply mode,
and the 5-report turn-off sequence — is a byte-for-byte match with the tuxedo-drivers kernel
driver. The CE00 bcdDevice=0x0002 firmware split is correctly enforced in both probe and
transport-open paths.

No code changes were required.

## Detailed Comparison

### 1. USB ID and firmware split

| Source | VID | PID | bcdDevice | Route |
|--------|-----|-----|-----------|-------|
| tuxedo-drivers | `0x048d` | `0xce00` | `0x0002` | `ite8291_zones_add` / `zones_write_state` |
| KeyRGB | `0x048d` | `0xce00` | `0x0002` | `Ite8291ZonesBackend` |

TUXEDO uses the same PID `0xce00` for both per-key (bcdDevice `0x0003`) and zone-only
(bcdDevice `0x0002`) firmware. The split is purely on `bcdDevice`. KeyRGB correctly enforces
this in both `_find_matching_supported_hidraw_device()` and `_open_matching_transport()`.

**Finding:** ✅ Exact match.

---

### 2. Zone enable report (`zones_write_on`)

**tuxedo-drivers:**
```c
ite8291_write_control(hdev, (u8[]){ 0x1a, 0x00, 0x01, 0x04, 0x00, 0x00, 0x00, 0x01 });
```

**KeyRGB:**
```python
def build_zone_enable_report() -> bytes:
    return bytes((0x1A, 0x00, 0x01, 0x04, 0x00, 0x00, 0x00, 0x01))
```

**Finding:** ✅ Byte-for-byte match.

---

### 3. Zone color define report

**tuxedo-drivers** (`ite8291_zones_write_state`):
```c
for (i = 0; i < ITE8291_NR_ZONES; ++i) {
    // ... color_scaling() quirk ...
    ite8291_write_control(hdev, (u8[]){ 0x14, 0x00, i + 1, red, green, blue, 0x00, 0x00 });
}
```

**KeyRGB:**
```python
def build_zone_color_report(zone_index: int, color) -> bytes:
    zone = int(zone_index)
    red, green, blue = _coerce_rgb(color)
    return bytes((0x14, 0x00, zone + 1, clamp_channel(red), clamp_channel(green), clamp_channel(blue), 0x00, 0x00))
```

**Finding:** ✅ Byte-for-byte match. Zone indices are 1-based in the packet (`zone + 1`),
matching TUXEDO.

---

### 4. Commit / apply mode report

**tuxedo-drivers** (after zone color writes):
```c
ite8291_write_control(hdev, (u8[]){ 0x08, 0x02, 0x01, 0x03, brightness, 0x08, 0x00, 0x00 });
```

**KeyRGB:**
```python
def build_commit_state_report(brightness: int) -> bytes:
    return bytes((0x08, 0x02, 0x01, 0x03, clamp_ui_brightness(brightness), 0x08, 0x00, 0x00))
```

**Finding:** ✅ Byte-for-byte match. Brightness max is `0x32` (50) in both implementations.

---

### 5. Turn-off sequence (`zones_write_off`)

**tuxedo-drivers** (5 reports in order):
```c
ite8291_write_control(hdev, (u8[]){ 0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 });
ite8291_write_control(hdev, (u8[]){ 0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00 });
ite8291_write_control(hdev, (u8[]){ 0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 });
ite8291_write_control(hdev, (u8[]){ 0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 });
ite8291_write_control(hdev, (u8[]){ 0x1a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01 });
```

**KeyRGB** (`build_turn_off_reports`):
```python
(
    bytes((0x09, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    bytes((0x12, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00)),
    bytes((0x08, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    bytes((0x08, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)),
    build_zone_disable_report(),  # (0x1A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01)
)
```

**Finding:** ✅ Byte-for-byte match, all 5 reports in the same order.

---

### 6. Write sequence for `set_color`

| Step | tuxedo-drivers (`zones_write_state`) | KeyRGB (`_apply_current_state`) |
|------|---------------------------------------|---------------------------------|
| 1 | `zones_write_on` (enable) | `build_zone_enable_report()` |
| 2 | 4× zone color define | 4× `build_zone_color_report(zone, color)` |
| 3 | commit/apply mode | `build_commit_state_report(brightness)` |

**Finding:** ✅ Same report order.

---

### 7. Number of zones and brightness range

| Constant | tuxedo-drivers | KeyRGB |
|----------|----------------|--------|
| Zone count | `ITE8291_NR_ZONES = 4` | `NUM_ZONES = 4` |
| Brightness max | `ITE8291_KBD_ZONES_BRIGHTNESS_MAX = 0x32` (50) | `UI_BRIGHTNESS_MAX = 50` |

**Finding:** ✅ Match.

---

### 8. DMI color scaling quirks

TUXEDO applies `color_scaling()` quirks for specific DMI product SKUs (e.g., Stellaris
models). KeyRGB does not apply DMI-specific scaling in this backend.

This is the same observation as the sibling `ite8291` per-key audit. KeyRGB's calibration/
profile workflow is the intended path for color accuracy corrections, not hardcoded protocol
scaling.

**Finding:** ✅ Policy difference, not a protocol bug.

---

### 9. Transport path

KeyRGB reuses the `ite8291.hidraw.HidrawFeatureOutputTransport`, which uses
`ioctl(HIDIOCSFEATURE)` to send 8-byte feature reports. TUXEDO uses
`hid_hw_raw_request(..., HID_FEATURE_REPORT, HID_REQ_SET_REPORT)` from kernel space. Both
produce the same USB HID control transfer.

**Finding:** ✅ Correct.

---

### 10. Capabilities and public contract

```python
BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)
```

This is correct: the zone-only firmware supports 4-zone RGB color but not per-key control or
hardware effects.

---

## Test Coverage

| Area | Tests | Coverage |
|------|-------|----------|
| Zone enable report bytes | 1 | ✅ |
| Zone color report bytes | 1 | ✅ |
| Commit state report bytes | 1 | ✅ |
| Turn-off sequence bytes | 1 | ✅ |
| `set_color` write order | 1 | ✅ |
| `set_key_colors` average fallback | 1 | ✅ |
| Turn-off device behavior | 1 | ✅ |
| Experimental metadata | 1 | ✅ |
| Forced hidraw path | 1 | ✅ |
| Probe unavailable/disabled/opt-in | 3 | ✅ |
| bcdDevice mismatch rejection | 1 | ✅ |
| Transport open error wrapping | 4 | ✅ |
| Device type and write order | 1 | ✅ |
| Fixed dimensions/effects/colors | 1 | ✅ |
| `is_available` reflects probe | 1 | ✅ |

Total: **18 tests** — comprehensive for this backend.

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | — | — | — | No changes needed |

**Overall: VALIDATED AS EXPERIMENTAL** — byte-for-byte protocol match with tuxedo-drivers
zone path. No bugs, no code changes required.
