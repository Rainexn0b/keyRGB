from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.widgets.color_wheel._color_wheel_ui as color_wheel_ui
from src.gui.widgets.color_wheel._color_wheel_ui import _ColorWheelUIMixin


class _FakeCanvas:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.delete_calls: list[object] = []
        self.rectangle_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []

    def delete(self, tag: object) -> None:
        self.delete_calls.append(tag)

    def create_rectangle(self, *args: object, **kwargs: object) -> None:
        self.rectangle_calls.append((args, dict(kwargs)))

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))


class _FakeConfigurable:
    def __init__(self, parent=None, *, config_error: Exception | None = None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.config_error = config_error
        self.options: dict[str, object] = {}
        self.config_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []

    def config(self, **kwargs: object) -> None:
        self.config_calls.append(dict(kwargs))
        if self.config_error is not None:
            raise self.config_error
        self.options.update(kwargs)

    def configure(self, **kwargs: object) -> None:
        self.config(**kwargs)

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))


class _FakeVar:
    def __init__(self, value: object) -> None:
        self.value = value
        self.set_calls: list[object] = []

    def get(self) -> object:
        return self.value

    def set(self, value: object) -> None:
        self.set_calls.append(value)
        self.value = value


class _ColorWheelHarness(_ColorWheelUIMixin):
    def __init__(
        self,
        *,
        current_color: tuple[int, int, int] = (1, 2, 3),
        current_value: float = 0.5,
        callback=None,
        release_callback=None,
    ) -> None:
        self.current_color = current_color
        self.current_value = current_value
        self.callback = callback
        self.release_callback = release_callback
        self.preview_canvas = _FakeCanvas()
        self.rgb_label = _FakeConfigurable()
        self.rgb_r_var = _FakeVar("stale-r")
        self.rgb_g_var = _FakeVar("stale-g")
        self.rgb_b_var = _FakeVar("stale-b")
        self._rgb_entry_syncing = False
        self._brightness_label_text = "Initial:"
        self.set_color_calls: list[tuple[int, int, int]] = []
        self.invoke_callback_calls: list[tuple[object, tuple[int, int, int], dict[str, object]]] = []
        self.size = 180
        self.show_brightness_slider = True
        self.show_rgb_label = True
        self._theme_bg_hex = "#101010"
        self._theme_border_hex = "#202020"
        self.update_preview_calls = 0

    def set_color(self, r: int, g: int, b: int) -> None:
        self.set_color_calls.append((r, g, b))
        self.current_color = (r, g, b)

    def _invoke_callback(self, cb, r: int, g: int, b: int, **kwargs: object) -> None:
        self.invoke_callback_calls.append((cb, (r, g, b), dict(kwargs)))
        cb(r, g, b, **kwargs)

    def _on_click(self, _event=None) -> None:
        pass

    def _on_drag(self, _event=None) -> None:
        pass

    def _on_release(self, _event=None) -> None:
        pass

    def _on_brightness_change(self, _value=None) -> None:
        pass

    def _update_preview(self) -> None:
        self.update_preview_calls += 1


