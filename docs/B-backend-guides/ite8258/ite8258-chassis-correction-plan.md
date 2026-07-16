# `ite8258-chassis` Backend Correction Plan

## Status

Draft — pending review and hardware validation.

## Background

The `ite8258-chassis` backend was translated from OpenRGB's Gen10 Lenovo USB controller implementation and merged as an experimental keyboard-first path for `0x048d:0xc197` (Lenovo Legion Pro 7 16IAX10H and related Gen10 systems).

An independent research report (`../../../B-Research/Keyrgb Hardware Expansion Research.md`) compared KeyRGB's implementation against a separate, fully-working Linux implementation tested on the same `83F5` hardware platform. That comparison revealed **three confirmed discrepancies** and **one suspected discrepancy** in the protocol layer. The keyboard path works, but these discrepancies must be resolved before chassis-zone support (logo, neon, vents) can be considered reliable.

This document is the authoritative correction plan. All fixes described here must land **before** the secondary-device route refactor (`docs/I-implementation-plans/secondary-device-route-refactor-plan.md`) proceeds.

---

## Confirmed Discrepancies

### 1. Direction Encoding — Left / Right Reversed

**Severity:** Confirmed wrong. Affects user-visible effect behavior.

**Current KeyRGB (`src/core/backends/ite8258_perkey_chassis/protocol.py`):**
```python
DIRECTION_UP = 0x01
DIRECTION_DOWN = 0x02
DIRECTION_LEFT = 0x03
DIRECTION_RIGHT = 0x04
```

**83F5 working implementation:**
```
up    = 0x01
down  = 0x02
right = 0x03   # ← KeyRGB calls this LEFT
left  = 0x04   # ← KeyRGB calls this RIGHT
```

**Impact:**
- `rainbow_wave` and `color_wave` effects spin in the opposite horizontal direction from user expectation.
- Other direction-aware effects (if any) are similarly inverted.

**Fix:** Swap `DIRECTION_LEFT` and `DIRECTION_RIGHT` values:
```python
DIRECTION_LEFT = 0x04
DIRECTION_RIGHT = 0x03
```

**Validation:**
- Unit tests for `_direction_code()` must be updated.
- Hardware validation: ask the user to set `rainbow_wave` with `direction="right"` and confirm it moves rightward across the keyboard.

---

### 2. Chassis Zone LED IDs — Truncated 8-Bit Constants

**Severity:** Confirmed wrong. Would cause chassis-zone writes to address incorrect LEDs or be ignored entirely.

**Current KeyRGB (`src/core/backends/ite8258_perkey_chassis/protocol.py`):**
```python
LOGO_LED_IDS: tuple[int, ...] = (0xDD,)
NEON_LED_IDS: tuple[int, ...] = (0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE)
VENT_LED_IDS: tuple[int, ...] = (0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
                                 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6,
                                 0xF7, 0xF8, 0xF9, 0xFA)
```

The packet encoder writes LED IDs as **little-endian 16-bit** (`packet[offset] = led_id & 0xFF; packet[offset+1] = (led_id >> 8) & 0xFF`).

So `0xDD` emits `DD 00` in the packet. But the 83F5 implementation uses full 16-bit codes:

| Surface | KeyRGB constant | Packet bytes | 83F5 working code | Packet bytes |
|---------|-----------------|--------------|-------------------|--------------|
| Logo | `0xDD` | `DD 00` | `0x05DD` | `DD 05` |
| Side/front accent (neon) | `0xF5` | `F5 00` | `0x01F5` | `F5 01` |
| Rear accent (vents) | `0xE9` | `E9 00` | `0x03E9` | `E9 03` |

**Impact:**
- Any packet targeting logo, neon, or vent zones with current constants would address the wrong LED namespace.
- The overlap between `VENT_LED_IDS` (`0xE9–0xFA`) and `NEON_LED_IDS` (`0xF5–0xFE`) at `0xF5–0xFA` is an artifact of truncation, not a real hardware overlap.

