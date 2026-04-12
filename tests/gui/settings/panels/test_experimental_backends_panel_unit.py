from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.experimental_backends_panel as experimental_backends_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []
        self.bind_calls = []
        self.after_calls = []
        self.configure_calls = []

    def pack(self, **kwargs):
        self.pack_calls.append(dict(kwargs))

    def bind(self, sequence, callback):
        self.bind_calls.append((sequence, callback))

    def after(self, delay_ms, callback):
        self.after_calls.append((delay_ms, callback))

    def configure(self, **kwargs):
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def winfo_width(self):
        return int(self.options.get("width_px", 520))


def _install_fake_ttk(monkeypatch: pytest.MonkeyPatch):
    registry = {"labels": [], "checkbuttons": []}

    class FakeLabel(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeCheckbutton(_FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["checkbuttons"].append(self)

    monkeypatch.setattr(
        experimental_backends_panel,
        "ttk",
        SimpleNamespace(Label=FakeLabel, Checkbutton=FakeCheckbutton),
    )
    return registry


def test_experimental_backends_panel_init_creates_title_and_description_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ttk(monkeypatch)
    parent = _FakeWidget(width_px=520)

    experimental_backends_panel.ExperimentalBackendsPanel(
        parent,
        var_experimental_backends=object(),
        on_toggle=lambda: None,
    )

    assert len(registry["labels"]) == 2
    assert registry["labels"][0].parent is parent
    assert registry["labels"][0].options == {
        "text": "Backend policy",
        "font": ("Sans", 11, "bold"),
    }
    assert registry["labels"][0].pack_calls == [{"anchor": "w", "pady": (0, 6)}]
    assert registry["labels"][1].parent is parent
    assert registry["labels"][1].options == {
        "text": (
            "Experimental backends are opt-in. Some are speculative. Others are research-backed, "
            "which means KeyRGB has public protocol notes or reverse-engineering references, but the "
            "backend is still not broadly validated on user hardware. Use at your own risk."
        ),
        "font": ("Sans", 9),
        "justify": "left",
        "wraplength": 420,
    }
    assert registry["labels"][1].pack_calls == [{"anchor": "w", "fill": "x", "pady": (0, 8)}]
    assert parent.bind_calls[0][0] == "<Configure>"
    assert parent.after_calls[0][0] == 0


def test_experimental_backends_panel_init_wires_checkbox_variable_and_toggle_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _install_fake_ttk(monkeypatch)
    parent = _FakeWidget(width_px=520)
    variable = object()
    toggle_calls: list[str] = []

    def on_toggle() -> None:
        toggle_calls.append("called")

    panel = experimental_backends_panel.ExperimentalBackendsPanel(
        parent,
        var_experimental_backends=variable,
        on_toggle=on_toggle,
    )

    assert len(registry["checkbuttons"]) == 1
    assert panel.chk_experimental is registry["checkbuttons"][0]
    assert panel.chk_experimental.parent is parent
    assert panel.chk_experimental.options == {
        "text": "Enable experimental backends (takes effect next launch)",
        "variable": variable,
        "command": on_toggle,
    }
    assert panel.chk_experimental.pack_calls == [{"anchor": "w"}]

    panel.chk_experimental.options["command"]()

    assert toggle_calls == ["called"]
