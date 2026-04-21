from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from src.core.config._settings_view import ConfigSettingsView


def _readonly_settings(settings: ConfigSettingsView | Mapping[str, Any] | None) -> ConfigSettingsView:
    if isinstance(settings, ConfigSettingsView):
        return settings
    return ConfigSettingsView.from_mapping(settings)


def _readonly_config_mapping(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        return MappingProxyType({})
    if isinstance(config, dict):
        return MappingProxyType(config)
    return MappingProxyType(dict(config))


def _readonly_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Wrap a mapping in MappingProxyType for readonly access through the snapshot."""
    if isinstance(value, MappingProxyType):
        return value
    return MappingProxyType(value)


def _readonly_sequence(value: Sequence[Any]) -> tuple[Any, ...]:
    """Convert a sequence to tuple for immutability."""
    if isinstance(value, tuple):
        return value
    return tuple(value)


@dataclass(frozen=True, slots=True)
class DiagnosticsConfigSnapshot:
    present: bool = False
    mtime: int | None = None
    settings: ConfigSettingsView | Mapping[str, Any] = field(default_factory=ConfigSettingsView)
    per_key_colors_count: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", _readonly_settings(self.settings))

    def settings_view(self) -> ConfigSettingsView:
        """Return settings as readonly typed view for boundary consumers."""

        settings = self.settings
        if isinstance(settings, ConfigSettingsView):
            return settings
        return ConfigSettingsView.from_mapping(settings)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"present": bool(self.present)}
        if self.mtime is not None:
            payload["mtime"] = int(self.mtime)
        if self.settings:
            payload["settings"] = self.settings_view().to_dict()
        if self.per_key_colors_count is not None:
            payload["per_key_colors_count"] = int(self.per_key_colors_count)
        if self.error is not None:
            payload["error"] = str(self.error)
        return payload


@dataclass(frozen=True, slots=True)
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

    def __post_init__(self) -> None:
        # Wrap all dict fields in MappingProxyType for readonly access through the snapshot.
        # Callers that have the original reference can still mutate the underlying data,
        # but mutations through the snapshot are prevented.
        object.__setattr__(self, "dmi", _readonly_mapping(self.dmi))
        object.__setattr__(self, "env", _readonly_mapping(self.env))
        object.__setattr__(self, "virt", _readonly_mapping(self.virt))
        object.__setattr__(self, "system", _readonly_mapping(self.system))
        object.__setattr__(self, "hints", _readonly_mapping(self.hints))
        object.__setattr__(self, "app", _readonly_mapping(self.app))
        object.__setattr__(self, "power_supply", _readonly_mapping(self.power_supply))
        object.__setattr__(self, "backends", _readonly_mapping(self.backends))
        object.__setattr__(self, "process", _readonly_mapping(self.process))

        # Convert all list fields to tuple for full immutability.
        object.__setattr__(self, "leds", _readonly_sequence(self.leds))
        object.__setattr__(self, "sysfs_leds", _readonly_sequence(self.sysfs_leds))
        object.__setattr__(self, "usb_devices", _readonly_sequence(self.usb_devices))
        object.__setattr__(self, "usb_ids", _readonly_sequence(self.usb_ids))

        # config field: wrap if it's a plain Mapping (may already be DiagnosticsConfigSnapshot).
        if isinstance(self.config, DiagnosticsConfigSnapshot):
            return
        object.__setattr__(self, "config", _readonly_config_mapping(self.config))

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
