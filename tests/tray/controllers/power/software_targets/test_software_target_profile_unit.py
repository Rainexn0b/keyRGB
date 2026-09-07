"""Direct unit coverage for secondary software-target profile helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from keyrgb.tray.controllers import _software_target_profile as profile
from keyrgb.tray.ui.menu_status import DeviceContextEntry


def _entry(**overrides: Any) -> DeviceContextEntry:
    base: dict[str, Any] = {
        "backend_name": "ite8233_none_chassis_lightbar_clevo",
        "connected": True,
        "device_type": "lightbar",
        "is_virtual_area": False,
        "key": "lightbar:048d:7001",
        "simulated": False,
        "source": "usb",
        "status": "ok",
        "text": "Lightbar",
    }
    base.update(overrides)
    return DeviceContextEntry(**base)


def _target(*, state_key: str = "lightbar") -> SimpleNamespace:
    return SimpleNamespace(
        state_key=state_key,
        turn_off=MagicMock(),
        set_color=MagicMock(),
    )


def test_restore_target_from_config_noop_when_route_unknown() -> None:
    tray = SimpleNamespace(config=SimpleNamespace())
    target = _target()
    entry = _entry(device_type="not-a-real-device", backend_name="missing")

    profile.restore_target_from_config(tray, entry=entry, target=target)

    target.turn_off.assert_not_called()
    target.set_color.assert_not_called()


def test_restore_target_from_config_turns_off_when_entry_disabled() -> None:
    tray = SimpleNamespace(
        config=SimpleNamespace(lightbar_brightness=20, lightbar_color=(1, 2, 3)),
        _active_secondary_lighting={
            "version": 1,
            "areas": {"lightbar": {"enabled": False, "color": [9, 8, 7], "brightness": 11}},
        },
    )
    target = _target()

    profile.restore_target_from_config(tray, entry=_entry(), target=target)

    target.turn_off.assert_called_once_with()
    target.set_color.assert_not_called()


def test_restore_target_from_config_applies_enabled_route_color() -> None:
    config = SimpleNamespace(lightbar_brightness=20, lightbar_color=(1, 2, 3))
    tray = SimpleNamespace(
        config=config,
        _active_secondary_lighting={
            "version": 1,
            "areas": {"lightbar": {"enabled": True, "color": [9, 8, 7], "brightness": 11}},
        },
    )
    target = _target()

    profile.restore_target_from_config(tray, entry=_entry(), target=target)

    target.set_color.assert_called_once()
    args, kwargs = target.set_color.call_args
    assert args[0] == (9, 8, 7)
    assert kwargs["brightness"] == 11


def test_restore_target_from_config_uses_legacy_snapshot_when_no_active_payload() -> None:
    config = SimpleNamespace(
        lightbar_brightness=33,
        lightbar_color=(4, 5, 6),
        lightbar_enabled=True,
    )
    tray = SimpleNamespace(config=config)
    # Ensure no _active_secondary_lighting attribute.
    assert not hasattr(tray, "_active_secondary_lighting")
    target = _target()

    profile.restore_target_from_config(tray, entry=_entry(), target=target)

    target.set_color.assert_called_once()
    (color,) = target.set_color.call_args.args
    assert color == (4, 5, 6)
    assert target.set_color.call_args.kwargs["brightness"] == 33


def test_reconcile_secondary_profile_state_applies_static_scene_when_payload_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_scene = MagicMock()
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.secondary_static_scene.apply_secondary_static_scene",
        apply_scene,
    )
    tray = SimpleNamespace()

    profile.reconcile_secondary_profile_state(
        tray,
        None,
        animated=False,
        proxy_cache_fn=lambda _t: {},
        handle_secondary_target_error_fn=MagicMock(),
    )

    apply_scene.assert_called_once_with(tray)


def test_reconcile_secondary_profile_state_skips_static_scene_when_animated_and_payload_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_scene = MagicMock()
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.secondary_static_scene.apply_secondary_static_scene",
        apply_scene,
    )

    profile.reconcile_secondary_profile_state(
        SimpleNamespace(),
        None,
        animated=True,
        proxy_cache_fn=lambda _t: {},
        handle_secondary_target_error_fn=MagicMock(),
    )

    apply_scene.assert_not_called()


def test_reconcile_secondary_profile_state_turns_off_removed_targets_when_animated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_scene = MagicMock()
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.secondary_static_scene.apply_secondary_static_scene",
        apply_scene,
    )
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.any_forced_off",
        lambda _tray: False,
    )

    lightbar = _target(state_key="lightbar")
    logo = _target(state_key="logo")
    tray = SimpleNamespace(
        _active_secondary_lighting={
            "version": 1,
            "areas": {
                "lightbar": {"enabled": True},
                "logo": {"enabled": True},
            },
        }
    )
    errors: list[tuple[object, str]] = []

    def handle_error(tray_obj: object, exc: Exception, *, action: str) -> None:
        errors.append((exc, action))

    # New payload keeps lightbar only.
    payload = {
        "version": 1,
        "areas": {
            "lightbar": {"enabled": True},
            "logo": {"enabled": False},
        },
    }

    profile.reconcile_secondary_profile_state(
        tray,
        payload,
        animated=True,
        proxy_cache_fn=lambda _t: {"lb": lightbar, "lg": logo},
        handle_secondary_target_error_fn=handle_error,
    )

    logo.turn_off.assert_called_once_with()
    lightbar.turn_off.assert_not_called()
    assert tray._active_secondary_lighting is payload
    apply_scene.assert_not_called()
    assert errors == []


def test_reconcile_secondary_profile_state_handles_turn_off_runtime_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.any_forced_off",
        lambda _tray: False,
    )
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.secondary_static_scene.apply_secondary_static_scene",
        MagicMock(),
    )

    failing = _target(state_key="logo")
    failing.turn_off.side_effect = RuntimeError("device gone")
    tray = SimpleNamespace(
        _active_secondary_lighting={"version": 1, "areas": {"logo": {"enabled": True}}},
    )
    handled: list[str] = []

    profile.reconcile_secondary_profile_state(
        tray,
        {"version": 1, "areas": {"logo": {"enabled": False}}},
        animated=True,
        proxy_cache_fn=lambda _t: {"lg": failing},
        handle_secondary_target_error_fn=lambda _t, _e, *, action: handled.append(action),
    )

    assert handled == ["disable_secondary_software_target"]


def test_reconcile_secondary_profile_state_applies_static_scene_when_not_animated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply_scene = MagicMock()
    monkeypatch.setattr(
        "keyrgb.tray.controllers._software_target_profile.secondary_static_scene.apply_secondary_static_scene",
        apply_scene,
    )
    tray = SimpleNamespace()
    payload = {
        "version": 1,
        "areas": {"lightbar": {"enabled": True, "color": [1, 2, 3], "brightness": 10}},
    }

    profile.reconcile_secondary_profile_state(
        tray,
        payload,
        animated=False,
        proxy_cache_fn=lambda _t: {},
        handle_secondary_target_error_fn=MagicMock(),
    )

    assert tray._active_secondary_lighting is payload
    apply_scene.assert_called_once_with(tray, payload=payload)