**Fix:** Update constants to match the 83F5 implementation's 16-bit codes:
```python
LOGO_LED_IDS: tuple[int, ...] = (0x05DD,)

NEON_LED_IDS: tuple[int, ...] = (
    0x01F5, 0x01F6, 0x01F7, 0x01F8, 0x01F9, 0x01FA,
    0x01FB, 0x01FC, 0x01FD, 0x01FE,
)

VENT_LED_IDS: tuple[int, ...] = (
    0x03E9, 0x03EA, 0x03EB, 0x03EC, 0x03ED, 0x03EE, 0x03EF,
    0x03F0, 0x03F1, 0x03F2, 0x03F3, 0x03F4, 0x03F5, 0x03F6,
    0x03F7, 0x03F8, 0x03F9, 0x03FA,
)
```

**Note:** `build_direct_color_report()` already writes 16-bit little-endian LED IDs correctly:
```python
packet[offset] = hardware_led_id & 0xFF
packet[offset + 1] = (hardware_led_id >> 8) & 0xFF
```
So updating the constants is sufficient; no encoder change is required.

**Validation:**
- Unit tests must verify that `LOGO_LED_IDS[0]` produces packet bytes `DD 05`.
- Hardware validation: ask the user to send a red direct-color packet to `LOGO_LED_IDS` and confirm the lid logo lights up.

---

### 3. Header Framing Model — Dynamic Payload Length vs Fixed Report Size

**Severity:** Suspected discrepancy. Needs hardware validation.

**Current KeyRGB (`src/core/backends/ite8258_perkey_chassis/protocol.py`):**
```python
def _packet(command: int, payload_length: int) -> bytearray:
    packet = bytearray(PACKET_SIZE)
    packet[0] = REPORT_ID
    packet[1] = int(command) & 0xFF
    packet[2] = int(payload_length) & 0xFF
    packet[3] = (int(payload_length) >> 8) & 0xFF
    return packet
```

Bytes 2–3 encode the **actual payload length** (variable, depending on command and data).

**83F5 working implementation:**
```
header = [0x07, op_type, 0xC0, 0x03]  # 0x03C0 = 960 (full report size)
```

This suggests the controller may expect the **full report size** (960) in bytes 2–3 for every packet, not the dynamic payload length.

**Impact:**
- The keyboard works with dynamic-length headers, which suggests the controller is **tolerant** of both formats for simple commands.
- However, multi-packet sequences (e.g., large grouped-profile saves, or direct-color writes with many LEDs) might fail or be truncated if the controller expects fixed-size framing.
- The 83F5 implementation uses fixed-size headers for **all** commands, including single-byte brightness sets.

**Fix approach (two options):**

**Option A — Conservative (recommended):** Change `_packet()` to always write `PACKET_SIZE - 4` (or `0x03C0`) in bytes 2–3, matching the 83F5 implementation. The controller receives the full 960-byte report either way; only the header changes.

```python
def _packet(command: int, payload_length: int) -> bytearray:
    packet = bytearray(PACKET_SIZE)
    packet[0] = REPORT_ID
    packet[1] = int(command) & 0xFF
    # Fixed report size in header, per 83F5 implementation
    packet[2] = (PACKET_SIZE - 4) & 0xFF
    packet[3] = ((PACKET_SIZE - 4) >> 8) & 0xFF
    return packet
```

**Option B — Minimal:** Keep dynamic length for now, but add a toggle (env var or protocol constant) so we can switch if hardware validation reveals issues.

**Recommendation:** Option A. The 83F5 implementation is proven on real hardware. Fixed-size headers are simpler and remove a variable that could cause subtle bugs during multi-packet sequences.

**Validation:**
- All packet-builder unit tests must be updated to expect `C0 03` in bytes 2–3.
- Hardware validation: after the fix, verify keyboard color, brightness, and effects still work. If anything breaks, revert to Option B.

---

