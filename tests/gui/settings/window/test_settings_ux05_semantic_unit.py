"""UX-05 Settings slice: semantic styles, no local font tuples, sane buttons.

Covers ``keyrgb/gui/settings/**`` only. Shared theme behavior (contrast maps,
focus scheduling) is pinned by ``tests/gui/theme_entrypoints/``; this module
pins the Settings-side wiring: every settings label uses a semantic
``keyrgb.gui.theme.metrics`` style, no local ``("Sans", N, ...)`` tuples
remain, and button styling stays neutral (Close remains a normal button).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import keyrgb.gui.settings.window as settings_window
from keyrgb.gui.settings.panels import (
    autostart_panel,
    bottom_bar_panel,
    dim_sync_panel,
    experimental_backends_panel,
    idle_transition_advanced_panel,
    power_management_panel,
    power_source_panel,
    time_scheduler_panel,
    version_panel,
)
from keyrgb.gui.theme import metrics as theme_metrics


class _FakeWidget:
    def __init__(self, parent=None, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.options: dict[str, object] = {}
        self.configure_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        self.grid_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object]] = []
        self.after_calls: list[tuple[int, object]] = []
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

    def after(self, delay_ms: int, callback) -> None:
        self.after_calls.append((delay_ms, callback))

    def columnconfigure(self, index: int, weight: int = 0, **_kwargs) -> None:
        self.columnconfigure_calls.append((index, weight))

    def winfo_width(self) -> int:
        return 800


class _FakeVar:
    def __init__(self, value) -> None:
        self._value = value

    def get(self):
        return self._value

    def set(self, value) -> None:
        self._value = value


def _fake_ttk(labels: list[_FakeWidget], buttons: list[_FakeWidget]) -> SimpleNamespace:
    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        labels.append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        buttons.append(widget)
        return widget

    def _other(parent=None, **kwargs):
        return _FakeWidget(parent, **kwargs)

    return SimpleNamespace(
        Label=_label,
        Button=_button,
        Checkbutton=_other,
        Radiobutton=_other,
        Frame=_other,
        LabelFrame=_other,
        Scale=_other,
        Spinbox=_other,
        Combobox=_other,
        Entry=_other,
        Separator=_other,
        Notebook=_other,
    )


def _install_fake_ttk(monkeypatch, module, labels, buttons) -> None:
    monkeypatch.setattr(module, "ttk", _fake_ttk(labels, buttons))


def _assert_semantic_labels(labels: list[_FakeWidget], *, first_section: bool = True) -> None:
    assert labels, "expected labels to have been created"
    for label in labels:
        assert "font" not in label.kwargs, label.kwargs
        assert "style" in label.kwargs, label.kwargs
        assert label.kwargs["style"] in theme_metrics.SEMANTIC_LABEL_STYLES, label.kwargs
    if first_section:
        assert labels[0].kwargs["style"] == theme_metrics.SECTION_LABEL_STYLE


def test_settings_sources_use_semantic_styles_not_local_font_tuples() -> None:
    """Pin the UX-05 contract: no local ('Sans', ...) tuples survive."""
    settings_dir = Path(settings_window.__file__).parent
    sources = sorted(
        [settings_dir / "window.py", settings_dir / "navigation.py", settings_dir / "scrollable_area.py"]
        + sorted((settings_dir / "panels").glob("*.py"))
    )
    assert sources, "expected settings sources to exist"
    offenders = [path.name for path in sources if 'font=("Sans"' in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_power_management_panel_uses_section_and_body_styles(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, power_management_panel, labels, buttons)
    power_management_panel.PowerManagementPanel(
        object(),
        var_enabled=_FakeVar(True),
        var_off_suspend=_FakeVar(False),
        var_restore_resume=_FakeVar(False),
        var_off_lid=_FakeVar(False),
        var_restore_lid=_FakeVar(False),
        on_toggle=lambda: None,
    )
    _assert_semantic_labels(labels)
    assert labels[1].kwargs["style"] == theme_metrics.BODY_LABEL_STYLE


def test_power_source_panel_uses_value_styles_for_brightness(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, power_source_panel, labels, buttons)
    power_source_panel.PowerSourcePanel(
        object(),
        var_ac_enabled=_FakeVar(True),
        var_battery_enabled=_FakeVar(False),
        var_ac_brightness=_FakeVar(20.0),
        var_battery_brightness=_FakeVar(10.0),
        var_ac_power_mode=_FakeVar("Balanced"),
        var_battery_power_mode=_FakeVar("Balanced"),
        power_mode_options=("Balanced",),
        on_toggle=lambda: None,
    )
    _assert_semantic_labels(labels)
    styles = [label.kwargs["style"] for label in labels]
    assert theme_metrics.BODY_LABEL_STYLE in styles
    assert theme_metrics.VALUE_LABEL_STYLE in styles


def test_dim_sync_panel_uses_caption_and_value_styles(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, dim_sync_panel, labels, buttons)
    dim_sync_panel.DimSyncPanel(
        object(),
        var_dim_sync_enabled=_FakeVar(True),
        var_dim_sync_mode=_FakeVar("temp"),
        var_dim_temp_brightness=_FakeVar(12.0),
        on_toggle=lambda: None,
    )
    _assert_semantic_labels(labels)
    styles = [label.kwargs["style"] for label in labels]
    assert theme_metrics.CAPTION_LABEL_STYLE in styles
    assert theme_metrics.VALUE_LABEL_STYLE in styles


def test_time_scheduler_panel_uses_body_and_value_styles(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, time_scheduler_panel, labels, buttons)
    time_scheduler_panel.TimeSchedulerPanel(
        object(),
        var_enabled=_FakeVar(True),
        var_day_start=_FakeVar("08:00"),
        var_night_start=_FakeVar("20:00"),
        var_day_base=_FakeVar(40.0),
        var_day_reactive=_FakeVar(50.0),
        var_night_base=_FakeVar(20.0),
        var_night_reactive=_FakeVar(50.0),
        on_toggle=lambda: None,
    )
    _assert_semantic_labels(labels)
    styles = [label.kwargs["style"] for label in labels]
    assert theme_metrics.BODY_LABEL_STYLE in styles
    assert theme_metrics.VALUE_LABEL_STYLE in styles


def test_autostart_and_experimental_panels_use_section_and_body_styles(monkeypatch) -> None:
    for module, factory in (
        (
            autostart_panel,
            lambda: autostart_panel.AutostartPanel(
                object(),
                var_autostart=_FakeVar(True),
                var_os_autostart=_FakeVar(False),
                on_toggle=lambda: None,
            ),
        ),
        (
            experimental_backends_panel,
            lambda: experimental_backends_panel.ExperimentalBackendsPanel(
                object(),
                var_experimental_backends=_FakeVar(False),
                on_toggle=lambda: None,
            ),
        ),
    ):
        labels: list[_FakeWidget] = []
        buttons: list[_FakeWidget] = []
        _install_fake_ttk(monkeypatch, module, labels, buttons)
        factory()
        _assert_semantic_labels(labels)
        assert labels[1].kwargs["style"] == theme_metrics.BODY_LABEL_STYLE


def test_idle_transition_panel_uses_caption_and_value_styles(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, idle_transition_advanced_panel, labels, buttons)
    idle_transition_advanced_panel.IdleTransitionAdvancedPanel(
        object(),
        var_controller_sleep_respect=_FakeVar(False),
        var_debounce_enter=_FakeVar(3.0),
        var_debounce_exit=_FakeVar(5.0),
        var_idle_fade_duration=_FakeVar(0.6),
        on_toggle=lambda: None,
    )
    _assert_semantic_labels(labels)
    styles = [label.kwargs["style"] for label in labels]
    assert theme_metrics.CAPTION_LABEL_STYLE in styles
    assert theme_metrics.VALUE_LABEL_STYLE in styles


def test_version_panel_uses_body_value_and_status_styles(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, version_panel, labels, buttons)
    monkeypatch.setattr(version_panel, "run_in_thread", lambda *args, **kwargs: None)
    root = _FakeWidget()
    version_panel.VersionPanel(object(), root=root, get_status_label=lambda: _FakeWidget())
    _assert_semantic_labels(labels)
    styles = [label.kwargs["style"] for label in labels]
    assert theme_metrics.BODY_LABEL_STYLE in styles
    assert theme_metrics.VALUE_LABEL_STYLE in styles
    assert theme_metrics.STATUS_LABEL_STYLE in styles
    # Version actions stay neutral: no primary/destructive button styling.
    for button in buttons:
        assert button.kwargs.get("style", None) not in theme_metrics.SEMANTIC_BUTTON_STYLES


def test_bottom_bar_panel_uses_status_style_and_neutral_close(monkeypatch) -> None:
    labels: list[_FakeWidget] = []
    buttons: list[_FakeWidget] = []
    _install_fake_ttk(monkeypatch, bottom_bar_panel, labels, buttons)
    panel = bottom_bar_panel.BottomBarPanel(object(), on_close=lambda: None)
    assert len(labels) == 2
    for label in labels:
        assert "font" not in label.kwargs
        assert label.kwargs["style"] == theme_metrics.STATUS_LABEL_STYLE
    assert panel.close_btn.kwargs["text"] == "Close"
    assert "style" not in panel.close_btn.kwargs
