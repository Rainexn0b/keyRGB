from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from PIL import Image, ImageTk

from src.core.config import Config
from src.core.resources.defaults import get_default_keymap
from src.core.resources.layout import BASE_IMAGE_SIZE, KeyDef, get_layout_keys
from src.core.resources.layouts import LAYOUT_CATALOG, resolve_layout_id
from src.gui.perkey.hardware import NUM_ROWS as BACKEND_NUM_ROWS, NUM_COLS as BACKEND_NUM_COLS
from src.gui.perkey.profile_management import sanitize_keymap_cells
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
_LAYOUT_LABELS = {layout.layout_id: layout.label for layout in LAYOUT_CATALOG}


def _keymap_path() -> Path:
    # Store keymaps per active profile.
    return keymap_path(get_active_profile_name())


def _save_keymap(keymap: Dict[str, Tuple[int, int]]) -> None:
    # Use shared saver to keep behavior consistent with per-key UI.
    save_keymap(get_active_profile_name(), keymap)


def _parse_default_keymap(layout_id: str) -> dict[str, tuple[int, int]]:
    parsed: dict[str, tuple[int, int]] = {}
    for key_id, coord_text in get_default_keymap(layout_id).items():
        try:
            row_text, col_text = coord_text.split(",", 1)
            parsed[key_id] = (int(row_text.strip()), int(col_text.strip()))
        except (AttributeError, TypeError, ValueError):
            continue
    return parsed


def _resolved_layout_label(layout_id: str) -> str:
    resolved_layout = resolve_layout_id(layout_id)
    return _LAYOUT_LABELS.get(resolved_layout, resolved_layout.upper())


def _load_profile_state(
    profile_name: str,
    *,
    physical_layout: str,
) -> tuple[
    Dict[str, Tuple[int, int]],
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


class KeymapCalibrator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator")
        apply_keyrgb_window_icon(self)

        # Avoid flashing a tiny default-sized window while widgets/images load.
        try:
            self.withdraw()
        except Exception:
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
            except Exception:
                return

        try:
            side.bind("<Configure>", _sync_side_wrap, add=True)
        except Exception:
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
        ttk.Button(side, text="Reset Backdrop", command=self._reset_backdrop).grid(
            row=7, column=0, sticky="ew", pady=(6, 0)
        )
        ttk.Button(side, text="Reset Keymap Defaults", command=self._reset_keymap_defaults).grid(
            row=8, column=0, sticky="ew", pady=(18, 0)
        )
        ttk.Button(side, text="Save", command=self._save).grid(row=9, column=0, sticky="ew", pady=(18, 0))
        ttk.Button(side, text="Save && Close", command=self._save_and_close).grid(
            row=10, column=0, sticky="ew", pady=(6, 0)
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
            except Exception:
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
            self._load_deck_image()
            self._redraw()
            self.lbl_status.configure(text="Backdrop updated")
        except Exception:
            self.lbl_status.configure(text="Failed to set backdrop")

    def _reset_backdrop(self) -> None:
        try:
            reset_backdrop_image(self.profile_name)
            self._load_deck_image()
            self._redraw()
            self.lbl_status.configure(text="Backdrop reset")
        except Exception:
            self.lbl_status.configure(text="Failed to reset backdrop")

    def _reset_keymap_defaults(self) -> None:
        physical_layout = str(self.cfg.physical_layout or "auto")
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
        if not self.probe.selected_key_id:
            self.lbl_status.configure(text="Select a key on the image first")
            return
        self.keymap[self.probe.selected_key_id] = self.probe.current_cell
        self.lbl_status.configure(text=f"Assigned {self.probe.selected_key_id} -> {self.probe.current_cell}")
        self._redraw()
        self._next()

    def _save(self) -> None:
        _save_keymap(self.keymap)
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
            selected_key_id=self.probe.selected_key_id,
            physical_layout=self.cfg.physical_layout,
            slot_overrides=self.layout_slot_overrides,
        )

    def _on_click(self, e: tk.Event) -> None:
        if self._transform is None:
            return
        x = e.x
        y = e.y
        hit = self._hit_test(x, y)
        if hit is None:
            self.probe.selected_key_id = None
            self.lbl_status.configure(text="No key hit")
        else:
            self.probe.selected_key_id = hit.key_id
            mapped = self.keymap.get(hit.key_id)
            self.lbl_status.configure(
                text=f"Selected {hit.label}" + (f" (mapped {mapped})" if mapped else " (unmapped)")
            )
        self._redraw()

    def _hit_test(self, x: int, y: int) -> Optional[KeyDef]:
        if self._transform is None:
            return None

        visible_keys = get_layout_keys(self.cfg.physical_layout, slot_overrides=self.layout_slot_overrides)
        return hit_test(
            transform=self._transform,
            x=x,
            y=y,
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            keys=visible_keys,
            image_size=BASE_IMAGE_SIZE,
        )


def main() -> None:
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator()
    app.mainloop()


if __name__ == "__main__":
    main()
