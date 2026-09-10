"""Uniform window color/effect handling, themed UI build, and focus."""

from __future__ import annotations

from types import SimpleNamespace

from keyrgb.gui.theme import focus as theme_focus, metrics as theme_metrics
from keyrgb.gui.windows import (
    _uniform_color_ui as uniform_color_ui,
    uniform,
)
from tests.gui.windows.uniform._uniform_ui_fakes import _FakeColorWheel, _FakeRoot, _FakeWidget


def test_on_color_change_updates_secondary_color_without_touching_keyboard_effect() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    stored: list[tuple[int, int, int]] = []

    class _Config:
        effect = "wave"
        color = (9, 9, 9)

    gui.config = _Config()
    gui._target_is_secondary = True
    gui._secondary_route = SimpleNamespace(state_key="mouse", config_color_attr=None)
    gui._store_secondary_color = lambda color: stored.append(tuple(color))
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = 0.0

    gui._on_color_change(7, 8, 9)

    assert stored == [(7, 8, 9)]
    assert gui.config.effect == "wave"
    assert gui.config.color == (9, 9, 9)


def test_on_color_change_preserves_keyboard_effect_while_updating_base_color() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)

    class _Config:
        effect = "wave"
        color = (1, 2, 3)

    gui.config = _Config()
    gui._target_is_secondary = False
    gui._pending_color = None
    gui._last_drag_commit_ts = 0.0
    gui._last_drag_committed_color = None
    gui._drag_commit_interval = 0.0

    gui._on_color_change(7, 8, 9)

    assert gui.config.effect == "wave"
    assert gui.config.color == (7, 8, 9)


def test_on_apply_preserves_keyboard_effect_when_apply_is_deferred() -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    applied: list[tuple[int, int, int, int]] = []
    statuses: list[tuple[str, bool]] = []

    class _Config:
        effect = "wave"
        color = (1, 2, 3)
        brightness = 25

    gui._color_supported = True
    gui.config = _Config()
    gui._target_is_secondary = False
    gui.color_wheel = SimpleNamespace(get_color=lambda: (4, 5, 6))
    gui._target_label = "Keyboard"
    gui._apply_color = lambda r, g, b, brightness: applied.append((r, g, b, brightness)) or "deferred"
    gui._set_status = lambda msg, *, ok: statuses.append((msg, ok))

    gui._on_apply()

    assert gui.config.effect == "wave"
    assert gui.config.color == (4, 5, 6)
    assert applied == [(4, 5, 6, 25)]
    assert statuses == [("✓ Saved Keyboard RGB(4, 5, 6)", True)]


