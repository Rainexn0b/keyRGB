# Audit: `sysfs-leds` — sysfs LED subsystem backend

**Audit date:** 2026-07-03
**Backend source:** `keyrgb/core/backends/sysfs/` (5 files, ~900 LOC)
**Test file:** `tests/core/backends/general/test_sysfs_leds_backend_unit.py` (42 collected tests)
**Stability:** `VALIDATED`
**Priority:** 150 (highest)
**Surface:** Every KeyRGB user with a kernel-supported keyboard backlight

## Reference Documents

1. **Linux kernel LED class documentation** (`Documentation/leds/leds-class.rst`):  
   Canonical ABI for `/sys/class/leds/*`. Defines `brightness`, `max_brightness`, naming scheme
   `"devicename:color:function"`, and the mandatory `:kbd_backlight` suffix for keyboard
   backlight LEDs.

2. **Linux kernel multi-color LED class documentation** (`Documentation/leds/leds-class-multicolor.rst`):  
   Defines `multi_intensity` (space-separated per-channel intensities), `multi_index` (color
   name array), and `multi_max_intensity` (per-channel max). Brightness scales the
   `multi_intensity` values proportionally.

3. **tuxedo-drivers source** (out-of-tree, v5.x+):  
   - `clevo_leds.h` — registers `rgb::kbd_backlight` (1 or 3 zones) via multi-color LED class
   - `uniwill_leds.h` — registers `rgb::kbd_backlight` (1 zone) via multi-color LED class
   - `ite_8291.c` — registers `rgb::kbd_backlight` ×126 per-key via multi-color LED class
   - `ite_8297.c` — registers `ite_8297:1` (R), `ite_8297:2` (G), `ite_8297:3` (B) as
     individual single-color LED class devices
   - `ite_829x.c` — registers `rgb::kbd_backlight` ×120 per-key via multi-color LED class

4. **In-kernel drivers** (torvalds/linux):  
   - `system76_acpi.c` — custom `color` attribute (hex `RRGGBB`), not multi-color class
   - `asus-wmi.c` — `asus::kbd_backlight` (brightness-only), separate platform sysfs attrs for RGB
   - `dell-wmi-led.c` — `dell::kbd_backlight` (brightness-only)
   - `hp-wmi.c` — multi-color LED class for `hp::kbd_backlight` (single/multi zone)

5. **OpenRGB**: ClevoKeyboardController does **not** use sysfs at all — it goes via USB HID
   directly. No sysfs reference to compare.

## Methodology

| Check | KeyRGB Source | Reference | Result |
|-------|---------------|-----------|--------|
| LED naming filter | `_is_candidate_led()` | Kernel doc: name must end with `:kbd_backlight` | ✅ Broad filter + scoring; correct |
| Candidate scoring | `_score_led_dir()` | Heuristic, no kernel equivalent | ✅ Sound design |
| `multi_intensity` format | `_multi_intensity_content()` | Kernel multi-color class: space-sep values | ✅ Matches |
| `multi_intensity` color order | `multi_index` when present; R G B fallback | Kernel `multi_index`; tuxedo-drivers default R-G-B | ✅ Correct |
| `multi_index` read-back | Cached during zone discovery | Kernel provides `multi_index` to verify color order | ✅ **Resolved** |
| `color` attribute (System76) | Uppercase hex `RRGGBB` | system76_acpi.c: `kstrtouint()` (case-insensitive) | ✅ Safe; uppercase works |
| `rgb` attribute (generic) | `f"{r} {g} {b}\n"` | Not a standard kernel interface; used by some platform drivers | ✅ Generic |
| ite_8297 channel detection | `ite_8297:1`/`:2`/`:3` triplets | tuxedo-drivers `ite_8297.c`: exactly these names | ✅ Match |
| ite_8297 brightness scaling | `rgb * (brightness/50)` | Kernel has no scaling for separate-channel LEDs | ✅ Sensible |
| Privileged helper LED filter | `kbd_backlight` or `ite_8297:[123]` | Security measure | ✅ **Resolved** |
| Duplicate ite_8297 scoring | Removed duplicate `+35` | Heuristic cleanup | ✅ **Resolved** |
| Multi-zone key mapping | X-coordinate bucket | No kernel spec; app-level choice | ✅ Correct for virtual zones |
| Test coverage | 28 tests | N/A | ✅ Excellent |

