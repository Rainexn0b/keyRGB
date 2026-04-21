from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from src.tray.pollers.config_polling_internal.core import ConfigApplyState, compute_config_apply_state, maybe_apply_fast_path
import src.tray.pollers.config_polling_internal.core as core_module
import src.tray.pollers.config_polling_internal._post_fast_path_apply as post_fast_path_module


class _FakeTray:
    def __init__(self, config: object) -> None:
        self.config = config
        self.backend = None
        self.refresh_calls = 0

    def _refresh_ui(self) -> None:
        self.refresh_calls += 1


def _mk_state(*, brightness: int = 20, software_effect_target: str = "keyboard") -> ConfigApplyState:
    return ConfigApplyState(
        effect="static",
        speed=3,
        brightness=brightness,
        color=(10, 20, 30),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(255, 255, 255),
        reactive_brightness=0,
        reactive_trail_percent=50,
        software_effect_target=software_effect_target,
    )


def test_compute_config_apply_state_happy_path_minimal_fake_config() -> None:
    config = SimpleNamespace(
        effect="static",
        speed=5,
        brightness=42,
        color=(1, 2, 3),
        reactive_use_manual_color=True,
        reactive_color=(4, 5, 6),
        software_effect_target="Keyboard",
    )
    tray = _FakeTray(config)

    state = compute_config_apply_state(tray)

    assert state == ConfigApplyState(
        effect="static",
        speed=5,
        brightness=42,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=True,
        reactive_color=(4, 5, 6),
        reactive_brightness=0,
        reactive_trail_percent=50,
        software_effect_target="keyboard",
    )


def test_compute_config_apply_state_degenerate_values_fall_back_to_defaults() -> None:
    # None values, wrong types, and missing attributes should safely fall back.
    config = SimpleNamespace(
        effect=None,
        speed="not-a-number",
        brightness=None,
        reactive_use_manual_color=None,
        reactive_color=object(),
        color=123,
    )
    tray = _FakeTray(config)

    state = compute_config_apply_state(tray)

    assert state == ConfigApplyState(
        effect="none",
        speed=0,
        brightness=0,
        color=(255, 255, 255),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(255, 255, 255),
        reactive_brightness=0,
        reactive_trail_percent=50,
        software_effect_target="keyboard",
    )


def test_maybe_apply_fast_path_delegates_and_refreshes_when_handled(monkeypatch: Any) -> None:
    tray = _FakeTray(SimpleNamespace())
    last_applied = _mk_state(software_effect_target="keyboard")
    current = _mk_state(software_effect_target="mouse")
    captured: dict[str, Any] = {}

    def _fake_classify_fast_path_change(*, last_applied: ConfigApplyState | None, current: ConfigApplyState) -> str:
        captured["classified"] = (last_applied, current)
        return "target_only"

    def _fake_apply_fast_path_change(
        _tray: object,
        *,
        change_kind: str,
        current: ConfigApplyState,
        sw_effects_set: set[str] | frozenset[str],
    ) -> bool:
        captured["applied"] = (_tray, change_kind, current, sw_effects_set)
        return True

    monkeypatch.setattr(core_module, "classify_fast_path_change", _fake_classify_fast_path_change)
    monkeypatch.setattr(core_module, "apply_fast_path_change", _fake_apply_fast_path_change)

    handled, new_last = maybe_apply_fast_path(
        tray,
        last_applied=last_applied,
        current=current,
        sw_effects_set={"rainbow_wave"},
    )

    assert handled is True
    assert new_last == current
    assert tray.refresh_calls == 1
    assert captured["classified"] == (last_applied, current)
    assert captured["applied"] == (tray, "target_only", current, {"rainbow_wave"})


