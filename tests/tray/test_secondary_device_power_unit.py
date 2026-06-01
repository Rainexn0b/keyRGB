from __future__ import annotations

from types import SimpleNamespace

from src.tray import secondary_device_power


def _route(**overrides: object) -> SimpleNamespace:
    data = {
        "device_type": "lightbar",
        "state_key": "lightbar",
        "config_brightness_attr": "lightbar_brightness",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_current_brightness_uses_secondary_config_facade() -> None:
    calls: list[tuple[str, tuple[str, ...], int]] = []

    class Config:
        def get_secondary_device_brightness(self, state_key: str, *, fallback_keys=(), default=0):
            calls.append((state_key, tuple(fallback_keys), int(default)))
            return 35

    assert secondary_device_power.current_brightness(Config(), _route()) == 35
    assert calls == [("lightbar", ("lightbar_brightness",), 0)]


def test_current_brightness_falls_back_to_safe_attr_reader() -> None:
    config = SimpleNamespace(lightbar_brightness="20")
    safe_calls: list[tuple[object, str, int]] = []

    def safe_int_attr(obj: object, attr_name: str, *, default=0, min_v=None, max_v=None) -> int:
        del min_v, max_v
        safe_calls.append((obj, attr_name, int(default)))
        return int(getattr(obj, attr_name, default))

    assert secondary_device_power.current_brightness(config, _route(), safe_int_attr=safe_int_attr) == 20
    assert safe_calls == [(config, "lightbar_brightness", 0)]


def test_restore_brightness_prefers_cached_last_nonzero_brightness() -> None:
    tray = SimpleNamespace()
    route = _route()

    secondary_device_power.cache_restore_brightness(tray, route, 15)

    assert secondary_device_power.restore_brightness(
        tray,
        route,
        current_brightness_fn=lambda: 45,
    ) == 15


def test_restore_brightness_uses_current_then_default_when_no_hint() -> None:
    tray = SimpleNamespace()
    route = _route()

    assert secondary_device_power.restore_brightness(
        tray,
        route,
        current_brightness_fn=lambda: 30,
    ) == 30
    assert secondary_device_power.restore_brightness(
        tray,
        route,
        current_brightness_fn=lambda: 0,
    ) == 25


def test_is_off_uses_current_brightness() -> None:
    assert secondary_device_power.is_off(SimpleNamespace(lightbar_brightness=0), _route()) is True
    assert secondary_device_power.is_off(SimpleNamespace(lightbar_brightness=5), _route()) is False
