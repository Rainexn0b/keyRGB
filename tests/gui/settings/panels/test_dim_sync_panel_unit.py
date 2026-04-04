from __future__ import annotations

from types import SimpleNamespace

import src.gui.settings.panels.dim_sync_panel as dim_sync_panel


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
    def __init__(self, value) -> None:
        self._value = value

    def get(self):
        return self._value


def test_init_builds_controls_and_slider_binding(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    checks: list[_FakeWidget] = []
    radios: list[_FakeWidget] = []
    frames: list[_FakeWidget] = []
    scales: list[_FakeWidget] = []

    monkeypatch.setattr(
        dim_sync_panel,
        "ttk",
        SimpleNamespace(
            Label=lambda parent=None, **kwargs: labels.append(_FakeWidget(parent, **kwargs)) or labels[-1],
            Checkbutton=lambda parent=None, **kwargs: checks.append(_FakeWidget(parent, **kwargs)) or checks[-1],
            Radiobutton=lambda parent=None, **kwargs: radios.append(_FakeWidget(parent, **kwargs)) or radios[-1],
            Frame=lambda parent=None, **kwargs: frames.append(_FakeWidget(parent, **kwargs)) or frames[-1],
            Scale=lambda parent=None, **kwargs: scales.append(_FakeWidget(parent, **kwargs)) or scales[-1],
        ),
    )

    toggle_calls: list[str] = []
    panel = dim_sync_panel.DimSyncPanel(
        object(),
        var_dim_sync_enabled=_FakeVar(True),
        var_dim_sync_mode=_FakeVar("temp"),
        var_dim_temp_brightness=_FakeVar(17.2),
        on_toggle=lambda: toggle_calls.append("toggle"),
    )

    assert labels[0].kwargs["text"] == "Screen dim/brightness sync"
    assert labels[1].kwargs["text"].startswith("Optionally react to your desktop")
    assert checks[0].kwargs["text"] == "Sync keyboard lighting with screen dimming/brightness"
    assert radios[0].kwargs["value"] == "off"
    assert radios[1].kwargs["value"] == "temp"
    assert panel.lbl_dim_temp_val.kwargs["text"] == "17"
    assert panel.scale_dim_temp.kwargs["from_"] == 1
    assert panel.scale_dim_temp.kwargs["to"] == 50
    assert panel.scale_dim_temp.bind_calls[0][0] == "<ButtonRelease-1>"

    checks[0].kwargs["command"]()
    radios[0].kwargs["command"]()
    radios[1].kwargs["command"]()
    panel.scale_dim_temp.bind_calls[0][1](None)
    panel.scale_dim_temp.kwargs["command"]("9.8")

    assert toggle_calls == ["toggle", "toggle", "toggle", "toggle"]
    assert panel.lbl_dim_temp_val.options["text"] == "9"


class _BadFloat:
    def __float__(self) -> float:
        raise ValueError("boom")


def _make_panel(*, dim_sync_enabled: bool, dim_sync_mode: str) -> dim_sync_panel.DimSyncPanel:
    panel = dim_sync_panel.DimSyncPanel.__new__(dim_sync_panel.DimSyncPanel)
    panel.var_dim_sync_enabled = _FakeVar(dim_sync_enabled)
    panel.var_dim_sync_mode = _FakeVar(dim_sync_mode)
    panel.chk_dim_sync = _FakeWidget()
    panel.rb_dim_off = _FakeWidget()
    panel.rb_dim_temp = _FakeWidget()
    panel.scale_dim_temp = _FakeWidget()
    return panel


def test_apply_enabled_state_disables_all_controls_when_power_management_disabled() -> None:
    panel = _make_panel(dim_sync_enabled=True, dim_sync_mode="temp")

    panel.apply_enabled_state(power_management_enabled=False)

    assert panel.chk_dim_sync.options["state"] == "disabled"
    assert panel.rb_dim_off.options["state"] == "disabled"
    assert panel.rb_dim_temp.options["state"] == "disabled"
    assert panel.scale_dim_temp.options["state"] == "disabled"


def test_apply_enabled_state_disables_temp_scale_when_dim_sync_is_disabled() -> None:
    panel = _make_panel(dim_sync_enabled=False, dim_sync_mode="temp")

    panel.apply_enabled_state(power_management_enabled=True)

    assert panel.chk_dim_sync.options["state"] == "normal"
    assert panel.rb_dim_off.options["state"] == "normal"
    assert panel.rb_dim_temp.options["state"] == "normal"
    assert panel.scale_dim_temp.options["state"] == "disabled"


def test_apply_enabled_state_enables_temp_scale_for_temp_mode() -> None:
    panel = _make_panel(dim_sync_enabled=True, dim_sync_mode="temp")

    panel.apply_enabled_state(power_management_enabled=True)

    assert panel.chk_dim_sync.options["state"] == "normal"
    assert panel.rb_dim_off.options["state"] == "normal"
    assert panel.rb_dim_temp.options["state"] == "normal"
    assert panel.scale_dim_temp.options["state"] == "normal"


def test_apply_enabled_state_disables_temp_scale_for_off_mode() -> None:
    panel = _make_panel(dim_sync_enabled=True, dim_sync_mode="off")

    panel.apply_enabled_state(power_management_enabled=True)

    assert panel.chk_dim_sync.options["state"] == "normal"
    assert panel.rb_dim_off.options["state"] == "normal"
    assert panel.rb_dim_temp.options["state"] == "normal"
    assert panel.scale_dim_temp.options["state"] == "disabled"


def test_set_label_int_updates_label_with_integer_text() -> None:
    label = _FakeWidget()

    dim_sync_panel.DimSyncPanel._set_label_int(label, "17.9")

    assert label.options["text"] == "17"
    assert label.configure_calls == [{"text": "17"}]


def test_set_label_int_falls_back_to_placeholder_on_parse_error() -> None:
    label = _FakeWidget()

    dim_sync_panel.DimSyncPanel._set_label_int(label, _BadFloat())

    assert label.options["text"] == "?"
    assert label.configure_calls == [{"text": "?"}]
