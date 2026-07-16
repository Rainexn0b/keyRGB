from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.gui.settings.panels.time_scheduler_panel as time_scheduler_panel


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
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *_args):
        pass


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeCheckbutton(_FakeWidget):
    pass


class _FakeEntry(_FakeWidget):
    pass


class _FakeScale(_FakeWidget):
    pass


class _FakeLabelFrame(_FakeWidget):
    pass


@pytest.fixture(autouse=True)
def _patch_ttk(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(time_scheduler_panel, "ttk", SimpleNamespace(
        Frame=_FakeFrame,
        Label=_FakeLabel,
        Checkbutton=_FakeCheckbutton,
        Entry=_FakeEntry,
        Scale=_FakeScale,
        LabelFrame=_FakeLabelFrame,
    ))


def test_panel_creates_expected_widgets() -> None:
    parent = _FakeFrame()
    toggles: list[None] = []

    panel = time_scheduler_panel.TimeSchedulerPanel(
        parent,
        var_enabled=_FakeVar(False),
        var_day_start=_FakeVar("08:00"),
        var_night_start=_FakeVar("20:00"),
        var_day_base=_FakeVar(25.0),
        var_day_reactive=_FakeVar(25.0),
        var_night_base=_FakeVar(10.0),
        var_night_reactive=_FakeVar(10.0),
        on_toggle=lambda: toggles.append(None),
    )

    assert isinstance(panel.chk_enabled, _FakeCheckbutton)
    assert isinstance(panel.ent_day_start, _FakeEntry)
    assert isinstance(panel.ent_night_start, _FakeEntry)
    assert len(panel._scales) == 4


def test_apply_enabled_state_enables_when_checked() -> None:
    parent = _FakeFrame()

    panel = time_scheduler_panel.TimeSchedulerPanel(
        parent,
        var_enabled=_FakeVar(True),
        var_day_start=_FakeVar("08:00"),
        var_night_start=_FakeVar("20:00"),
        var_day_base=_FakeVar(25.0),
        var_day_reactive=_FakeVar(25.0),
        var_night_base=_FakeVar(10.0),
        var_night_reactive=_FakeVar(10.0),
        on_toggle=lambda: None,
    )

    panel.apply_enabled_state()

    assert panel.ent_day_start.options.get("state") == "normal"
    assert panel.ent_night_start.options.get("state") == "normal"
    for scale in panel._scales:
        assert scale.options.get("state") == "normal"


def test_apply_enabled_state_disables_when_unchecked() -> None:
    parent = _FakeFrame()

    panel = time_scheduler_panel.TimeSchedulerPanel(
        parent,
        var_enabled=_FakeVar(False),
        var_day_start=_FakeVar("08:00"),
        var_night_start=_FakeVar("20:00"),
        var_day_base=_FakeVar(25.0),
        var_day_reactive=_FakeVar(25.0),
        var_night_base=_FakeVar(10.0),
        var_night_reactive=_FakeVar(10.0),
        on_toggle=lambda: None,
    )

    panel.apply_enabled_state()

    assert panel.ent_day_start.options.get("state") == "disabled"
    assert panel.ent_night_start.options.get("state") == "disabled"
    for scale in panel._scales:
        assert scale.options.get("state") == "disabled"
