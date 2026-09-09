"""Focused UX-08 coverage for color-wheel manual RGB key entry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.widgets.color_wheel._color_wheel_ui as color_wheel_ui
from keyrgb.gui.widgets.color_wheel._color_wheel_ui import _ColorWheelUIMixin


class _FakeCanvas:
    def __init__(self, parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.bind_calls: list[tuple[str, object]] = []

    def delete(self, tag: object) -> None:
        pass

    def create_rectangle(self, *args: object, **kwargs: object) -> None:
        pass

    def pack(self, **kwargs: object) -> None:
        pass

    def grid(self, **kwargs: object) -> None:
        pass

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.options: dict[str, object] = {}
        self.bind_calls: list[tuple[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def config(self, **kwargs: object) -> None:
        self.options.update(kwargs)

    def configure(self, **kwargs: object) -> None:
        self.config(**kwargs)

    def pack(self, **kwargs: object) -> None:
        pass

    def grid(self, **kwargs: object) -> None:
        pass

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))


class _FakeVar:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.value = value


class _Harness(_ColorWheelUIMixin):
    def __init__(self) -> None:
        self.current_color = (1, 2, 3)
        self.current_value = 0.5
        self.callback = None
        self.release_callback = None
        self.preview_canvas = _FakeCanvas()
        self.rgb_label = _FakeWidget()
        self.rgb_r_var = _FakeVar("1")
        self.rgb_g_var = _FakeVar("2")
        self.rgb_b_var = _FakeVar("3")
        self._rgb_entry_syncing = False
        self._brightness_label_text = "Brightness:"
        self.size = 180
        self.show_brightness_slider = True
        self.show_rgb_label = True
        self._theme_bg_hex = "#101010"
        self._theme_border_hex = "#202020"
        self.set_calls: list[tuple[int, int, int]] = []

    def set_color(self, r: int, g: int, b: int) -> None:
        self.set_calls.append((r, g, b))
        self.current_color = (r, g, b)

    def _invoke_callback(self, cb, r: int, g: int, b: int, **kwargs: object) -> None:
        pass

    def _on_click(self, _event=None) -> None:
        pass

    def _on_drag(self, _event=None) -> None:
        pass

    def _on_release(self, _event=None) -> None:
        pass

    def _on_brightness_change(self, _value=None) -> None:
        pass

    def _update_preview(self) -> None:
        pass


def _build_wheel(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    monkeypatch.setattr(
        color_wheel_ui,
        "tk",
        SimpleNamespace(
            Canvas=lambda parent=None, **kwargs: _FakeCanvas(parent, **kwargs),
            DoubleVar=lambda value=0: _FakeVar(value),
            StringVar=lambda value="": _FakeVar(value),
        ),
    )
    monkeypatch.setattr(
        color_wheel_ui,
        "ttk",
        SimpleNamespace(
            Frame=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Label=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Scale=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Entry=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
            Button=lambda parent=None, **kwargs: _FakeWidget(parent, **kwargs),
        ),
    )
    wheel = _Harness()
    _ColorWheelUIMixin._create_widgets(wheel)
    return wheel


def test_manual_entries_bind_return_and_kp_enter_to_same_route(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _build_wheel(monkeypatch)

    for entry in (wheel.rgb_r_entry, wheel.rgb_g_entry, wheel.rgb_b_entry):
        sequences = [sequence for sequence, _ in entry.bind_calls]
        assert sequences == ["<Return>", "<KP_Enter>"]


def test_return_and_kp_enter_handlers_invoke_manual_set(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _build_wheel(monkeypatch)
    calls: list[str] = []
    wheel._on_manual_rgb_set = lambda: calls.append("set")  # type: ignore[method-assign]

    # Rebuild is not needed: existing bound lambdas close over the method
    # lookup at call time, so invoke each bound handler.
    for entry in (wheel.rgb_r_entry, wheel.rgb_g_entry, wheel.rgb_b_entry):
        for _sequence, handler in entry.bind_calls:
            handler(None)

    assert calls == ["set"] * 6


def test_manual_entries_have_no_native_navigation_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _build_wheel(monkeypatch)

    for entry in (wheel.rgb_r_entry, wheel.rgb_g_entry, wheel.rgb_b_entry):
        sequences = [sequence for sequence, _ in entry.bind_calls]
        for sequence in sequences:
            assert "Tab" not in sequence
            assert "Up" not in sequence
            assert "Down" not in sequence
            assert "Left" not in sequence
            assert "Right" not in sequence
        assert set(sequences) == {"<Return>", "<KP_Enter>"}
