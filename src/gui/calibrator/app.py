from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

from PIL import Image, ImageTk

from src.core.config import Config
from src.core.resources.layout import BASE_IMAGE_SIZE, REFERENCE_DEVICE_KEYS, KeyDef
from .geometry import hit_test, key_canvas_bbox
from .probe import CalibrationProbeState
from src.gui.utils.profile_backdrop_storage import load_backdrop_image, reset_backdrop_image, save_backdrop_image
from .keyboard_preview import KeyboardPreviewSession
from .profile_storage import (
    get_active_profile_name,
    keymap_path,
    load_keymap,
    load_layout_global,
    load_layout_per_key,
    save_keymap,
)

from src.gui.utils.window_icon import apply_keyrgb_window_icon
from src.gui.theme import apply_clam_theme
from src.gui.utils.key_draw_style import key_draw_style
from src.gui.reference.overlay_geometry import (
    CanvasTransform,
    calc_centered_drawn_bbox,
    transform_from_drawn_bbox,
)


MATRIX_ROWS = 6
MATRIX_COLS = 21


def _keymap_path() -> Path:
    # Store keymaps per active profile.
    return keymap_path(get_active_profile_name())


def _save_keymap(keymap: Dict[str, Tuple[int, int]]) -> None:
    # Use shared saver to keep behavior consistent with per-key UI.
    save_keymap(get_active_profile_name(), keymap)
class KeymapCalibrator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator")
        apply_keyrgb_window_icon(self)

        self.bg_color, self.fg_color = apply_clam_theme(self)

        self.cfg = Config()
        self.preview = KeyboardPreviewSession(self.cfg, rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.profile_name = get_active_profile_name()
        self.keymap = load_keymap(self.profile_name)
        self.layout_tweaks = load_layout_global(self.profile_name)
        self.per_key_layout_tweaks = load_layout_per_key(self.profile_name)

        self.probe = CalibrationProbeState(rows=MATRIX_ROWS, cols=MATRIX_COLS)

        self._deck_pil: Optional[Image.Image] = None
        self._deck_tk: Optional[ImageTk.PhotoImage] = None
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
        side.grid(row=0, column=1, sticky="ns", padx=(16, 0))

        title = ttk.Label(side, text="Keymap Calibrator", font=("Sans", 14, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.lbl_cell = ttk.Label(side, text="", font=("Sans", 9))
        self.lbl_cell.grid(row=1, column=0, sticky="w", pady=(0, 8))

        self.lbl_status = ttk.Label(
            side,
            text=(
                "Step 1: look at the lit key on the keyboard\n"
                "Step 2: click that key on the image\n"
                "Step 3: click 'Assign selected key' (or press Enter)"
            ),
            justify="left",
        )
        self.lbl_status.grid(row=2, column=0, sticky="w", pady=(0, 12))

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
        ttk.Button(side, text="Save", command=self._save).grid(row=8, column=0, sticky="ew", pady=(18, 0))
        ttk.Button(side, text="Save && Close", command=self._save_and_close).grid(
            row=9, column=0, sticky="ew", pady=(6, 0)
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
        w = min(1200, int(sw * 0.92))
        h = min(720, int(sh * 0.92))
        self.geometry(f"{w}x{h}")
        self.minsize(min(980, w), min(560, h))

        self._load_deck_image()
        self._apply_current_probe()
        self._redraw()

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

    def _restore_original_config(self) -> None:
        self.preview.restore()

    def _on_close(self) -> None:
        self._restore_original_config()
        self.destroy()

    def _load_deck_image(self) -> None:
        # Prefer per-profile custom backdrop; fall back to default asset.
        self._deck_pil = load_backdrop_image(self.profile_name)

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
        self.canvas.delete("all")

        cw = max(1, int(self.canvas.winfo_width()))
        ch = max(1, int(self.canvas.winfo_height()))
        x0, y0, dw, dh, _scale = calc_centered_drawn_bbox(canvas_w=cw, canvas_h=ch, image_size=BASE_IMAGE_SIZE)
        self._transform = transform_from_drawn_bbox(x0=x0, y0=y0, draw_w=dw, draw_h=dh, image_size=BASE_IMAGE_SIZE)

        if self._deck_pil is not None:
            resized = self._deck_pil.resize((dw, dh), Image.Resampling.LANCZOS)
            self._deck_tk = ImageTk.PhotoImage(resized)
            self.canvas.create_image(x0, y0, anchor="nw", image=self._deck_tk)

        # Draw key rectangles (similar styling to the per-key editor)
        for key in REFERENCE_DEVICE_KEYS:
            x1, y1, x2, y2 = key_canvas_bbox(
                transform=self._transform,
                key=key,
                layout_tweaks=self.layout_tweaks,
                per_key_layout_tweaks=self.per_key_layout_tweaks,
                image_size=BASE_IMAGE_SIZE,
            )
            mapped = self.keymap.get(key.key_id)
            selected = self.probe.selected_key_id == key.key_id

            style = key_draw_style(mapped=mapped is not None, selected=selected)

            self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=style.outline,
                width=style.width,
                fill=style.fill,
                stipple=style.stipple,
                dash=style.dash,
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=key.label,
                fill=style.text_fill,
                font=("TkDefaultFont", 9),
                tags=(f"pkey_{key.key_id}", "pkey"),
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

        return hit_test(
            transform=self._transform,
            x=x,
            y=y,
            layout_tweaks=self.layout_tweaks,
            per_key_layout_tweaks=self.per_key_layout_tweaks,
            keys=REFERENCE_DEVICE_KEYS,
            image_size=BASE_IMAGE_SIZE,
        )


def main() -> None:
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator()
    app.mainloop()


if __name__ == "__main__":
    main()
