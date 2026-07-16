# Audit: `ite8258-chassis` — Lenovo Legion Pro 7 Gen10 composite ITE 8258 backend

- **Audit date:** 2026-07-04 (Issue #7 regression addendum: 2026-07-15)
- **Backend source:** `src/core/backends/ite8258_perkey_chassis/`
- **Test file:** `tests/core/backends/ite/test_ite8258_chassis_backend_unit.py` (+ Issue #7 integration test)
- **Stability:** `EXPERIMENTAL`
- **Evidence level:** `REVERSE_ENGINEERED`
- **Priority:** 97

## References

1. **OpenRGB Lenovo Gen7/8/10 USB controller**
   - `Controllers/LenovoControllers/LenovoDevices.h`
   - `Controllers/LenovoControllers/LenovoUSBControllerDetect.cpp`
   - `Controllers/LenovoControllers/LenovoUSBController_Gen7_8/LenovoUSBController_Gen7_8.h`
   - `Controllers/LenovoControllers/LenovoUSBController_Gen7_8/LenovoUSBController_Gen7_8.cpp`
   - `Controllers/LenovoControllers/LenovoUSBController_Gen7_8/RGBController_Lenovo_Gen7_8.cpp`
2. **legion-spectrum-control** (83F5 working implementation, `0x048d:0xc197`)
   - `README.md`
   - Independent Linux per-key/chassis implementation tested on Lenovo Legion Pro 7 16IAX10H
3. **LenovoLegionToolkit**
   - `LenovoLegionToolkit.Lib/Native.cs`
4. **Internal correction plan**
   - `../B-backend-guides/ite8258/ite8258-chassis-correction-plan.md`
5. **Composite coordination reference and current hardening plan**
   - `../1-src/12-composite-profile-coordination.md`
   - `../I-implementation-plans/issue-7-composite-profile-hardening-and-validation-plan.md`

## Summary

The three protocol discrepancies identified in the internal correction plan are **already
resolved** in the current code:

1. **Direction encoding** — `DIRECTION_LEFT = 0x04`, `DIRECTION_RIGHT = 0x03` now matches the
   83F5 implementation.
2. **Chassis-zone LED IDs** — logo, neon, and vent constants use full 16-bit codes
   (`0x05DD`, `0x01F5..0x01FE`, `0x03E9..0x03FA`), not truncated 8-bit values.
3. **Header framing** — `_packet()` writes the fixed report size (`PACKET_SIZE`) in bytes 2–3,
   matching the 83F5 implementation, not a dynamic payload length.

The original audit found no additional packet-format bugs. The 2026-07-15 Issue #7
follow-up did find a transaction-model bug: keyboard and virtual-zone calls each
started their own `SAVE_PROFILE` payload at group 1, although the controller expects
one full effect description for the shared keyboard/chassis profile. Production
devices now share a coordinator that retains all surfaces, serializes the complete
multi-report transaction, and prevents child cleanup after global off from replaying
the keyboard scene. Probe identifiers also include the OpenRGB-backed HID usage
page/usage and feature-report size, matching the sibling `ite8258` backend.

The coordinator is the project's backend-local reference implementation for
composite controllers. It is not yet a generic shared API. A maintainer follow-up
also confirmed that all-compatible software rendering can request up to four
complete c197 commits per frame; the hardening plan tracks a backend-owned output
transaction without changing the independent logical-route model.

## Detailed Comparison

### 1. USB ID and device scope

| Source | PID | Interpretation |
|--------|-----|----------------|
| OpenRGB `LenovoDevices.h` | `0xC197` | `LEGION_7GEN10` |
| OpenRGB `RGBController_Lenovo_Gen7_8.cpp` | `0xC197` | Not 24-zone, not keyboard-only → composite |
| legion-spectrum-control | `0x048d:0xc197` | Lenovo Legion Pro 7 16IAX10H (83F5) |
| KeyRGB `ite8258-chassis` | `0xC197` | Composite keyboard/chassis backend |

**Finding:** Correct. This backend is scoped to `0xC197` only, matching OpenRGB's
`LEGION_7GEN10` and the 83F5 working implementation. The 24-zone keyboard-only `0xC195`
remains in the separate `ite8258` backend.

---

### 2. Packet envelope and header framing

| Field | KeyRGB | OpenRGB / legion-spectrum-control | Result |
|-------|--------|-----------------------------------|--------|
| Report ID | `0x07` | `0x07` | ✅ |
| Feature report size | `960` | `960` | ✅ |
| Header framing | Fixed `PACKET_SIZE` in bytes 2–3 | Fixed `0x03C0` | ✅ |
| Save/effect command | `0xCB` | `SAVE_PROFILE` / `EffectChange` | ✅ |
| Brightness command | `0xCE` | `SET_BRIGHTNESS` | ✅ |
| Switch profile | `0xC8` | `SWITCH_PROFILE` / `ProfileChange` | ✅ |
| Direct mode | `0xA1` / `0xD0` | `DIRECT_MODE` / `SET_DIRECT_MODE` | ✅ |

**Finding:** Correct. The fixed header framing matches the 83F5 implementation. This differs
from the sibling `ite8258` backend, which correctly uses a dynamic payload length for the
24-zone `0xC195` device — the two backends intentionally diverge here because the firmware
variants expect different framing.

---

### 3. Profile targeting

KeyRGB sends `0xC8` switch-profile and `0xD0` direct-mode-off before every profile write,
brightness change, and turn-off. This mirrors OpenRGB's approach of switching to the active
profile before writing, and matches the 83F5 implementation's fixed-header pre-write sequence.

**Finding:** Correct.

---

### 4. Per-key matrix and LED IDs

The chassis backend uses a 7×20 sparse matrix map with 101 mapped keyboard LED IDs, matching
the Lenovo Legion Pro 7 Gen10 ANSI layout. `led_id_from_row_col()` correctly raises
`ValueError` for unmapped (sparse) cells.

OpenRGB does not publish the exact same per-key matrix for `LEGION_7GEN10`, but the LED ID
range (`0x01..0xA1`) and the sparse 7×20 structure are consistent with the Gen10 per-key
controller documented by legion-spectrum-control.

**Finding:** Correct for the 83F5 hardware platform. Documented as product-variant data, not
universal ITE 8258 constants.

---

### 5. Chassis-zone LED IDs

| Zone | KeyRGB | legion-spectrum-control | Result |
|------|--------|--------------------------|--------|
| Logo | `0x05DD` | `0x05DD` | ✅ |
| Neon | `0x01F5..0x01FE` | `0x01F5..0x01FE` | ✅ |
| Vent | `0x03E9..0x03FA` | `0x03E9..0x03FA` | ✅ |

The packet encoder writes these as little-endian 16-bit values, producing the correct wire
bytes (e.g., `DD 05` for logo).

**Finding:** Correct. The previous 8-bit truncation bug is resolved.

---

### 6. Direction and spin constants

| Concept | KeyRGB | legion-spectrum-control | Result |
|---------|--------|--------------------------|--------|
| Up | `0x01` | `0x01` | ✅ |
| Down | `0x02` | `0x02` | ✅ |
| Left | `0x04` | `0x04` | ✅ |
| Right | `0x03` | `0x03` | ✅ |
| Spin right | `0x01` | `0x01` | ✅ |
| Spin left | `0x02` | `0x02` | ✅ |

**Finding:** Correct. The previous left/right swap is resolved.

---

### 7. Modes and effects

| Mode | KeyRGB | OpenRGB / LLT | Result |
|------|--------|----------------|--------|
| Screw rainbow | `0x01` | `0x01` | ✅ |
| Rainbow wave | `0x02` | `0x02` | ✅ |
| Color change | `0x03` | `0x03` | ✅ |
| Color pulse | `0x04` | `0x04` | ✅ |
| Color wave | `0x05` | `0x05` | ✅ |
| Smooth | `0x06` | `0x06` | ✅ |
| Rain | `0x07` | `0x07` | ✅ |
| Ripple | `0x08` | `0x08` | ✅ |
| Audio bounce | `0x09` | `0x09` | ✅ |
| Audio ripple | `0x0A` | `0x0A` | ✅ |
| Static | `0x0B` | `0x0B` | ✅ |
| Type | `0x0C` | `0x0C` | ✅ |

**Finding:** Correct. The chassis backend correctly includes rain, ripple, audio_bounce,
audio_ripple, and type — effects that the 24-zone `0xC195` device does not support.

---

### 8. Shared hidraw transport

The chassis backend uses `SharedHidrawTransportManager` so the keyboard device and zone
devices (logo/neon/vent) share a single hidraw file descriptor. A shared
`Ite8258ChassisProfileCoordinator` now also retains the complete desired group scene and
holds one lock across profile switch, direct-mode disable, every save-profile packet,
and controller brightness. Sharing only the transport was insufficient because its
write lock covers one report, not a complete multi-report profile transaction.

**Finding:** Correct architecture.

---

### 9. Zone device contract

`Ite8258ChassisZoneDevice` correctly:
- Stages a zone-first write until a primary keyboard scene exists, so it never emits an
  incomplete zones-only profile.
- Rebuilds the complete keyboard/logo/neon/vent group list for zone colour or off changes,
  with a black static group representing an off zone.
- Suppresses child off replay while controller-wide off is latched, preserving the desired
  scene for resume without relighting the keyboard during shutdown.
- Raises `RuntimeError` for `set_key_colors` and `set_effect` (zones are uniform-color only)
- Shares the parent transport proxy

**Finding:** Correct.

---

### 10. Capability contract

```python
BackendCapabilities(per_key=True, color=True, hardware_effects=True, palette=False)
```

This is acceptable: the keyboard surface exposes the full 7×20 per-key matrix, while the
zone surfaces are exposed through the secondary-device route system.

---

## Test Coverage

Focused tests (36) cover:

- turn-off, brightness, switch-profile, direct-mode, direct-color report bytes
- direction code corrections (left/right swap resolved)
- 16-bit chassis-zone LED IDs (logo, neon, vent)
- direct-color report emits correct little-endian LED IDs
- `led_id_from_row_col` matches the 83F5 matrix
- uniform static group report bytes
- keyboard `set_color` send order (switch-profile → direct-off → save-profile → brightness)
- sparse/gap key mapping
- zone device `set_color`, `turn_off`, and per-zone LED IDs
- zone-first staging, full-scene sibling preservation, global-off/resume latching,
  and non-interleaving concurrent profile transactions
- experimental opt-in probe behavior
- transport-open error wrapping
- shared transport (keyboard + zones open hidraw once)
- diagnostics matrix metadata

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | Direction encoding (left/right swap) | Code | High | ✅ Already resolved |
| 2 | 16-bit chassis-zone LED IDs | Code | High | ✅ Already resolved |
| 3 | Fixed header framing | Code | Medium | ✅ Already resolved |
| 4 | Include usage page/usage/report size in probe identifiers | Diagnostics | Low | ✅ Done |
| 5 | Add shared hidraw usage/report-descriptor filtering | Code | Low (demoted) | ⏳ Lower urgency than the hardening plan implied: the 2026-07-16 review of the reporter's v0.28.2 support bundle shows the c197 controller exposes exactly one hidraw node (`hidraw3`); the two other `048d` nodes are the companion `c193` device. The multi-interface selection ambiguity this guards against does not exist on real c197 hardware. Revisit if a multi-interface c197 unit appears, or bundle with c195 when a c195 reporter surfaces. Note: the bundle's descriptor read for `hidraw3` returned `report_descriptor_error: [Errno 22] Invalid argument`, so the descriptor-capture path needs a look before any re-capture. |
| 6 | Add product-variant registry if a non-83F5 `0xC197` laptop appears | Architecture | Low | ⏳ Follow-up |
| 7 | Coordinate keyboard and virtual zones as one full hardware profile | Code | High | ✅ Done for Issue #7 follow-up |

**Overall: AUTOMATED VALIDATION COMPLETE; REPORTER CONFIRMED v0.29.2 WORKING; STRUCTURED PER-SURFACE VALIDATION STILL PENDING** — packet format,
mode IDs, chassis-zone LED IDs, direction/spin constants, header framing, and full-scene
transaction composition match public references and focused tests. On 2026-07-16 the Issue #7
reporter confirmed "0.29.2 is working well" and closed the ticket, closing the v0.29.1
flash-then-dark regression on the 83F5 hardware. That is a regression-closure signal, not a
structured per-surface validation (the Phase 8 reporter checklist was not run). The backend
remains `EXPERIMENTAL`; promotion is gated on the Phase 8 per-surface checklist, not Phase 6
(which is demoted because c197 exposes a single hidraw node).
