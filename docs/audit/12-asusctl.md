# Audit: `asusctl` — ASUS Aura CLI backend

**Audit date:** 2026-07-04  
**Backend source:** `src/core/backends/asusctl/` (3 files, ~319 LOC)  
**Test file:** `tests/core/backends/general/test_asusctl_backend_unit.py` (26 tests)  
**Stability:** `VALIDATED`  
**Evidence level:** N/A (CLI integration)  
**Priority:** 120

---

## References

1. **asusctl** source (Rust CLI / daemon) — `asusctl/src/aura_cli.rs` from
   `gitlab.com/asus-linux/asusctl` (archived but readable).
2. **OpenRGB** ASUS controllers — not directly applicable because KeyRGB delegates
   to the system `asusctl` binary rather than speaking the USB protocol itself.

---

## Summary

**No functional bugs found.** The backend is a pragmatic subprocess wrapper
around `asusctl` and correctly uses the documented CLI surface.

The main opportunities are around **hardware effects**, **zone/power commands**,
and **capabilities advertisement**:

1. `asusctl aura` supports many hardware effects (`breathe`, `rain`, `laser`,
   `ripple`, `pulse`, `comet`, `flash`, `stars`, etc.), but KeyRGB only uses
   `static`.
2. `asusctl` has per-zone power commands (`aura power keyboard/logo/lightbar/...`)
   that KeyRGB does not expose.
3. `capabilities().hardware_effects` is `False`, which is technically true for
   the current code but could be `True` if effects are wired up.
4. The backend is marked `VALIDATED` even though it is a CLI integration on
   Linux-only hardware. This is consistent with the repo's Linux-first
   assumption, but the confidence of 92 assumes `asusctl` is present and
   responsive on ASUS hardware.

---

## Detailed Comparison

### 1. CLI commands used by KeyRGB

| Purpose | KeyRGB command | asusctl support |
|---------|---------------|-----------------|
| Probe / info | `asusctl info` | ✅ Yes |
| Probe / aura help | `asusctl aura --help` | ✅ Yes |
| Brightness get | `asusctl leds get` | ✅ Yes (parses "brightness: Med") |
| Brightness set | `asusctl leds set <level>` | ✅ Yes (`off`, `low`, `med`, `high`) |
| Static color | `asusctl aura effect static -c <hex> [--zone <zone>]` | ✅ Yes |

**Finding:** ✅ All commands KeyRGB uses are real asusctl commands.

---

### 2. Brightness mapping

KeyRGB maps its internal 0–50 UI scale to asusctl's four levels:

| KeyRGB brightness | asusctl level |
|-------------------|---------------|
| 0 | `off` |
| 1–16 | `low` |
| 17–33 | `med` |
| 34–50 | `high` |

asusctl's own `LedBrightness` parser maps:

| Text | Raw level |
|------|-----------|
| `off` | `0x00` |
| `low` | `0x01` |
| `med` | `0x02` |
| `high` | `0x03` |

**Finding:** ✅ The mapping is internally consistent and matches asusctl's
four-level model.

---

### 3. Zone handling

KeyRGB supports virtual zones via `KEYRGB_ASUSCTL_ZONES=left,right,center`.
When zones are configured, `set_color()` loops over each zone:

```text
asusctl aura effect static -c <hex> --zone <zone>
```

`set_key_colors()` buckets keys into zones by horizontal position and averages
colors per zone.

asusctl's `AuraZone` accepts numeric (`0`, `1`) and named (`logo`,
`lightbar-left`, etc.) zone identifiers.

**Finding:** ✅ The zone concept is sound. The limitation is that KeyRGB does
not validate zone names against asusctl's accepted set.

---

### 4. Missing hardware effects

asusctl `aura` subcommands include:

- `static`
- `breathe` (two-color)
- `stars`
- `rain`
- `highlight`
- `laser`
- `ripple`
- `pulse`
- `comet`
- `flash`

KeyRGB `set_effect()` is currently a no-op.

**Finding:** ⏳ Hardware effects are unimplemented but possible. The `static`
path is the safest baseline and works across all Aura laptops.

---

### 5. Power/zone enable commands

asusctl exposes `asusctl aura power keyboard/logo/lightbar/lid/rear-glow/ally`
with `boot`, `awake`, `sleep`, `shutdown` switches. KeyRGB does not use these.

**Finding:** ⏳ Not a bug, but a feature gap. Users who want to disable the
lightbar or logo independently cannot do so through KeyRGB.

---

### 6. Capabilities

```python
BackendCapabilities(per_key=(len(zones) > 1), color=True, hardware_effects=False, palette=False)
```

- `per_key`: `True` only if zones are configured. This is virtual per-key via
  horizontal bucketing, not true per-key addressing.
- `color`: `True`.
- `hardware_effects`: `False` — currently accurate because effects are not wired.

**Finding:** ✅ Correct for current implementation.

---

### 7. Exception handling

The backend uses `_RECOVERABLE_SUBPROCESS_EXCEPTIONS = (OSError, subprocess.SubprocessError)`
for probe-time failures and keeps unexpected `RuntimeError`/assertions as fatal.
This matches the exception-transparency policy.

Device-time failures use `_run_ok()` which raises `RuntimeError` with the
command context. This is reasonable for a CLI wrapper.

---

### 8. Naming convention note

Under the agreed model (`ITE<chip>_<capability>[_<oem>]`), this backend does not
fit because it is not ITE-silicon-specific. The name `asusctl-aura` is a
**tool-integration** name rather than a chip+capability name. This is acceptable
because the backend is a wrapper around a vendor CLI, not a direct hardware
protocol. If the convention is later extended to non-ITE backends, a prefix
like `cli_asusctl_aura` or `vendor_asus_aura` would be clearer.

---

## Test Coverage

| Area | Tests | Coverage |
|------|-------|----------|
| RGB / brightness helpers | 1 | ✅ |
| `_run_ok` error context | 1 | ✅ |
| `get_brightness` parsing | 4 | ✅ |
| `turn_off` / `is_off` | 1 | ✅ |
| `set_color` uniform and zoned | 2 | ✅ |
| `set_key_colors` single/multi zone | 3 | ✅ |
| `set_effect` no-op | 1 | ✅ |
| Backend env helpers / capabilities | 1 | ✅ |
| Probe identifiers | 1 | ✅ |
| Probe disabled / missing binary | 1 | ✅ |
| Probe exception / nonzero / empty | 4 | ✅ |
| Aura help exception handling | 2 | ✅ |
| Backend accessors | 1 | ✅ |

Total: **26 tests** — good coverage for a CLI wrapper.

---

## Action Items

| # | Action | Type | Priority | Status |
|---|--------|------|----------|--------|
| 1 | Consider wiring asusctl hardware effects (`breathe`, `rain`, etc.) | Feature | Low | ⏳ Follow-up |
| 2 | Consider exposing per-zone power control | Feature | Low | ⏳ Follow-up |
| 3 | Document that `per_key` is virtual zone-based, not true per-key | Docs | Low | ⏳ Follow-up |
| 4 | Document naming convention exception for CLI backends | Docs | Low | ⏳ Follow-up |

**Overall: VALIDATED** — the `asusctl` CLI integration is correctly implemented
for the static color path. Hardware effects and zone power are deliberate
follow-up features rather than bugs.
