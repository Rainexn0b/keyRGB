# Tech debt tracking

This is the active backlog for the maintainability issues identified in the March 2026 review.

Conventions:

- Priority: P0 blocks safe iteration, P1 is high leverage, P2 is valuable but can be phased.
- Effort: S, M, L are rough engineering slices.
- Status: `todo`, `active`, `done`, `monitoring`.

## Backlog

| ID | Area | Item | Priority | Effort | Buildpython signal | Status |
|---:|---|---|:---:|:---:|---|---|
| 1 | Exceptions | Narrow broad exception handling in runtime hot paths and improve failure visibility. See [exception-handling-debt.md](exception-handling-debt.md). | P0 | L | Code Hygiene (`silent_broad_except`, `logged_broad_except`, `fallback_broad_except`) | todo |
| 2 | Tray runtime | Replace tray flag sprawl with a typed state model and clearer controller boundaries. See [tray-runtime-state.md](tray-runtime-state.md). | P0 | L | LOC Check, File Size, forbidden private-attr access in Code Hygiene | todo |
| 3 | Backends / tests | Raise confidence in sysfs, ASUS, and experimental backends with fixture-driven tests. See [backend-coverage-and-confidence.md](backend-coverage-and-confidence.md). | P0 | L | Pytest, future coverage debt step, Architecture Validation | todo |
| 4 | Backends / architecture | Extract a shared USB backend layer for probe, capability, and permission patterns. See [backend-shared-usb-layer.md](backend-shared-usb-layer.md). | P1 | M | File Size, LOC Check, Architecture Validation | todo |
| 5 | Polling / event flow | Reduce polling-driven coupling and move toward a clearer event model for config and runtime state. See [polling-and-config-sync.md](polling-and-config-sync.md). | P1 | M | File Size, LOC Check, Code Hygiene hotspot counts | todo |
| 6 | Tooling | Keep debt visible in buildpython and CI with debt-oriented profiles, baselines, and summaries. See [buildpython-debt-automation.md](buildpython-debt-automation.md). | P1 | S | Build Summary debt snapshot, Code Hygiene, Code Markers, Architecture Validation | active |

## Notes

- The repo already has useful debt tracking primitives in `buildpython`: baselines, hotspot reports, and a build-summary debt snapshot.
- The weakest machine signal today is coverage confidence for hardware-facing code. That remains mostly a documentation and workflow gap rather than a missing concept in the build runner.