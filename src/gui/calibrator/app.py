from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from PIL import Image, ImageTk

from src.core.config import Config
from src.core.profile import profiles
from src.core.resources.defaults import get_default_keymap
from src.core.resources.layout_legends import load_layout_legend_pack
from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef, get_layout_keys
from src.core.resources.layouts import LAYOUT_CATALOG, resolve_layout_id
from src.gui.perkey.hardware import NUM_ROWS as BACKEND_NUM_ROWS, NUM_COLS as BACKEND_NUM_COLS
from src.gui.perkey.profile_management import keymap_cells_for, sanitize_keymap_cells
from .helpers.canvas_render import redraw_calibration_canvas
from .helpers.geometry import hit_test
from .helpers.probe import CalibrationProbeState
from src.gui.utils.profile_backdrop_storage import (
    load_backdrop_image,
    reset_backdrop_image,
    save_backdrop_image,
)
from src.gui.utils.deck_render_cache import DeckRenderCache
from .helpers.keyboard_preview import KeyboardPreviewSession
from .helpers.profile_storage import (
    get_active_profile_name,
    keymap_path,
    load_keymap,
    load_layout_global,
    load_layout_per_key,
    load_layout_slots,
    save_keymap,
)

from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme
from src.gui.reference.overlay_geometry import (
    CanvasTransform,
)


MATRIX_ROWS = BACKEND_NUM_ROWS
MATRIX_COLS = BACKEND_NUM_COLS
KeyCell = Tuple[int, int]
KeyCells = Tuple[KeyCell, ...]
Keymap = Dict[str, KeyCells]
_LAYOUT_LABELS = {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}
_BACKDROP_MODE_LABELS = {
    "none": "No backdrop",
    "builtin": "Built-in seed",
    "custom": "Custom image",
}
_TK_RUNTIME_ERRORS = (tk.TclError, RuntimeError)
_WRAP_SYNC_ERRORS = _TK_RUNTIME_ERRORS + (TypeError, ValueError)
_BACKDROP_UPDATE_ERRORS = _TK_RUNTIME_ERRORS + (OSError, TypeError, ValueError)


def _keymap_path() -> Path:
    # Store keymaps per active profile.
    return keymap_path(get_active_profile_name())


def _save_keymap(keymap: Keymap, *, physical_layout: str | None = None) -> None:
    # Use shared saver to keep behavior consistent with per-key UI.
    save_keymap(get_active_profile_name(), keymap, physical_layout=physical_layout)


def _parse_default_keymap(layout_id: str) -> Keymap:
    return sanitize_keymap_cells(
        profiles.normalize_keymap(get_default_keymap(layout_id), physical_layout=layout_id),
        num_rows=MATRIX_ROWS,
        num_cols=MATRIX_COLS,
    )


def _resolved_layout_label(layout_id: str) -> str:
    resolved_layout = resolve_layout_id(layout_id)
    return _LAYOUT_LABELS.get(resolved_layout, resolved_layout.upper())


def _load_profile_state(
    profile_name: str,
    *,
    physical_layout: str,
) -> tuple[
    Keymap,
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, Dict[str, object]],
]:
    keymap = sanitize_keymap_cells(
        load_keymap(profile_name, physical_layout=physical_layout),
        num_rows=MATRIX_ROWS,
        num_cols=MATRIX_COLS,
    )
    layout_tweaks = load_layout_global(profile_name, physical_layout=physical_layout)
    per_key_layout_tweaks = load_layout_per_key(profile_name, physical_layout=physical_layout)
    layout_slot_overrides = load_layout_slots(profile_name, physical_layout)
    return keymap, layout_tweaks, per_key_layout_tweaks, layout_slot_overrides


def _selected_layout_legend_pack(cfg: object, *, physical_layout: str) -> str | None:
    requested = str(getattr(cfg, "layout_legend_pack", "auto") or "auto").strip().lower()
    if not requested or requested == "auto":
        return None

    pack = load_layout_legend_pack(requested)
    if not pack:
        return None

    resolved_pack_layout = str(pack.get("layout_id") or physical_layout).strip().lower()
    return requested if resolved_pack_layout == str(physical_layout or "auto").strip().lower() else None


def _physical_layout_id(app: object) -> str:
    cfg = getattr(app, "cfg", None)
    return str(getattr(cfg, "physical_layout", "auto") or "auto")


