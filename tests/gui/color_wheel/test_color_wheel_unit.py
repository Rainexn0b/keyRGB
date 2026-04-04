from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.gui.widgets.color_wheel.color_wheel as color_wheel_module
from src.gui.widgets.color_wheel.color_wheel import ColorWheel


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


def test_render_initial_draws_wheel_updates_selection_and_marks_ready() -> None:
    wheel = _make_wheel()
    wheel._wheel_ready = False
    calls: list[str] = []
    wheel._draw_wheel = lambda: calls.append("draw")
    wheel._update_selection = lambda: calls.append("select")

    wheel._render_initial()

    assert calls == ["draw", "select"]
    assert wheel._wheel_ready is True


def test_invoke_callback_delegates_to_shared_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def fake_invoke_callback(cb, *args: object, **kwargs: object) -> None:
        calls.append((cb, args, dict(kwargs)))

    monkeypatch.setattr(color_wheel_module, "invoke_callback", fake_invoke_callback)

    wheel._invoke_callback("cb", 1, 2, 3, source="manual")

    assert calls == [("cb", (1, 2, 3), {"source": "manual"})]


def test_resolve_theme_bg_hex_prefers_ttk_style(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()

    class _FakeStyle:
        def lookup(self, name: str, _option: str) -> str:
            if name == "TFrame":
                return "#112233"
            return ""

    monkeypatch.setattr(color_wheel_module.ttk, "Style", lambda: _FakeStyle())

    assert wheel._resolve_theme_bg_hex() == "#112233"


def test_resolve_theme_bg_hex_falls_back_to_widget_background(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()

    def raise_style() -> object:
        raise RuntimeError("no style")

    monkeypatch.setattr(color_wheel_module.ttk, "Style", raise_style)
    wheel.cget = lambda _name: "#445566"

    assert wheel._resolve_theme_bg_hex() == "#445566"


def test_resolve_theme_bg_hex_uses_default_when_other_lookups_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()

    def raise_style() -> object:
        raise RuntimeError("no style")

    monkeypatch.setattr(color_wheel_module.ttk, "Style", raise_style)

    def raise_cget(_name: str) -> str:
        raise RuntimeError("no bg")

    wheel.cget = raise_cget

    assert wheel._resolve_theme_bg_hex() == "#2b2b2b"


def test_resolve_theme_bg_hex_uses_default_when_tk_lookups_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()

    def raise_style() -> object:
        raise color_wheel_module.tk.TclError("theme unavailable")

    def raise_cget(_name: str) -> str:
        raise color_wheel_module.tk.TclError("background unavailable")

    monkeypatch.setattr(color_wheel_module.ttk, "Style", raise_style)
    wheel.cget = raise_cget

    assert wheel._resolve_theme_bg_hex() == "#2b2b2b"


def test_draw_wheel_uses_existing_cache_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wheel = _make_wheel()
    wheel.canvas = _FakeCanvas()
    wheel._theme_bg_rgb = (9, 8, 7)
    wheel._theme_border_hex = "#123456"
    cache_file = tmp_path / "wheel.ppm"
    cache_file.write_bytes(b"P6\n2 2\n255\n" + bytes(16))

    monkeypatch.setattr(color_wheel_module, "wheel_cache_path", lambda **_kwargs: cache_file)
    monkeypatch.setattr(
        color_wheel_module, "build_wheel_ppm_bytes", lambda **_kwargs: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(
        color_wheel_module, "write_bytes_atomic", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())
    )
    monkeypatch.setattr(color_wheel_module.tk, "PhotoImage", lambda *, file: {"file": file})

    wheel._draw_wheel()

    assert wheel.canvas.delete_calls == ["wheel"]
    assert wheel._wheel_image == {"file": str(cache_file)}
    assert wheel.canvas.image_calls == [((0, 0), {"anchor": "nw", "image": wheel._wheel_image, "tags": "wheel"})]
    assert wheel.canvas.oval_calls[0][1]["outline"] == "#123456"


def test_draw_wheel_falls_back_to_temp_file_when_cache_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wheel = _make_wheel()
    wheel.canvas = _FakeCanvas()
    ppm_bytes = b"P6\n1 1\n255\n\x00\x00\x00"
    cache_file = tmp_path / "missing-wheel.ppm"
    unlinked: list[str] = []
    original_unlink = os.unlink

    monkeypatch.setattr(color_wheel_module, "wheel_cache_path", lambda **_kwargs: cache_file)
    monkeypatch.setattr(color_wheel_module, "build_wheel_ppm_bytes", lambda **_kwargs: ppm_bytes)

    def raise_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(color_wheel_module, "write_bytes_atomic", raise_write)
    monkeypatch.setattr(color_wheel_module.tk, "PhotoImage", lambda *, file: {"file": file})

    def tracked_unlink(path: str) -> None:
        unlinked.append(path)
        if os.path.exists(path):
            original_unlink(path)

    monkeypatch.setattr(color_wheel_module.os, "unlink", tracked_unlink)

    wheel._draw_wheel()

    assert wheel._wheel_image is not None
    assert unlinked
    assert not os.path.exists(unlinked[0])
    assert wheel.canvas.image_calls


def test_draw_wheel_ignores_temp_file_cleanup_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wheel = _make_wheel()
    wheel.canvas = _FakeCanvas()
    ppm_bytes = b"P6\n1 1\n255\n\x00\x00\x00"
    cache_file = tmp_path / "missing-wheel.ppm"
    unlinked: list[str] = []
    original_unlink = os.unlink

    monkeypatch.setattr(color_wheel_module, "wheel_cache_path", lambda **_kwargs: cache_file)
    monkeypatch.setattr(color_wheel_module, "build_wheel_ppm_bytes", lambda **_kwargs: ppm_bytes)

    def raise_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(color_wheel_module, "write_bytes_atomic", raise_write)
    monkeypatch.setattr(color_wheel_module.tk, "PhotoImage", lambda *, file: {"file": file})

    def raise_unlink(path: str) -> None:
        unlinked.append(path)
        raise PermissionError("busy")

    monkeypatch.setattr(color_wheel_module.os, "unlink", raise_unlink)

    try:
        wheel._draw_wheel()
    finally:
        for path in unlinked:
            if os.path.exists(path):
                original_unlink(path)

    assert wheel._wheel_image is not None
    assert unlinked
    assert wheel.canvas.image_calls


def test_update_selection_draws_double_outline_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.canvas = _FakeCanvas()
    wheel._update_selection = ColorWheel._update_selection.__get__(wheel, ColorWheel)
    monkeypatch.setattr(color_wheel_module, "hsv_to_xy", lambda *_args: (20.0, 30.0))

    wheel._update_selection()

    assert wheel.canvas.delete_calls == ["selector"]
    assert len(wheel.canvas.oval_calls) == 2
    assert wheel.canvas.oval_calls[0][1]["outline"] == "white"
    assert wheel.canvas.oval_calls[1][1]["outline"] == "black"


@pytest.mark.parametrize("method_name", ["_on_click", "_on_drag"])
def test_pointer_handlers_gate_on_wheel_ready(method_name: str) -> None:
    wheel = _make_wheel()
    calls: list[tuple[int, int]] = []
    wheel._select_color_at = lambda x, y: calls.append((x, y))
    wheel._wheel_ready = False

    getattr(wheel, method_name)(_event(x=3, y=4))
    assert calls == []

    wheel._wheel_ready = True
    getattr(wheel, method_name)(_event(x=3, y=4))
    assert calls == [(3, 4)]


def test_on_release_invokes_release_callback_with_brightness_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.current_color = (7, 8, 9)
    wheel.current_value = 0.42
    wheel.release_callback = object()
    calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def fake_invoke_callback(cb, *args: object, **kwargs: object) -> None:
        calls.append((cb, args, dict(kwargs)))

    monkeypatch.setattr(color_wheel_module, "invoke_callback", fake_invoke_callback)

    wheel._on_release(_event())

    assert calls == [
        (
            wheel.release_callback,
            (7, 8, 9),
            {"source": "wheel_release", "brightness_percent": 42.0},
        )
    ]


def test_select_color_at_ignores_points_outside_wheel() -> None:
    wheel = _make_wheel()
    calls: list[str] = []
    wheel._update_color = lambda *, source: calls.append(source)
    old_hue = wheel.current_hue
    old_sat = wheel.current_saturation

    original_xy_to_hsv = color_wheel_module.xy_to_hsv
    color_wheel_module.xy_to_hsv = lambda *_args: None
    try:
        wheel._select_color_at(99, 88)
    finally:
        color_wheel_module.xy_to_hsv = original_xy_to_hsv

    assert calls == []
    assert wheel.current_hue == old_hue
    assert wheel.current_saturation == old_sat


def test_select_color_at_center_preserves_hue_and_clears_saturation(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    wheel.current_hue = 0.33
    calls: list[str] = []
    wheel._update_color = lambda *, source: calls.append(source)
    monkeypatch.setattr(color_wheel_module, "xy_to_hsv", lambda *_args: (None, 0.0))

    wheel._select_color_at(1, 2)

    assert wheel.current_hue == 0.33
    assert wheel.current_saturation == 0
    assert calls == ["wheel"]


def test_select_color_at_updates_hue_and_saturation(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel = _make_wheel()
    calls: list[str] = []
    wheel._update_color = lambda *, source: calls.append(source)
    monkeypatch.setattr(color_wheel_module, "xy_to_hsv", lambda *_args: (0.75, 0.9))

    wheel._select_color_at(5, 6)

    assert wheel.current_hue == 0.75
    assert wheel.current_saturation == 0.9
    assert calls == ["wheel"]


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
