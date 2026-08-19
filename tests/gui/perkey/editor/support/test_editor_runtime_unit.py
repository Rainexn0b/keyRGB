"""Direct unit coverage for per-key editor_support.runtime helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from keyrgb.gui.perkey.editor_support import runtime as editor_runtime


class _Scope:
    def __init__(self, value: str = "global") -> None:
        self._value = value

    def get(self) -> str:
        return self._value


class _Status:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def set_status(self, editor: object, message: str) -> None:
        self.messages.append(message)

    def saved_overlay_tweaks_for_key(self, key_id: str) -> str:
        return f"saved-key:{key_id}"

    def saved_overlay_tweaks_global(self) -> str:
        return "saved-global"

    def reset_overlay_tweaks_for_key(self, key_id: str) -> str:
        return f"reset-key:{key_id}"

    def reset_overlay_tweaks_global(self) -> str:
        return "reset-global"

    def auto_synced_overlay_tweaks(self) -> str:
        return "auto-synced"

    def hardware_write_paused(self) -> str:
        return "hw-paused"


def _make_editor(**overrides: Any) -> SimpleNamespace:
    base = {
        "overlay_scope": _Scope("global"),
        "selected_key_id": None,
        "profile_name": "Default",
        "layout_tweaks": {"scale": 1.0},
        "per_key_layout_tweaks": {"esc": {"dx": 1.0}},
        "_physical_layout": "ansi_100",
        "_setup_panel_mode": None,
        "overlay_controls": SimpleNamespace(sync_vars_from_scope=lambda: None),
        "canvas": SimpleNamespace(redraw=lambda: None),
        "config": SimpleNamespace(color=(10, 20, 30)),
        "kb": object(),
        "colors": {(0, 0): (1, 2, 3)},
        "_commit_pipeline": SimpleNamespace(
            commit=lambda **kwargs: (kwargs["kb"], kwargs["colors"]),
        ),
        "_selected_overlay_identity": lambda: None,
        "_get_visible_layout_keys": lambda: ("esc", "a"),
    }
    base.update(overrides)
    editor = SimpleNamespace(**base)
    # Methods need to bind to instance for identity selection tests.
    if not callable(overrides.get("_selected_overlay_identity")):

        def _selected() -> str | None:
            return editor.selected_key_id

        editor._selected_overlay_identity = _selected
    return editor


def test_save_layout_tweaks_saves_per_key_when_key_scope_selected() -> None:
    saved: list[tuple[object, str]] = []
    status = _Status()
    editor = _make_editor(overlay_scope=_Scope("key"), selected_key_id="esc")
    profiles = SimpleNamespace(
        save_layout_per_key=lambda tweaks, name: saved.append((tweaks, name)),
        save_layout_global=lambda *_a: (_ for _ in ()).throw(AssertionError("global")),
    )

    editor_runtime.save_layout_tweaks(editor, profiles=profiles, status=status)

    assert saved == [(editor.per_key_layout_tweaks, "Default")]
    assert status.messages == ["saved-key:esc"]


def test_save_layout_tweaks_saves_global_when_scope_is_global() -> None:
    saved: list[tuple[object, str]] = []
    status = _Status()
    editor = _make_editor()
    profiles = SimpleNamespace(
        save_layout_per_key=lambda *_a: (_ for _ in ()).throw(AssertionError("per-key")),
        save_layout_global=lambda tweaks, name: saved.append((tweaks, name)),
    )

    editor_runtime.save_layout_tweaks(editor, profiles=profiles, status=status)

    assert saved == [(editor.layout_tweaks, "Default")]
    assert status.messages == ["saved-global"]


def test_reset_layout_tweaks_removes_per_key_entry() -> None:
    status = _Status()
    synced: list[str] = []
    redrawn: list[str] = []
    editor = _make_editor(
        overlay_scope=_Scope("key"),
        selected_key_id="esc",
        per_key_layout_tweaks={"esc": {"dx": 2.0}, "a": {"dx": 1.0}},
        overlay_controls=SimpleNamespace(sync_vars_from_scope=lambda: synced.append("sync")),
        canvas=SimpleNamespace(redraw=lambda: redrawn.append("redraw")),
    )

    editor_runtime.reset_layout_tweaks(
        editor,
        get_default_layout_tweaks=lambda _layout: {"scale": 9.0},
        status=status,
    )

    assert "esc" not in editor.per_key_layout_tweaks
    assert editor.per_key_layout_tweaks == {"a": {"dx": 1.0}}
    assert synced == ["sync"]
    assert redrawn == ["redraw"]
    assert status.messages == ["reset-key:esc"]


def test_reset_layout_tweaks_restores_global_defaults() -> None:
    status = _Status()
    editor = _make_editor()
    defaults = {"scale": 2.5, "dx": 0.0}

    editor_runtime.reset_layout_tweaks(
        editor,
        get_default_layout_tweaks=lambda layout: defaults if layout == "ansi_100" else {},
        status=status,
    )

    assert editor.layout_tweaks == defaults
    assert status.messages == ["reset-global"]


def test_auto_sync_per_key_overlays_redraws_and_syncs_when_overlay_panel_open() -> None:
    status = _Status()
    calls: dict[str, object] = {}
    synced: list[str] = []
    redrawn: list[str] = []
    editor = _make_editor(
        _setup_panel_mode="overlay",
        overlay_controls=SimpleNamespace(sync_vars_from_scope=lambda: synced.append("sync")),
        canvas=SimpleNamespace(redraw=lambda: redrawn.append("redraw")),
    )
    overlay = SimpleNamespace(
        auto_sync_per_key_overlays=lambda **kwargs: calls.update(kwargs),
    )

    editor_runtime.auto_sync_per_key_overlays(editor, overlay=overlay, status=status)

    assert calls["layout_tweaks"] == editor.layout_tweaks
    assert calls["per_key_layout_tweaks"] == editor.per_key_layout_tweaks
    assert calls["keys"] == ("esc", "a")
    assert synced == ["sync"]
    assert redrawn == ["redraw"]
    assert status.messages == ["auto-synced"]


def test_auto_sync_per_key_overlays_skips_control_sync_outside_overlay_panel() -> None:
    status = _Status()
    synced: list[str] = []
    editor = _make_editor(
        _setup_panel_mode="keymap",
        overlay_controls=SimpleNamespace(sync_vars_from_scope=lambda: synced.append("sync")),
    )
    overlay = SimpleNamespace(auto_sync_per_key_overlays=lambda **_k: None)

    editor_runtime.auto_sync_per_key_overlays(editor, overlay=overlay, status=status)

    assert synced == []
    assert status.messages == ["auto-synced"]


def test_commit_updates_kb_and_colors_and_reports_paused_hardware() -> None:
    status = _Status()
    prev_kb = object()
    new_colors = {(1, 1): (9, 9, 9)}
    captured: dict[str, object] = {}

    def commit_fn(**kwargs: object) -> tuple[None, dict[tuple[int, int], tuple[int, int, int]]]:
        captured.update(kwargs)
        return None, new_colors

    editor = _make_editor(
        kb=prev_kb,
        colors={(0, 0): (1, 2, 3)},
        _commit_pipeline=SimpleNamespace(commit=commit_fn),
    )
    hardware = SimpleNamespace(NUM_ROWS=6, NUM_COLS=21)
    color_utils = SimpleNamespace(rgb_ints=lambda value: tuple(int(v) for v in value))
    keyboard_apply = SimpleNamespace(push_per_key_colors=object())

    editor_runtime.commit(
        editor,
        force=True,
        hardware=hardware,
        color_utils=color_utils,
        keyboard_apply=keyboard_apply,
        status=status,
        last_non_black_color_or=lambda _editor, fallback: (40, 50, 60),
    )

    assert editor.kb is None
    assert editor.colors == new_colors
    assert captured["force"] is True
    assert captured["num_rows"] == 6
    assert captured["num_cols"] == 21
    assert captured["base_color"] == (40, 50, 60)
    assert captured["fallback_color"] == (10, 20, 30)
    assert captured["push_fn"] is keyboard_apply.push_per_key_colors
    assert status.messages == ["hw-paused"]


def test_commit_does_not_status_when_kb_remains_available() -> None:
    status = _Status()
    kb = object()
    editor = _make_editor(
        kb=kb,
        _commit_pipeline=SimpleNamespace(commit=lambda **_k: (kb, {})),
    )

    editor_runtime.commit(
        editor,
        force=False,
        hardware=SimpleNamespace(NUM_ROWS=1, NUM_COLS=1),
        color_utils=SimpleNamespace(rgb_ints=lambda value: tuple(value)),
        keyboard_apply=SimpleNamespace(push_per_key_colors=None),
        status=status,
        last_non_black_color_or=lambda _e, fallback: fallback,
    )

    assert editor.kb is kb
    assert status.messages == []


def test_load_keymap_sanitizes_profile_payload() -> None:
    editor = _make_editor(profile_name="Night", _physical_layout="iso_105")
    loaded = {"a": ((0, 1),)}
    profiles = SimpleNamespace(
        load_keymap=lambda name, *, physical_layout: loaded if name == "Night" and physical_layout == "iso_105" else {},
    )
    sanitized = {"a": ((0, 1), (0, 2))}
    profile_management = SimpleNamespace(
        sanitize_keymap_cells=lambda keymap, *, num_rows, num_cols: (
            sanitized if keymap is loaded and num_rows == 6 and num_cols == 21 else {}
        ),
    )

    result = editor_runtime.load_keymap(
        editor,
        profiles=profiles,
        profile_management=profile_management,
        hardware=SimpleNamespace(NUM_ROWS=6, NUM_COLS=21),
    )

    assert result == sanitized
