from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EffectSpeedOverrides:
    """Typed boundary for optional per-effect speed overrides."""

    values: dict[str, Any]

    @classmethod
    def from_settings(cls, raw: object) -> EffectSpeedOverrides | None:
        if not isinstance(raw, dict):
            return None
        return cls(values=raw)

    @classmethod
    def ensure_in_settings(cls, settings: dict[str, Any]) -> EffectSpeedOverrides:
        current = cls.from_settings(settings.get("effect_speeds"))
        if current is not None:
            return current

        created: dict[str, Any] = {}
        settings["effect_speeds"] = created
        return cls(values=created)

    def lookup(self, effect_name: str) -> tuple[bool, object | None]:
        if effect_name not in self.values:
            return False, None
        return True, self.values[effect_name]

    def assign(self, effect_name: str, speed: int) -> None:
        self.values[effect_name] = speed
