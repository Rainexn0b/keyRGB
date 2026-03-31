from __future__ import annotations

import pytest

import src.gui.settings.panels.power_management_panel as power_management_panel


class _FakeWidget:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs) -> None:
        self.configure_calls.append(dict(kwargs))
        self.options.update(kwargs)


class _FakeVar:
    def __init__(self, value: object) -> None:
        self._value = value

    def get(self) -> object:
        return self._value


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