from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.tray.pollers.config_polling import ConfigApplyState, _maybe_apply_fast_path
from src.tray.pollers.config_polling_internal._config_apply_state import _safe_secondary_signature


def _state(*, secondary_sig: tuple | None) -> ConfigApplyState:
    return ConfigApplyState(
        effect="none",
        speed=1,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(4, 5, 6),
        secondary_sig=secondary_sig,
    )


def test_secondary_signature_is_immutable_and_order_independent() -> None:
    first = SimpleNamespace(
        _settings={
            "secondary_device_state": {
                "mouse": {"color": [1, 2, 3], "enabled": True},
                "logo": {"enabled": False},
            }
        }
    )
    second = SimpleNamespace(
        _settings={
            "secondary_device_state": {
                "logo": {"enabled": False},
                "mouse": {"enabled": True, "color": [1, 2, 3]},
            }
        }
    )

    signature = _safe_secondary_signature(first)
    assert signature == _safe_secondary_signature(second)
    assert isinstance(signature, tuple)
    assert isinstance(signature[0], tuple)


def test_secondary_only_fast_path_reconciles_without_keyboard_restart() -> None:
    tray = MagicMock()
    tray.config = SimpleNamespace(
        _settings={"secondary_device_state": {"mouse": {"enabled": True, "color": [9, 8, 7]}}},
        effect="none",
        software_effect_target="keyboard",
    )
    last = _state(secondary_sig=(("mouse", (("enabled", False),)),))
    current = _state(secondary_sig=(("mouse", (("enabled", True),)),))

    with patch(
        "src.tray.pollers.config_polling_internal.helpers._software_target_controller.reconcile_secondary_profile_state"
    ) as reconcile:
        handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    reconcile.assert_called_once()
    tray.engine.stop.assert_not_called()
    tray.engine.kb.set_color.assert_not_called()


def test_secondary_signature_change_is_not_misclassified_as_base_or_target_change() -> None:
    from src.tray.pollers.config_polling_internal._fast_path import classify_fast_path_change

    assert (
        classify_fast_path_change(
            last_applied=_state(secondary_sig=(("a", ()),)), current=_state(secondary_sig=(("b", ()),))
        )
        == "secondary_only"
    )


def test_normal_uniform_apply_restores_static_scene_regardless_of_effect_output() -> None:
    from src.tray.pollers.config_polling_internal import _apply_callbacks

    tray = MagicMock()
    tray.config = SimpleNamespace(software_effect_target="keyboard")
    current = _state(secondary_sig=(("logo", (("enabled", True),)),))

    with patch("src.tray.pollers.config_polling_internal.helpers._apply_secondary_static_from_config") as apply_static:
        _apply_callbacks._apply_uniform(tray, current, cause="startup")

    apply_static.assert_called_once_with(tray)


def test_default_empty_secondary_mirror_reconciles_as_legacy_state() -> None:
    from src.tray.pollers.config_polling_internal import helpers

    tray = MagicMock()
    tray.config = SimpleNamespace(_settings={"secondary_device_state": {}})

    with patch(
        "src.tray.pollers.config_polling_internal.helpers._software_target_controller.reconcile_secondary_profile_state"
    ) as reconcile:
        helpers._apply_secondary_static_from_config(tray)

    reconcile.assert_called_once_with(tray, None, animated=False)


def test_partial_v028_secondary_mirror_reconciles_as_legacy_state() -> None:
    from src.tray.pollers.config_polling_internal import helpers

    tray = MagicMock()
    tray.config = SimpleNamespace(
        _settings={
            "secondary_device_state": {
                "ite8258_chassis_logo": {
                    "brightness": 25,
                    "color": [1, 2, 3],
                }
            }
        }
    )

    with patch(
        "src.tray.pollers.config_polling_internal.helpers._software_target_controller.reconcile_secondary_profile_state"
    ) as reconcile:
        helpers._apply_secondary_static_from_config(tray)

    reconcile.assert_called_once_with(tray, None, animated=False)
