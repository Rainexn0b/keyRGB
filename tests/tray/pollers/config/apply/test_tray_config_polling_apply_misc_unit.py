from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from keyrgb.tray.pollers import config_polling
from keyrgb.tray.pollers.config_polling import ConfigApplyState, _apply_from_config_once
from keyrgb.tray.pollers.config_polling_internal import _planning, core as config_polling_core
from keyrgb.tray.pollers.config_polling_internal._apply_plan import ConfigApplyPlan


def _mk_tray_base(*, effect: str, brightness: int) -> MagicMock:
    from tests.tray.fakes import make_owner_backed_mock_tray

    tray = make_owner_backed_mock_tray(
        is_off=False,
        user_forced_off=False,
        power_forced_off=False,
        idle_forced_off=False,
    )
    tray.config = SimpleNamespace(
        CONFIG_FILE="/tmp/keyrgb-test-config.json",
        effect=effect,
        speed=4,
        brightness=brightness,
        color=(1, 2, 3),
        per_key_colors={},
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )
    tray.engine.running = True
    tray.engine.kb = MagicMock()
    tray.engine.kb_lock = MagicMock(__enter__=lambda s: None, __exit__=lambda s, *args: None)
    return tray


def test_apply_from_config_once_returns_early_when_state_unchanged() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=25)

    last_applied = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    new_last, warn_at = _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=last_applied,
        last_apply_warn_at=0.0,
    )

    assert new_last == last_applied
    assert warn_at == 0.0
    tray._start_current_effect.assert_not_called()
    tray.engine.set_brightness.assert_not_called()


def test_classify_apply_from_config_delegates_without_mutating_inputs() -> None:
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    plan = ConfigApplyPlan(persist_effect="wave", execution_kind="apply")

    with patch.object(_planning, "classify_config_apply_plan", return_value=plan) as planner:
        returned = _planning.classify_apply_from_config(
            configured_effect="rainbow_wave",
            current=current,
        )

    assert returned is plan
    planner.assert_called_once_with(configured_effect="rainbow_wave", current=current)
    assert current.effect == "rainbow_wave"


def test_resolve_apply_from_config_policy_reads_effect_then_delegates() -> None:
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )
    config = SimpleNamespace(effect="wave")
    plan = ConfigApplyPlan(persist_effect="rainbow_wave", execution_kind="apply")

    with patch.object(_planning, "classify_apply_from_config", return_value=plan) as planner:
        returned = _planning.resolve_apply_from_config_policy(
            config,
            current=current,
            read_str_attr_fn=config_polling_core.safe_str_attr,
        )

    assert returned is plan
    planner.assert_called_once_with(configured_effect="wave", current=current)


def test_apply_from_config_once_uses_planning_output_contract_as_is() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=10)

    with patch.object(
        config_polling_core,
        "resolve_apply_from_config_policy",
        return_value=ConfigApplyPlan(persist_effect="wave", execution_kind="apply"),
    ):
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )

    assert tray.config.effect == "wave"
    tray.engine.turn_off.assert_not_called()
    tray._start_current_effect.assert_called_once()


def test_apply_from_config_once_logs_signature_exception_throttled() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=25)

    with (
        patch.object(config_polling, "_compute_config_apply_state", side_effect=RuntimeError("boom")),
        patch.object(config_polling.time, "monotonic", side_effect=[100.0, 120.0, 200.0]),
    ):
        last, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )
        assert warn_at == 100.0
        tray._log_exception.assert_called_once()

        tray._log_exception.reset_mock()
        last2, warn_at2 = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=last,
            last_apply_warn_at=warn_at,
        )
        assert warn_at2 == 100.0
        tray._log_exception.assert_not_called()

        tray._log_exception.reset_mock()
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=last2,
            last_apply_warn_at=warn_at2,
        )
        tray._log_exception.assert_called_once()


def test_apply_from_config_once_turns_off_on_zero_brightness_and_throttles_engine_errors() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=0)
    tray.engine.turn_off = MagicMock(side_effect=RuntimeError("boom"))

    with patch.object(config_polling.time, "monotonic", return_value=100.0):
        new_last, warn_at = _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )

    assert isinstance(new_last, ConfigApplyState)
    assert tray.is_off is True
    assert warn_at == 100.0
    tray._log_exception.assert_any_call("Failed to turn off engine: %s", ANY)


def test_apply_from_config_once_propagates_unexpected_turn_off_error() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=0)
    tray.engine.turn_off = MagicMock(side_effect=AssertionError("unexpected turn-off bug"))

    with pytest.raises(AssertionError, match="unexpected turn-off bug"):
        _apply_from_config_once(
            tray,
            ite_num_rows=6,
            ite_num_cols=21,
            cause="mtime_change",
            last_applied=None,
            last_apply_warn_at=0.0,
        )


def test_apply_from_config_once_sets_last_brightness_when_positive() -> None:
    tray = _mk_tray_base(effect="rainbow_wave", brightness=12)

    _apply_from_config_once(
        tray,
        ite_num_rows=6,
        ite_num_cols=21,
        cause="mtime_change",
        last_applied=None,
        last_apply_warn_at=0.0,
    )

    assert tray._last_brightness == 12
    assert tray.tray_idle_power_state.last_brightness == 12
