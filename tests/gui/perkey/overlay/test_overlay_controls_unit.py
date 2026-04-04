from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.gui.perkey.overlay.controls import OverlayControls


class _FakeVar:
    def __init__(self, value: float | str = 0.0):
        self.value = value

    def get(self) -> float | str:
        return self.value

    def set(self, value: float) -> None:
        self.value = value


class _FakeCanvas:
    def __init__(self) -> None:
        self.redraw_calls = 0

    def redraw(self) -> None:
        self.redraw_calls += 1


class _FakeEditor:
    def __init__(
        self,
        *,
        scope: str = "global",
        selected_key_id: str | None = None,
        layout_tweaks: dict[str, float] | None = None,
        per_key_layout_tweaks: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.overlay_scope = _FakeVar(scope)
        self.selected_key_id = selected_key_id
        self.layout_tweaks = dict(layout_tweaks or {})
        self.per_key_layout_tweaks = dict(per_key_layout_tweaks or {})
        self.canvas = _FakeCanvas()
        self.save_calls = 0
        self.reset_calls = 0
        self.auto_sync_calls = 0

    def save_layout_tweaks(self) -> None:
        self.save_calls += 1

    def reset_layout_tweaks(self) -> None:
        self.reset_calls += 1

    def auto_sync_per_key_overlays(self) -> None:
        self.auto_sync_calls += 1


def _make_controls(
    *,
    scope: str = "global",
    selected_key_id: str | None = None,
    layout_tweaks: dict[str, float] | None = None,
    per_key_layout_tweaks: dict[str, dict[str, float]] | None = None,
    var_values: dict[str, float | str] | None = None,
) -> SimpleNamespace:
    values = {
        "dx": 0.0,
        "dy": 0.0,
        "sx": 1.0,
        "sy": 1.0,
        "inset": 0.06,
    }
    values.update(var_values or {})

    return SimpleNamespace(
        editor=_FakeEditor(
            scope=scope,
            selected_key_id=selected_key_id,
            layout_tweaks=layout_tweaks,
            per_key_layout_tweaks=per_key_layout_tweaks,
        ),
        dx_var=_FakeVar(values["dx"]),
        dy_var=_FakeVar(values["dy"]),
        sx_var=_FakeVar(values["sx"]),
        sy_var=_FakeVar(values["sy"]),
        inset_var=_FakeVar(values["inset"]),
    )


def test_sync_vars_from_scope_loads_selected_key_values_and_global_inset_default() -> None:
    controls = _make_controls(
        scope="key",
        selected_key_id="esc",
        layout_tweaks={"dx": 9.0, "dy": 8.0, "sx": 7.0, "sy": 6.0, "inset": 0.25},
        per_key_layout_tweaks={"esc": {"dx": "1.5", "dy": -2.0, "sx": "1.2", "sy": 0.8}},
    )

    OverlayControls.sync_vars_from_scope(controls)

    assert controls.dx_var.get() == pytest.approx(1.5)
    assert controls.dy_var.get() == pytest.approx(-2.0)
    assert controls.sx_var.get() == pytest.approx(1.2)
    assert controls.sy_var.get() == pytest.approx(0.8)
    assert controls.inset_var.get() == pytest.approx(0.25)


def test_sync_vars_from_scope_loads_global_values_when_scope_is_global() -> None:
    controls = _make_controls(
        scope="global",
        selected_key_id="esc",
        layout_tweaks={"dx": "2.5", "dy": -1.25, "sx": "1.4", "sy": 0.9, "inset": "0.15"},
        per_key_layout_tweaks={"esc": {"dx": 99.0, "dy": 99.0, "sx": 99.0, "sy": 99.0, "inset": 99.0}},
    )

    OverlayControls.sync_vars_from_scope(controls)

    assert controls.dx_var.get() == pytest.approx(2.5)
    assert controls.dy_var.get() == pytest.approx(-1.25)
    assert controls.sx_var.get() == pytest.approx(1.4)
    assert controls.sy_var.get() == pytest.approx(0.9)
    assert controls.inset_var.get() == pytest.approx(0.15)


def test_apply_from_vars_clamps_values_and_updates_global_payload() -> None:
    controls = _make_controls(
        scope="global",
        layout_tweaks={"dx": 1.0},
        per_key_layout_tweaks={"esc": {"dx": 9.0}},
        var_values={"dx": "3.5", "dy": -4.0, "sx": 0.1, "sy": 9.0, "inset": -2.0},
    )

    OverlayControls.apply_from_vars(controls)

    assert controls.editor.layout_tweaks == {
        "dx": pytest.approx(3.5),
        "dy": pytest.approx(-4.0),
        "sx": pytest.approx(0.3),
        "sy": pytest.approx(4.0),
        "inset": pytest.approx(0.0),
    }
    assert controls.editor.per_key_layout_tweaks == {"esc": {"dx": 9.0}}
    assert controls.editor.canvas.redraw_calls == 1


def test_apply_from_vars_clamps_values_and_updates_selected_key_payload() -> None:
    controls = _make_controls(
        scope="key",
        selected_key_id="enter",
        layout_tweaks={"dx": 1.0, "dy": 2.0, "sx": 1.0, "sy": 1.0, "inset": 0.06},
        per_key_layout_tweaks={"esc": {"dx": 9.0}},
        var_values={"dx": 1.25, "dy": "-2.5", "sx": 3.2, "sy": 0.2, "inset": 120.0},
    )

    OverlayControls.apply_from_vars(controls)

    assert controls.editor.layout_tweaks == {"dx": 1.0, "dy": 2.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    assert controls.editor.per_key_layout_tweaks["enter"] == {
        "dx": pytest.approx(1.25),
        "dy": pytest.approx(-2.5),
        "sx": pytest.approx(3.2),
        "sy": pytest.approx(0.3),
        "inset": pytest.approx(80.0),
    }
    assert controls.editor.per_key_layout_tweaks["esc"] == {"dx": 9.0}
    assert controls.editor.canvas.redraw_calls == 1


def test_save_tweaks_applies_current_values_before_persisting() -> None:
    events: list[str] = []
    editor = _FakeEditor()
    controls = SimpleNamespace(editor=editor)
    controls.apply_from_vars = lambda: events.append("apply")
    editor.save_layout_tweaks = lambda: events.append("save")

    OverlayControls.save_tweaks(controls)

    assert events == ["apply", "save"]


def test_reset_tweaks_and_auto_sync_delegate_to_editor_methods() -> None:
    controls = _make_controls()

    OverlayControls.reset_tweaks(controls)
    OverlayControls.auto_sync(controls)

    assert controls.editor.reset_calls == 1
    assert controls.editor.auto_sync_calls == 1