def test_create_widgets_builds_slider_preview_and_manual_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    frames: list[_FakeConfigurable] = []
    labels: list[_FakeConfigurable] = []
    scales: list[_FakeConfigurable] = []
    entries: list[_FakeConfigurable] = []
    buttons: list[_FakeConfigurable] = []
    canvases: list[_FakeCanvas] = []
    double_vars: list[_FakeVar] = []
    string_vars: list[_FakeVar] = []

    monkeypatch.setattr(
        color_wheel_ui,
        "tk",
        SimpleNamespace(
            Canvas=lambda parent=None, **kwargs: canvases.append(_FakeCanvas(parent, **kwargs)) or canvases[-1],
            DoubleVar=lambda value=0: double_vars.append(_FakeVar(value)) or double_vars[-1],
            StringVar=lambda value="": string_vars.append(_FakeVar(value)) or string_vars[-1],
        ),
    )
    monkeypatch.setattr(
        color_wheel_ui,
        "ttk",
        SimpleNamespace(
            Frame=lambda parent=None, **kwargs: frames.append(_FakeConfigurable(parent, **kwargs)) or frames[-1],
            Label=lambda parent=None, **kwargs: labels.append(_FakeConfigurable(parent, **kwargs)) or labels[-1],
            Scale=lambda parent=None, **kwargs: scales.append(_FakeConfigurable(parent, **kwargs)) or scales[-1],
            Entry=lambda parent=None, **kwargs: entries.append(_FakeConfigurable(parent, **kwargs)) or entries[-1],
            Button=lambda parent=None, **kwargs: buttons.append(_FakeConfigurable(parent, **kwargs)) or buttons[-1],
        ),
    )

    wheel = _ColorWheelHarness(current_color=(4, 5, 6), current_value=0.25)

    _ColorWheelUIMixin._create_widgets(wheel)

    assert len(canvases) == 2
    assert wheel.canvas.kwargs["width"] == 180
    assert wheel.canvas.kwargs["bg"] == "#101010"
    assert [event for event, _ in wheel.canvas.bind_calls] == ["<Button-1>", "<B1-Motion>", "<ButtonRelease-1>"]
    assert len(double_vars) == 1
    assert double_vars[0].value == 25.0
    assert wheel.brightness_title_label.kwargs["text"] == "Initial:"
    assert wheel.brightness_slider.kwargs["variable"] is double_vars[0]
    assert wheel.brightness_slider.kwargs["command"] == wheel._on_brightness_change
    assert wheel.brightness_label.kwargs["text"] == "25%"
    assert wheel.brightness_label.options["width"] == 5
    assert wheel.preview_canvas.kwargs["highlightbackground"] == "#202020"
    assert wheel.rgb_label.kwargs["width"] == 16
    assert [var.value for var in string_vars] == ["4", "5", "6"]
    assert wheel.rgb_r_entry.kwargs["textvariable"] is wheel.rgb_r_var
    assert wheel.rgb_g_entry.kwargs["textvariable"] is wheel.rgb_g_var
    assert wheel.rgb_b_entry.kwargs["textvariable"] is wheel.rgb_b_var
    assert [event for event, _ in wheel.rgb_r_entry.bind_calls] == ["<Return>"]
    assert [event for event, _ in wheel.rgb_g_entry.bind_calls] == ["<Return>"]
    assert [event for event, _ in wheel.rgb_b_entry.bind_calls] == ["<Return>"]
    assert buttons[0].kwargs["text"] == "Set"
    assert buttons[0].kwargs["command"] == wheel._on_manual_rgb_set
    assert wheel.update_preview_calls == 1


def test_create_widgets_skips_slider_and_rgb_label_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    canvases: list[_FakeCanvas] = []
    monkeypatch.setattr(
        color_wheel_ui,
        "tk",
        SimpleNamespace(
            Canvas=lambda parent=None, **kwargs: canvases.append(_FakeCanvas(parent, **kwargs)) or canvases[-1],
            DoubleVar=lambda value=0: _FakeVar(value),
            StringVar=lambda value="": _FakeVar(value),
        ),
    )
    monkeypatch.setattr(
        color_wheel_ui,
        "ttk",
        SimpleNamespace(
            Frame=lambda parent=None, **kwargs: _FakeConfigurable(parent, **kwargs),
            Label=lambda parent=None, **kwargs: _FakeConfigurable(parent, **kwargs),
            Scale=lambda parent=None, **kwargs: _FakeConfigurable(parent, **kwargs),
            Entry=lambda parent=None, **kwargs: _FakeConfigurable(parent, **kwargs),
            Button=lambda parent=None, **kwargs: _FakeConfigurable(parent, **kwargs),
        ),
    )

    wheel = _ColorWheelHarness()
    wheel.show_brightness_slider = False
    wheel.show_rgb_label = False
    wheel._theme_bg_hex = None
    wheel._theme_border_hex = None

    _ColorWheelUIMixin._create_widgets(wheel)

    assert len(canvases) == 2
    assert wheel.canvas.kwargs["bg"] == "#2b2b2b"
    assert wheel.preview_canvas.kwargs["highlightbackground"] == "#666666"
    assert not hasattr(wheel, "brightness_slider")
    assert wheel.rgb_label is None
    assert wheel.update_preview_calls == 1


def test_set_brightness_label_text_updates_existing_label() -> None:
    wheel = _ColorWheelHarness()
    wheel.brightness_title_label = _FakeConfigurable()

    wheel.set_brightness_label_text("Value:")

    assert wheel._brightness_label_text == "Value:"
    assert wheel.brightness_title_label.config_calls == [{"text": "Value:"}]
    assert wheel.brightness_title_label.options["text"] == "Value:"


