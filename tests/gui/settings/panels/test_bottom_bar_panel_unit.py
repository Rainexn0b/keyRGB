from __future__ import annotations

from types import SimpleNamespace

import src.gui.settings.panels.bottom_bar_panel as bottom_bar_panel


def _install_fake_ttk(
    monkeypatch,
    *,
    frame_width: int = 0,
    bind_error: bool = False,
    after_error: bool = False,
):
    registry = {"frames": [], "labels": [], "buttons": []}

    class FakeWidget:
        def __init__(self, parent=None, **kwargs):
            self.parent = parent
            self.options = dict(kwargs)
            self.configure_calls = []
            self.pack_calls = []
            self.grid_calls = []
            self.pack_forget_calls = 0
            self.grid_remove_calls = 0

        def configure(self, **kwargs):
            self.configure_calls.append(dict(kwargs))
            self.options.update(kwargs)

        def pack(self, **kwargs):
            self.pack_calls.append(dict(kwargs))

        def grid(self, **kwargs):
            self.grid_calls.append(dict(kwargs))

        def pack_forget(self):
            self.pack_forget_calls += 1

        def grid_remove(self):
            self.grid_remove_calls += 1

    class FakeFrame(FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            self.width = frame_width
            self.bind_calls = []
            self.bound_callbacks = {}
            self.after_calls = []
            self.columnconfigure_calls = []
            registry["frames"].append(self)

        def bind(self, event, callback):
            if bind_error:
                raise RuntimeError("bind failed")
            self.bind_calls.append((event, callback))
            self.bound_callbacks[event] = callback

        def after(self, delay_ms, callback):
            if after_error:
                raise RuntimeError("after failed")
            self.after_calls.append((delay_ms, callback))

        def columnconfigure(self, index, weight=0, **_kwargs):
            self.columnconfigure_calls.append((index, weight))

        def winfo_width(self):
            return self.width

    class FakeLabel(FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["labels"].append(self)

    class FakeButton(FakeWidget):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent, **kwargs)
            registry["buttons"].append(self)

    monkeypatch.setattr(
        bottom_bar_panel,
        "ttk",
        SimpleNamespace(Frame=FakeFrame, Label=FakeLabel, Button=FakeButton),
    )
    return registry


def test_bottom_bar_panel_initialization_binds_and_schedules_wrap_sync(monkeypatch) -> None:
    _install_fake_ttk(monkeypatch, frame_width=1000)
    close_calls = []

    panel = bottom_bar_panel.BottomBarPanel(object(), on_close=lambda: close_calls.append("closed"))

    assert panel.frame.options["padding"] == (16, 8, 16, 12)
    assert panel.frame.columnconfigure_calls == [(0, 1)]
    assert panel.hardware_hint.options["text"] == ""
    assert panel.hardware_hint.options["wraplength"] == 820
    assert panel._hardware_hint_packed is False
    assert panel.status.grid_calls == [{"row": 0, "column": 1, "sticky": "w"}]
    assert panel.close_btn.grid_calls == [{"row": 0, "column": 2, "sticky": "e", "padx": (12, 0)}]
    assert panel.frame.bind_calls[0][0] == "<Configure>"
    assert panel.frame.after_calls[0][0] == 0

    panel.close_btn.options["command"]()
    assert close_calls == ["closed"]

    bound_callback = panel.frame.bound_callbacks["<Configure>"]
    bound_callback()
    assert panel.hardware_hint.configure_calls[-1] == {"wraplength": 740}

    panel.frame.width = 300
    scheduled_callback = panel.frame.after_calls[0][1]
    scheduled_callback()
    assert panel.hardware_hint.configure_calls[-1] == {"wraplength": 200}


def test_bottom_bar_panel_wrap_sync_ignores_small_width_and_configure_failures(monkeypatch) -> None:
    _install_fake_ttk(monkeypatch, frame_width=1)
    panel = bottom_bar_panel.BottomBarPanel(object(), on_close=lambda: None)
    callback = panel.frame.bound_callbacks["<Configure>"]

    callback()
    assert panel.hardware_hint.configure_calls == []

    panel.frame.width = 640

    def raise_configure(**_kwargs):
        raise RuntimeError("configure failed")

    panel.hardware_hint.configure = raise_configure
    callback()


def test_bottom_bar_panel_tolerates_bind_and_after_failures(monkeypatch) -> None:
    _install_fake_ttk(monkeypatch, bind_error=True, after_error=True)

    panel = bottom_bar_panel.BottomBarPanel(object(), on_close=lambda: None)

    assert panel.frame.bind_calls == []
    assert panel.frame.bound_callbacks == {}
    assert panel.frame.after_calls == []
    assert panel.status.grid_calls == [{"row": 0, "column": 1, "sticky": "w"}]
    assert panel.close_btn.grid_calls == [{"row": 0, "column": 2, "sticky": "e", "padx": (12, 0)}]


def test_set_hardware_hint_packs_and_unpacks_idempotently(monkeypatch) -> None:
    _install_fake_ttk(monkeypatch)
    panel = bottom_bar_panel.BottomBarPanel(object(), on_close=lambda: None)

    panel.set_hardware_hint("GPU RGB control is unavailable on battery")

    assert panel.hardware_hint.options["text"] == "GPU RGB control is unavailable on battery"
    assert panel.hardware_hint.grid_calls == [
        {
            "row": 0,
            "column": 0,
            "sticky": "ew",
            "padx": (0, 12),
        }
    ]
    assert panel._hardware_hint_packed is True

    panel.set_hardware_hint("Updated hardware hint")
    assert panel.hardware_hint.options["text"] == "Updated hardware hint"
    assert len(panel.hardware_hint.grid_calls) == 1

    panel.set_hardware_hint("   ")
    assert panel.hardware_hint.options["text"] == ""
    assert panel.hardware_hint.grid_remove_calls == 1
    assert panel._hardware_hint_packed is False

    panel.set_hardware_hint("")
    assert panel.hardware_hint.grid_remove_calls == 1
    assert panel._hardware_hint_packed is False
