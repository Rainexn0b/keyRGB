from __future__ import annotations

from types import SimpleNamespace

import pytest

import keyrgb.gui.widgets.color_wheel.color_wheel as color_wheel_module
from keyrgb.gui.widgets.color_wheel.color_wheel import ColorWheel


class _FakeCanvas:
    def __init__(self) -> None:
        self.delete_calls: list[str] = []
        self.image_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.oval_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def delete(self, tag: str) -> None:
        self.delete_calls.append(tag)

    def create_image(self, *args: object, **kwargs: object) -> None:
        self.image_calls.append((args, dict(kwargs)))

    def create_oval(self, *args: object, **kwargs: object) -> None:
        self.oval_calls.append((args, dict(kwargs)))


class _FakeLabel:
    def __init__(self) -> None:
        self.config_calls: list[dict[str, object]] = []
        self.options: dict[str, object] = {}

    def config(self, **kwargs: object) -> None:
        self.config_calls.append(dict(kwargs))
        self.options.update(kwargs)


class _FakeVar:
    def __init__(self, value: float = 0.0) -> None:
        self.value = float(value)
        self.set_calls: list[float] = []

    def set(self, value: float) -> None:
        value_f = float(value)
        self.set_calls.append(value_f)
        self.value = value_f


def _make_wheel() -> ColorWheel:
    wheel = ColorWheel.__new__(ColorWheel)
    wheel.size = 100
    wheel.radius = 50
    wheel.canvas = _FakeCanvas()
    wheel.current_color = (12, 34, 56)
    wheel.current_hue = 0.25
    wheel.current_saturation = 0.5
    wheel.current_value = 0.5
    wheel.callback = None
    wheel.release_callback = None
    wheel._theme_bg_rgb = (1, 2, 3)
    wheel._theme_border_hex = "#abcdef"
    wheel._wheel_image = None
    wheel._wheel_ready = True
    wheel._suspend_brightness_events = False
    wheel.brightness_label = _FakeLabel()
    wheel.brightness_var = _FakeVar(50.0)
    wheel._update_preview = lambda: None
    wheel._update_selection = lambda: None
    wheel.cget = lambda _name: "#778899"
    return wheel


def _event(*, x: int = 10, y: int = 20) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def test_on_brightness_change_updates_state_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.release_callback = object()
    wheel.current_color = (1, 2, 3)
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []
    updates: list[str] = []
    wheel._update_color = lambda *, source: updates.append(source)

    def fake_invoke_callback(cb, *args: object, **kwargs: object) -> None:
        calls.append((cb, args, dict(kwargs)))

    monkeypatch.setattr(color_wheel_module, "invoke_callback", fake_invoke_callback)

    wheel._on_brightness_change("37.5")

    assert wheel.current_value == 0.375
    assert wheel.brightness_label.options["text"] == "37%"
    assert updates == ["brightness"]
    assert calls == [
        (
            wheel.release_callback,
            (1, 2, 3),
            {"source": "brightness", "brightness_percent": 37.5},
        )
    ]


def test_on_brightness_change_respects_suspension_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.release_callback = object()
    wheel._suspend_brightness_events = True
    wheel._update_color = lambda *, source: None

    monkeypatch.setattr(
        color_wheel_module,
        "invoke_callback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected callback")),
    )

    wheel._on_brightness_change(15)

    assert wheel.current_value == 0.15


def test_set_brightness_percent_clamps_updates_label_and_restores_guard() -> None:
    wheel = _make_wheel()
    updates: list[str] = []
    wheel._update_color = lambda *, source: updates.append(source)

    wheel.set_brightness_percent("120")

    assert wheel.brightness_var.value == 100.0
    assert wheel.current_value == 1.0
    assert wheel.brightness_label.options["text"] == "100%"
    assert updates == ["brightness"]
    assert wheel._suspend_brightness_events is False


@pytest.mark.parametrize("value", ["oops", object()])
def test_set_brightness_percent_invalid_input_coerces_to_zero(value: object) -> None:
    wheel = _make_wheel()
    updates: list[str] = []
    wheel._update_color = lambda *, source: updates.append(source)

    wheel.set_brightness_percent(value)

    assert wheel.brightness_var.value == 0.0
    assert wheel.current_value == 0.0
    assert wheel.brightness_label.options["text"] == "0%"
    assert updates == ["brightness"]
    assert wheel._suspend_brightness_events is False


def test_set_brightness_percent_without_slider_updates_value_and_visuals() -> None:
    wheel = _make_wheel()
    updates: list[str] = []
    wheel._update_color = lambda *, source: updates.append(source)
    del wheel.brightness_var
    del wheel.brightness_label

    wheel.set_brightness_percent(28)

    assert wheel.current_value == pytest.approx(0.28)
    assert updates == ["brightness"]
    assert wheel._suspend_brightness_events is False


def test_set_brightness_percent_does_not_invoke_callback_while_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.callback = object()
    wheel._update_selection = ColorWheel._update_selection.__get__(wheel, ColorWheel)
    wheel._update_preview = lambda: None
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def fake_invoke_callback(cb, *args: object, **kwargs: object) -> None:
        calls.append((cb, args, dict(kwargs)))

    monkeypatch.setattr(color_wheel_module, "invoke_callback", fake_invoke_callback)

    wheel.set_brightness_percent(28)

    assert calls == []


def test_update_color_recomputes_rgb_updates_visuals_and_invokes_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.callback = object()
    selections: list[str] = []
    previews: list[str] = []
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []
    wheel._update_selection = lambda: selections.append("selection")
    wheel._update_preview = lambda: previews.append("preview")

    def fake_invoke_callback(cb, *args: object, **kwargs: object) -> None:
        calls.append((cb, args, dict(kwargs)))

    monkeypatch.setattr(color_wheel_module, "invoke_callback", fake_invoke_callback)

    wheel.current_hue = 0.0
    wheel.current_saturation = 1.0
    wheel.current_value = 0.5
    wheel._update_color(source="manual")

    assert wheel.current_color == (127, 0, 0)
    assert selections == ["selection"]
    assert previews == ["preview"]
    assert calls == [
        (
            wheel.callback,
            (127, 0, 0),
            {"source": "manual", "brightness_percent": 50.0},
        )
    ]


def test_set_color_updates_hsv_slider_and_visuals() -> None:
    wheel = _make_wheel()
    selections: list[str] = []
    previews: list[str] = []
    wheel._update_selection = lambda: selections.append("selection")
    wheel._update_preview = lambda: previews.append("preview")

    wheel.set_color(0, 128, 255)

    assert wheel.current_color == (0, 128, 255)
    assert wheel.brightness_var.value == pytest.approx(100.0)
    assert wheel.brightness_label.options["text"] == "100%"
    assert selections == ["selection"]
    assert previews == ["preview"]
    assert wheel.get_color() == (0, 128, 255)


def test_set_color_without_slider_updates_visuals() -> None:
    wheel = _make_wheel()
    selections: list[str] = []
    previews: list[str] = []
    wheel._update_selection = lambda: selections.append("selection")
    wheel._update_preview = lambda: previews.append("preview")
    del wheel.brightness_var
    del wheel.brightness_label

    wheel.set_color(0, 128, 255)

    assert wheel.current_color == (0, 128, 255)
    assert wheel.current_value == pytest.approx(1.0)
    assert selections == ["selection"]
    assert previews == ["preview"]
    assert wheel.get_color() == (0, 128, 255)
