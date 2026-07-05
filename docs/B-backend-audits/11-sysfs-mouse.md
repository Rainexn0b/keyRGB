# Audit: `sysfs-mouse` — auxiliary sysfs LED backend for mice

**Audit date:** 2026-07-04  
**Backend source:** `src/core/backends/sysfs_mouse/` (3 files, ~412 LOC)  
**Test file:** `tests/core/backends/general/test_sysfs_mouse_backend_unit.py` (4 tests)  
**Stability:** `EXPERIMENTAL`  
**Evidence level:** `SPECULATIVE`  
**Priority:** 10

---

## References

1. **Linux kernel LED class docs** — `leds-class.rst`, `leds-class-multicolor.rst`
2. **OpenRGB** mouse controllers (Logitech HID++ 2.0, Razer) — used for real-world
   mouse LED naming conventions and sysfs usage patterns, though OpenRGB talks
   HID directly rather than sysfs.
3. **KeyRGB `sysfs-leds` backend** — shares `SysfsLedKeyboardDevice`, `_device_methods.py`,
   `common.py`, and `privileged.py`.

---

## Summary

`sysfs-mouse` is a thin scoring/filtering layer over the existing sysfs LED
infrastructure. It reuses the well-audited sysfs LED writing logic from
`sysfs-leds`, so the core protocol is sound.

**No functional bugs found** in the LED write path. The main improvement
opportunities are around **heuristic coverage**, **test coverage**, and a
small **scoring edge case**.

### Findings

1. **Vendor coverage is reasonable but not exhaustive.** The current vendor
   list covers the major gaming-mouse brands. OpenRGB's controller set is much
   larger; missing vendors include `coolermaster`, `asus`, `msi`, `zhaoxin`,
   `keychron`, `vgn`, `attackshark`, etc. However, adding tokens without real
   sysfs node names to test against is low-value.
2. **Scoring prioritizes multicolor capability too strongly for a simple mouse.**
   `_is_color_capable_led()` gives `+50` for `multi_intensity`/`color`/`rgb`.
   This is fine, but the total score can become dominated by color support and
   accidentally outrank a more specific name match. In practice this is
   mitigated by the noisy-token filter and the sort key, but it is worth
   watching.
3. **`dimensions()` returns `(1, 1)` effectively.** It calls
   `safe_int_attr(self, "_zone_count_hint", default=1)` on the backend instance,
   which has no `_zone_count_hint` attribute. The device class inherits from
   `SysfsLedKeyboardDevice`, which computes zones from sysfs. The backend's
   `dimensions()` therefore always returns `(1, 1)`, regardless of how many
   mouse LED zones were found.
4. **Test coverage is thin** (4 tests) compared to other backends (20–58 tests).
   Edge cases like multiple zones, permission-fallback via helper, brightness
   scaling, and `set_key_colors` averaging are not exercised.
5. **No udev/rules work needed** — this backend operates entirely through
   existing sysfs LED nodes; permissions depend on the system's LED group/
   uaccess rules, not a KeyRGB-specific rule.

---

## Detailed Comparison

### 1. LED naming heuristics vs. kernel conventions

The kernel LED class naming convention is:

```text
<devicename>:<color>:<function>
```

Examples:
- `input5::numlock`
- `:kbd_backlight`
- `usbmouse::rgb`

**KeyRGB heuristic tokens:**

| Token group | Examples |
|-------------|----------|
| Mouse evidence | `mouse`, `pointer` |
| Vendor evidence | `logitech`, `razer`, `steelseries`, `corsair`, `roccat`, `glorious`, `hyperx`, `pulsar`, `lamzu`, `zowie`, `finalmouse`, `endgame` |
| Strong zone | `scroll`, `scrollwheel`, `wheel`, `dpi` |
| Weak zone | `logo` |
| Noisy exclusions | `capslock`, `numlock`, `scrolllock`, `micmute`, `mute`, `kbd`, `keyboard`, `lightbar`, `battery`, `charging`, `power`, `wlan`, `rfkill`, `tpacpi` |

**Logic:**
- LED is a candidate if:
  - name/metadata contains `mouse`/`pointer`; OR
  - vendor token + strong zone token (`logitech:scroll`); OR
  - vendor token + `logo` + metadata contains `mouse`/`pointer`.
