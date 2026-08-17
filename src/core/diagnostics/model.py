from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from src.core.config._settings_view import ConfigSettingsView


def unfreeze_snapshot(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): unfreeze_snapshot(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [unfreeze_snapshot(item) for item in value]
    return value


def freeze_snapshot(value: object) -> object:
    """Return a detached deep-frozen copy of nested mappings and sequences."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): freeze_snapshot(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(freeze_snapshot(item) for item in value)
    return value


def _readonly_settings(settings: ConfigSettingsView | Mapping[str, Any] | None) -> ConfigSettingsView:
    source = settings.to_dict() if isinstance(settings, ConfigSettingsView) else settings
    frozen = freeze_snapshot(source if isinstance(source, Mapping) else {})
    return ConfigSettingsView.from_mapping(frozen if isinstance(frozen, Mapping) else {})


def _readonly_config_mapping(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    frozen = freeze_snapshot(config if isinstance(config, Mapping) else {})
    return frozen if isinstance(frozen, Mapping) else MappingProxyType({})


def _readonly_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen = freeze_snapshot(value)
    return frozen if isinstance(frozen, Mapping) else MappingProxyType({})


def _readonly_sequence(value: Sequence[Any]) -> tuple[Any, ...]:
    frozen = freeze_snapshot(value)
    return frozen if isinstance(frozen, tuple) else (frozen,)


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
            payload["settings"] = unfreeze_snapshot(self.settings_view().to_dict())
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
            "dmi": unfreeze_snapshot(self.dmi),
            "leds": unfreeze_snapshot(self.leds),
            "sysfs_leds": unfreeze_snapshot(self.sysfs_leds),
            "usb_ids": unfreeze_snapshot(self.usb_ids),
            "env": unfreeze_snapshot(self.env),
            "virt": unfreeze_snapshot(self.virt),
            "system": unfreeze_snapshot(self.system),
            "hints": unfreeze_snapshot(self.hints),
            "app": unfreeze_snapshot(self.app),
            "power_supply": unfreeze_snapshot(self.power_supply),
            "backends": unfreeze_snapshot(self.backends),
            "usb_devices": unfreeze_snapshot(self.usb_devices),
            "config": self.config.to_dict()
            if isinstance(self.config, DiagnosticsConfigSnapshot)
            else unfreeze_snapshot(self.config),
            "process": unfreeze_snapshot(self.process),
        }
