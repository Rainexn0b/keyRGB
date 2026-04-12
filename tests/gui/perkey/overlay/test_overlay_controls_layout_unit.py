from __future__ import annotations

from types import SimpleNamespace

import src.gui.perkey.overlay.controls as overlay_controls_module


class _FakeVar:
    def __init__(self, value: float | str = 0.0) -> None:
        self.value = value

    def get(self) -> float | str:
        return self.value

    def set(self, value: float | str) -> None:
        self.value = value


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.options = dict(kwargs)
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))


def test_build_ui_uses_grid_scope_selector_row(monkeypatch) -> None:
    registry = {"frames": [], "radios": [], "labels": [], "entries": [], "buttons": []}

    def _frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["frames"].append(widget)
        return widget

    def _radiobutton(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["radios"].append(widget)
        return widget

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labels"].append(widget)
        return widget

    def _entry(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["entries"].append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["buttons"].append(widget)
        return widget

    monkeypatch.setattr(
        overlay_controls_module,
        "ttk",
        SimpleNamespace(
            Frame=_frame,
            Radiobutton=_radiobutton,
            Label=_label,
            Entry=_entry,
            Button=_button,
        ),
    )

    controls = SimpleNamespace(
        editor=SimpleNamespace(overlay_scope=_FakeVar("global")),
        dx_var=_FakeVar(),
        dy_var=_FakeVar(),
        sx_var=_FakeVar(1.0),
        sy_var=_FakeVar(1.0),
        inset_var=_FakeVar(0.06),
        apply_from_vars=lambda: None,
        save_tweaks=lambda: None,
        reset_tweaks=lambda: None,
        auto_sync=lambda: None,
        sync_vars_from_scope=lambda: None,
        columnconfigure=lambda *_args, **_kwargs: None,
    )

    overlay_controls_module.OverlayControls._build_ui(controls)

    scope_row = registry["frames"][0]
    assert scope_row.grid_calls == [{"row": 0, "column": 0, "columnspan": 2, "sticky": "ew", "pady": (0, 8)}]
    assert scope_row.columnconfigure_calls == [(0, 1), (1, 1)]
    assert registry["radios"][0].grid_calls == [{"row": 0, "column": 0, "sticky": "w"}]
    assert registry["radios"][1].grid_calls == [{"row": 0, "column": 1, "sticky": "w", "padx": (10, 0)}]