- LED is excluded if any noisy token is present.

**Finding:** ✅ The heuristic is sound and conservative. It avoids false positives
from keyboard LEDs, lightbars, and system indicators. Real-world mouse sysfs
nodes from `hid-logitech-dj`, `razerdriver`, `rivalcfg`, etc. often include
vendor names in the device metadata, so vendor+zone fallback is plausible.

**Risk:** A non-gaming mouse LED that contains `mouse` in metadata but no RGB
attribute will be rejected by `_is_color_capable_led()`, so false positives are
low.

---

### 2. Color writing path

`SysfsMouseDevice` inherits `SysfsLedKeyboardDevice`, which writes:

1. `multi_intensity` (multicolor class) — with `multi_index`-aware ordering.
2. `color` (hex attribute, e.g. System76 style).
3. `rgb` (space-separated attribute).
4. `brightness` for dimming.

This is the same path audited in `sysfs-leds` and is correct per kernel docs.

**Finding:** ✅ Reuses audited sysfs LED logic.

---

### 3. Capabilities

```python
BackendCapabilities(per_key=False, color=True, hardware_effects=False, palette=False)
```

Correct for an auxiliary single/multi-zone mouse LED.

---

### 4. Dimensions edge case

`SysfsMouseBackend.dimensions()`:

```python
def dimensions(self) -> tuple[int, int]:
    return (1, max(1, safe_int_attr(self, "_zone_count_hint", default=1)))
```

The backend instance has no `_zone_count_hint`; this always returns `(1, 1)`.
The actual device instance (`SysfsMouseDevice`) would know the zone count, but
`KeyboardBackend.dimensions()` is called on the backend object.

**Impact:** Low. The tray/UI currently treats mouse as a uniform-capable
auxiliary device. If multi-zone mouse support is ever exposed, this will need
to reflect the real zone count or stay at `(1, 1)` intentionally.

**Recommendation:** Either document that mouse is intentionally single-zone, or
make `dimensions()` delegate to the discovered LED count.

---

### 5. Experimental opt-in

The backend correctly requires `KEYRGB_ENABLE_EXPERIMENTAL_BACKENDS=1` and
falls back to a helper when brightness is not writable. This mirrors
`sysfs-leds` behavior.

---

### 6. Comparison to OpenRGB mouse controllers

OpenRGB does **not** use sysfs for mouse control; it speaks vendor HID protocols
(Logitech HID++ 2.0, Razer USB HID, etc.). Therefore there is no direct protocol
to compare. The useful comparison is naming:

- OpenRGB has dedicated controllers per vendor.
- KeyRGB's sysfs approach is generic and will only work for mice whose kernel
driver exposes LED class nodes (e.g. `hid-logitech-dj` RGB variants,
`razerdriver` for some Razer mice, community drivers).

**Finding:** The scope is correctly limited to sysfs-exposed mouse LEDs.

---

## Test Coverage

| Area | Tests | Coverage |
|------|-------|----------|
| Basic probe + device roundtrip | 1 | ✅ |
| Experimental opt-in gate | 1 | ✅ |
| Metadata-backed vendor+logo match | 1 | ✅ |
| Reject non-mouse vendor logo without metadata | 1 | ✅ |
| Multi-zone handling | 0 | ⏳ |
| Brightness scaling | 0 | ⏳ |
| Helper fallback | 0 | ⏳ |
| `set_key_colors` averaging | 0 | ⏳ |
| Color attribute paths (`color`, `rgb`) | 0 | ⏳ |

Total: **4 tests** — thinner than other backends.

---

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | Document `dimensions()` behavior or align with discovered zone count | Code/Docs | Low | ⏳ Follow-up |
| 2 | Expand tests for multi-zone, helper fallback, brightness scaling, alternate color attrs | Tests | Medium | ⏳ Follow-up |
| 3 | Consider adding `coolermaster`, `keychron` once sysfs evidence exists | Code | Low | ⏳ Follow-up |

**Overall: VALIDATED AS EXPERIMENTAL** — no functional bugs; relies on
well-audited sysfs LED writing path. Heuristic coverage and test coverage are
the main improvement opportunities.
