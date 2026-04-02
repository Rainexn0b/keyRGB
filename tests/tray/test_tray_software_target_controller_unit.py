from __future__ import annotations

import pytest
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

def test_configure_engine_software_targets_logs_recoverable_engine_setter_failure() -> None:
    from src.tray.controllers.software_target_controller import configure_engine_software_targets

    class _Engine:
        def __init__(self) -> None:
            self.secondary_software_targets_provider = None

        @property
        def software_effect_target(self) -> str:
            return "keyboard"

        @software_effect_target.setter
        def software_effect_target(self, _value: str) -> None:
            raise RuntimeError("setter failed")

    tray = _make_tray()
    tray.engine = _Engine()

    configure_engine_software_targets(tray)

    tray._log_exception.assert_called_once()
    assert tray._log_exception.call_args.args[0] == "Failed to sync engine software target: %s"
    assert str(tray._log_exception.call_args.args[1]) == "setter failed"
    assert callable(tray.engine.secondary_software_targets_provider)


def test_restore_secondary_software_targets_bubbles_unhandled_exceptions() -> None:
    from src.tray.controllers.software_target_controller import restore_secondary_software_targets

    tray = _make_tray()

    with patch(
        "src.tray.controllers.software_target_controller._iter_secondary_targets",
        return_value=[({}, object())],
    ):
        with patch(
            "src.tray.controllers.software_target_controller._restore_target_from_config",
            side_effect=LookupError("unexpected bug"),
        ):
            with pytest.raises(LookupError, match="unexpected bug"):
                restore_secondary_software_targets(tray)


def test_handle_secondary_target_error_falls_back_to_logger_when_tray_logging_raises() -> None:
    from src.tray.controllers.software_target_controller import _handle_secondary_target_error

    original_exc = RuntimeError("device failed")
    tray = _make_tray()
    tray._log_exception.side_effect = RuntimeError("logger failed")

    with patch("src.tray.controllers.software_target_controller.logger.exception") as log_exception:
        with patch("src.tray.controllers.software_target_controller.logger.error") as log_error:
            _handle_secondary_target_error(tray, original_exc, action="restore_secondary_software_target")

    tray._log_exception.assert_called_once_with("Error during restore_secondary_software_target: %s", original_exc)
    log_exception.assert_called_once()
    assert log_exception.call_args.args[0] == "Tray exception logger failed while logging boundary: %s"
    assert str(log_exception.call_args.args[1]) == "logger failed"

    log_error.assert_called_once()
    assert log_error.call_args.args[0] == "Error during restore_secondary_software_target: %s"
    assert log_error.call_args.args[1] is original_exc
    exc_info = log_error.call_args.kwargs["exc_info"]
    assert exc_info[0] is RuntimeError
    assert exc_info[1] is original_exc
    assert exc_info[2] is original_exc.__traceback__

