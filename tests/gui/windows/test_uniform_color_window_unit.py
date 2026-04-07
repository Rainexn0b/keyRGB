from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.windows.uniform as uniform


def test_probe_color_support_defaults_to_true_when_backend_capability_probe_fails() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise RuntimeError("boom")

    assert gui._probe_color_support(BrokenBackend()) is True


def test_probe_color_support_propagates_unexpected_capability_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def capabilities(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._probe_color_support(BrokenBackend())


def test_select_backend_best_effort_propagates_unexpected_selection_failure(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.requested_backend = "sysfs-leds"

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    with pytest.raises(AssertionError):
        gui._select_backend_best_effort()


def test_select_backend_best_effort_uses_secondary_route_backend(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    sentinel = object()
    gui._secondary_route = SimpleNamespace(get_backend=lambda: sentinel)

    monkeypatch.setattr(uniform, "select_backend", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("boom")))

    assert gui._select_backend_best_effort() is sentinel


def test_acquire_device_best_effort_returns_none_when_device_is_busy(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    err = OSError("busy")

    class BusyBackend:
        def get_device(self):
            raise err

    monkeypatch.setattr(uniform, "is_device_busy", lambda exc: exc is err)

    assert gui._acquire_device_best_effort(BusyBackend()) is None


def test_acquire_device_best_effort_propagates_unexpected_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenBackend:
        def get_device(self):
            raise AssertionError("boom")

    with pytest.raises(AssertionError):
        gui._acquire_device_best_effort(BrokenBackend())


def test_apply_color_returns_false_for_recoverable_runtime_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise RuntimeError("boom")

    gui.kb = BrokenKeyboard()

    assert gui._apply_color(1, 2, 3, 25) is False


def test_apply_color_returns_false_for_unexpected_write_failure() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class BrokenKeyboard:
        def set_color(self, _color, *, brightness: int):
            assert brightness == 25
            raise AssertionError("boom")

    gui.kb = BrokenKeyboard()

    assert gui._apply_color(1, 2, 3, 25) is False


def test_commit_color_to_config_uses_secondary_route_state(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    calls: list[tuple[str, tuple[int, int, int], str | None]] = []

    class _Config:
        effect = "wave"

        def set_secondary_device_color(self, state_key: str, color, *, legacy_key=None, default=(255, 0, 0)):
            assert default == (255, 0, 0)
            calls.append((state_key, tuple(color), legacy_key))

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)

    gui._commit_color_to_config(4, 5, 6)

    assert calls == [("mouse", (4, 5, 6), None)]
    assert gui.config.effect == "wave"


def test_on_color_change_updates_secondary_color_without_touching_keyboard_effect() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    stored: list[tuple[int, int, int]] = []

    class _Config:
        effect = "wave"
        color = (9, 9, 9)

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)
    gui._store_secondary_color = lambda color: stored.append(tuple(color))
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = 0.0

    gui._on_color_change(7, 8, 9)

    assert stored == [(7, 8, 9)]
    assert gui.config.effect == "wave"
    assert gui.config.color == (9, 9, 9)
