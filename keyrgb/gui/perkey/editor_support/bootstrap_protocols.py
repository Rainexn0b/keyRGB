"""Structural protocols for the per-key editor bootstrap.

Owns the duck-typed Tk/config/canvas ``Protocol`` surface for
``initialize_editor`` so ``bootstrap.py`` stays small. Adds no behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from keyrgb.core.backends.base import KeyboardDevice
from keyrgb.core.config import Config

from ..commit_pipeline import PerKeyCommitPipeline
from ..profile_management import KeyCells, Keymap, PerKeyColors

LayoutTweaks = dict[str, float]
PerKeyLayoutTweaks = dict[str, dict[str, float]]
LayoutSlotOverrides = dict[str, dict[str, object]]
LightbarOverlay = dict[str, bool | float]


class _TkVarProtocol(Protocol):
    def get(self) -> object: ...

    def set(self, value: object) -> None: ...


class _TkRootProtocol(Protocol):
    def title(self, text: str) -> None: ...

    def update_idletasks(self) -> None: ...

    def after(self, delay_ms: int, callback: Callable[..., object]) -> object: ...

    def after_cancel(self, after_id: object) -> None: ...

    def bind(self, sequence: str, func: Callable[..., object], add: object = ...) -> object: ...

    def protocol(self, name: str, func: Callable[..., object]) -> object: ...

    def winfo_screenwidth(self) -> int: ...

    def winfo_screenheight(self) -> int: ...

    def winfo_width(self) -> int: ...

    def winfo_height(self) -> int: ...

    def winfo_x(self) -> int: ...

    def winfo_y(self) -> int: ...

    def winfo_reqwidth(self) -> int: ...

    def winfo_reqheight(self) -> int: ...

    def geometry(self, value: str) -> None: ...

    def minsize(self, width: int, height: int) -> None: ...


class _TkModuleProtocol(Protocol):  # noqa: PYI046 - re-exported via bootstrap
    def Tk(self) -> _TkRootProtocol: ...

    def StringVar(self, value: object = ...) -> _TkVarProtocol: ...

    def BooleanVar(self, value: object = ...) -> _TkVarProtocol: ...

    def DoubleVar(self, value: object = ...) -> _TkVarProtocol: ...


class _ProfilesProtocol(Protocol):  # noqa: PYI046 - re-exported via bootstrap
    def get_active_profile(self) -> str: ...

    def load_backdrop_mode(self, name: str | None = None) -> str: ...

    def load_backdrop_transparency(self, name: str | None = None) -> float: ...

    def load_lightbar_overlay(self, name: str | None = None) -> LightbarOverlay: ...

    def load_secondary_lighting(self, name: str | None = None) -> dict[str, object] | None: ...


class _VisibleLayoutKeyProtocol(Protocol):
    key_id: str
    slot_id: str | None


class _CanvasProtocol(Protocol):
    def redraw(self) -> None: ...


class _PerKeyEditorBootstrapApp(Protocol):  # noqa: PYI046 - re-exported via bootstrap
    _key_size: int
    _key_gap: int
    _key_margin: int
    _wheel_size: int
    _right_panel_width: int
    _resize_job: object | None
    root: _TkRootProtocol
    bg_color: str
    fg_color: str
    config: Config
    profile_name: str
    _physical_layout: str
    _layout_legend_pack: str
    has_lightbar_device: bool
    lightbar_overlay: LightbarOverlay
    secondary_lighting: dict[str, object] | None
    _layout_var: _TkVarProtocol
    _legend_pack_var: _TkVarProtocol
    _backdrop_mode_var: _TkVarProtocol
    backdrop_transparency: _TkVarProtocol
    _backdrop_transparency_save_job: object | None
    _backdrop_transparency_redraw_job: object | None
    _last_non_black_color: tuple[int, int, int]
    colors: PerKeyColors
    keymap: Keymap
    layout_tweaks: LayoutTweaks
    per_key_layout_tweaks: PerKeyLayoutTweaks
    layout_slot_overrides: LayoutSlotOverrides
    overlay_scope: _TkVarProtocol
    apply_all_keys: _TkVarProtocol
    sample_tool_enabled: _TkVarProtocol
    _sample_tool_has_sampled: bool
    _setup_panel_mode: str | None
    _profile_name_var: _TkVarProtocol
    _ac_power_source_profile_var: _TkVarProtocol
    _battery_power_source_profile_var: _TkVarProtocol
    selected_key_id: str | None
    selected_slot_id: str | None
    selected_cells: KeyCells
    selected_cell: tuple[int, int] | None
    _commit_pipeline: PerKeyCommitPipeline
    kb: KeyboardDevice | None
    canvas: _CanvasProtocol

    def _on_close(self) -> None: ...

    def _save_profile(self) -> None: ...

    def _detect_lightbar_device(self) -> bool: ...

    def _load_keymap(self) -> Keymap: ...

    def _load_layout_tweaks(self) -> LayoutTweaks: ...

    def _load_per_key_layout_tweaks(self) -> PerKeyLayoutTweaks: ...

    def _load_layout_slot_overrides(self) -> LayoutSlotOverrides: ...

    def _get_visible_layout_keys(self) -> Sequence[_VisibleLayoutKeyProtocol]: ...

    def select_slot_id(self, slot_id: str) -> None: ...