def _visible_layout_keys(app: object) -> list[KeyDef]:
    physical_layout = _physical_layout_id(app)
    cfg = getattr(app, "cfg", None)
    return list(
        get_layout_keys(
            physical_layout,
            legend_pack_id=_selected_layout_legend_pack(cfg, physical_layout=physical_layout)
            if cfg is not None
            else None,
            slot_overrides=getattr(app, "layout_slot_overrides", None),
        )
    )


def _visible_key_for_slot_id(app: object, slot_id: str | None) -> KeyDef | None:
    normalized_slot_id = str(slot_id or "").strip()
    if not normalized_slot_id:
        return None

    for key in _visible_layout_keys(app):
        if str(getattr(key, "slot_id", None) or key.key_id) == normalized_slot_id:
            return key
    return None


def _probe_selected_slot_id(app: object) -> str | None:
    probe = getattr(app, "probe", None)
    selected_slot_id = str(getattr(probe, "selected_slot_id", "") or "").strip()
    if selected_slot_id:
        return selected_slot_id

    selected_key_id = str(getattr(probe, "selected_key_id", "") or "").strip()
    if not selected_key_id:
        return None

    for key in _visible_layout_keys(app):
        if str(key.key_id) == selected_key_id:
            return str(getattr(key, "slot_id", None) or key.key_id)
    return selected_key_id


def _probe_selected_key_id(app: object) -> str | None:
    slot_id = _probe_selected_slot_id(app)
    key = _visible_key_for_slot_id(app, slot_id)
    if key is not None:
        return str(key.key_id)

    probe = getattr(app, "probe", None)
    selected_key_id = str(getattr(probe, "selected_key_id", "") or "").strip()
    return selected_key_id or None


