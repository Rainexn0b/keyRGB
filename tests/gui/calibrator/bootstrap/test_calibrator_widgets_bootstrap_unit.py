"""Unit coverage for calibrator build_widgets and finish_init."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from keyrgb.gui.calibrator import _app_bootstrap as boot
from keyrgb.gui.theme import focus as theme_focus, metrics as theme_metrics


class _Widget:
    def __init__(self, kind: str = "w", **kwargs: object) -> None:
        self.kind = kind
        self.kwargs = kwargs
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[object, ...]] = []
        self.configure_calls: list[dict[str, object]] = []
        self.column_calls: list[tuple[object, ...]] = []
        self.row_calls: list[tuple[object, ...]] = []
        self.focus_calls = 0
        self._width = 300

    def grid(self, *args: object, **kwargs: object) -> None:
        self.grid_calls.append(kwargs)

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(kwargs)

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.column_calls.append((index, weight, kwargs))

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.row_calls.append((index, weight, kwargs))

    def winfo_width(self) -> int:
        return self._width

    def focus_set(self) -> None:
        self.focus_calls += 1


class _Tk:
    def __init__(self) -> None:
        self.widgets: list[_Widget] = []
        self.bool_vars: list[object] = []

    def Canvas(self, parent: object = None, **kwargs: object) -> _Widget:
        w = _Widget("canvas", parent=parent, **kwargs)
        self.widgets.append(w)
        return w

    def BooleanVar(self, master: object = None, value: object = None, name: str | None = None) -> SimpleNamespace:
        var = SimpleNamespace(value=value, get=lambda: value)
        self.bool_vars.append(var)
        return var


class _Ttk:
    def __init__(self) -> None:
        self.widgets: list[_Widget] = []

    def Frame(self, parent: object = None, **kwargs: object) -> _Widget:
        w = _Widget("frame", parent=parent, **kwargs)
        self.widgets.append(w)
        return w

    def Label(self, parent: object = None, **kwargs: object) -> _Widget:
        w = _Widget("label", parent=parent, **kwargs)
        self.widgets.append(w)
        return w

    def Button(self, parent: object = None, **kwargs: object) -> _Widget:
        w = _Widget("button", parent=parent, **kwargs)
        self.widgets.append(w)
        return w

    def Checkbutton(self, parent: object = None, **kwargs: object) -> _Widget:
        w = _Widget("check", parent=parent, **kwargs)
        self.widgets.append(w)
        return w


class _App:
    def __init__(self) -> None:
        self.bg_color = "#101010"
        self.column_calls: list[tuple[Any, ...]] = []
        self.row_calls: list[tuple[Any, ...]] = []
        self.bind_calls: list[tuple[Any, ...]] = []
        self.after_calls: list[tuple[int, object]] = []
        self._focused: object = None
        self.destroy = MagicMock()
        self._redraw = MagicMock()
        self._on_click = MagicMock()
        self._prev = MagicMock()
        self._next = MagicMock()
        self._assign = MagicMock()
        self._skip = MagicMock()
        self._on_show_backdrop_changed = MagicMock()
        self._reset_keymap_defaults = MagicMock()
        self._save = MagicMock()
        self._save_and_close = MagicMock()
        self._on_close = MagicMock()

    def columnconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.column_calls.append((index, weight, kwargs))

    def rowconfigure(self, index: int, weight: int = 0, **kwargs: object) -> None:
        self.row_calls.append((index, weight, kwargs))

    def bind(self, sequence: str, callback: object, add: object = None) -> None:
        self.bind_calls.append((sequence, callback, add))

    def after(self, delay_ms: int, callback: object) -> None:
        self.after_calls.append((delay_ms, callback))

    def focus_get(self) -> object:
        return self._focused


def test_build_widgets_creates_canvas_controls_and_keybindings() -> None:
    app = _App()
    tk = _Tk()
    ttk = _Ttk()

    boot.build_widgets(app, tk=tk, ttk=ttk, tk_runtime_errors=(RuntimeError,), wrap_sync_errors=(RuntimeError,))

    assert app.canvas is not None
    assert app.lbl_cell is not None
    assert app.lbl_status is not None
    assert app._show_backdrop_var is not None
    assert any(seq == "<Return>" for seq, _cb, _add in app.bind_calls)
    assert any(seq == "<Escape>" for seq, _cb, _add in app.bind_calls)
    assert any(seq == "<Right>" for seq, _cb, _add in app.bind_calls)
    assert any(w.kind == "button" and w.kwargs.get("text") == "Save" for w in ttk.widgets)

    # canvas configure binding redraws
    configure_cb = next(cb for seq, cb, _ in app.canvas.bind_calls if seq == "<Configure>")
    configure_cb(object())  # type: ignore[operator]
    app._redraw.assert_called()

    # keyboard shortcuts
    assign_cb = next(cb for seq, cb, _ in app.bind_calls if seq == "<Return>")
    assign_cb(object())  # type: ignore[operator]
    app._assign.assert_called()

    esc_cb = next(cb for seq, cb, _ in app.bind_calls if seq == "<Escape>")
    esc_cb(object())  # type: ignore[operator]
    app._on_close.assert_called_once()
    app.destroy.assert_not_called()

    # wrap sync after(0)
    assert app.after_calls and app.after_calls[0][0] == 0
    wrap_cb = app.after_calls[0][1]
    assert callable(wrap_cb)
    wrap_cb()
    assert app.lbl_status.configure_calls


def test_build_widgets_tolerates_bind_and_wrap_errors() -> None:
    app = _App()
    tk = _Tk()
    ttk = _Ttk()

    original_frame = ttk.Frame

    def failing_side_frame(parent: object = None, **kwargs: object) -> _Widget:
        w = original_frame(parent, **kwargs)
        if kwargs.get("padding") == 0:

            def boom(*_a: object, **_k: object) -> None:
                raise RuntimeError("bind fail")

            w.bind = boom  # type: ignore[method-assign]
            w.winfo_width = lambda: (_ for _ in ()).throw(RuntimeError("width"))  # type: ignore[method-assign]
        return w

    ttk.Frame = failing_side_frame  # type: ignore[method-assign]

    boot.build_widgets(app, tk=tk, ttk=ttk, tk_runtime_errors=(RuntimeError,), wrap_sync_errors=(RuntimeError,))
    # should not raise; after wrap still scheduled
    assert app.after_calls


def test_finish_init_schedules_load_and_swallows_deiconify_errors() -> None:
    calls: list[str] = []

    class _AppFinish:
        def _load_deck_image(self) -> None:
            calls.append("load")

        def _apply_current_probe(self) -> None:
            calls.append("probe")

        def _redraw(self) -> None:
            calls.append("redraw")

        def deiconify(self) -> None:
            raise RuntimeError("no window")

        def lift(self) -> None:
            calls.append("lift")

        def after(self, delay_ms: int, callback: object) -> None:
            assert delay_ms == 0
            assert callable(callback)
            callback()

    boot.finish_init(_AppFinish(), tk_runtime_errors=(RuntimeError,))
    assert calls == ["load", "probe", "redraw"]


def test_build_widgets_uses_theme_styles_outer_padding_and_assign_focus() -> None:
    app = _App()
    tk = _Tk()
    ttk = _Ttk()

    boot.build_widgets(app, tk=tk, ttk=ttk, tk_runtime_errors=(RuntimeError,), wrap_sync_errors=(RuntimeError,))

    # Outer frame uses the shared spacing metric.
    outer = ttk.widgets[0]
    assert outer.kind == "frame"
    assert outer.kwargs.get("padding") == theme_metrics.OUTER_PADDING

    labels = [w for w in ttk.widgets if w.kind == "label"]
    title = next(w for w in labels if w.kwargs.get("text") == "Keymap Calibrator")
    assert title.kwargs.get("style") == theme_metrics.TITLE_LABEL_STYLE
    assert "font" not in title.kwargs

    assert app.lbl_cell.kwargs.get("style") == theme_metrics.BODY_LABEL_STYLE
    assert "font" not in app.lbl_cell.kwargs

    assert app.lbl_status.kwargs.get("style") == theme_metrics.STATUS_LABEL_STYLE
    assert "font" not in app.lbl_status.kwargs

    # No calibrator-chrome widget keeps a local Sans tuple; canvas labels
    # (TkDefaultFont in canvas_render) are out of scope here.
    for w in ttk.widgets:
        font = w.kwargs.get("font")
        assert not (isinstance(font, tuple) and font and font[0] == "Sans"), w.kwargs

    assign_btn = next(w for w in ttk.widgets if w.kind == "button" and w.kwargs.get("text") == "Assign selected key")
    assert assign_btn.kwargs.get("style") == theme_metrics.PRIMARY_BUTTON_STYLE

    # Save actions stay on the default button style (only Assign is primary).
    for text in ("Save", "Save && Close"):
        btn = next(w for w in ttk.widgets if w.kind == "button" and w.kwargs.get("text") == text)
        assert "style" not in btn.kwargs

    # Initial focus is scheduled non-forcing on Assign via `after`.
    focus_entries = [(d, cb) for d, cb in app.after_calls if d == theme_focus.INITIAL_FOCUS_DELAY_MS]
    assert len(focus_entries) == 1
    focus_cb = focus_entries[0][1]
    assert callable(focus_cb)
    assert app._focused is None
    focus_cb()
    assert assign_btn.focus_calls == 1

    # Existing bindings and control order are unchanged.
    assert any(seq == "<Return>" for seq, _cb, _add in app.bind_calls)
    assert any(seq == "<KP_Enter>" for seq, _cb, _add in app.bind_calls)
    assert [w.kwargs.get("text") for w in ttk.widgets if w.kind == "button"] == [
        "Prev",
        "Next",
        "Assign selected key",
        "Skip (nothing lit)",
        "Reset Keymap Defaults",
        "Save",
        "Save && Close",
    ]