def test_on_color_release_preserves_keyboard_effect_and_reports_applied_status(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    applied: list[tuple[int, int, int, int]] = []
    statuses: list[tuple[str, bool]] = []

    class _Config:
        effect = "wave"
        color = (1, 2, 3)
        brightness = 40

    gui.config = _Config()
    gui._target_is_secondary = False
    gui._target_label = "Keyboard"
    gui._last_drag_committed_color = None
    gui._last_drag_commit_ts = 0.0
    gui._apply_color = lambda r, g, b, brightness: applied.append((r, g, b, brightness)) or True
    gui._set_status = lambda msg, *, ok: statuses.append((msg, ok))

    monkeypatch.setattr(uniform.time, "monotonic", lambda: 12.5)

    gui._on_color_release(7, 8, 9)

    assert gui.config.effect == "wave"
    assert gui.config.color == (7, 8, 9)
    assert applied == [(7, 8, 9, 40)]
    assert gui._last_drag_committed_color == (7, 8, 9)
    assert gui._last_drag_commit_ts == 12.5
    assert statuses == [("✓ Applied Keyboard RGB(7, 8, 9)", True)]


def _build_ui(color_supported: bool) -> tuple[_FakeRoot, dict[str, list[_FakeWidget]], SimpleNamespace]:
    root = _FakeRoot()
    registry: dict[str, list[_FakeWidget]] = {"frames": [], "labels": [], "buttons": []}

    def _frame(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["frames"].append(widget)
        return widget

    def _label(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["labels"].append(widget)
        return widget

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        registry["buttons"].append(widget)
        return widget

    gui = SimpleNamespace(
        root=root,
        _target_label="Keyboard",
        _color_supported=color_supported,
        _initial_color=lambda: (12, 34, 56),
        _on_color_change=lambda *_args, **_kwargs: None,
        _on_color_release=lambda *_args, **_kwargs: None,
        _on_apply=lambda: None,
        _on_close=lambda: None,
    )

    def _wheel(parent, **kwargs):
        return _FakeColorWheel(parent, **kwargs)

    uniform_color_ui.build_uniform_window_ui(
        gui,
        ttk_module=SimpleNamespace(Frame=_frame, Label=_label, Button=_button),
        color_wheel_cls=_wheel,
        wrap_sync_errors=(RuntimeError,),
        tk_widget_state_errors=(RuntimeError,),
    )
    return root, registry, gui


def test_build_uniform_window_ui_uses_theme_styles_outer_padding_and_primary_apply() -> None:
    _root, registry, gui = _build_ui(color_supported=True)

    assert registry["frames"][0].kwargs.get("padding") == theme_metrics.OUTER_PADDING

    title = registry["labels"][0]
    assert title.kwargs.get("style") == theme_metrics.TITLE_LABEL_STYLE
    assert "font" not in title.kwargs
    assert title.pack_calls[0] == {"pady": (0, theme_metrics.SECTION_GAP_Y)}

    status = registry["labels"][-1]
    assert status.kwargs.get("style") == theme_metrics.STATUS_LABEL_STYLE
    assert "font" not in status.kwargs

    for widget in (*registry["frames"], *registry["labels"], *registry["buttons"]):
        font = widget.kwargs.get("font")
        assert not (isinstance(font, tuple) and font and font[0] == "Sans"), widget.kwargs

    apply_button = registry["buttons"][0]
    close_button = registry["buttons"][1]
    assert apply_button.kwargs.get("style") == theme_metrics.PRIMARY_BUTTON_STYLE
    assert "style" not in close_button.kwargs
    assert apply_button.configure_calls == []
    assert gui._apply_button is apply_button
    assert gui._close_button is close_button


def test_build_uniform_window_ui_styles_unsupported_body_and_disables_apply() -> None:
    _root, registry, gui = _build_ui(color_supported=False)

    assert registry["frames"][0].kwargs.get("padding") == theme_metrics.OUTER_PADDING
    unsupported = registry["labels"][1]
    assert unsupported.kwargs.get("style") == theme_metrics.BODY_LABEL_STYLE
    assert "font" not in unsupported.kwargs
    assert gui.color_wheel is None
    assert registry["buttons"][0].configure_calls == [{"state": "disabled"}]
    assert gui._apply_button is registry["buttons"][0]
    assert gui._close_button is registry["buttons"][1]


def test_schedule_initial_focus_targets_apply_when_enabled(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.root = _FakeRoot()
    gui._color_supported = True
    gui._apply_button = _FakeWidget()
    gui._close_button = _FakeWidget()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(uniform, "schedule_initial_focus", lambda root, target: calls.append((root, target)))

    gui._schedule_initial_focus()

    assert calls == [(gui.root, gui._apply_button)]


def test_schedule_initial_focus_targets_close_when_unsupported(monkeypatch) -> None:
    gui = uniform.UniformColorGUI.__new__(uniform.UniformColorGUI)
    gui.root = _FakeRoot()
    gui._color_supported = False
    gui._apply_button = _FakeWidget()
    gui._close_button = _FakeWidget()
    calls: list[tuple[object, object]] = []
    monkeypatch.setattr(uniform, "schedule_initial_focus", lambda root, target: calls.append((root, target)))

    gui._schedule_initial_focus()

    assert calls == [(gui.root, gui._close_button)]


def test_uniform_initial_focus_is_scheduled_non_forcing() -> None:
    root = _FakeRoot()
    apply_btn = _FakeWidget()
    close_btn = _FakeWidget()
    gui = SimpleNamespace(
        root=root,
        _target_label="Keyboard",
        _color_supported=True,
        _initial_color=lambda: (1, 2, 3),
        _on_color_change=lambda *_args, **_kwargs: None,
        _on_color_release=lambda *_args, **_kwargs: None,
        _on_apply=lambda: None,
        _on_close=lambda: None,
    )

    def _frame(parent=None, **kwargs):
        return _FakeWidget(parent, **kwargs)

    def _label(parent=None, **kwargs):
        return _FakeWidget(parent, **kwargs)

    buttons: list[_FakeWidget] = []

    def _button(parent=None, **kwargs):
        widget = _FakeWidget(parent, **kwargs)
        buttons.append(widget)
        return widget

    uniform_color_ui.build_uniform_window_ui(
        gui,
        ttk_module=SimpleNamespace(Frame=_frame, Label=_label, Button=_button),
        color_wheel_cls=_FakeColorWheel,
        wrap_sync_errors=(RuntimeError,),
        tk_widget_state_errors=(RuntimeError,),
    )
    # Window-level scheduling uses the stored Apply reference.
    uniform.schedule_initial_focus(root, gui._apply_button)
    _ = (apply_btn, close_btn)

    focus_entries = [(delay, cb) for delay, cb in root.after_calls if delay == theme_focus.INITIAL_FOCUS_DELAY_MS]
    assert focus_entries
    focus_entries[0][1]()
    assert gui._apply_button.focus_calls == 1
