from __future__ import annotations

import src.gui.settings.panels.dim_sync_panel as dim_sync_panel


class _FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)


class _FakeVar:
    def __init__(self, value) -> None:
        self._value = value

    def get(self):
        return self._value


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