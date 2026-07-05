# Backend Audit Handoff — Naming Convention & Rename Completion

**Status:** COMPLETE — all 12 backend audits finished; naming convention applied with backward-compatible aliases.  
**Last updated:** 2026-07-05  
**Author:** Guided agent (backend audit pass)  

---

## 1. Naming convention

### Model

```text
ITE<chip>_<capability>[_<capability>...][_<oem>]
```

| Position | Meaning | Examples |
|----------|---------|----------|
| `ITE<chip>` | Silicon / controller family | `ITE8295`, `ITE8258`, `ITE8291`, `ITE8297` |
| `<capability>` | Lighting abstraction exposed by this backend | `perkey`, `zones`, `chassis`, `uniform`, `lightbar` |
| `[<capability>...]` | Optional second capability if one HID interface exposes multiple color targets | `chassis_zones` |
| `[<oem>]` | Manufacturer-specific wiring/quirk variant | `lenovo`, `wootbook` |

Capabilities, when combined, are ordered: **`chassis` > `zones` > `perkey`**.

All ITE backend names use **underscores** exclusively. Non-ITE backends
(`sysfs-leds`, `sysfs-mouse`, `asusctl-aura`) retain their existing hyphenated
names because they do not follow the `ITE<chip>` convention.

### One backend vs. two backends

- **Combine** when a single HID interface exposes multiple color targets with the same protocol and probe logic.
- **Split** when the capabilities require different protocols, different HID interfaces, or different probe behavior.

---

## 2. Renames applied

The following directories and canonical backend names were changed. Old names
continue to work via aliases in `src/core/backends/registry.py`.

| Old name | New canonical name | Old directory | New directory |
|---|---|---|---|
| `ite8291r3` | `ite8291r3_perkey` | `ite8291r3/` | `ite8291r3_perkey/` |
| `ite8910` | `ite8910_perkey` | `ite8910/` | `ite8910_perkey/` |
| `ite8291` | `ite8291_perkey` | `ite8291/` | `ite8291_perkey/` |
| `ite8291-zones` | `ite8291_zones` | `ite8291_zones/` | `ite8291_zones/` |
| `ite8258` | `ite8258_zones` | `ite8258/` | `ite8258_zones/` |
| `ite8258-chassis` | `ite8258_chassis` | `ite8258_chassis/` | `ite8258_chassis/` |
| `ite8295-zones` | `ite8295_zones` | `ite8295_zones/` | `ite8295_zones/` |
| `ite8233` | `ite8233_lightbar` | `ite8233/` | `ite8233_lightbar/` |
| `ite8297` | `ite8297_uniform` | `ite8297/` | `ite8297_uniform/` |

The alias map in `registry.py::_BACKEND_NAME_ALIASES` handles all old names.
Secondary device route identifiers (e.g., `ite8258-chassis-logo`) and the
`asusctl-aura` backend were left unchanged.

### Files touched by the rename

- `src/core/backends/registry.py` — alias map, `name` attributes, imports
- `src/core/backends/ite8291r3_perkey/` — renamed + `name` updated
- `src/core/backends/ite8910_perkey/` — renamed + `name` updated
- `src/core/backends/ite8291_perkey/` — renamed + `name` updated
- `src/core/backends/ite8258_zones/` — renamed + `name` updated
- `src/core/backends/ite8233_lightbar/` — renamed + `name` updated
- `src/core/backends/ite8297_uniform/` — renamed + `name` updated
- `src/core/backends/README.md` — new naming policy and inventory
- `src/tray/app/_startup.py` — startup hints use canonical names
- `src/tray/ui/_device_status.py` — display-name lookup uses canonical names
- `src/core/secondary_device_routes.py` — alias resolution before route matching
- `src/core/diagnostics/_classify.py` — classification strings use canonical names
- `tests/core/backends/test_report_pacing_unit.py` — updated env key expectations
- `tests/core/backends/ite/test_ite8291r3_native_backend_unit.py` — updated env key
- `tests/core/backends/general/test_backend_registry_unit.py` — alias-resolution coverage
- `docs/B-backend-audits/00-index.md` — canonical names in audit index
- `docs/B-backend-audits/BACKEND_AUDIT_HANDOFF.md` — this file

---

## 3. Completed audit actions

### ITE8295_zones PID expansion

- Expanded `SUPPORTED_PRODUCT_IDS` to the OpenRGB-confirmed Lenovo 4-zone family:
  `0xC955, 0xC963, 0xC965, 0xC973, 0xC975, 0xC984, 0xC985`.
