from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _readonly_settings(settings: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(settings, Mapping) or not settings:
        return MappingProxyType({})
    return MappingProxyType(dict(settings))


@dataclass(frozen=True, slots=True)
class DiagnosticsConfigSnapshot:
    present: bool = False
    mtime: int | None = None
    settings: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    per_key_colors_count: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _readonly_settings(self.settings))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"present": bool(self.present)}
        if self.mtime is not None:
            payload["mtime"] = int(self.mtime)
        if self.settings:
            payload["settings"] = dict(self.settings)
        if self.per_key_colors_count is not None:
            payload["per_key_colors_count"] = int(self.per_key_colors_count)
        if self.error is not None:
            payload["error"] = str(self.error)
        return payload


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
    config: DiagnosticsConfigSnapshot | Mapping[str, Any]
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
            "config": self.config.to_dict()
            if isinstance(self.config, DiagnosticsConfigSnapshot)
            else dict(self.config),
            "process": dict(self.process),
        }
