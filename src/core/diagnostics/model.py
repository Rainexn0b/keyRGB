from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Diagnostics:
    dmi: dict[str, str]
    leds: list[dict[str, str]]
    sysfs_leds: list[dict[str, str]]
    usb_ids: list[str]
    env: dict[str, str]
    virt: dict[str, str]
    system: dict[str, Any]
    hints: dict[str, Any]
    app: dict[str, Any]
    power_supply: dict[str, Any]
    backends: dict[str, Any]
    usb_devices: list[dict[str, Any]]
    config: dict[str, Any]
    process: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dmi": dict(self.dmi),
            "leds": list(self.leds),
            "sysfs_leds": list(self.sysfs_leds),
            "usb_ids": list(self.usb_ids),
            "env": dict(self.env),
            "virt": dict(self.virt),
            "system": dict(self.system),
            "hints": dict(self.hints),
            "app": dict(self.app),
            "power_supply": dict(self.power_supply),
            "backends": dict(self.backends),
            "usb_devices": list(self.usb_devices),
            "config": dict(self.config),
            "process": dict(self.process),
        }
