from __future__ import annotations

from dataclasses import dataclass, field

from src.core.config._lighting import _secondary_device_accessors as accessors


@dataclass
class _FakeConfig:
    _settings: dict[str, object] = field(default_factory=dict)
    DEFAULTS: object = field(default_factory=dict)
    save_calls: int = 0

    def _save(self) -> None:
        self.save_calls += 1

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:
        value = int(value)
        if value <= 0:
            return 0
        if value >= 50:
            return 50
        return max(5, int(round(value / 5) * 5))


def _default_setting(defaults: object, key: str, *, fallback_keys: tuple[str, ...] = (), default: object) -> object:
    if not isinstance(defaults, dict):
        return default
    if key in defaults:
        return defaults[key]
    for fallback_key in fallback_keys:
        if fallback_key in defaults:
            return defaults[fallback_key]
    return default


def _coerce_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default


def test_set_secondary_device_brightness_preserves_existing_color_field() -> None:
    cfg = _FakeConfig(
        _settings={
            "secondary_device_state": {
                "mouse": {
                    "color": [1, 2, 3],
                }
            }
        }
    )

    accessors.set_secondary_device_brightness(cfg, "mouse", 17)

    assert cfg._settings["secondary_device_state"] == {
        "mouse": {
            "brightness": 15,
            "color": [1, 2, 3],
        }
    }
    assert cfg.save_calls == 1


def test_get_secondary_device_color_prefers_state_entry_over_compatibility_fallback() -> None:
    cfg = _FakeConfig(
        _settings={
            "secondary_device_state": {
                "lightbar": {
                    "color": [9, "bad", 10],
                }
            },
            "legacy_lightbar_color": [1, 2, 3],
        },
        DEFAULTS={
            "legacy_lightbar_color": [4, 5, 6],
        },
    )

    color = accessors.get_secondary_device_color(
        cfg,
        "lightbar",
        fallback_keys=("legacy_lightbar_color",),
        default=(255, 0, 0),
        default_setting_fn=_default_setting,
    )

    assert color == (9, 0, 10)


def test_get_secondary_device_brightness_falls_back_to_compatibility_key_then_normalizes() -> None:
    cfg = _FakeConfig(
        _settings={
            "legacy_primary": 23,
            "legacy_secondary": 12,
        },
        DEFAULTS={
            "legacy_primary": 8,
            "legacy_secondary": 10,
        },
    )

    brightness = accessors.get_secondary_device_brightness(
        cfg,
        "mouse",
        fallback_keys=("legacy_primary", "legacy_secondary"),
        default=0,
        default_setting_fn=_default_setting,
        coerce_int_setting_fn=_coerce_int,
    )

    assert brightness == 25