## Findings

### Finding 1 (resolved): `multi_index` color order handling

**Files:** `device.py`, `_device_methods.py`

**Original risk:** When writing to `multi_intensity`, the code assumed the color channel
order was always R, G, B. The kernel multi-color class docs state: *"The order of the
colors will be arbitrary."* The sibling `multi_index` file provides the canonical mapping
from index to color name.

**Resolution:** `SysfsLedKeyboardDevice` now reads and caches `multi_index` during sysfs
zone discovery. `_multi_intensity_content()` uses that cached order when writing
`multi_intensity`, while preserving the old R-G-B fallback if `multi_index` is absent,
unreadable, or contains unsupported channel names.

**Validation:** Added tests for `blue green red` reordering and unknown-index fallback.

**Severity:** Resolved. The backend now follows the kernel ABI while preserving behavior
for known TUXEDO/Clevo drivers that expose `red green blue`.

---

### Finding 2 (resolved): Privileged helper accepts ite_8297 channel names

**File:** `privileged.py`, `helper_can_apply_led()`:

```python
if "kbd_backlight" not in name.lower() and not _is_ite8297_channel(name):
    return False
```

**What changed:** The helper still keeps the conservative `kbd_backlight` allowlist, but now
also accepts the known tuxedo-drivers ITE 8297 channel triplet: `ite_8297:1`, `ite_8297:2`,
and `ite_8297:3`.

**Impact:** On real hardware, ite_8297 channels are created by the tuxedo-drivers kernel
module with appropriate permissions already set, so the helper is never needed. This is
purely a theoretical gap.

**Validation:** Updated privileged-helper and probe tests to assert channels 1–3 are allowed,
while invalid `ite_8297:4` remains rejected.

**Severity:** Resolved.

---

### Finding 3 (resolved): Duplicate `ite_8297:` scoring bonus

**File:** `common.py`, `_score_led_dir()`:

```python
# Line 92-93
if name.startswith("ite_8297:"):
    score += 35

...

# Duplicate bonus removed.
```

**What changed:** The duplicate `+35` bonus under the RGB-capability section was removed.
ITE 8297 channels still receive the intended strong name-signal score.

**Severity:** Resolved. This was a heuristic cleanup with no expected behavior change on
real hardware.

---

### Finding 4 (informational): `brightness` attribute semantics for multi-color LEDs

**What:** For multi-color LED class devices (`multi_intensity` present), the kernel applies
brightness scaling automatically: `effective = brightness * intensity / max_brightness`.
KeyRGB writes the full RGB values to `multi_intensity` (unscaled) and then writes a separate
brightness value. This is the correct approach — it lets the kernel do the scaling.

See `_device_methods.py` lines 55–59:
```python
# Writes full RGB values (not scaled by brightness)
common._safe_write_text(multi_intensity_path, _multi_intensity_content(zone, color))
self._set_zone_brightness(led_dir, self._to_sysfs_brightness(brightness))
```

**Severity:** ✅ Correct, no action needed.

---

### Finding 5 (informational): `close()` is a no-op — no persistent transport

**File:** `device.py`, line 330–332:

```python
def close(self) -> None:
    # No persistent transport to release for sysfs.
    return
```

**What:** Sysfs reads/writes are stateless file operations — no file handles or URBs to
release. This is correct by design.

**Severity:** ✅ Correct, no action needed.

---

### Finding 6 (informational): `_max()` does not cache `max_brightness`

**File:** `device.py`, line 160–165:

```python
def _max(self) -> int:
    try:
        m = common._read_int(self.max_brightness_path)
        return max(1, int(m))
    except _SYSFS_STATE_ERRORS:
        return 1
```

**What:** `max_brightness` is read from sysfs on every call. While this is technically a
sysfs read per call, `max_brightness` is stable for a given hardware session. The kernel
LED class does not change `max_brightness` after registration.

**Severity:** ✅ Correct (safe, no caching issues). If performance were ever a concern,
this could be cached with a lazy-init pattern, but it's not a bottleneck.

---

### Finding 7 (informational): Keyboard naming conformance

The candidate filter and scoring function align with the kernel LED class naming convention
from `Documentation/leds/leds-class.rst`:

