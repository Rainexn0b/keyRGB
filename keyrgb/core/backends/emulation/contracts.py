"""Static emulated capabilities and dimensions.

These values copy each backend's declared contract so emulation never has to
call ``capabilities()`` / ``dimensions()`` methods that may open sysfs or
hidraw.
"""

from __future__ import annotations

from dataclasses import dataclass

from keyrgb.core.backends.base import BackendCapabilities

_COLOR = BackendCapabilities(brightness=True, per_key=False, color=True, hardware_effects=False, palette=False)
_ZONED = BackendCapabilities(
    brightness=True, per_key=False, color=True, hardware_effects=False, palette=False, zoned=True
)
_ZONED_HW = BackendCapabilities(
    brightness=True, per_key=False, color=True, hardware_effects=True, palette=False, zoned=True
)
_PERKEY = BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=False, palette=False)
_PERKEY_HW = BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=True, palette=False)
_PERKEY_PALETTE = BackendCapabilities(brightness=True, per_key=True, color=True, hardware_effects=True, palette=True)
_BRIGHTNESS_ONLY = BackendCapabilities(
    brightness=True, per_key=False, color=False, hardware_effects=False, palette=False
)


@dataclass(frozen=True)
class EmulatedContract:
    capabilities: BackendCapabilities
    dimensions: tuple[int, int]


EMULATED_CONTRACTS: dict[str, EmulatedContract] = {
    "asusctl-aura": EmulatedContract(_ZONED, (6, 21)),
    "ite8291r3_perkey": EmulatedContract(_PERKEY_PALETTE, (6, 21)),
    "ite8910_perkey": EmulatedContract(_PERKEY_HW, (6, 20)),
    "ite8291_perkey": EmulatedContract(_PERKEY, (6, 21)),
    "ite8291_zones_clevo": EmulatedContract(_ZONED, (1, 4)),
    "ite8258_zones_lenovo_legion": EmulatedContract(_PERKEY_HW, (4, 6)),
    "ite8258_perkey_chassis": EmulatedContract(_PERKEY_HW, (7, 20)),
    "ite8295_zones_lenovo_ideapad": EmulatedContract(_ZONED_HW, (1, 4)),
    "ite8233_none_chassis_lightbar_clevo": EmulatedContract(_COLOR, (1, 1)),
    "ite8291_none_chassis_lightbar_tongfang": EmulatedContract(_COLOR, (1, 1)),
    "ite8297_uniform": EmulatedContract(_COLOR, (1, 1)),
    "sysfs-leds": EmulatedContract(_BRIGHTNESS_ONLY, (6, 21)),
    "sysfs-mouse": EmulatedContract(_COLOR, (1, 1)),
}


def contract_for_backend(name: str) -> EmulatedContract:
    contract = EMULATED_CONTRACTS.get(name)
    if contract is None:
        raise KeyError(name)
    return contract
