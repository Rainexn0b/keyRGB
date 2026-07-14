from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.secondary_device_routes import BRIGHTNESS_POLICY_INDEPENDENT, BRIGHTNESS_POLICY_PRIMARY_SHARED


@pytest.fixture(autouse=True)
def _stub_profile_state_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.profiles.update_secondary_lighting_area",
        lambda state_key, updates: {"version": 1, "areas": {state_key: dict(updates)}},
    )


def _make_tray(selected_context: str = "ite8258-chassis-logo") -> SimpleNamespace:
    return SimpleNamespace(
        selected_device_context=selected_context,
        config=SimpleNamespace(
            ite8258_chassis_logo_brightness=25,
            ite8258_chassis_neon_brightness=25,
            ite8258_chassis_vent_brightness=25,
            set_secondary_device_brightness=lambda _state_key, _value, *, compatibility_key=None: None,
        ),
        _update_menu=MagicMock(),
        _log_exception=MagicMock(),
        _notify_permission_issue=MagicMock(),
        _log_event=MagicMock(),
    )


def _fake_route_for_logo(device_calls: list) -> SimpleNamespace:
    class DummyLogoDevice:
        def set_brightness(self, brightness: int) -> None:
            device_calls.append(("set_brightness", int(brightness)))

        def turn_off(self) -> None:
            device_calls.append(("turn_off",))

    return SimpleNamespace(
        device_type="logo",
        display_name="Logo",
        backend_name="ite8258-chassis-logo",
        state_key="ite8258_chassis_logo",
        config_brightness_attr="ite8258_chassis_logo_brightness",
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_PRIMARY_SHARED,
        get_device=lambda: DummyLogoDevice(),
    )


def test_apply_selected_secondary_brightness_rejects_shared_virtual_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray("ite8258-chassis-logo")
    device_calls: list = []
    route = _fake_route_for_logo(device_calls)

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda _tray: {"key": tray.selected_device_context, "device_type": "logo"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda _entry: route,
    )

    assert apply_selected_secondary_brightness(tray, "6") is False
    assert device_calls == []


def test_turn_off_selected_virtual_logo_device_turns_off_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tray.controllers.secondary_device_controller import turn_off_selected_secondary_device

    tray = _make_tray("ite8258-chassis-logo")
    device_calls: list = []
    route = _fake_route_for_logo(device_calls)

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda _tray: {"key": tray.selected_device_context, "device_type": "logo"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda _entry: route,
    )

    assert turn_off_selected_secondary_device(tray) is True
    assert device_calls == [("turn_off",)]


def test_turn_on_selected_virtual_logo_device_reapplies_profile_static_color(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tray.controllers.secondary_device_controller import (
        turn_off_selected_secondary_device,
        turn_on_selected_secondary_device,
    )

    tray = _make_tray("ite8258-chassis-logo")
    tray.config.ite8258_chassis_logo_brightness = 10
    device_calls: list = []
    route = _fake_route_for_logo(device_calls)
    reapplied: list[str] = []

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda _tray: {"key": tray.selected_device_context, "device_type": "logo"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda _entry: route,
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.apply_secondary_static_route",
        lambda _tray, selected_route: reapplied.append(selected_route.state_key) or True,
    )

    assert turn_off_selected_secondary_device(tray) is True
    assert device_calls == [("turn_off",)]

    assert turn_on_selected_secondary_device(tray) is True
    assert device_calls == [("turn_off",)]
    assert reapplied == ["ite8258_chassis_logo"]


def test_one_shot_controller_closes_virtual_zone_device_after_brightness_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.tray.controllers.secondary_device_controller import apply_selected_secondary_brightness

    tray = _make_tray("ite8258-chassis-logo")
    close_calls: list[bool] = []

    class DummyLogoDevice:
        def set_brightness(self, brightness: int) -> None:
            pass

        def close(self) -> None:
            close_calls.append(True)

    route = SimpleNamespace(
        device_type="logo",
        display_name="Logo",
        backend_name="ite8258-chassis-logo",
        state_key="ite8258_chassis_logo",
        config_brightness_attr="ite8258_chassis_logo_brightness",
        supports_profile_state=True,
        brightness_policy=BRIGHTNESS_POLICY_INDEPENDENT,
        get_device=lambda: DummyLogoDevice(),
    )

    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.selected_device_context_entry",
        lambda _tray: {"key": tray.selected_device_context, "device_type": "logo"},
    )
    monkeypatch.setattr(
        "src.tray.controllers.secondary_device_controller.route_for_context_entry",
        lambda _entry: route,
    )

    assert apply_selected_secondary_brightness(tray, "6") is True
    assert close_calls == [True]