def test_maybe_apply_fast_path_delegates_and_skips_refresh_when_not_handled(monkeypatch: Any) -> None:
    tray = _FakeTray(SimpleNamespace())
    last_applied = _mk_state(software_effect_target="keyboard")
    current = _mk_state(brightness=30, software_effect_target="keyboard")
    captured: dict[str, Any] = {}

    def _fake_classify_fast_path_change(*, last_applied: ConfigApplyState | None, current: ConfigApplyState) -> str:
        captured["classified"] = (last_applied, current)
        return "none"

    def _fake_apply_fast_path_change(
        _tray: object,
        *,
        change_kind: str,
        current: ConfigApplyState,
        sw_effects_set: set[str] | frozenset[str],
    ) -> bool:
        captured["applied"] = (_tray, change_kind, current, sw_effects_set)
        return False

    monkeypatch.setattr(core_module, "classify_fast_path_change", _fake_classify_fast_path_change)
    monkeypatch.setattr(core_module, "apply_fast_path_change", _fake_apply_fast_path_change)

    handled, new_last = maybe_apply_fast_path(
        tray,
        last_applied=last_applied,
        current=current,
        sw_effects_set=frozenset({"rainbow_wave"}),
    )

    assert handled is False
    assert new_last == current
    assert tray.refresh_calls == 0
    assert captured["classified"] == (last_applied, current)
    assert captured["applied"] == (tray, "none", current, frozenset({"rainbow_wave"}))


def test_execute_non_fast_path_plan_uses_local_post_fast_path_executor(monkeypatch: Any) -> None:
    tray = SimpleNamespace(_log_event=MagicMock())
    current = SimpleNamespace(effect="none", brightness=15)
    last_applied = _mk_state(brightness=10)
    captured: dict[str, Any] = {}

    def _fake_apply_post_fast_path_execution(
        _tray: object,
        *,
        current: object,
        ite_num_rows: int,
        ite_num_cols: int,
        cause: str,
        last_apply_warn_at: float,
        monotonic_fn: object,
        is_device_disconnected_fn: object,
        sync_reactive_fn: object,
        apply_perkey_fn: object,
        apply_uniform_fn: object,
        apply_effect_fn: object,
        runtime_boundary_exceptions: tuple[type[Exception], ...],
    ) -> float:
        captured["apply"] = {
            "tray": _tray,
            "current": current,
            "ite_num_rows": ite_num_rows,
            "ite_num_cols": ite_num_cols,
            "cause": cause,
            "last_apply_warn_at": last_apply_warn_at,
            "monotonic_fn": monotonic_fn,
            "is_device_disconnected_fn": is_device_disconnected_fn,
            "sync_reactive_fn": sync_reactive_fn,
            "apply_perkey_fn": apply_perkey_fn,
            "apply_uniform_fn": apply_uniform_fn,
            "apply_effect_fn": apply_effect_fn,
            "runtime_boundary_exceptions": runtime_boundary_exceptions,
        }
        return 33.0

    monkeypatch.setattr(
        post_fast_path_module,
        "apply_post_fast_path_execution",
        _fake_apply_post_fast_path_execution,
    )

    result = post_fast_path_module.execute_non_fast_path_plan(
        tray,
        apply_plan=SimpleNamespace(execution_kind="apply"),
        current=current,
        last_applied=last_applied,
        cause="mtime_change",
        last_apply_warn_at=12.0,
        state_for_log_fn=lambda state: {"state": state},
        monotonic_fn=lambda: 99.0,
        ite_num_rows=6,
        ite_num_cols=21,
        is_device_disconnected_fn=lambda exc: False,
        apply_turn_off_fn=MagicMock(),
        sync_reactive_fn=MagicMock(),
        apply_perkey_fn=MagicMock(),
        apply_uniform_fn=MagicMock(),
        apply_effect_fn=MagicMock(),
        config_fallback_exceptions=(AttributeError,),
        runtime_boundary_exceptions=(RuntimeError,),
    )

    assert result == 33.0
    tray._log_event.assert_called_once_with(
        "config",
        "detected_change",
        cause="mtime_change",
        old={"state": last_applied},
        new={"state": current},
    )
    assert captured["apply"]["tray"] is tray
    assert captured["apply"]["current"] is current
    assert captured["apply"]["ite_num_rows"] == 6
    assert captured["apply"]["ite_num_cols"] == 21
    assert captured["apply"]["cause"] == "mtime_change"
    assert captured["apply"]["last_apply_warn_at"] == 12.0