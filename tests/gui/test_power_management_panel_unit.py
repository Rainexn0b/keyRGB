from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.power_management_panel as power_management_panel


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeVar:
    def __init__(self, value: object) -> None:
        self._value = value
        self.get_calls = 0

    def get(self) -> object:
        self.get_calls += 1
        return self._value


def test_init_builds_labels_and_checkboxes(monkeypatch: pytest.MonkeyPatch) -> None:
    labels: list[_FakeWidget] = []
    checks: list[_FakeWidget] = []

    monkeypatch.setattr(
        power_management_panel,
        "ttk",
        SimpleNamespace(
            Label=lambda parent=None, **kwargs: labels.append(_FakeWidget(parent, **kwargs)) or labels[-1],
            Checkbutton=lambda parent=None, **kwargs: checks.append(_FakeWidget(parent, **kwargs)) or checks[-1],
        ),
    )

    calls: list[str] = []
    parent = object()
    var_enabled = _FakeVar(True)
    var_off_suspend = _FakeVar(False)
    var_restore_resume = _FakeVar(True)
    var_off_lid = _FakeVar(False)
    var_restore_lid = _FakeVar(True)

    panel = power_management_panel.PowerManagementPanel(
        parent,
        var_enabled=var_enabled,
        var_off_suspend=var_off_suspend,
        var_restore_resume=var_restore_resume,
        var_off_lid=var_off_lid,
        var_restore_lid=var_restore_lid,
        on_toggle=lambda: calls.append("toggle"),
    )

    assert panel._var_enabled is var_enabled
    assert labels[0].kwargs["text"] == "Power Management"
    assert labels[1].kwargs["text"].startswith("Control whether KeyRGB")
    assert [widget.kwargs["text"] for widget in checks] == [
        "Enable power management",
        "Turn off on suspend",
        "Restore on resume",
        "Turn off on lid close",
        "Restore on lid open",
    ]
    assert checks[0].kwargs["variable"] is var_enabled
    assert checks[1].kwargs["variable"] is var_off_suspend
    assert checks[2].kwargs["variable"] is var_restore_resume
    assert checks[3].kwargs["variable"] is var_off_lid
    assert checks[4].kwargs["variable"] is var_restore_lid

    for widget in checks:
        widget.kwargs["command"]()

    assert calls == ["toggle", "toggle", "toggle", "toggle", "toggle"]


def _make_panel(enabled_value: object) -> power_management_panel.PowerManagementPanel:
    panel = power_management_panel.PowerManagementPanel.__new__(power_management_panel.PowerManagementPanel)
    panel._var_enabled = _FakeVar(enabled_value)
    panel.chk_enabled = _FakeWidget()
    panel.chk_off_suspend = _FakeWidget()
    panel.chk_restore_resume = _FakeWidget()
    panel.chk_off_lid = _FakeWidget()
    panel.chk_restore_lid = _FakeWidget()
    return panel


@pytest.mark.parametrize(
    ("enabled_value", "expected_state"),
    [
        (True, "normal"),
        (False, "disabled"),
    ],
)
def test_apply_enabled_state_updates_all_dependent_checkboxes(
    enabled_value: bool,
    expected_state: str,
) -> None:
    panel = _make_panel(enabled_value)

    panel.apply_enabled_state()

    assert panel.chk_off_suspend.configure_calls == [{"state": expected_state}]
    assert panel.chk_restore_resume.configure_calls == [{"state": expected_state}]
    assert panel.chk_off_lid.configure_calls == [{"state": expected_state}]
    assert panel.chk_restore_lid.configure_calls == [{"state": expected_state}]
    assert panel.chk_off_suspend.options["state"] == expected_state
    assert panel.chk_restore_resume.options["state"] == expected_state
    assert panel.chk_off_lid.options["state"] == expected_state
    assert panel.chk_restore_lid.options["state"] == expected_state


def test_apply_enabled_state_uses_bool_coercion_for_main_enabled_var() -> None:
    panel = _make_panel(1)

    panel.apply_enabled_state()

    assert panel.chk_off_suspend.options["state"] == "normal"
    assert panel.chk_restore_resume.options["state"] == "normal"
    assert panel.chk_off_lid.options["state"] == "normal"
    assert panel.chk_restore_lid.options["state"] == "normal"


def test_apply_enabled_state_does_not_reconfigure_main_enabled_checkbox() -> None:
    panel = _make_panel(False)

    panel.apply_enabled_state()

    assert panel.chk_enabled.configure_calls == []