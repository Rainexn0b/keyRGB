# Backend Effects Runtime Boundaries

Last updated: 2026-03-29

## Summary

KeyRGB's tray and backend-selection flow now model hardware effects per selected backend, but the effects engine historically executed hardware I/O through a separate legacy singleton adapter. That created a split-brain runtime where:

- the tray decided capabilities and hardware effect visibility from the selected backend
- the engine acquired the device and hardware effect builders through a global effects adapter
- software and reactive effects stayed backend-agnostic

This document records the current findings, the refactor slice completed now, and the remaining debt.

## Findings

### Good boundaries already in place

- `src/core/backends/base.py` defines a small backend protocol: capabilities, device access, dimensions, `effects()`, and `colors()`.
- Tray hardware effect selection is backend-aware and collision-safe via `hw:` namespacing.
- Software effects remain backend-agnostic and should stay that way.

### Debt that existed before this refactor

- `src/core/effects/ite_backend.py` selected a backend once at import time and exported global `get()`, `hw_effects`, and `hw_colors` values.
- `src/core/effects/device.py` acquired the keyboard through that global adapter instead of the tray-selected backend.
- `src/core/effects/engine_start.py` resolved hardware effect builders and color/palette metadata through the same global adapter.
- The tray could therefore present one backend while the engine executed against another backend snapshot if selection state diverged.

### Constraints and decisions

- Do not support cross-backend hardware effect borrowing at runtime.
- Keep software effects backend-agnostic.
- Keep backend-owned hardware effect definitions separated by backend.

## Refactor slice completed

This refactor removes the main runtime coupling without trying to solve all legacy boundaries at once.

### Done now

- `EffectsEngine` accepts an optional selected backend.
- Engine device acquisition uses the injected backend when available.
- Engine hardware effect execution resolves builders and color metadata from the injected backend instead of the legacy singleton adapter.
- Tray startup selects the backend first and passes it into `EffectsEngine`.

### Intentionally not changed in this slice

- The software/reactive effect library remains backend-agnostic.
- No cross-backend hardware effect reuse was added.

## Remaining debt

### 1. Hardware effect descriptor migration is incomplete

The backend contract now uses typed hardware effect descriptors, and the active hardware-effect backends have been migrated to that model. Runtime payload building no longer accepts legacy callable builders directly.

Impact:

- runtime hardware effect execution is descriptor-only, which is the desired boundary
- legacy builder introspection still exists only at backend wrapper boundaries for older callable-style libraries such as `ite8291r3-ctl`
- new backends should use descriptors directly rather than rely on closure inspection helpers

Desired direction:

- keep legacy callable wrapping quarantined at backend boundaries only
- keep supported params explicit, such as `speed`, `brightness`, `color`, `direction`

### 2. Legacy config-name fallback remains as compatibility glue

The catalog now keeps explicit legacy config-name migration rules instead of treating the old generic hardware list as a canonical runtime catalog.

Impact:

- tray selection, tray status, startup restore, config polling, power-policy handling, and tray icon state now resolve against backend-owned effect definitions first
- direct engine runtime dispatch no longer accepts generic hardware names that the selected backend does not expose
- legacy generic hardware-name fallback now mainly remains in config-resolution compatibility paths that migrate older saved values such as `rainbow`
- there is still compatibility logic translating unsupported generic hardware requests to software fallback or uniform none

Desired direction:

- keep backend-owned detection authoritative for UI and tray runtime state
- reduce config-side fallback behavior once backend coverage and config migration are stable

## Recommended next slices

1. Reduce the remaining legacy config-name fallback once backend-owned effect coverage and config migration are stable.
