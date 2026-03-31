from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.power_source_panel as power_source_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))

    def bind(self, event: str, callback) -> None:
        self.bind_calls.append((event, callback))


class _FakeVar:
    def __init__(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value


def _make_panel() -> power_source_panel.PowerSourcePanel:
    panel = power_source_panel.PowerSourcePanel.__new__(power_source_panel.PowerSourcePanel)
    panel.chk_ac_enabled = _FakeWidget()
    panel.chk_battery_enabled = _FakeWidget()
    panel.scale_ac_brightness = _FakeWidget()
    panel.scale_battery_brightness = _FakeWidget()
    return panel


def test_init_builds_controls_and_wires_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    labels: list[_FakeWidget] = []
    frames: list[_FakeWidget] = []
    checks: list[_FakeWidget] = []
    scales: list[_FakeWidget] = []

    def make_label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        labels.append(widget)
        return widget

    def make_frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        frames.append(widget)
        return widget

    def make_check(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        checks.append(widget)
        return widget

    def make_scale(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        scales.append(widget)
        return widget

    monkeypatch.setattr(
        power_source_panel,
        "ttk",
        SimpleNamespace(
            Label=make_label,
            Frame=make_frame,
            Checkbutton=make_check,
            Scale=make_scale,
        ),
    )

    toggle_calls: list[str] = []
    parent = object()
    panel = power_source_panel.PowerSourcePanel(
        parent,
        var_ac_enabled=_FakeVar(True),
        var_battery_enabled=_FakeVar(False),
        var_ac_brightness=_FakeVar(12.7),
        var_battery_brightness=_FakeVar(7.2),
        on_toggle=lambda: toggle_calls.append("toggle"),
    )

    assert labels[0].kwargs["text"] == "Plugged In vs Battery"
    assert labels[1].kwargs["text"].startswith("Choose whether the keyboard lighting")
    assert panel.chk_ac_enabled.kwargs["text"] == "When plugged in (AC): enable lighting"
    assert panel.chk_battery_enabled.kwargs["text"] == "On battery: enable lighting"
    assert panel.lbl_ac_brightness_val.kwargs["text"] == "12"
    assert panel.lbl_battery_brightness_val.kwargs["text"] == "7"
    assert panel.scale_ac_brightness.kwargs["variable"].get() == 12.7
    assert panel.scale_battery_brightness.kwargs["variable"].get() == 7.2
    assert panel.scale_ac_brightness.bind_calls[0][0] == "<ButtonRelease-1>"
    assert panel.scale_battery_brightness.bind_calls[0][0] == "<ButtonRelease-1>"

    panel.chk_ac_enabled.kwargs["command"]()
    panel.chk_battery_enabled.kwargs["command"]()
    panel.scale_ac_brightness.bind_calls[0][1](None)
    panel.scale_battery_brightness.bind_calls[0][1](None)
    assert toggle_calls == ["toggle", "toggle", "toggle", "toggle"]

    panel.scale_ac_brightness.kwargs["command"]("19.9")
    panel.scale_battery_brightness.kwargs["command"]("3.1")
    assert panel.lbl_ac_brightness_val.options["text"] == "19"
    assert panel.lbl_battery_brightness_val.options["text"] == "3"


def test_set_label_int_updates_label_with_truncated_integer_text() -> None:
    label = _FakeWidget()

    power_source_panel.PowerSourcePanel._set_label_int(label, "12.9")

    assert label.configure_calls == [{"text": "12"}]
    assert label.options["text"] == "12"


def test_set_label_int_falls_back_to_question_mark_on_parse_failure() -> None:
    label = _FakeWidget()

    power_source_panel.PowerSourcePanel._set_label_int(label, "not-a-number")

    assert label.configure_calls == [{"text": "?"}]
    assert label.options["text"] == "?"


@pytest.mark.parametrize(
    ("power_management_enabled", "expected_state"),
    [
        (True, "normal"),
        (False, "disabled"),
    ],
)
def test_apply_enabled_state_updates_ac_and_battery_controls(
    power_management_enabled: bool,
    expected_state: str,
) -> None:
    panel = _make_panel()

    panel.apply_enabled_state(power_management_enabled=power_management_enabled)

    assert panel.chk_ac_enabled.configure_calls == [{"state": expected_state}]
    assert panel.chk_battery_enabled.configure_calls == [{"state": expected_state}]
    assert panel.scale_ac_brightness.configure_calls == [{"state": expected_state}]
    assert panel.scale_battery_brightness.configure_calls == [{"state": expected_state}]
    assert panel.chk_ac_enabled.options["state"] == expected_state
    assert panel.chk_battery_enabled.options["state"] == expected_state
    assert panel.scale_ac_brightness.options["state"] == expected_state
    assert panel.scale_battery_brightness.options["state"] == expected_state