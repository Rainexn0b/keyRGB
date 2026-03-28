from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.tray.pollers.config_polling import (
    ConfigApplyState,
    _compute_config_apply_state,
    _maybe_apply_fast_path,
    _state_for_log,
)


def test_compute_config_apply_state_perkey_sig_handles_unorderable_items() -> None:
    tray = MagicMock()
    tray.config = SimpleNamespace(
        effect="perkey",
        per_key_colors={1: (1, 2, 3), "x": (4, 5, 6)},
        speed=1,
        brightness=2,
        color=(7, 8, 9),
        reactive_use_manual_color=False,
        reactive_color=(10, 20, 30),
    )

    state = _compute_config_apply_state(tray)
    assert state.effect == "perkey"
    assert state.perkey_sig is None


def test_compute_config_apply_state_handles_property_exceptions() -> None:
    class _Cfg:
        effect = "rainbow_wave"
        speed = 1
        brightness = 2
        per_key_colors = {}

        @property
        def reactive_use_manual_color(self):
            raise RuntimeError("boom")

        @property
        def reactive_color(self):
            raise RuntimeError("boom")

        @property
        def color(self):
            raise RuntimeError("boom")

    tray = MagicMock()
    tray.config = _Cfg()

    state = _compute_config_apply_state(tray)
    assert state.reactive_use_manual is False
    assert state.reactive_color == (255, 255, 255)
    assert state.color == (255, 255, 255)


def test_state_for_log_returns_none_on_unexpected_state_shape() -> None:
    class _BadIterable:
        def __iter__(self):
            raise RuntimeError("boom")

    bad = ConfigApplyState(
        effect="x",
        speed=1,
        brightness=2,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(1, 2, 3),
    )

    object.__setattr__(bad, "color", _BadIterable())

    assert _state_for_log(bad) is None


def test_maybe_apply_fast_path_handles_shape_errors_gracefully() -> None:
    tray = MagicMock()
    tray.engine = MagicMock()

    last_applied = object()
    current = ConfigApplyState(
        effect="rainbow_wave",
        speed=4,
        brightness=25,
        color=(1, 2, 3),
        perkey_sig=None,
        reactive_use_manual=False,
        reactive_color=(10, 20, 30),
    )

    handled, new_last = _maybe_apply_fast_path(tray, last_applied=last_applied, current=current)
    assert handled is False
    assert new_last == current