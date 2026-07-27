"""Direct unit coverage for reactive color window pure state helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from src.gui.windows import _reactive_color_state as state


class _TkError(Exception):
    pass


class _Var:
    def __init__(self, value: object = 0) -> None:
        self.value = value
        self.sets: list[object] = []

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.sets.append(value)
        self.value = value


class _Label:
    def __init__(self, *, fail: bool = False) -> None:
        self.text: str | None = None
        self.fail = fail

    def config(self, **kwargs: object) -> None:
        if self.fail:
            raise _TkError("gone")
        self.text = str(kwargs.get("text"))


class _Wheel:
    def __init__(self, *, fail: bool = False) -> None:
        self.percent: int | None = None
        self.fail = fail

    def set_brightness_percent(self, percent: int) -> None:
        if self.fail:
            raise _TkError("gone")
        self.percent = percent


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.reactive_color_state")


def test_read_reactive_brightness_percent_converts_and_clamps(logger: logging.Logger) -> None:
    assert state.read_reactive_brightness_percent(SimpleNamespace(reactive_brightness=25), logger=logger) == 50
    assert state.read_reactive_brightness_percent(SimpleNamespace(reactive_brightness=0), logger=logger) == 0
    assert state.read_reactive_brightness_percent(SimpleNamespace(reactive_brightness=60), logger=logger) == 100
    # falls back to brightness when reactive_brightness missing
    assert state.read_reactive_brightness_percent(SimpleNamespace(brightness=10), logger=logger) == 20


def test_read_reactive_brightness_percent_invalid(logger: logging.Logger) -> None:
    assert state.read_reactive_brightness_percent(SimpleNamespace(reactive_brightness="x"), logger=logger) is None


def test_sync_reactive_brightness_widgets_handles_none_and_errors(logger: logging.Logger) -> None:
    var = _Var()
    label = _Label()
    state.sync_reactive_brightness_widgets(var, label, percent=None, tk_error=_TkError, logger=logger)
    assert var.sets == []

    state.sync_reactive_brightness_widgets(var, label, percent=40, tk_error=_TkError, logger=logger)
    assert var.sets == [40.0]
    assert label.text == "40%"

    failing = _Label(fail=True)
    state.sync_reactive_brightness_widgets(var, failing, percent=10, tk_error=_TkError, logger=logger)


def test_sync_color_wheel_brightness_gates(logger: logging.Logger) -> None:
    wheel = _Wheel()
    manual = _Var(False)

    state.sync_color_wheel_brightness(None, manual, percent=50, tk_error=_TkError, logger=logger)
    state.sync_color_wheel_brightness(wheel, _Var(True), percent=50, tk_error=_TkError, logger=logger)
    assert wheel.percent is None

    state.sync_color_wheel_brightness(wheel, manual, percent=None, tk_error=_TkError, logger=logger)
    assert wheel.percent is None

    state.sync_color_wheel_brightness(wheel, manual, percent=33, tk_error=_TkError, logger=logger)
    assert wheel.percent == 33

    state.sync_color_wheel_brightness(_Wheel(fail=True), manual, percent=10, tk_error=_TkError, logger=logger)


def test_commit_color_to_config_success_and_failure(logger: logging.Logger) -> None:
    config = SimpleNamespace()
    use_manual = _Var(False)
    state.commit_color_to_config(config, use_manual, (1, 2, 3), tk_error=_TkError, logger=logger)
    assert config.reactive_use_manual_color is True
    assert use_manual.value is True
    assert config.reactive_color == (1, 2, 3)

    class _Bad:
        def __setattr__(self, name: str, value: Any) -> None:
            raise RuntimeError("nope")

    state.commit_color_to_config(_Bad(), use_manual, (9, 9, 9), tk_error=_TkError, logger=logger)


def test_commit_brightness_to_config_clamps_and_handles_errors(logger: logging.Logger) -> None:
    assert state.commit_brightness_to_config(SimpleNamespace(), None, logger=logger) is None
    assert state.commit_brightness_to_config(SimpleNamespace(), "bad", logger=logger) is None  # type: ignore[arg-type]

    config = SimpleNamespace()
    assert state.commit_brightness_to_config(config, 50.0, logger=logger) == 25
    assert config.reactive_brightness == 25
    assert state.commit_brightness_to_config(config, -10.0, logger=logger) == 0
    assert state.commit_brightness_to_config(config, 200.0, logger=logger) == 50

    class _Bad:
        def __setattr__(self, name: str, value: Any) -> None:
            raise OSError("disk")

    assert state.commit_brightness_to_config(_Bad(), 40.0, logger=logger) is None


def test_read_and_commit_trail_percent(logger: logging.Logger) -> None:
    assert state.read_reactive_trail_percent(SimpleNamespace(reactive_trail_percent=75), logger=logger) == 75
    assert state.read_reactive_trail_percent(SimpleNamespace(), logger=logger) == 40
    # Falsy persisted values fall back to the default trail percent.
    assert state.read_reactive_trail_percent(SimpleNamespace(reactive_trail_percent=0), logger=logger) == 40
    assert state.read_reactive_trail_percent(SimpleNamespace(reactive_trail_percent=200), logger=logger) == 100
    assert state.read_reactive_trail_percent(SimpleNamespace(reactive_trail_percent="x"), logger=logger) is None

    var = _Var()
    label = _Label()
    state.sync_reactive_trail_widgets(var, label, percent=None, tk_error=_TkError, logger=logger)
    state.sync_reactive_trail_widgets(var, label, percent=55, tk_error=_TkError, logger=logger)
    assert var.value == 55.0
    assert label.text == "55%"
    state.sync_reactive_trail_widgets(var, _Label(fail=True), percent=10, tk_error=_TkError, logger=logger)

    assert state.commit_trail_to_config(SimpleNamespace(), None, logger=logger) is None
    assert state.commit_trail_to_config(SimpleNamespace(), object(), logger=logger) is None  # type: ignore[arg-type]

    config = SimpleNamespace()
    assert state.commit_trail_to_config(config, 66.4, logger=logger) == 66
    assert config.reactive_trail_percent == 66
    assert state.commit_trail_to_config(config, 0.0, logger=logger) == 1
    assert state.commit_trail_to_config(config, 150.0, logger=logger) == 100

    class _Bad:
        def __setattr__(self, name: str, value: Any) -> None:
            raise ValueError("bad")

    assert state.commit_trail_to_config(_Bad(), 40.0, logger=logger) is None
