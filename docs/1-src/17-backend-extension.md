# Backend extension

Status: **Done**

## Purpose

Adding a built-in backend should not require editing a central import list, and
shared composite-controller state must not collapse two physical devices into
one bag keyed only by backend name.

## Registration contract

Each backend package owns a module-level `BACKEND_REGISTRATION`:

| Field | Owner | Meaning |
|---|---|---|
| `BackendMetadata.name` | package | Canonical backend id |
| `priority` | package | Auto-selection rank after safety tier and confidence |
| `role` | package | `primary` participates in selection; `auxiliary` is diagnostics/secondary only |
| `provider` | package | `kernel-sysfs` or `usb-userspace` when known |
| `stability` / `experimental_evidence` | package | Policy classification |

`keyrgb/core/backends/registry.py` discovers those markers from backend packages.
Primary specs are derived from `role=primary` and sorted by priority, then name.
Auxiliary backends such as `sysfs-mouse` are discovered the same way and exposed
through `iter_auxiliary_specs()` for diagnostics.

Runtime capabilities remain instance data from `backend.capabilities()`.
`backend_caps` is still the tray capability-gating model.

## Shared controller identity

`controller_identity(backend_name=..., hidraw=...)` is the shared-state key for
HID transport entries and ITE 8258 chassis profile coordinators. Keyboard and
zone facades on one hidraw node still share one transport and one coordinator.
Two hidraw nodes with the same backend name do not.

When no hidraw path is known (single-device tests or unmatched scan), the key
falls back to the backend name so existing one-controller sharing is preserved.

## How to add a built-in backend

1. Create `keyrgb/core/backends/<package>/` with the backend class.
2. Export `BACKEND_REGISTRATION` from that package `__init__.py`.
3. Set `role=auxiliary` only for non-primary devices.
4. Do not add USB IDs without hardware evidence, diagnostics, and tests.
5. Keep `capabilities()` as a runtime method; do not treat method presence as
   capability evidence.

Aliases for renamed backends still live in `registry._BACKEND_NAME_ALIASES`
because they are compatibility data, not package identity.

Every backend package directory (except `policies/` and `_*`) must export
`BACKEND_REGISTRATION`. Tests fail if a package is added without the marker.

Hardware firmware effects belong on the backend (`effects()` +
`hardware_effect_builder()`), not in `catalog.HW_EFFECTS`. Software/reactive
effects use `EFFECT_REGISTRATION`; see `docs/1-src/16-effect-runtime-contracts.md`.