class KeymapCalibrator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator")
        apply_keyrgb_window_icon(self)

        # Avoid flashing a tiny default-sized window while widgets/images load.
        try:
            self.withdraw()
        except _TK_RUNTIME_ERRORS:
            pass

        self.bg_color, self.fg_color = apply_clam_theme(self)

        self.cfg = Config()
        self.preview = KeyboardPreviewSession(self.cfg, rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.profile_name = get_active_profile_name()
        (
            self.keymap,
            self.layout_tweaks,
            self.per_key_layout_tweaks,
            self.layout_slot_overrides,
        ) = _load_profile_state(
            self.profile_name,
            physical_layout=str(self.cfg.physical_layout or "auto"),
        )

        self.probe = CalibrationProbeState(rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self._deck_pil: Optional[Image.Image] = None
        self._deck_tk: Optional[ImageTk.PhotoImage] = None
        self._deck_render_cache: DeckRenderCache[ImageTk.PhotoImage] = DeckRenderCache()
        self._transform: Optional[CanvasTransform] = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=16)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(root, background=self.bg_color, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<Button-1>", self._on_click)

        side = ttk.Frame(root, padding=0)
        side.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        side.columnconfigure(0, weight=1)

        title = ttk.Label(side, text="Keymap Calibrator", font=("Sans", 14, "bold"), anchor="w")
        title.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.lbl_cell = ttk.Label(side, text="", font=("Sans", 9), anchor="w")
        self.lbl_cell.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        self.lbl_status = ttk.Label(
            side,
            text=(
                "Step 1: look at the lit key on the keyboard\n"
                "Step 2: click that key on the image\n"
                "Step 3: click 'Assign selected key' (or press Enter)"
            ),
            anchor="w",
            justify="left",
        )
        self.lbl_status.grid(row=2, column=0, sticky="ew", pady=(0, 12))

        def _sync_side_wrap(_e=None) -> None:
            try:
                w = int(side.winfo_width())
                self.lbl_status.configure(wraplength=max(220, w - 8))
            except _WRAP_SYNC_ERRORS:
                return

        try:
            side.bind("<Configure>", _sync_side_wrap, add=True)
        except _TK_RUNTIME_ERRORS:
            pass
        self.after(0, _sync_side_wrap)

        btns = ttk.Frame(side)
        btns.grid(row=3, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Prev", command=self._prev).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Next", command=self._next).grid(row=0, column=1, sticky="ew")

        ttk.Button(side, text="Assign selected key", command=self._assign).grid(
            row=4, column=0, sticky="ew", pady=(10, 0)
        )
        ttk.Button(side, text="Skip (nothing lit)", command=self._skip).grid(row=5, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(side, text="Set Backdrop...", command=self._set_backdrop).grid(
            row=6, column=0, sticky="ew", pady=(18, 0)
        )
        ttk.Label(side, text="Backdrop mode", anchor="w", justify="left").grid(
            row=7, column=0, sticky="ew", pady=(10, 0)
        )
        self._backdrop_mode_var = tk.StringVar(value=profiles.load_backdrop_mode(self.profile_name))
        self._backdrop_mode_combo = ttk.Combobox(
            side,
            state="readonly",
            width=20,
            values=[_BACKDROP_MODE_LABELS[mode] for mode in ("none", "builtin", "custom")],
        )
        self._backdrop_mode_combo.set(_BACKDROP_MODE_LABELS.get(self._backdrop_mode_var.get(), "Built-in seed"))
        self._backdrop_mode_combo.grid(row=8, column=0, sticky="ew", pady=(6, 0))
        self._backdrop_mode_combo.bind("<<ComboboxSelected>>", self._on_backdrop_mode_changed)
        ttk.Button(side, text="Reset Backdrop", command=self._reset_backdrop).grid(
            row=9, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(side, text="Reset Keymap Defaults", command=self._reset_keymap_defaults).grid(
            row=10, column=0, sticky="ew", pady=(18, 0)
        )
        ttk.Button(side, text="Save", command=self._save).grid(row=11, column=0, sticky="ew", pady=(18, 0))
        ttk.Button(side, text="Save && Close", command=self._save_and_close).grid(
            row=12, column=0, sticky="ew", pady=(6, 0)
        )

        # Keyboard shortcuts.
        self.bind("<Return>", lambda _e: self._assign())
        self.bind("<KP_Enter>", lambda _e: self._assign())
        self.bind("<Right>", lambda _e: self._next())
        self.bind("<Left>", lambda _e: self._prev())
        self.bind("<Escape>", lambda _e: self.destroy())

        # Size to screen so all controls fit.
        self.update_idletasks()
        sw = int(self.winfo_screenwidth())
        sh = int(self.winfo_screenheight())
        w = min(1400, int(sw * 0.95))
        h = min(860, int(sh * 0.95))
        self.geometry(f"{w}x{h}")
        self.minsize(min(1100, w), min(650, h))

        def _finish_init() -> None:
            self._load_deck_image()
            self._apply_current_probe()
            self._redraw()
            try:
                self.deiconify()
                self.lift()
            except _TK_RUNTIME_ERRORS:
                pass

        # Defer image load/draw until after geometry is applied.
        self.after(0, _finish_init)

    def _set_backdrop(self) -> None:
        path = filedialog.askopenfilename(
            title="Select keyboard backdrop image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            save_backdrop_image(profile_name=self.profile_name, source_path=path)
            profiles.save_backdrop_mode("custom", self.profile_name)
            self._backdrop_mode_var.set("custom")
            self._backdrop_mode_combo.set("Custom image")
            self._load_deck_image()
            self._redraw()
            self.lbl_status.configure(text="Backdrop updated")
        except _BACKDROP_UPDATE_ERRORS:
            self.lbl_status.configure(text="Failed to set backdrop")

    def _reset_backdrop(self) -> None:
        try:
            reset_backdrop_image(self.profile_name)
            profiles.save_backdrop_mode("builtin", self.profile_name)
            self._backdrop_mode_var.set("builtin")
            self._backdrop_mode_combo.set("Built-in seed")
            self._load_deck_image()
            self._redraw()
            self.lbl_status.configure(text="Backdrop reset")
        except _BACKDROP_UPDATE_ERRORS:
            self.lbl_status.configure(text="Failed to reset backdrop")

    def _on_backdrop_mode_changed(self, _event=None) -> None:
        label = self._backdrop_mode_combo.get()
        for mode, mode_label in _BACKDROP_MODE_LABELS.items():
            if mode_label == label:
                self._backdrop_mode_var.set(mode)
                break
        else:
            self._backdrop_mode_var.set("builtin")

        try:
            profiles.save_backdrop_mode(self._backdrop_mode_var.get(), self.profile_name)
            self._load_deck_image()
            self._redraw()
        except _BACKDROP_UPDATE_ERRORS:
            self.lbl_status.configure(text="Failed to update backdrop mode")

    def _reset_keymap_defaults(self) -> None:
        physical_layout = _physical_layout_id(self)
        self.keymap = sanitize_keymap_cells(
            _parse_default_keymap(physical_layout),
            num_rows=MATRIX_ROWS,
            num_cols=MATRIX_COLS,
        )
        self._redraw()
        self.lbl_status.configure(text=f"Reset keymap to {_resolved_layout_label(physical_layout)} defaults")

    def _restore_original_config(self) -> None:
        self.preview.restore()

    def _on_close(self) -> None:
        self._restore_original_config()
        self.destroy()

    def _load_deck_image(self) -> None:
        # Prefer per-profile custom backdrop; fall back to default asset.
        self._deck_pil = load_backdrop_image(self.profile_name)
        self._deck_render_cache.clear()

    def _apply_current_probe(self) -> None:
        r, c = self.probe.current_cell
        self.lbl_cell.configure(text=f"Probing matrix cell: ({r}, {c})")
        self.preview.apply_probe_cell(r, c)
        # Give the tray poller a moment to apply.
        self.after(50, lambda: None)

    def _prev(self) -> None:
        self.probe.prev_cell()
        self._apply_current_probe()

    def _next(self) -> None:
        self.probe.next_cell()
        self._apply_current_probe()

    def _skip(self) -> None:
        # Explicitly record "no key" by just moving on.
        self.probe.clear_selection()
        self.lbl_status.configure(text="Skipped. Move to next cell.")
        self._next()

    def _assign(self) -> None:
        slot_id = _probe_selected_slot_id(self)
        key_id = _probe_selected_key_id(self)
        if not slot_id and not key_id:
            self.lbl_status.configure(text="Select a key on the image first")
            return
        key_identity = str(slot_id or key_id)
        display_key_id = str(key_id or key_identity)
        cells = list(
            keymap_cells_for(
                self.keymap,
                display_key_id,
                slot_id=slot_id,
                physical_layout=_physical_layout_id(self),
            )
        )
        if self.probe.current_cell not in cells:
            cells.append(self.probe.current_cell)
        self.keymap[key_identity] = tuple(cells)
        self.lbl_status.configure(text=f"Assigned {display_key_id} -> {self.probe.current_cell} ({len(cells)} cell(s))")
        self._redraw()
        self._next()

    def _save(self) -> None:
        _save_keymap(self.keymap, physical_layout=_physical_layout_id(self))
        self.lbl_status.configure(text=f"Saved to {str(_keymap_path())}")

    def _save_and_close(self) -> None:
        self._save()
        self._restore_original_config()
        self.destroy()

    def _redraw(self) -> None:
        self._transform, self._deck_tk = redraw_calibration_canvas(
            canvas=self.canvas,
            deck_pil=self._deck_pil,
            deck_render_cache=self._deck_render_cache,
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            keymap=self.keymap,
            selected_slot_id=_probe_selected_slot_id(self),
            selected_key_id=_probe_selected_key_id(self),
            physical_layout=_physical_layout_id(self),
            legend_pack_id=_selected_layout_legend_pack(self.cfg, physical_layout=_physical_layout_id(self)),
            slot_overrides=self.layout_slot_overrides,
        )

    def _on_click(self, e: tk.Event) -> None:
        if self._transform is None:
            return
        x = e.x
        y = e.y
        hit = self._hit_test(x, y)
        if hit is None:
            self.probe.clear_selection()
            self.lbl_status.configure(text="No key hit")
        else:
            self.probe.selected_slot_id = str(getattr(hit, "slot_id", None) or hit.key_id)
            self.probe.selected_key_id = str(hit.key_id)
            mapped = keymap_cells_for(
                self.keymap,
                hit.key_id,
                slot_id=self.probe.selected_slot_id,
                physical_layout=_physical_layout_id(self),
            )
            self.lbl_status.configure(
                text=f"Selected {hit.label}" + (f" (mapped {mapped})" if mapped else " (unmapped)")
            )
        self._redraw()

    def _hit_test(self, x: int, y: int) -> Optional[KeyDef]:
        if self._transform is None:
            return None

        return hit_test(
            transform=self._transform,
            x=x,
            y=y,
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            keys=_visible_layout_keys(self),
            image_size=BASE_IMAGE_SIZE,
        )


def main() -> None:
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator()
    app.mainloop()


if __name__ == "__main__":
    main()