- `_is_candidate_led()` matches names containing `kbd`, `keyboard`, `rgb:kbd`,
  `tuxedo::kbd`, `clevo::kbd`, `hp_omen::kbd`, `dell::kbd`, `tpacpi::kbd`, `asus::kbd`,
  `system76::kbd`, `ite_8297:`
- The scoring function gives +40 for exact `kbd_backlight` substring match and an
  additional +10 if the name ends with `kbd_backlight`
- Lock-key LEDs (`capslock`, `numlock`, `scrolllock`, `micmute`, `mute`) are penalized −60

This matches the kernel convention that keyboard backlight LED names must end with
`:kbd_backlight` (or the newer `:kbd_zoned_backlight-*` pattern).

**Severity:** ✅ Correct, no action needed.

---

## Test Coverage Analysis

| Area | Tests | Coverage |
|------|-------|----------|
| Probe (available/unavailable) | 3 | ✅ |
| LED enumeration errors | 1 | ✅ |
| Capabilities error handling | 1 | ✅ |
| Scoring / candidate selection | 4 | ✅ |
| Brightness read/write | 1 | ✅ |
| ITE 8297 channel triplet detection & state | 5 | ✅ |
| System76 `color_*` files | 1 | ✅ |
| `multi_intensity` color setting | 3 | ✅ |
| `multi_index` channel order/fallback | 2 | ✅ |
| `color` attribute | 1 | ✅ |
| `rgb` attribute | 2 | ✅ |
| Helper fallback for color | 2 | ✅ |
| Helper fallback for brightness | 1 | ✅ |
| Virtual N-zone key mapping | 1 | ✅ |
| Debug logging isolation | 6 | ✅ |
| `_safe_write_text` tripwire | 2 | ✅ |
| `is_off` / `turn_off` | 1 | ✅ |
| `set_effect` no-op | 1 | ✅ |
| API stability | 1 | ✅ |

Total: **42 collected tests** — comprehensive coverage of all major code paths, error handling,
privileged helper fallback, and debug logging isolation.

**Gap:** No test covers reading `multi_max_intensity` or verifying its clamping behavior.
However, this is kernel-side behavior; KeyRGB relies on the kernel to clamp. Not a test
gap per se — KeyRGB intentionally delegates to the kernel.

## External Interface Summary

The backend implements the `KeyboardBackend` / `KeyboardDevice` protocol:

```python
class SysfsLedsBackend(KeyboardBackend):
    name = "sysfs-leds"
    priority = 150
    stability = BackendStability.VALIDATED
    # probe(), is_available(), capabilities(), get_device(), dimensions(), effects(), colors()

class SysfsLedKeyboardDevice(KeyboardDevice):
    # get_brightness(), set_brightness(), set_color(), set_key_colors(),
    # set_effect(), turn_off(), is_off(), close(), capabilities()
```

The `KeyboardBackend.capabilities()` reports:
- `per_key`: `True` if N-zones > 1 (virtual zone mapping enabled)
- `color`: `True` if any zone supports `multi_intensity`, `color`, `rgb`, or `color_*` attrs
- `hardware_effects`: always `False` (sysfs has no effect engine)
- `palette`: always `False`

This is the correct contract. ✅

## Summary

| Category | Status |
|----------|--------|
| **Protocol correctness** | ✅ All sysfs file formats match kernel specs |
| **Color order (multi_intensity)** | ✅ Uses kernel `multi_index` when present, R-G-B fallback otherwise |
| **ITE 8297 channel detection** | ✅ Matches tuxedo-drivers ite_8297.c |
| **System76 color attr** | ✅ Uppercase hex works |
| **Scoring heuristics** | ✅ Sound; duplicate ite_8297 bonus removed |
| **Privileged helper** | ✅ Conservative; includes known ite_8297 channel triplet |
| **Error handling** | ✅ Comprehensive try/except coverage |
| **Test coverage** | ✅ 42 sysfs-leds tests, excellent coverage |
| **Public API stability** | ✅ No changes needed |

**Overall: VALIDATED** — no protocol bugs found. All sysfs audit residuals are resolved.

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | **Read `multi_index` to verify color order** before writing `multi_intensity` | Code | Low | ✅ Done |
| 2 | **Extend `helper_can_apply_led()`** to accept `ite_8297:[123]` patterns | Code | Low | ✅ Done |
| 3 | **Remove duplicate `ite_8297:` scoring** in `_score_led_dir()` | Cleanup | Informational | ✅ Done |
