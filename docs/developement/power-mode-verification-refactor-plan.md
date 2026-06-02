# Power Mode Verification Refactor Plan

## Purpose

This plan fixes the recurring bug where KeyRGB configures a power mode (e.g. **Performance** on AC, **Extreme Saver** on battery) but the tray reports **Balanced** instead, and the automatic power-source loop logs repeated activation warnings.

The bug has surfaced twice because earlier fixes only patched `_infer_mode` heuristics without addressing the structural coupling between **application**, **observation**, and **verification**. This plan fixes the immediate issue with the safest change, then refactors the boundary so the same class of bug cannot reappear.

## Root Cause

The failure chain is in `src/core/power/system/modes.py`:

1. `PowerSourceLoopPolicy` emits `ActivatePowerMode(PowerMode.PERFORMANCE)`.
2. `_activate_power_source_mode` calls `set_mode(PowerMode.PERFORMANCE, allow_interactive=False)`.
3. `set_mode` writes cpufreq sysfs knobs via `_apply_mode_sysfs`.
4. **Crucially**, `set_mode` then calls `_mode_is_active(mode)`, which calls `get_status()` → `_infer_mode()`.
5. `_infer_mode` is a **best-effort heuristic** that reads back governor, EPP, and boost state.
6. If `_infer_mode` disagrees with the requested mode, `set_mode` returns `False`.
7. The power-source loop sees a failed activation, logs a warning, and retries every 30 seconds.
8. The tray menu calls `get_status()` independently and displays whatever `_infer_mode` returned — usually `Balanced`.

### Why `_infer_mode` disagrees (confirmed edge cases)

| Edge case | Why it happens | Result |
|-----------|---------------|--------|
| **EPP fallback mismatch** | `_pick_epp_value` legitimately falls back to `"balance_performance"` when `"performance"` EPP is unavailable, but `_infer_mode` only recognizes exact `"performance"`. | `BALANCED` |
| **Mixed EPP across policies** | On heterogeneous CPUs, P-cores may apply `"performance"` EPP while E-cores apply `"balance_performance"`. `_infer_mode` requires `all(value == "performance")`. | `BALANCED` |
| **Governor=performance + boost disabled** | If boost is explicitly off (permissions, hardware, or BIOS), `_infer_mode` rejects `PERFORMANCE` even when the governor is `"performance"`. | `BALANCED` |

All three cases share the same structural flaw: **verification is coupled to a heuristic that is allowed to be wrong**.

## Immediate Fix (Best Fix)

Decouple `set_mode` success from `_mode_is_active`.

### What changes

In `src/core/power/system/modes.py`, change `set_mode` so that:

- If `_apply_mode_sysfs` completes **without raising**, consider the direct-write path successful. Do **not** gate success on `_mode_is_active`.
- If direct writes raise `PermissionError` or `OSError`, fall through to the privileged helper as before.
- If the helper runs and returns `True` (process exit 0), consider the activation successful.
- `_mode_is_active` is preserved as a **diagnostic/observation** helper, not a gate. It can be used for UI display, logging, and optional warning telemetry, but it must not cause `set_mode` to return `False` when the writes themselves succeeded.

### Why this is the best fix

- It stops the false-negative retry loop immediately.
- It respects the reality that cpufreq sysfs state is driver-specific and sometimes ambiguous.
- It preserves all safety: if sysfs writes fail, we still try the helper; if the helper fails, we still return `False`.
- It is low-risk and localized to one function.

### Code target

- `src/core/power/system/modes.py` — `set_mode`
- `tests/core/power/monitoring/test_system_power_modes_unit.py` — update `test_set_mode_returns_false_when_helper_succeeds_but_mode_stays_wrong` to reflect the new contract, and add tests for the direct-write-success path.

## Long-Term Refactor

Separate the three responsibilities that are currently tangled in `modes.py`.

### Target architecture: three layers

```
┌─────────────────────────────────────────┐
│  Policy layer (tray / settings / loop)  │
│  Decides *which* mode should be active  │
│  Trusts the apply layer for success     │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Apply layer (sysfs + helper)           │
│  Writes cpufreq knobs best-effort       │
│  Returns True if writes completed       │
│  Returns False if writes failed         │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  Observation layer (diagnostics / UI)   │
│  Reads sysfs and guesses current mode   │
│  Never used to decide success/failure   │
│  Can be wrong without breaking policy   │
└─────────────────────────────────────────┘
```

### Specific refactor steps

#### 1. Extract the Apply Layer

Move `_apply_mode_sysfs`, `_write_scaling_freq_range`, `_write_mode_epp_preferences`, `_set_boost_enabled`, and the helper invocation into a dedicated module:

- **New file**: `src/core/power/system/_apply.py`
- **Responsibility**: Write cpufreq knobs. Return `True` if all applicable writes completed, `False` if any required write failed.
- **No verification logic**: This module must not import or call `_infer_mode` or `get_status`.

