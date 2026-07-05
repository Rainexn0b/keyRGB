# Tech debt tracking

This is a lightweight backlog for maintainability work.

Conventions:

- **Priority**: P0 (blocks work) → P3 (nice-to-have)
- **Effort**: S/M/L (rough)
- Keep items small; split into multiple tickets if a refactor is big.

## Backlog

| ID | Area | Item | Priority | Effort | Status | Notes |
|---:|---|---|:---:|:---:|---|---|
| 1 | Diagnostics | Split `src/core/diagnostics/` into collectors + formatting module | P0 | M | done | Highest LOC and touches many support workflows. |
| 2 | Settings UI | Extract scrollframe + diagnostics panel from `src/gui/settings/window.py` | P0 | M | done | Keep behavior identical; reduce single-file complexity. |
| 3 | Power | Extract AC/battery transition policy into unit-testable object | P1 | M | done | Mirror style of `BatterySaverPolicy`. |
| 4 | Power | Separate “platform IO” (dbus/sysfs) from “policy/state” | P1 | L | todo | Can be incremental once policy extraction exists. |
| 5 | Tray | Reduce responsibility in `src/tray/application.py` (delegate to services) | P2 | M | done | Mostly cleanup; avoid feature churn. |
| 6 | TCC | Isolate DBus parsing & command invocation from UI | P2 | M | done | Align with service/view split. |
| 7 | Legacy | Document legacy module boundaries; decide deprecation path | P2 | S | done | Start as docs-only. |
| 8 | Testing | Increase unit test coverage for non-UI policies and parsers | P2 | M | todo | Focus on “pure” logic modules. |

## Notes / decisions

- Split/rename work should keep stable import paths where possible to avoid breaking packaging.
- Avoid compatibility wrappers; update imports/callers directly.
