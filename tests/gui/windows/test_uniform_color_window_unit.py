from __future__ import annotations

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
