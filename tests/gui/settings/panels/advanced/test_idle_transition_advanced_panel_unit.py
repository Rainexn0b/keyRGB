from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from keyrgb.gui.settings.panels import idle_transition_advanced_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.columnconfigure_calls: list[tuple[int, int]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))


class _FakeVar:
    def __init__(self, value) -> None:
        self._value = value

    def get(self):
        return self._value


def _install_ttk(monkeypatch, registry: dict[str, list]) -> None:
    monkeypatch.setattr(
        idle_transition_advanced_panel,
        "ttk",
        SimpleNamespace(
            Label=lambda parent=None, **kwargs: (
                registry["labels"].append(_FakeWidget(parent, **kwargs)) or registry["labels"][-1]
            ),
            Checkbutton=lambda parent=None, **kwargs: (
                registry["checks"].append(_FakeWidget(parent, **kwargs)) or registry["checks"][-1]
            ),
            Radiobutton=lambda parent=None, **kwargs: (
                registry["radios"].append(_FakeWidget(parent, **kwargs)) or registry["radios"][-1]
            ),
            Frame=lambda parent=None, **kwargs: (
                registry["frames"].append(_FakeWidget(parent, **kwargs)) or registry["frames"][-1]
            ),
            Scale=lambda parent=None, **kwargs: (
                registry["scales"].append(_FakeWidget(parent, **kwargs)) or registry["scales"][-1]
            ),
            Spinbox=lambda parent=None, **kwargs: (
                registry["spinboxes"].append(_FakeWidget(parent, **kwargs)) or registry["spinboxes"][-1]
            ),
        ),
    )


def _registry() -> dict[str, list]:
    return {"labels": [], "checks": [], "radios": [], "frames": [], "scales": [], "spinboxes": []}


def test_init_builds_controller_sleep_delays_and_fade(monkeypatch) -> None:
    registry = _registry()
    _install_ttk(monkeypatch, registry)
    toggle_calls: list[str] = []
    panel = idle_transition_advanced_panel.IdleTransitionAdvancedPanel(
        object(),
        var_controller_sleep_respect=_FakeVar(False),
        var_debounce_enter=_FakeVar(6),
        var_debounce_exit=_FakeVar(10),
        var_idle_fade_duration=_FakeVar(0.6),
        on_toggle=lambda: toggle_calls.append("toggle"),
    )

    assert registry["labels"][0].kwargs["text"] == "Controller sleep and idle timing"
    assert registry["checks"][0].kwargs["text"] == ("Let the controller's own sleep timeout turn the keyboard off")
    assert "wraplength" not in registry["checks"][0].kwargs
    assert registry["labels"][1].kwargs["text"].startswith("Recommended for supported ITE controllers")
    assert registry["labels"][1].kwargs["wraplength"] == 400
    assert registry["labels"][2].kwargs["text"] == "Delay before reacting to screen idle/blanking, in seconds."
    assert registry["spinboxes"][0].kwargs["from_"] == 0.5
    assert registry["spinboxes"][0].kwargs["to"] == 30.0
    assert registry["spinboxes"][0].kwargs["increment"] == 0.5
    assert registry["spinboxes"][0].kwargs["format"] == "%.1f"
    assert registry["spinboxes"][1].kwargs["from_"] == 0.5
    assert registry["spinboxes"][1].kwargs["to"] == 30.0
    assert registry["spinboxes"][1].kwargs["increment"] == 0.5
    assert registry["spinboxes"][1].kwargs["format"] == "%.1f"
    assert panel.lbl_fade_duration_val.kwargs["text"] == "0.6 s"
    assert panel.scale_fade_duration.kwargs["from_"] == 0.1
    assert panel.scale_fade_duration.kwargs["to"] == 3.0
    assert panel.scale_fade_duration.bind_calls[0][0] == "<ButtonRelease-1>"
    assert panel.spn_enter.bind_calls[0][0] == "<Return>"
    assert panel.spn_exit.bind_calls[0][0] == "<Return>"

    registry["checks"][0].kwargs["command"]()
    registry["spinboxes"][0].kwargs["command"]()
    registry["spinboxes"][1].kwargs["command"]()
    panel.spn_enter.bind_calls[0][1](None)
    panel.spn_exit.bind_calls[0][1](None)
    panel.scale_fade_duration.bind_calls[0][1](None)
    panel.scale_fade_duration.kwargs["command"]("1.2")

    assert toggle_calls == ["toggle"] * 6
    assert panel.lbl_fade_duration_val.options["text"] == "1.2 s"


def _make_panel() -> idle_transition_advanced_panel.IdleTransitionAdvancedPanel:
    panel = idle_transition_advanced_panel.IdleTransitionAdvancedPanel.__new__(
        idle_transition_advanced_panel.IdleTransitionAdvancedPanel
    )
    panel.chk_controller_sleep = _FakeWidget()
    panel.spn_enter = _FakeWidget()
    panel.spn_exit = _FakeWidget()
    panel.scale_fade_duration = _FakeWidget()
    return panel


def test_apply_enabled_state_never_disables_controller_sleep_checkbox() -> None:
    panel = _make_panel()

    panel.apply_enabled_state(power_management_enabled=False)

    assert panel.spn_enter.options["state"] == "disabled"
    assert panel.spn_exit.options["state"] == "disabled"
    assert panel.scale_fade_duration.options["state"] == "disabled"
    # Intentionally not gated by power management.
    assert panel.chk_controller_sleep.configure_calls == []


def test_apply_enabled_state_enables_timing_controls_with_power_management() -> None:
    panel = _make_panel()

    panel.apply_enabled_state(power_management_enabled=True)

    assert panel.spn_enter.options["state"] == "normal"
    assert panel.spn_exit.options["state"] == "normal"
    assert panel.scale_fade_duration.options["state"] == "normal"
    assert panel.chk_controller_sleep.configure_calls == []


class _BadFloat:
    def __float__(self) -> float:
        raise ValueError("boom")


def test_set_label_seconds_updates_label_with_seconds_text() -> None:
    label = _FakeWidget()

    idle_transition_advanced_panel.IdleTransitionAdvancedPanel._set_label_seconds(label, "1.24")

    assert label.options["text"] == "1.2 s"
    assert label.configure_calls == [{"text": "1.2 s"}]


def test_set_label_seconds_falls_back_to_placeholder_on_parse_error() -> None:
    label = _FakeWidget()

    idle_transition_advanced_panel.IdleTransitionAdvancedPanel._set_label_seconds(label, _BadFloat())

    assert label.options["text"] == "?"
    assert label.configure_calls == [{"text": "?"}]


def test_set_label_seconds_falls_back_when_widget_rejects_primary_update() -> None:
    class _RetryLabel(_FakeWidget):
        def configure(self, **kwargs) -> None:
            if kwargs.get("text") != "?":
                raise RuntimeError("widget not ready")
            super().configure(**kwargs)

    label = _RetryLabel()

    idle_transition_advanced_panel.IdleTransitionAdvancedPanel._set_label_seconds(label, "1.2")

    assert label.configure_calls == [{"text": "?"}]
    assert label.options["text"] == "?"


def test_set_label_seconds_swallows_destroyed_widget_errors() -> None:
    class _DestroyedLabel:
        def configure(self, **kwargs) -> None:
            raise tk.TclError("widget destroyed")

    idle_transition_advanced_panel.IdleTransitionAdvancedPanel._set_label_seconds(_DestroyedLabel(), "1.2")
