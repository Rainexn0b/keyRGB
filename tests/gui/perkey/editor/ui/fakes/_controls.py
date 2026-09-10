"""Fake editor panels and editor double for per-key editor UI tests."""

from __future__ import annotations

from types import SimpleNamespace

from tests.gui.perkey.editor.ui.fakes._widgets import _FakeRoot, _FakeVar


class _FakeLayoutSetupControls:
    def __init__(self, parent=None, *, editor):
        self.parent = parent
        self.editor = editor
        self.grid_calls = []
        self.grid_remove_calls = 0
        self.pack_calls = []

    def grid(self, **kwargs) -> None:
        self.grid_calls.append(dict(kwargs))

    def grid_remove(self) -> None:
        self.grid_remove_calls += 1

    def pack(self, **kwargs) -> None:
        self.pack_calls.append(dict(kwargs))


class _FakeLightingAreasPanel(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor, tk_module=None, ttk_module=None, **kwargs):
        super().__init__(parent, editor=editor)
        import os as _os

        forced = getattr(editor, "_force_lighting_areas_visible", None)
        if forced is not None:
            self._should_show = bool(forced)
        else:
            self._should_show = _os.environ.get("KEYRGB_SIMULATE_SECONDARY_DEVICES") == "1"
        # Mirror production LightingAreasPanel._grid_options: grid() with no
        # args re-applies the canonical options instead of row 0 / col 0.
        self._grid_options: dict[str, object] = {}

    @property
    def should_show(self) -> bool:
        return bool(self._should_show)

    def grid(self, **kwargs) -> None:
        if kwargs:
            self._grid_options = dict(kwargs)
        self.grid_calls.append(dict(self._grid_options))

    def record_hidden_placement(self, options) -> None:
        self._grid_options = dict(options)


class _FakeOverlayControls(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor):
        super().__init__(parent, editor=editor)
        self.sync_calls = 0

    def sync_vars_from_scope(self) -> None:
        self.sync_calls += 1


class _FakeOptionalKeysControls(_FakeLayoutSetupControls):
    pass


class _FakeLightbarControls(_FakeLayoutSetupControls):
    def __init__(self, parent=None, *, editor):
        super().__init__(parent, editor=editor)
        self.sync_calls = 0

    def sync_vars_from_editor(self) -> None:
        self.sync_calls += 1


class _FakeEditor:
    def __init__(self, root: _FakeRoot):
        self.root = root
        self.bg_color = "#202020"
        self.fg_color = "#efefef"
        self._right_panel_width = 320
        self._backdrop_mode_var = _FakeVar("builtin")
        self.backdrop_transparency = _FakeVar(45)
        self._last_non_black_color = (10, 20, 30)
        self._wheel_size = 180
        self.apply_all_keys = _FakeVar(False)
        self.sample_tool_enabled = _FakeVar(True)
        self._profile_name_var = _FakeVar("gaming")
        self.config = SimpleNamespace(ac_perkey_profile_name="movie", battery_perkey_profile_name=None)
        self._ac_power_source_profile_var = _FakeVar("movie")
        self._battery_power_source_profile_var = _FakeVar("Keep current profile")
        self._save_power_source_profile_policy_calls = 0
        self._on_backdrop_mode_changed_calls = 0
        self._setup_panel_mode: str | None = None
        self._show_setup_panel_calls: list[str] = []

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        self._on_backdrop_mode_changed_calls += 1

    def _set_backdrop(self) -> None:
        return None

    def _reset_backdrop(self) -> None:
        return None

    def _on_backdrop_transparency_changed(self, _value=None) -> None:
        return None

    def _on_color_change(self, *_args) -> None:
        return None

    def _on_color_release(self, *_args) -> None:
        return None

    def _on_sample_tool_toggled(self) -> None:
        return None

    def _fill_all(self) -> None:
        return None

    def _clear_all(self) -> None:
        return None

    def _toggle_layout_setup(self) -> None:
        return None

    def _toggle_overlay(self) -> None:
        return None

    def _hide_setup_panel(self) -> None:
        return None

    def _show_setup_panel(self, mode: str) -> None:
        self._setup_panel_mode = str(mode)
        self._show_setup_panel_calls.append(str(mode))

    def _run_calibrator(self) -> None:
        return None

    def _open_guided_setup(self) -> None:
        return None

    def _reload_keymap(self) -> None:
        return None

    def _new_profile(self) -> None:
        return None

    def _activate_profile(self) -> None:
        return None

    def _save_profile(self) -> None:
        return None

    def _delete_profile(self) -> None:
        return None

    def _set_default_profile(self) -> None:
        return None

    def _save_power_source_profile_policy(self) -> None:
        self._save_power_source_profile_policy_calls += 1