@pytest.mark.parametrize("raw_text", ["", None])
def test_set_brightness_label_text_falls_back_and_swallows_label_errors(raw_text: str | None) -> None:
    wheel = _ColorWheelHarness()
    wheel.brightness_title_label = _FakeConfigurable(config_error=RuntimeError("boom"))

    wheel.set_brightness_label_text(raw_text)

    assert wheel._brightness_label_text == "Brightness:"
    assert wheel.brightness_title_label.config_calls == [{"text": "Brightness:"}]


def test_update_preview_refreshes_canvas_label_and_manual_vars() -> None:
    wheel = _ColorWheelHarness(current_color=(12, 34, 56))

    _ColorWheelUIMixin._update_preview(wheel)

    assert wheel.preview_canvas.delete_calls == ["all"]
    assert wheel.preview_canvas.rectangle_calls == [
        ((0, 0, 200, 30), {"fill": "#0c2238", "outline": ""})
    ]
    assert wheel.rgb_label.config_calls == [{"text": "RGB(12,34,56)"}]
    assert wheel.rgb_r_var.value == "12"
    assert wheel.rgb_g_var.value == "34"
    assert wheel.rgb_b_var.value == "56"
    assert wheel.rgb_r_var.set_calls == ["12"]
    assert wheel.rgb_g_var.set_calls == ["34"]
    assert wheel.rgb_b_var.set_calls == ["56"]
    assert wheel._rgb_entry_syncing is False


def test_update_preview_respects_rgb_entry_sync_guard() -> None:
    wheel = _ColorWheelHarness(current_color=(7, 8, 9))
    wheel._rgb_entry_syncing = True

    _ColorWheelUIMixin._update_preview(wheel)

    assert wheel.preview_canvas.delete_calls == ["all"]
    assert wheel.preview_canvas.rectangle_calls == [
        ((0, 0, 200, 30), {"fill": "#070809", "outline": ""})
    ]
    assert wheel.rgb_label.config_calls == [{"text": "RGB(7,8,9)"}]
    assert wheel.rgb_r_var.value == "stale-r"
    assert wheel.rgb_g_var.value == "stale-g"
    assert wheel.rgb_b_var.value == "stale-b"
    assert wheel.rgb_r_var.set_calls == []
    assert wheel.rgb_g_var.set_calls == []
    assert wheel.rgb_b_var.set_calls == []
    assert wheel._rgb_entry_syncing is True


def test_on_manual_rgb_set_parses_clamps_and_notifies_callbacks() -> None:
    callback_calls: list[tuple[tuple[int, int, int], dict[str, object]]] = []
    release_calls: list[tuple[tuple[int, int, int], dict[str, object]]] = []

    def callback(r: int, g: int, b: int, **kwargs: object) -> None:
        callback_calls.append(((r, g, b), dict(kwargs)))

    def release_callback(r: int, g: int, b: int, **kwargs: object) -> None:
        release_calls.append(((r, g, b), dict(kwargs)))

    wheel = _ColorWheelHarness(current_value=0.42, callback=callback, release_callback=release_callback)
    wheel.rgb_r_var = _FakeVar(" 300 ")
    wheel.rgb_g_var = _FakeVar(" -2 ")
    wheel.rgb_b_var = _FakeVar("oops")

    wheel._on_manual_rgb_set()

    expected_kwargs = {"source": "manual", "brightness_percent": 42.0}

    assert wheel.set_color_calls == [(255, 0, 0)]
    assert wheel.invoke_callback_calls == [
        (callback, (255, 0, 0), expected_kwargs),
        (release_callback, (255, 0, 0), expected_kwargs),
    ]
    assert callback_calls == [((255, 0, 0), expected_kwargs)]
    assert release_calls == [((255, 0, 0), expected_kwargs)]


def test_on_manual_rgb_set_accepts_trimmed_numbers_before_clamping() -> None:
    wheel = _ColorWheelHarness(current_value=0.375)
    wheel.rgb_r_var = _FakeVar(" 5 ")
    wheel.rgb_g_var = _FakeVar("260")
    wheel.rgb_b_var = _FakeVar(" 17\n")

    wheel._on_manual_rgb_set()

    assert wheel.set_color_calls == [(5, 255, 17)]
    assert wheel.invoke_callback_calls == []