## Additional Gaps (Not Discrepancies, But Missing)

### 4. Missing Protocol Operations

The 83F5 implementation supports several commands that KeyRGB does not yet model:

| Command | Code | Purpose | KeyRGB status |
|---------|------|---------|---------------|
| Key count query | `0xC4` | Read keyboard LED count from controller | Missing |
| Key page query | `0xC5` | Read key-page layout info | Missing |
| Profile default/reset | `0xC9` | Reset profile to factory defaults | Missing |
| Logo status read | `0xA5` | Read current logo lighting state | Missing |
| Logo status write | `0xA6` | Write logo lighting state directly | Missing |

**Impact:** Low for keyboard-first support. These are advanced features for full chassis parity.

**Fix:** Add the constants to `protocol.py` as dormant definitions. Do not wire them into the device facade yet.

```python
# Dormant — not yet wired into device facade
GET_KEY_COUNT = 0xC4
GET_KEY_PAGE = 0xC5
RESET_PROFILE = 0xC9
GET_LOGO_STATUS = 0xA5
SET_LOGO_STATUS = 0xA6
```

---

### 5. Keyboard Layout — ANSI Matrix Map Only

**Clarification:** KeyRGB has full UI-level layout support. The per-key editor supports ANSI, ISO, KS, ABNT, and JIS visual layouts, and the calibrator lets users manually remap any key to any matrix cell. However, the `ite8258_perkey_chassis` **backend protocol constants** are currently ANSI-only.

**Current state:** `KEYBOARD_MATRIX_MAP` (140 slots mapping row/col to LED index) and `KEYBOARD_LED_IDS` are hardcoded for ANSI key positions. The `led_id_from_row_col()` function uses this map directly.

**Impact:**
- An ISO Legion Gen10 user would see misaligned keys (especially the ISO Enter and the key next to Left Shift) unless they manually recalibrate the entire keyboard.
- KeyRGB's visual layout switching and deck rendering would work fine, but the hardware matrix → LED ID translation would be wrong for ISO-specific key positions.

**Fix:** None required for this sprint. If an ISO user reports issues, the path forward is:
1. Add an ISO variant of `KEYBOARD_MATRIX_MAP` in `protocol.py`
2. Decide how the backend selects the correct variant (env var `KEYRGB_ITE8258_CHASSIS_LAYOUT`? auto-detect?)
3. Update `led_id_from_row_col()` to use the selected variant
4. No UI changes needed — the per-key editor already handles ISO visual layouts

---

## The `0xc193` Companion Device

**Status:** Confirmed out of scope.

The research report and the 83F5 implementation both confirm that **`0x048d:0xc193` ("Lenovo Lighting") is not the RGB controller.** All keyboard, logo, and accent lighting is driven through `0x048d:0xc197`.

**Action:**
- Keep the udev rule for `0xc193` (harmless, may be needed for future discovery)
- Do **not** add `0xc193` to any backend's `SUPPORTED_PRODUCT_IDS`
- Do **not** mention `0xc193` in user-facing troubleshooting docs

---

## Implementation Order

All fixes are backend-internal (no UI changes), so they can land incrementally:

### Sprint 1 — Direction fix + header fix

1. Swap `DIRECTION_LEFT` / `DIRECTION_RIGHT` in `protocol.py`
2. Update `_packet()` to use fixed report size in bytes 2–3
3. Update all packet-builder unit tests for new header bytes
4. Run `buildpython --profile=release`
5. Release as patch version (e.g., `0.25.11`)
6. Ask the user to validate: `rainbow_wave direction=right`, keyboard color/brightness/effects

### Sprint 2 — Chassis zone LED ID correction