- Updated `system/udev/99-ite8291-wootbook.rules` with hidraw uaccess rules for the new PIDs.
- Updated backend docstring and tests.
- L5P-KB-RGB lists additional PIDs (`0xC983`, `0xC993`, `0xC994`, `0xC995`) not corroborated by OpenRGB; left out intentionally.

### ITE8233 lightbar audit

- Audited against OpenRGB `ClevoLightbarController`.
- Confirmed byte-for-byte protocol match for PID `0x7001`.
- Added missing hidraw uaccess rules for `0x6010`, `0x7000`, `0x7001`.
- Documented discrepancies: usage page metadata (`0xFF89` vs OpenRGB `0xFF03`), feature report probe mismatch, scan mode gap, and naming ambiguity (ITE 8233 vs ITE 8291 rev 0.03).
- PIDs `0x7000` and `0x6010` remain experimental / not independently corroborated.

### Sysfs-mouse audit

- Audited against kernel LED class docs and OpenRGB mouse controller naming.
- No functional bugs; backend reuses audited `sysfs-leds` writing path.
- Expanded tests from 4 to 9 and clarified `dimensions()` always returning `(1, 1)`.

### Asusctl audit

- Audited against asusctl source (`asusctl/src/aura_cli.rs`).
- Confirmed all KeyRGB commands (`info`, `leds get/set`, `aura effect static`) are valid.
- Confirmed brightness mapping matches asusctl's four-level model.
- Documented unimplemented but available features: hardware effects (`breathe`, `rain`, `laser`, etc.) and per-zone power control.

### Naming cleanup

- Applied the `ITE<chip>_<capability>` convention to all ITE backends.
- Added backward-compatible aliases for every renamed backend.
- Preserved non-ITE backend names (`sysfs-leds`, `sysfs-mouse`, `asusctl-aura`).
- Preserved secondary device route identifiers that use hyphens.

---

## 4. Validation

- `tests/core/backends/ tests/tray/ tests/core/diagnostics/` — **1300 passed, 1 skipped**
- `python -m buildpython --run-steps=19` — **PASS** (exception-transparency health 100/100)
- `ruff check src/core/backends/ tests/core/backends/ tests/tray/ src/tray/app/_startup.py` — 5 pre-existing unused-import warnings in unrelated test files (not introduced by this change)

---

## 5. Open questions / residual follow-ups

1. **ite8233_lightbar chip identity:** OpenRGB identifies the chip as **ITE 8291 rev 0.03**, while the HID descriptor reports "ITE Device(8233)". KeyRGB kept `ite8233` because the HID-reported name is concrete evidence. If future hardware diagnostics prove it is an ITE 8291 variant, introduce `ite8291_lightbar` as an alias or rename.
2. **ite8233_lightbar usage page:** KeyRGB documents `0xFF89`; OpenRGB uses `0xFF03` for `0x7001`. Does not affect hidraw matching (VID/PID-only). Verify against real descriptors before changing probe identifiers.
3. **ite8233_lightbar scan mode:** OpenRGB exposes scan (`0x06`); KeyRGB defines the constant but does not handle it. Implement after confirming 7-slot color behavior.
4. **CLI backends naming exception:** `asusctl-aura` does not fit the `ITE<chip>_<capability>` model. This is acceptable; if the convention is extended to CLI integrations in the future, prefer `cli_asusctl_aura` or `vendor_asus_aura`.

---

## 6. References

- `src/core/backends/README.md` — finalized naming policy and backend inventory
- `docs/B-backend-audits/00-index.md` — full audit plan and status
- `docs/B-backend-audits/09-ite8295-zones.md` — ITE8295_zones audit
- `docs/B-backend-audits/10-ite8233.md` — ITE8233 lightbar audit
- `docs/B-backend-audits/12-asusctl.md` — ASUS Aura CLI audit
- `src/core/backends/registry.py` — alias resolution
- `system/udev/99-ite8291-wootbook.rules`

---

## 7. How to add a future alias

1. Rename the directory and update the backend's `name` attribute.
2. Add `"old_name": "canonical_name"` to `_BACKEND_NAME_ALIASES` in `registry.py`.
3. Update imports, display names, diagnostics classification, and startup hints.
4. Keep secondary route identifiers stable unless they are also user-visible.
5. Add alias-resolution tests in `tests/core/backends/general/test_backend_registry_unit.py`.
6. After one release cycle, the alias can be removed if desired.
