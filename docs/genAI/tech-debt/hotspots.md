# Hotspots

This is a lightweight inventory of the largest modules and why they’re harder to maintain.

The intent is not to “ban large files”, but to identify where responsibilities are mixing (UI + IO + policy + formatting, etc.).

## Largest Python files (LOC snapshot)

Source command:

```bash
find src -type f -name '*.py' -print0 | xargs -0 wc -l | sort -n | tail -n 15
```

Snapshot (2025-12-30):

| LOC | File | Why it’s a hotspot |
|---:|---|---|
| 354 | `src/core/power_management/manager.py` (via `src/core/power.py`) | Power policy + polling + event monitoring + controller integration; mixed “policy” vs “platform IO”. |
| 501 | `src/gui/settings/window.py` | Settings window still combines layout + state + integration points; next candidates are splitting view/state/services. |
| 487 | `src/core/effects/engine.py` | Large effect engine surface; potential duplication vs new backends; hard to reason about side effects. |
| 427 | `src/gui/perkey/editor.py` | Big UI + per-key editing state; likely candidates for splitting UI widgets vs persistence vs apply-to-hardware. |
| 410 | `src/gui/tcc_profiles.py` | UI + service interactions + validation; can be split into view vs service layer. |
| 359 | `src/gui/perkey/canvas.py` | Custom drawing/event handling gets large quickly; can be decomposed into smaller widgets/classes. |
| 353 | `src/gui/calibrator.py` | Calibration workflow UI + storage + geometry; can be split into steps/state machine. |
| 320 | `src/gui/perkey/editor.py` | Per-key UI is featureful and naturally large; consider further splitting UI/widgets/state. |
| 319 | `src/core/tcc_power_profiles/__init__.py` | Still holds higher-level operations; submodules now isolate parsing/root-apply concerns. |
| 312 | `src/tray/app.py` | Tray lifecycle, menu, backend selection, polling; already somewhat factored but still busy. |
| 312 | `src/core/config.py` | Config persistence + defaults + schema evolution; should stay boring and well-tested. |
| 290 | `src/tray/menu.py` | Menu building is sizeable; candidate for further separation. |
| 259 | `src/core/diagnostics_collectors.py` | Main best-effort IO collectors live here; more splitting is possible if it grows again. |
| 233 | `src/core/diagnostics.py` | Orchestrator wrapper around collectors/formatting; should stay relatively small. |

## Common maintainability smells in this repo

- **“UI + business logic + IO” in one module** (most visible in `src/gui/power.py`).
- **Many best-effort fallbacks** (diagnostics/power probing) without a structured abstraction can become hard to test.
- **Policy vs mechanism mixed together** (power policy logic tied to polling threads and controller calls).
- **Legacy vs new code overlap** (legacy effects/UI vs new tray/runtime architecture).

## Near-term priorities (suggested)

1. Split `src/core/diagnostics.py` into a small orchestrator + focused collectors.
2. Split `src/gui/power.py` into UI layout, state/persistence, diagnostics UI.
3. Extract “power policy” into a unit-testable component (similar to `BatterySaverPolicy`).