1. Update `LOGO_LED_IDS`, `NEON_LED_IDS`, `VENT_LED_IDS` to 16-bit codes
2. Add dormant missing-op constants (`0xC4`, `0xC5`, `0xC9`, `0xA5`, `0xA6`)
3. Add unit tests verifying packet bytes for chassis-zone LED IDs
4. Run `buildpython --profile=release`
5. Release as patch version (e.g., `0.25.12`)
6. Ask the user to validate with a small test script:
   - Set logo to red (`0x05DD`)
   - Set neon to green (`0x01F5–0x01FE`)
   - Set vents to blue (`0x03E9–0x03FA`)

### Sprint 3 — Hardware validation confirmation

1. If all zones respond correctly, mark the protocol as **validated**
2. Update `ite8258-chassis-backend-plan.md` — mark Stage 1/2 as complete, Stage 3 validated
3. Update `AGENTS.md` and `README.md` with confirmed chassis-zone support notes
4. **Then** proceed with the secondary-device route refactor

---

## Files to Modify

| File | Change |
|------|--------|
| `src/core/backends/ite8258_perkey_chassis/protocol.py` | Swap direction constants; fix header framing; update chassis zone LED IDs; add dormant op constants |
| `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py` | Update expected packet bytes for new header; add chassis-zone packet tests; update direction tests |
| `src/core/backends/ite8258_perkey_chassis/device.py` | No changes in Sprint 1–2 (device facade stays keyboard-only until protocol is validated) |
| `docs/B-backend-guides/ite8258/ite8258-chassis-backend-plan.md` | Mark stages complete, add validation notes |
| `AGENTS.md` | Update supported-hardware notes if chassis zones are validated |
| `README.md` | Update backend table if chassis zones are validated |

---

## Test Plan

| Test | Sprint | What it proves |
|------|--------|----------------|
| `test_direction_code_left_right` | 1 | `_direction_code("left")` returns `0x04`, `_direction_code("right")` returns `0x03` |
| `test_packet_header_fixed_size` | 1 | Every packet builder emits `C0 03` in bytes 2–3 |
| `test_build_direct_color_logo_led_id` | 2 | `0x05DD` emits bytes `DD 05` in direct-color packet |
| `test_build_direct_color_neon_led_id` | 2 | `0x01F5` emits bytes `F5 01` |
| `test_build_direct_color_vent_led_id` | 2 | `0x03E9` emits bytes `E9 03` |
| `test_effect_group_direction_encoding` | 1 | `color_wave` with `direction="right"` uses `0x03` not `0x04` |
| Hardware: keyboard basics | 1 | Header fix does not break existing keyboard functionality |
| Hardware: direction validation | 1 | `rainbow_wave right` moves visually rightward |
| Hardware: logo red | 2 | Lid logo lights red when direct-color packet targets `0x05DD` |
| Hardware: neon green | 2 | Front strip lights green when targeting `0x01F5–0x01FE` |
| Hardware: vent blue | 2 | Side/rear vents light blue when targeting `0x03E9–0x03FA` |

---

## Rollback Plan

If the header fix (Sprint 1) breaks keyboard behavior:

1. Revert `_packet()` to dynamic payload length
2. Investigate whether specific commands need fixed-size headers while others tolerate dynamic
3. Consider per-command header strategy if the controller is selectively tolerant

If chassis zone LED IDs (Sprint 2) do not produce visible lighting:

1. Capture USB packet traces from the 83F5 implementation for comparison
2. Check whether the controller requires a specific initialization sequence before accepting chassis-zone writes
3. Verify that direct-mode (`0xA1`) must be enabled before chassis-zone packets are processed

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-03 | Fix direction encoding now | One-line change with user-visible impact; no risk to keyboard path |
| 2026-06-03 | Fix header to fixed report size | Matches proven 83F5 implementation; removes subtle multi-packet risk |
| 2026-06-03 | Update chassis LED IDs to 16-bit | Truncated constants would never work on real hardware; must be corrected before any UI/routing work |
| 2026-06-03 | Keep `0xc193` out of backend scope | Research confirms `0xc197` is the sole RGB controller on this platform |
| 2026-06-03 | Add dormant op constants | Low-cost documentation of known protocol surface; prevents re-discovery later |
