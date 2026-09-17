from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from keyrgb.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT


def _make_lightbar_route(*, device_factory):
    return SimpleNamespace(
        device_type="lightbar",
        backend_name="ite8233_none_chassis_lightbar_clevo",
        display_name="Lightbar",
        state_key="lightbar",
        get_device=device_factory,
        config_brightness_attr="lightbar_brightness",
        config_color_attr="lightbar_color",
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
    )


@pytest.fixture(autouse=True)
def _stub_profile_brightness_persistence(monkeypatch):
    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.profiles.update_secondary_lighting_area",
        lambda state_key, updates: {"version": 1, "areas": {state_key: dict(updates)}},
    )


def _make_tray() -> SimpleNamespace:
    tray = SimpleNamespace(
        selected_device_context="lightbar:048d:7001",
        config=SimpleNamespace(lightbar_brightness=25, lightbar_color=(255, 0, 0)),
        _update_menu=MagicMock(),
        _log_exception=MagicMock(),
        _notify_permission_issue=MagicMock(),
        _log_event=MagicMock(),
    )
    tray.config.set_secondary_device_enabled = MagicMock()
    return tray


def test_turn_on_selected_secondary_device_restores_last_nonzero_brightness(monkeypatch) -> None:
    from keyrgb.tray.controllers.secondary_device_controller import (
        turn_off_selected_secondary_device,
        turn_on_selected_secondary_device,
    )

    tray = _make_tray()
    tray.config.lightbar_brightness = 10
    tray._active_secondary_lighting = {
        "version": 1,
        "areas": {"lightbar": {"enabled": True, "brightness": 10, "color": [10, 20, 30]}},
    }
    seen: list[tuple[int, str] | tuple[int, tuple[int, int, int], int]] = []
    constructed = 0

    def update_profile(state_key: str, updates: dict[str, object]) -> dict[str, object]:
        entry = dict(tray._active_secondary_lighting["areas"][state_key])
        entry.update(updates)
        return {"version": 1, "areas": {state_key: entry}}

    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.profiles.update_secondary_lighting_area",
        update_profile,
    )

    class DummyDevice:
        def __init__(self, device_id: int) -> None:
            self.device_id = device_id

        def turn_off(self) -> None:
            seen.append((self.device_id, "off"))

        def set_color(self, color: tuple[int, int, int], *, brightness: int) -> None:
            seen.append((self.device_id, color, int(brightness)))

        def set_brightness(self, brightness: int) -> None:
            raise AssertionError(f"fresh-device cache must not be used: {brightness}")

    def make_device() -> DummyDevice:
        nonlocal constructed
        constructed += 1
        return DummyDevice(constructed)

    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda entry: _make_lightbar_route(device_factory=make_device),
    )

    assert turn_off_selected_secondary_device(tray) is True
    assert tray.config.lightbar_brightness == 0

    assert turn_on_selected_secondary_device(tray) is True
    assert tray.config.lightbar_brightness == 10
    assert tray.config.set_secondary_device_enabled.call_args_list[-1].args == ("lightbar", True)
    assert tray._active_secondary_lighting["areas"]["lightbar"] == {
        "brightness": 10,
        "color": [10, 20, 30],
        "enabled": True,
    }
    assert seen == [(1, "off"), (2, (10, 20, 30), 10)]
    assert tray._update_menu.call_count == 2


def test_turn_on_selected_secondary_device_restores_active_profile_brightness(monkeypatch) -> None:
    from keyrgb.tray.controllers.secondary_device_controller import turn_on_selected_secondary_device

    tray = _make_tray()
    tray.config.lightbar_brightness = 0
    tray._active_secondary_lighting = {
        "version": 1,
        "areas": {"lightbar": {"enabled": False, "brightness": 40, "color": [8, 16, 24]}},
    }
    seen: list[tuple[tuple[int, int, int], int]] = []

    class DummyDevice:
        def set_color(self, color: tuple[int, int, int], *, brightness: int) -> None:
            seen.append((color, int(brightness)))

        def set_brightness(self, brightness: int) -> None:
            raise AssertionError(f"fresh-device cache must not be used: {brightness}")

    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda tray_obj: {"key": tray_obj.selected_device_context, "device_type": "lightbar"},
    )
    monkeypatch.setattr(
        "keyrgb.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda entry: _make_lightbar_route(device_factory=lambda: DummyDevice()),
    )

    assert turn_on_selected_secondary_device(tray) is True
    assert seen == [((8, 16, 24), 40)]
    assert tray.config.lightbar_brightness == 40
    assert tray._active_secondary_lighting["areas"]["lightbar"] == {"brightness": 40, "enabled": True}
