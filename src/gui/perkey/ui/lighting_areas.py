"""Lighting areas panel for the main per-key profile editor."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Callable, cast

from src.core.secondary_device_runtime import iter_effective_secondary_routes

from ..secondary_lighting import SecondaryLightingArea, SecondaryLightingDraft
from .status import set_status

if TYPE_CHECKING:
    from ..editor import PerKeyEditor


_UI_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError, tk.TclError)
_KEYBOARD_TARGET = "keyboard"


def _hex_color(color: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % color


def _rgb_text(color: tuple[int, int, int]) -> str:
    return f"RGB: {color[0]}, {color[1]}, {color[2]}"


class LightingAreasPanel:
    """Edit profile-owned secondary route state without touching keyboard cells."""

    def __init__(self, parent, *, editor: PerKeyEditor, tk_module=tk, ttk_module=ttk, **kwargs) -> None:
        self._tk = tk_module
        self._ttk = ttk_module
        self._frame = ttk_module.LabelFrame(parent, text="Lighting areas", padding=10, **kwargs)
        self.editor = editor
        self._rows: dict[str, dict[str, object]] = {}
        self._selection = tk_module.StringVar(value=_KEYBOARD_TARGET)
        self._should_show = False
        self._hint_label = ttk_module.Label(self._frame, text="Select an area to edit it with the colour wheel.")
        self._simulation_label = ttk_module.Label(
            self._frame, text="Simulation: no hardware access", foreground="#f5c542"
        )
        self._empty_label = ttk_module.Label(self._frame, text="No secondary lighting areas detected.")
        self._frame.columnconfigure(0, weight=1)
        self.sync_from_editor()

    def grid(self, **kwargs: object) -> None:
        self._frame.grid(**kwargs)

    def grid_remove(self) -> None:
        self._frame.grid_remove()

    @property
    def should_show(self) -> bool:
        return self._should_show

    @property
    def draft(self) -> SecondaryLightingDraft:
        current = getattr(self.editor, "secondary_lighting", None)
        draft = vars(self).get("_draft")
        if not isinstance(draft, SecondaryLightingDraft):
            draft = SecondaryLightingDraft(current, config=getattr(self.editor, "config", None))
            self._draft = draft
        return draft

    def _set_draft(self, draft: SecondaryLightingDraft) -> None:
        self._draft = draft
        self.editor.secondary_lighting = draft.payload

    def _clear_rows(self) -> None:
        for widgets in self._rows.values():
            frame = widgets.get("frame")
            destroy = getattr(frame, "destroy", None)
            if callable(destroy):
                destroy()
        self._rows.clear()

    def sync_from_editor(self) -> None:
        effective = iter_effective_secondary_routes(include_unavailable=True)
        draft = SecondaryLightingDraft(
            getattr(self.editor, "secondary_lighting", None),
            config=getattr(self.editor, "config", None),
            effective_routes=effective,
        )
        self._draft = draft
        self.editor.secondary_lighting = draft.payload
        self._clear_rows()
        for widget in (self._hint_label, self._simulation_label, self._empty_label):
            widget.grid_remove()

        available = [area for area in draft.areas() if area.available]
        if not available:
            self._empty_label.grid(row=0, column=0, sticky="w")
            self._should_show = False
            self.grid_remove()
            return

        self._should_show = True
        self.grid()
        self._selection.set(_KEYBOARD_TARGET)
        self._hint_label.grid(row=0, column=0, sticky="w", pady=(0, 8))
        row = 1
        self._ttk.Radiobutton(
            self._frame,
            text="Keyboard keys",
            variable=self._selection,
            value=_KEYBOARD_TARGET,
            command=self.select_keyboard,
        ).grid(row=row, column=0, sticky="w", pady=(0, 8))
        row += 1
        if any(area.simulated for area in available):
            self._simulation_label.grid(row=row, column=0, sticky="w", pady=(0, 8))
            row += 1
        saved_areas = draft.payload.get("areas")
        saved_keys = saved_areas.keys() if isinstance(saved_areas, dict) else ()
        for area in draft.areas():
            if area.available or area.state_key in saved_keys:
                self._build_row(row, area)
                row += 1

    def _build_row(self, row: int, area: SecondaryLightingArea) -> None:
        frame = self._ttk.Frame(self._frame)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(2, weight=1)
        enabled = self._tk.BooleanVar(value=area.enabled)
        preview = self._tk.Canvas(frame, width=26, height=22, highlightthickness=1)
        preview.grid(row=0, column=3, padx=(8, 4))
        preview.create_rectangle(2, 2, 24, 20, fill=_hex_color(area.color), outline="")
        select_callback = cast(
            Callable[[], object],
            lambda key=area.state_key: self._select_area(key),
        )
        enabled_callback = cast(
            Callable[[], object],
            lambda key=area.state_key, var=enabled: self._enabled_changed(key, var),
        )
        self._ttk.Radiobutton(
            frame,
            variable=self._selection,
            value=area.state_key,
            command=select_callback,
        ).grid(row=0, column=0, sticky="w")
        self._ttk.Checkbutton(
            frame,
            text="Enabled",
            variable=enabled,
            command=enabled_callback,
        ).grid(row=0, column=1, sticky="w", padx=(4, 12))
        self._ttk.Label(
            frame,
            text=area.display_name,
        ).grid(row=0, column=2, sticky="w")
        color_label = self._ttk.Label(
            frame,
            text=_rgb_text(area.color),
        )
        color_label.grid(row=0, column=4, sticky="e")
        if area.simulated:
            self._ttk.Label(frame, text="simulated").grid(row=0, column=5, sticky="e", padx=(8, 0))
        self._rows[area.state_key] = {
            "frame": frame,
            "enabled": enabled,
            "preview": preview,
            "color_label": color_label,
        }

    def _enabled_changed(self, state_key: str, variable: object) -> None:
        try:
            value = bool(variable.get())  # type: ignore[attr-defined]
            self.draft.set_enabled(state_key, value)
            self._set_draft(self.draft)
            set_status(self.editor, f"{state_key} {'enabled' if value else 'disabled'}")
        except _UI_ERRORS as exc:
            set_status(self.editor, f"Failed to update {state_key}: {exc}")

    def _select_area(self, state_key: str) -> None:
        area = next((item for item in self.draft.areas() if item.state_key == state_key), None)
        if area is None:
            return
        try:
            self.editor.color_wheel.set_color(*area.color)
            set_status(self.editor, f"Editing {area.display_name} with the colour wheel")
        except _UI_ERRORS as exc:
            set_status(self.editor, f"Failed to select {area.display_name}: {exc}")

    def select_keyboard(self) -> None:
        """Return the shared wheel to its normal keyboard-key target."""

        self._selection.set(_KEYBOARD_TARGET)
        selected_identity = getattr(self.editor, "selected_slot_id", None) or getattr(
            self.editor, "selected_key_id", None
        )
        finalize_selection = getattr(self.editor, "_finalize_selection", None)
        if selected_identity and callable(finalize_selection):
            finalize_selection(str(selected_identity))
            return
        fallback = tuple(getattr(self.editor, "_last_non_black_color", (255, 0, 0)))
        self.editor.color_wheel.set_color(*fallback)
        set_status(self.editor, "Keyboard selected — click a key to edit it")

    def apply_wheel_color(self, color: tuple[int, int, int], *, released: bool) -> bool:
        """Apply the shared wheel to the selected area, if one is selected."""

        state_key = str(self._selection.get() or "").strip()
        if not state_key or state_key == _KEYBOARD_TARGET:
            return False
        area = next((item for item in self.draft.areas() if item.state_key == state_key), None)
        if area is None:
            self.select_keyboard()
            return False
        normalized = self.draft.set_color(state_key, color)
        self._set_draft(self.draft)
        self._refresh_row_color(state_key, normalized)
        if normalized != (0, 0, 0):
            self.editor._last_non_black_color = normalized
        if released:
            set_status(self.editor, f"Updated {area.display_name} colour")
        return True

    def _refresh_row_color(self, state_key: str, color: tuple[int, int, int]) -> None:
        widgets = self._rows.get(state_key)
        if not widgets:
            return
        preview = widgets.get("preview")
        delete = getattr(preview, "delete", None)
        create_rectangle = getattr(preview, "create_rectangle", None)
        if callable(delete) and callable(create_rectangle):
            delete("all")
            create_rectangle(2, 2, 24, 20, fill=_hex_color(color), outline="")
        color_label = widgets.get("color_label")
        configure = getattr(color_label, "configure", None)
        if callable(configure):
            configure(text=_rgb_text(color))


__all__ = ["LightingAreasPanel"]
