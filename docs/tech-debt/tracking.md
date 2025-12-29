# Tech debt tracking

This is a lightweight backlog for maintainability work.

Conventions:

- **Priority**: P0 (blocks work) → P3 (nice-to-have)
- **Effort**: S/M/L (rough)
- Keep items small; split into multiple tickets if a refactor is big.

## Backlog

| ID | Area | Item | Priority | Effort | Status | Notes |
|---:|---|---|:---:|:---:|---|---|
| 1 | Diagnostics | Split `src/core/diagnostics.py` into collectors + formatting module | P0 | M | todo | Highest LOC and touches many support workflows. |
| 2 | Settings UI | Extract scrollframe + diagnostics panel from `src/gui/power.py` | P0 | M | todo | Keep behavior identical; reduce single-file complexity. |
| 3 | Power | Extract AC/battery transition policy into unit-testable object | P1 | M | todo | Mirror style of `BatterySaverPolicy`. |
| 4 | Power | Separate “platform IO” (dbus/sysfs) from “policy/state” | P1 | L | todo | Can be incremental once policy extraction exists. |
| 5 | Tray | Reduce responsibility in `src/tray/app.py` (delegate to services) | P2 | M | todo | Mostly cleanup; avoid feature churn. |
| 6 | TCC | Isolate DBus parsing & command invocation from UI | P2 | M | todo | Align with service/view split. |
| 7 | Legacy | Document legacy module boundaries; decide deprecation path | P2 | S | todo | Start as docs-only. |
| 8 | Testing | Increase unit test coverage for non-UI policies and parsers | P2 | M | todo | Focus on “pure” logic modules. |

## Notes / decisions

- Split/rename work should keep stable import paths where possible to avoid breaking packaging.
- Prefer re-export shims for 1 release cycle when moving modules.
