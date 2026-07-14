"""Profile-backed state for the per-key editor's secondary lighting panel."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from src.core import secondary_lighting_state
from src.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT, SecondaryDeviceRoute
from src.core.secondary_device_runtime import EffectiveSecondaryRoute, iter_effective_secondary_routes


RGB = secondary_lighting_state.RGB


@dataclass(frozen=True)
class SecondaryLightingArea:
    """One route as presented by the editor."""

    route: SecondaryDeviceRoute
    available: bool
    simulated: bool
    availability_reason: str
    enabled: bool
    color: RGB
    brightness: int | None

    @property
    def state_key(self) -> str:
        return self.route.state_key

    @property
    def display_name(self) -> str:
        return self.route.display_name


class SecondaryLightingDraft:
    """Mutable editor draft which keeps unknown profile data intact."""

    def __init__(
        self,
        payload: Mapping[str, object] | None,
        *,
        config: object | None = None,
        effective_routes: Iterable[EffectiveSecondaryRoute] | None = None,
    ) -> None:
        self._payload: dict[str, object] = deepcopy(dict(payload or {"version": 1, "areas": {}}))
        self._payload["version"] = 1
        raw_areas = self._payload.get("areas")
        self._areas: dict[str, object] = (
            {str(key): deepcopy(value) for key, value in raw_areas.items()} if isinstance(raw_areas, Mapping) else {}
        )
        self._payload["areas"] = self._areas
        self._config = config
        self._effective_routes = tuple(
            iter_effective_secondary_routes(include_unavailable=True) if effective_routes is None else effective_routes
        )
        self._seed_available_routes_from_config()

    def _seed_available_routes_from_config(self) -> None:
        """Materialize visible config state in memory until an explicit Save."""
        for effective in self._effective_routes:
            route = effective.route
            if not effective.available or not route.supports_profile_state:
                continue
            raw_entry = self._areas.get(route.state_key)
            entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
            entry.setdefault("enabled", self._config_enabled(self._config, route))
            entry.setdefault("color", list(self._config_color(self._config, route)))
            if route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT:
                entry.setdefault("brightness", self._config_brightness(self._config, route))
            self._areas[route.state_key] = entry

    @property
    def payload(self) -> dict[str, object]:
        return deepcopy(self._payload)

    @property
    def has_available_routes(self) -> bool:
        return any(item.available and item.route.supports_profile_state for item in self._effective_routes)

    @staticmethod
    def _config_color(config: object | None, route: SecondaryDeviceRoute) -> RGB:
        return secondary_lighting_state.config_color(config, route)

    @staticmethod
    def _config_enabled(config: object | None, route: SecondaryDeviceRoute) -> bool:
        return secondary_lighting_state.config_enabled(config, route)

    @staticmethod
    def _config_brightness(config: object | None, route: SecondaryDeviceRoute) -> int:
        return secondary_lighting_state.config_brightness(config, route)

    def areas(self) -> tuple[SecondaryLightingArea, ...]:
        result: list[SecondaryLightingArea] = []
        for effective in self._effective_routes:
            route = effective.route
            if not route.supports_profile_state:
                continue
            raw_entry = self._areas.get(route.state_key, {})
            entry = raw_entry if isinstance(raw_entry, Mapping) else {}
            result.append(
                SecondaryLightingArea(
                    route=route,
                    available=effective.available,
                    simulated=effective.simulated,
                    availability_reason=effective.availability_reason,
                    enabled=secondary_lighting_state.normalize_enabled(
                        entry.get("enabled"), self._config_enabled(self._config, route)
                    ),
                    color=secondary_lighting_state.normalize_color(
                        entry.get("color"), self._config_color(self._config, route)
                    ),
                    brightness=(
                        secondary_lighting_state.normalize_brightness(
                            entry.get("brightness"),
                            self._config_brightness(self._config, route),
                        )
                        if route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT
                        else None
                    ),
                )
            )
        return tuple(result)

    def set_enabled(self, state_key: str, enabled: bool) -> None:
        key = str(state_key)
        raw_entry = self._areas.get(key)
        entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
        entry["enabled"] = bool(enabled)
        self._areas[key] = entry

    def set_color(self, state_key: str, color: object) -> RGB:
        normalized = secondary_lighting_state.normalize_color(color)
        key = str(state_key)
        raw_entry = self._areas.get(key)
        entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
        entry["color"] = list(normalized)
        self._areas[key] = entry
        return normalized

    def set_brightness(self, state_key: str, brightness: object) -> int:
        normalized = secondary_lighting_state.normalize_brightness(brightness)
        key = str(state_key)
        raw_entry = self._areas.get(key)
        entry = dict(raw_entry) if isinstance(raw_entry, Mapping) else {}
        entry["brightness"] = normalized
        self._areas[key] = entry
        return normalized

    def refresh(self, payload: Mapping[str, object] | None) -> None:
        replacement = SecondaryLightingDraft(
            payload,
            config=self._config,
            effective_routes=self._effective_routes,
        )
        self._payload = replacement._payload
        self._areas = replacement._areas


__all__ = ["RGB", "SecondaryLightingArea", "SecondaryLightingDraft"]
