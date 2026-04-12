from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from src.tray.pollers.config_polling import ConfigApplyState, _maybe_apply_fast_path
from src.tray.pollers.config_polling_internal.helpers import _sync_software_target_policy


def _mk_tray(*, engine_running: bool = True) -> MagicMock:
    tray = MagicMock()
    tray.engine = MagicMock()
    tray.engine.running = engine_running
    tray.config = SimpleNamespace(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )
    return tray


def test_fastpath_reactive_change_updates_engine_without_restart() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=True,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    assert tray.engine.reactive_use_manual_color is True
    assert tray.engine.reactive_color == (10, 20, 30)
    tray.engine.set_brightness.assert_not_called()


def test_fastpath_brightness_change_for_running_sw_effect_does_not_restart_and_no_hw_write() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    tray.engine.set_brightness.assert_called_once_with(30, apply_to_hardware=False)


def test_fastpath_brightness_change_not_taken_if_engine_not_running() -> None:
    tray = _mk_tray(engine_running=False)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, _ = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is False
    tray.engine.set_brightness.assert_not_called()


def test_fastpath_brightness_change_not_taken_for_non_sw_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="wave",  # treated as hardware effect name
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    current = ConfigApplyState(
        effect="wave",
        speed=4,
        brightness=30,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, _ = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is False
    tray.engine.set_brightness.assert_not_called()


def test_fastpath_software_target_change_updates_policy_without_restart() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        software_effect_target="keyboard",
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        software_effect_target="all_uniform_capable",
    )

    with patch("src.tray.pollers.config_polling_internal.helpers._sync_software_target_policy") as sync_policy:
        handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    sync_policy.assert_called_once_with(tray, current)
    tray.engine.set_brightness.assert_not_called()


def test_sync_software_target_policy_logs_config_setter_failure_and_still_updates_runtime_policy() -> None:
    class BrokenConfig:
        def __setattr__(self, name: str, value: object) -> None:
            if name == "software_effect_target":
                raise RuntimeError(f"cannot persist {value}")
            super().__setattr__(name, value)

    tray = _mk_tray(engine_running=True)
    tray.config = BrokenConfig()
    tray._log_exception = MagicMock()
    tray.is_off = False

    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        software_effect_target="keyboard",
    )

    with (
        patch(
            "src.tray.pollers.config_polling_internal.helpers.configure_engine_software_targets"
        ) as configure_targets,
        patch("src.tray.pollers.config_polling_internal.helpers.restore_secondary_software_targets") as restore_targets,
    ):
        _sync_software_target_policy(tray, current)

    tray._log_exception.assert_called_once()
    configure_targets.assert_called_once_with(tray)
    restore_targets.assert_called_once_with(tray)


def test_sync_software_target_policy_propagates_unexpected_config_setter_failure() -> None:
    class BrokenConfig:
        def __setattr__(self, name: str, value: object) -> None:
            if name == "software_effect_target":
                raise AssertionError(f"unexpected persist bug: {value}")
            super().__setattr__(name, value)

    tray = _mk_tray(engine_running=True)
    tray.config = BrokenConfig()
    tray._log_exception = MagicMock()
    tray.is_off = False

    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        software_effect_target="keyboard",
    )

    with pytest.raises(AssertionError, match="unexpected persist bug"):
        _sync_software_target_policy(tray, current)


def test_fastpath_trail_percent_change_updates_engine_without_restart() -> None:
    tray = _mk_tray(engine_running=True)

    last = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        reactive_trail_percent=50,
    )
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
        reactive_trail_percent=80,
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last, current=current)

    assert handled is True
    assert new_last == current
    assert tray.engine.reactive_trail_percent == 80
    tray.engine.set_brightness.assert_not_called()
