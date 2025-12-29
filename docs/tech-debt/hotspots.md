# Hotspots

This is a lightweight inventory of the largest modules and why they’re harder to maintain.

The intent is not to “ban large files”, but to identify where responsibilities are mixing (UI + IO + policy + formatting, etc.).

## Largest Python files (LOC snapshot)

Source command:

```bash
find src -type f -name '*.py' -print0 | xargs -0 wc -l | sort -n | tail -n 15
```

Snapshot (2025-12-29):

| LOC | File | Why it’s a hotspot |
|---:|---|---|
| 882 | `src/core/diagnostics.py` | Many unrelated collectors in one module; long formatting function; lots of best-effort IO paths; harder to test in isolation. |
| 759 | `src/gui/power.py` | Settings window contains layout, scrolling mechanics, state/persistence, diagnostics rendering, browser integration; multiple concerns. |
| 538 | `src/core/tcc_power_profiles.py` | DBus parsing + CLI fallback + profile model + error handling in one file; parsing logic is non-trivial. |
| 525 | `src/core/power.py` | Power policy + polling + event monitoring + controller integration; mixed “policy” vs “platform IO”. |
| 487 | `src/legacy/effects.py` | Large effect engine surface; potential duplication vs new backends; hard to reason about side effects. |
| 427 | `src/gui/perkey/editor.py` | Big UI + per-key editing state; likely candidates for splitting UI widgets vs persistence vs apply-to-hardware. |
| 410 | `src/gui/tcc_profiles.py` | UI + DBus interactions + validation; probably split into view vs service layer. |
| 359 | `src/gui/perkey/canvas.py` | Custom drawing/event handling gets large quickly; can be decomposed into smaller widgets/classes. |
| 353 | `src/gui/calibrator.py` | Calibration workflow UI + storage + geometry; can be split into steps/state machine. |
| 320 | `src/legacy/gui_perkey.py` | Legacy UI; consider deprecating or isolating. |
| 312 | `src/tray/app.py` | Tray lifecycle, menu, backend selection, polling; already somewhat factored but still busy. |
| 312 | `src/legacy/config.py` | Config persistence + defaults + schema evolution; should stay boring and well-tested. |

## Common maintainability smells in this repo

- **“UI + business logic + IO” in one module** (most visible in `src/gui/power.py`).
- **Many best-effort fallbacks** (diagnostics/power probing) without a structured abstraction can become hard to test.
- **Policy vs mechanism mixed together** (power policy logic tied to polling threads and controller calls).
- **Legacy vs new code overlap** (legacy effects/UI vs new tray/runtime architecture).

## Near-term priorities (suggested)

1. Split `src/core/diagnostics.py` into a small orchestrator + focused collectors.
2. Split `src/gui/power.py` into UI layout, state/persistence, diagnostics UI.
3. Extract “power policy” into a unit-testable component (similar to `BatterySaverPolicy`).
