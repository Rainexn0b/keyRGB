"""Direct unit coverage for reactive color interaction helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest

from src.gui.windows import _reactive_color_interactions as ix


class _TkError(Exception):
    pass


class _Var:
    def __init__(self, value: object = False) -> None:
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


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.reactive_interactions")


def test_drag_state_defaults_and_meta_source() -> None:
    assert ix._last_drag_commit_ts_or_default(object()) == 0.0
    assert ix._drag_commit_interval_or_default(object()) == 0.06
    assert ix._last_drag_committed_color_or_none(object()) is None

    gui = SimpleNamespace(_last_drag_commit_ts=1.5, _drag_commit_interval=0.1, _last_drag_committed_color=(1, 2, 3))
    assert ix._last_drag_commit_ts_or_default(gui) == 1.5
    assert ix._drag_commit_interval_or_default(gui) == 0.1
    assert ix._last_drag_committed_color_or_none(gui) == (1, 2, 3)

    assert ix._meta_source({"source": " Brightness "}) == "brightness"
    assert ix._meta_source({}) == ""


def test_toggle_manual_and_visual_mode(logger: logging.Logger) -> None:
    config = SimpleNamespace(reactive_use_manual_color=False, reactive_visual_mode="subtle")
    use_manual = _Var(True)
    gui = SimpleNamespace(_color_supported=False, _use_manual_var=use_manual, config=config)

    ix._on_toggle_manual(gui, tk_error=_TkError, logger=logger)
    assert use_manual.sets == [False]

    use_manual.value = True
    gui._color_supported = True
    ix._on_toggle_manual(gui, tk_error=_TkError, logger=logger)
    assert config.reactive_use_manual_color is True

    class _BadConfig:
        def __setattr__(self, name: str, value: Any) -> None:
            raise OSError("nope")

    gui.config = _BadConfig()
    ix._on_toggle_manual(gui, tk_error=_TkError, logger=logger)

    vivid = _Var(True)
    gui2 = SimpleNamespace(_reactive_vivid_visuals_var=vivid, config=SimpleNamespace(reactive_visual_mode="subtle"))
    ix._on_toggle_reactive_visual_mode(gui2, logger=logger)
    assert gui2.config.reactive_visual_mode == "vivid"
    vivid.value = False
    ix._on_toggle_reactive_visual_mode(gui2, logger=logger)
    assert gui2.config.reactive_visual_mode == "subtle"

    gui2.config = _BadConfig()
    ix._on_toggle_reactive_visual_mode(gui2, logger=logger)


def test_brightness_change_throttle_and_release(logger: logging.Logger) -> None:
    synced: list[int] = []
    statuses: list[tuple[str, bool]] = []
    commits: list[float] = []

    def sync_fn(wheel, use_manual, *, percent, tk_error, logger):
        synced.append(int(percent or 0))

    gui = SimpleNamespace(
        _reactive_brightness_label=_Label(),
        _reactive_brightness_var=_Var(40),
        color_wheel=object(),
        _use_manual_var=_Var(False),
        _last_drag_commit_ts=10.0,
        _drag_commit_interval=1.0,
        _last_drag_committed_brightness=None,
        _commit_brightness_to_config=lambda pct: commits.append(float(pct)) or 20,
        _set_status=lambda msg, *, ok: statuses.append((msg, ok)),
    )

    # invalid value -> 0, throttled by interval
    clock = {"t": 10.1}
    ix._on_reactive_brightness_change(
        gui,
        "bad",
        tk_error=_TkError,
        logger=logger,
        sync_color_wheel_brightness_fn=sync_fn,
        time_monotonic=lambda: clock["t"],
    )
    assert gui._reactive_brightness_label.text == "0%"
    assert commits == []  # throttled

    clock["t"] = 12.0
    ix._on_reactive_brightness_change(
        gui,
        50,
        tk_error=_TkError,
        logger=logger,
        sync_color_wheel_brightness_fn=sync_fn,
        time_monotonic=lambda: clock["t"],
    )
    assert commits == [50.0]
    assert gui._last_drag_committed_brightness == 40  # hw 20 * 2

    # release success
    statuses.clear()
    ix._on_reactive_brightness_release(
        gui,
        tk_error=_TkError,
        logger=logger,
        sync_color_wheel_brightness_fn=sync_fn,
        time_monotonic=lambda: 99.0,
    )
    assert statuses[-1][1] is True
    assert "Saved reactive brightness" in statuses[-1][0]

    # release failure
    gui._commit_brightness_to_config = lambda _pct: None
    statuses.clear()
    ix._on_reactive_brightness_release(
        gui,
        tk_error=_TkError,
        logger=logger,
        sync_color_wheel_brightness_fn=sync_fn,
        time_monotonic=lambda: 100.0,
    )
    assert statuses == [("✗ Failed to save reactive brightness", False)]


def test_trail_change_and_release() -> None:
    statuses: list[tuple[str, bool]] = []
    gui = SimpleNamespace(
        _reactive_trail_label=_Label(fail=True),
        _reactive_trail_var=_Var("bad"),
        _commit_trail_to_config=lambda pct: None,
        _set_status=lambda msg, *, ok: statuses.append((msg, ok)),
    )
    ix._on_reactive_trail_change(gui, "nope", tk_error=_TkError)
    # label failure swallowed; default pct path exercised

    gui._reactive_trail_label = _Label()
    ix._on_reactive_trail_change(gui, 77, tk_error=_TkError)
    assert gui._reactive_trail_label.text == "77%"

    ix._on_reactive_trail_release(gui, tk_error=_TkError)
    assert statuses[-1] == ("✗ Failed to save wave thickness", False)

    gui._reactive_trail_var = _Var(55)
    gui._commit_trail_to_config = lambda pct: round(float(pct))
    statuses.clear()
    ix._on_reactive_trail_release(gui, tk_error=_TkError)
    assert statuses[-1] == ("✓ Saved wave thickness 55%", True)


def test_color_change_and_release_paths() -> None:
    commits: list[tuple[int, int, int]] = []
    statuses: list[tuple[str, bool]] = []
    gui = SimpleNamespace(
        _color_supported=False,
        _last_drag_commit_ts=0.0,
        _drag_commit_interval=0.0,
        _last_drag_committed_color=None,
        _commit_color_to_config=lambda color: commits.append(color),
        _set_status=lambda msg, *, ok: statuses.append((msg, ok)),
    )

    ix._on_color_change(gui, 1, 2, 3, time_monotonic=lambda: 1.0, meta={})
    assert commits == []

    gui._color_supported = True
    ix._on_color_change(gui, 1, 2, 3, time_monotonic=lambda: 1.0, meta={"source": "brightness"})
    assert commits == []

    ix._on_color_change(gui, 4, 5, 6, time_monotonic=lambda: 1.0, meta={})
    assert commits == [(4, 5, 6)]
    assert gui._last_drag_committed_color == (4, 5, 6)

    # throttle same color
    commits.clear()
    gui._drag_commit_interval = 10.0
    gui._last_drag_commit_ts = 1.0
    ix._on_color_change(gui, 4, 5, 6, time_monotonic=lambda: 2.0, meta={})
    assert commits == []

    # release unsupported
    gui._color_supported = False
    ix._on_color_release(gui, 1, 2, 3, time_monotonic=lambda: 3.0, meta={})
    assert statuses[-1][1] is False

    gui._color_supported = True
    statuses.clear()
    commits.clear()
    ix._on_color_release(gui, 7, 8, 9, time_monotonic=lambda: 4.0, meta={"source": "brightness"})
    assert commits == []

    ix._on_color_release(gui, 7, 8, 9, time_monotonic=lambda: 5.0, meta={})
    assert commits == [(7, 8, 9)]
    assert "Saved RGB(7, 8, 9)" in statuses[-1][0]
