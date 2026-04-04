from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.autostart_panel as autostart_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.options = dict(kwargs)
        self.pack_calls = []

    def pack(self, **kwargs):
        self.pack_calls.append(dict(kwargs))


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
        autostart_panel,
        "ttk",
        SimpleNamespace(Label=FakeLabel, Checkbutton=FakeCheckbutton),
    )
    return registry


def test_autostart_panel_init_creates_expected_labels_and_checkbuttons(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ttk(monkeypatch)
    parent = object()
    var_autostart = object()
    var_os_autostart = object()

    panel = autostart_panel.AutostartPanel(
        parent,
        var_autostart=var_autostart,
        var_os_autostart=var_os_autostart,
        on_toggle=lambda: None,
    )

    assert [label.parent for label in registry["labels"]] == [parent, parent]
    assert [label.options["text"] for label in registry["labels"]] == [
        "Autostart",
        "Control what happens when KeyRGB launches, and whether it\nstarts automatically when you log in.",
    ]
    assert [label.options["font"] for label in registry["labels"]] == [
        ("Sans", 11, "bold"),
        ("Sans", 9),
    ]
    assert registry["labels"][0].pack_calls == [{"anchor": "w", "pady": (0, 6)}]
    assert registry["labels"][1].pack_calls == [{"anchor": "w", "pady": (0, 8)}]

    assert panel.chk_autostart is registry["checkbuttons"][0]
    assert panel.chk_os_autostart is registry["checkbuttons"][1]
    assert [checkbutton.parent for checkbutton in registry["checkbuttons"]] == [parent, parent]
    assert [checkbutton.options["text"] for checkbutton in registry["checkbuttons"]] == [
        "Start lighting on launch",
        "Start KeyRGB on login",
    ]
    assert registry["checkbuttons"][0].options["variable"] is var_autostart
    assert registry["checkbuttons"][1].options["variable"] is var_os_autostart
    assert registry["checkbuttons"][0].pack_calls == [{"anchor": "w"}]
    assert registry["checkbuttons"][1].pack_calls == [{"anchor": "w", "pady": (6, 0)}]


def test_autostart_panel_checkbuttons_invoke_supplied_toggle_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _install_fake_ttk(monkeypatch)
    toggle_calls = []

    autostart_panel.AutostartPanel(
        object(),
        var_autostart=object(),
        var_os_autostart=object(),
        on_toggle=lambda: toggle_calls.append("toggle"),
    )

    for checkbutton in registry["checkbuttons"]:
        checkbutton.options["command"]()

    assert toggle_calls == ["toggle", "toggle"]
