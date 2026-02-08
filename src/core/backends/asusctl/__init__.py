"""ASUS lighting backend via `asusctl`.

This backend shells out to the system `asusctl` utility (asusd/rog-control-center).
It is intended for ASUS laptops where kernel/sysfs control is limited.

Notes:
- `asusctl` primarily exposes per-*zone* Aura control via CLI. KeyRGB can map its
  per-key editor to zones ("virtual per-key") when multiple zones are configured.
- True per-key (per-switch) Aura control is not exposed by the `asusctl` CLI on
  many devices; implementing that would require a protocol-level backend.
"""

from .backend import AsusctlAuraBackend

__all__ = ["AsusctlAuraBackend"]