#### 2. Extract the Observation Layer

Move `_infer_mode`, `_read_boost_enabled`, `_read_epp`, and `get_status` into a dedicated module:

- **New file**: `src/core/power/system/_observe.py`
- **Responsibility**: Read sysfs and return the best-guess `PowerMode`.
- **No write logic**: This module must not import or call any write helpers.
- **Relax heuristics** as part of the move:
  - Accept `"balance_performance"` as a performance signal.
  - Accept mixed EPP values when all values are in `{"performance", "balance_performance"}`.
  - Add a clear docstring that this is heuristic and may disagree with the last-applied mode.

#### 3. Make `modes.py` a thin facade

`src/core/power/system/modes.py` becomes a public facade that wires apply + observation together for callers that still want both, but does not use observation to veto apply success:

```python
def set_mode(mode: PowerMode, *, allow_interactive: bool = True) -> bool:
    """Apply a power mode. Returns True if sysfs/helper writes succeeded."""
    applied = _apply.apply_mode(mode, allow_interactive=allow_interactive)
    return applied

def get_status() -> PowerModeStatus:
    """Observe the current system state. Best-effort; may disagree with last-applied mode."""
    return _observe.infer_status()
```

#### 4. Stop swallowing EPP write failures silently

In the apply layer, `_write_mode_epp_preferences` currently catches `OSError` and passes silently. Change it to:

- Return a result object or boolean indicating whether the write succeeded.
- The caller decides whether EPP failure is fatal (it usually isn't for Balanced/Performance, but it is worth logging).
- This removes a hidden failure mode that currently makes debugging impossible.

#### 5. Update the power-source loop

In `src/core/power/management/manager.py`:

- `_activate_power_source_mode` should continue to log when `set_mode` returns `False` (real write/helper failure).
- Add an **optional** diagnostic log when `get_status().mode` disagrees with the desired mode, but do not treat it as a failure.
- This prevents the retry loop from firing on detection mismatches.

#### 6. Update tests

- `tests/core/power/monitoring/test_system_power_modes_unit.py`
  - Remove or rename tests that assert `set_mode` returns `False` after successful helper/direct writes.
  - Add tests for mixed-policy EPP detection in the observation layer.
  - Add tests for the apply layer confirming that write success is independent of readback.
- `tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py`
  - Add a test confirming that `_activate_power_source_mode` does not retry when `set_mode` returns `True` but `get_status` disagrees.

## Files To Change

| File | Change |
|------|--------|
| `src/core/power/system/modes.py` | Make `set_mode` trust write success; keep `_mode_is_active` for observation only; optionally re-export from new modules. |
| `src/core/power/system/_apply.py` | **New.** Extract all sysfs write logic and helper invocation. No readback. |
| `src/core/power/system/_observe.py` | **New.** Extract `_infer_mode`, `get_status`, and all read helpers. Relax EPP heuristics. |
| `src/core/power/system/__init__.py` | Re-export public names (`PowerMode`, `PowerModeStatus`, `set_mode`, `get_status`, `is_supported`). |
| `src/core/power/management/manager.py` | Update `_activate_power_source_mode` to log mismatches without retrying. |
| `tests/core/power/monitoring/test_system_power_modes_unit.py` | Update test contracts; add mixed-policy and `balance_performance` detection tests. |
| `tests/core/power/manager/test_power_manager_battery_saver_loop_unit.py` | Add test for "apply succeeds but observation disagrees" scenario. |

## Definition Of Done

- [ ] `set_mode` returns `True` when sysfs/helper writes succeed, even if `_infer_mode` would return a different mode.
- [ ] `_infer_mode` recognizes `"balance_performance"` and mixed `{"performance", "balance_performance"}` EPP states as consistent with `PERFORMANCE`.
- [ ] Apply logic and observation logic live in separate modules with no import cycle.
- [ ] The power-source loop stops retrying on detection mismatches.
- [ ] Tests cover the new contracts and the previously failing edge cases.
- [ ] CHANGELOG.md notes the fix and the verification behavior change.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Removing verification could mask real apply failures | The helper still returns `False` on real failures. Direct sysfs writes that raise are still caught. Only the *heuristic readback veto* is removed. |
| `_infer_mode` heuristic change could misclassify real states | The observation layer is allowed to be wrong; it only affects UI display and diagnostics, not policy decisions. Tests will pin the new heuristic. |
| Module split could break imports | `modes.py` stays as a facade re-exporting public names. Internal callers migrate incrementally. |

## Related Context

- [CHANGELOG.md](../../CHANGELOG.md) — v0.25.3 entry notes the previous `_infer_mode` improvement; v0.25.4–v0.25.5 entries note helper/polkit changes.
- `src/core/power/system/modes.py` — current monolithic module.
- `src/core/power/policies/power_source_loop_policy.py` — the retry logic that amplifies the bug.
- `src/core/power/management/manager.py` — `_activate_power_source_mode` and the power-source loop.
