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
    def copied_from_settings(cls, raw: object) -> dict[str, Any] | None:
        """Return a detached copy of per-effect overrides when present."""

        boundary = cls.from_settings(raw)
        if boundary is None:
            return None
        return boundary.copy_values()

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

    def copy_values(self) -> dict[str, Any]:
        """Return a detached mapping snapshot for call sites.

        This keeps call-site snapshot logic consistent and avoids leaking the
        in-settings mutable mapping when only a copy is required.
        """

        return dict(self.values)
