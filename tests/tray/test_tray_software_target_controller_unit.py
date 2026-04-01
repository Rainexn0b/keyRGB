from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch


def _make_tray() -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(
            software_effect_target="all_uniform_capable",
            lightbar_brightness=25,
            lightbar_color=(9, 8, 7),
        ),
        engine=SimpleNamespace(
            software_effect_target="keyboard",
            secondary_software_targets_provider=None,
            device_available=True,
            _ensure_device_available=lambda: True,
        ),
        backend=None,
        backend_probe=None,
        device_discovery={
            "candidates": [
                {
                    "device_type": "lightbar",
                    "product": "ITE Device(8233)",
                    "usb_vid": "0x048d",
                    "usb_pid": "0x7001",
                    "status": "supported",
                }
            ]
        },
        secondary_device_controls={"lightbar:048d:7001": True},
        is_off=False,
        _log_event=MagicMock(),
        _log_exception=MagicMock(),
        _notify_permission_issue=MagicMock(),
    )


def test_apply_software_effect_target_selection_persists_and_restores_when_leaving_all_mode() -> None:
    from src.tray.controllers.software_target_controller import apply_software_effect_target_selection

    tray = _make_tray()

    with patch("src.tray.controllers.software_target_controller.restore_secondary_software_targets") as restore:
        result = apply_software_effect_target_selection(tray, "keyboard")

    assert result == "keyboard"
    assert tray.config.software_effect_target == "keyboard"
    assert tray.engine.software_effect_target == "keyboard"
    restore.assert_called_once_with(tray)


def test_secondary_software_render_targets_reuses_cached_proxy_instances() -> None:
    from src.tray.controllers.software_target_controller import secondary_software_render_targets

    tray = _make_tray()

    first = secondary_software_render_targets(tray)
    second = secondary_software_render_targets(tray)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0] is second[0]


def test_software_effect_target_options_enable_all_mode_when_auxiliary_device_exists() -> None:
    from src.tray.controllers.software_target_controller import software_effect_target_options

    tray = _make_tray()

    options = software_effect_target_options(tray)

    assert options == [
        {"key": "keyboard", "label": "Keyboard Only", "enabled": True},
        {"key": "all_uniform_capable", "label": "All Compatible Devices", "enabled": True},
    ]