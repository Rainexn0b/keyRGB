# Hotspots

This is a lightweight inventory of the largest modules and why they’re harder to maintain.

The intent is not to “ban large files”, but to identify where responsibilities are mixing (UI + IO + policy + formatting, etc.).

## Largest Python files (LOC snapshot)

Source command:

```bash
find src -type f -name '*.py' ! -path 'src/tests/*' -print0 | xargs -0 wc -l | sort -n | tail -n 15
```

Snapshot (2026-01-01):

| LOC | File | Why it’s a hotspot |
|---:|---|---|
| 384 | `src/gui/widgets/color_wheel.py` | Custom UI widget with non-trivial event handling + rendering. |
| 379 | `src/core/config.py` | Config persistence + defaults + schema evolution; should stay boring and well-tested. |
| 354 | `src/tray/pollers/idle_power_polling.py` | Idle detection + power policy glue; timing + polling logic can get subtle. |
| 349 | `src/gui/calibrator/app.py` | Calibration workflow UI + storage + geometry; candidate for splitting into steps/state. |
| 347 | `src/gui/tcc_profiles.py` | UI + service interactions + validation; can be split into view vs service layer. |
| 345 | `src/gui/perkey/canvas.py` | Custom drawing/event handling; can be decomposed into smaller widgets/classes. |
| 327 | `src/core/power_management/manager.py` | Power policy + polling + event monitoring + controller integration; mixed “policy” vs “platform IO”. |
| 320 | `src/core/tcc_power_profiles/ops_write.py` | Complex write/apply logic; good candidate for more unit-testable helpers. |
| 316 | `src/core/effects/engine.py` | Large effect engine surface; hard to reason about side effects. |
| 300 | `src/gui/perkey/editor.py` | Big UI + per-key editing state; candidate for splitting UI widgets vs persistence vs apply-to-hardware. |
| 289 | `src/core/resources/layout.py` | Layout model + transforms; easy to accrete responsibilities over time. |
| 255 | `src/gui/settings/window.py` | Settings window combines layout + state + integration points. |
| 239 | `src/tray/ui/menu_sections.py` | Menu building is sizeable; candidate for further separation. |
| 234 | `src/core/backends/sysfs/backend.py` | Hardware-facing IO with multiple edge cases; keep defensive and well-tested. |
| 231 | `src/gui/uniform.py` | UI + state + hardware operations; naturally grows as features expand. |

## Common maintainability smells in this repo

- **“UI + business logic + IO” in one module** (most visible in `src/gui/settings/window.py`).
- **Many best-effort fallbacks** (diagnostics/power probing) without a structured abstraction can become hard to test.
- **Policy vs mechanism mixed together** (power policy logic tied to polling threads and controller calls).
- **Legacy vs new code overlap** (legacy effects/UI vs new tray/runtime architecture).

## Near-term priorities (suggested)

1. Keep `src/core/diagnostics/` as a small orchestrator + focused collectors.
2. Split `src/gui/settings/window.py` into UI layout, state/persistence, diagnostics UI.
3. Extract “power policy” into a unit-testable component (similar to `BatterySaverPolicy`).
