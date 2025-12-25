#!/usr/bin/env python3
"""KeyRGB Per-Key Editor (Tkinter)

Redesigned per-key UX using the existing HSV ColorWheel:
- Click a key to select it
- Drag around the ColorWheel to update that key in real-time (throttled)
- Changes are written to config; the tray app applies them (single USB owner)
- If the tray isn't running, this GUI will apply directly when it can acquire the device
"""

from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
import subprocess

from pathlib import Path

from PIL import Image, ImageTk

try:
    from .color_wheel import ColorWheel
    from .config_legacy import Config
    from .y15_pro_layout import BASE_IMAGE_SIZE, Y15_PRO_KEYS, KeyDef
    from . import profiles
except Exception:
    # Fallback for direct execution (e.g. `python src/gui_perkey.py`).
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.color_wheel import ColorWheel
    from src.config_legacy import Config
    from src.y15_pro_layout import BASE_IMAGE_SIZE, Y15_PRO_KEYS, KeyDef
    from src import profiles

try:
    from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS
except Exception:
    # Repo fallback if dependency wasn't installed.
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    vendored = repo_root / "ite8291r3-ctl"
    if vendored.exists():
        sys.path.insert(0, str(vendored))
    try:
        from ite8291r3_ctl.ite8291r3 import get, NUM_ROWS, NUM_COLS
    except Exception:
        get = None
        NUM_ROWS, NUM_COLS = 6, 21


class PerKeyEditor:
    def __init__(self):
        # Layout sizing tuned to fit on-screen without scrollbars.
        # Target: ~30–40% of typical 2560×1600 screens.
        self._key_size = 28
        self._key_gap = 2
        self._key_margin = 8
        self._wheel_size = 240
        self._right_panel_width = 320
        self._resize_job = None

        self.root = tk.Tk()
        self.root.title("KeyRGB - Per-Key Colors")
        # Compute a content-fitting window size (no scrollbars).
        self.root.update_idletasks()

        keyboard_w = (self._key_margin * 2) + (NUM_COLS * self._key_size) + ((NUM_COLS - 1) * self._key_gap)
        keyboard_h = (self._key_margin * 2) + (NUM_ROWS * self._key_size) + ((NUM_ROWS - 1) * self._key_gap)

        # Account for container padding + panel gap.
        chrome_w = 16 * 2 + 16
        chrome_h = 16 * 2 + 80

        w0 = keyboard_w + self._right_panel_width + chrome_w
        # Right panel now includes: sliders, buttons, profiles, overlay alignment.
        # Keep a conservative baseline so the bottom controls don't clip.
        h0 = max(keyboard_h + chrome_h, self._wheel_size + 420)

        screen_w = int(self.root.winfo_screenwidth())
        screen_h = int(self.root.winfo_screenheight())
        max_w = int(screen_w * 0.92)
        max_h = int(screen_h * 0.92)

        # Start larger, but never exceed the screen.
        w = min(int(w0 * 1.5), max_w)
        h = min(int(h0 * 1.5), max_h)

        self.root.geometry(f"{w}x{h}")
        # Minimum size must not exceed the screen, otherwise Tk can place it off-screen.
        self.root.minsize(min(w0, max_w), min(h0, max_h))

        style = ttk.Style()
        style.theme_use("clam")

        self.bg_color = "#2b2b2b"
        self.fg_color = "#e0e0e0"

        self.root.configure(bg=self.bg_color)
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        style.configure("TButton", background="#404040", foreground=self.fg_color)
        style.map("TButton", background=[("active", "#505050")])

        self.config = Config()
        self.colors: dict[tuple[int, int], tuple[int, int, int]] = dict(self.config.per_key_colors)

        self.profile_name = profiles.get_active_profile()

        self.keymap: dict[str, tuple[int, int]] = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks: dict[str, dict[str, float]] = self._load_per_key_layout_tweaks()
        self._overlay_vars = None
        self._overlay_scope = tk.StringVar(value="global")  # global | key
        self._profiles_visible = False
        self._profile_name_var = tk.StringVar(value=self.profile_name)
        self.selected_key_id: str | None = None
        self.selected_cell: tuple[int, int] | None = None

        self._drag_ctx: dict | None = None

        self._last_commit_ts = 0.0
        self._commit_interval = 0.06

        self.kb = None
        if get is not None:
            try:
                self.kb = get()
            except Exception:
                self.kb = None

        self._build_ui()
        self._draw_keyboard()

        # If no mapping exists yet, steer the user to the calibrator.
        if not self.keymap:
            self.status_label.config(text="No keymap found — click 'Run Keymap Calibrator'")

        # Auto-reload keymap when returning focus (e.g., after calibrator closes).
        self.root.bind("<FocusIn>", lambda _e: self._reload_keymap())

        # Prefer selecting a mapped key if any exist.
        for kd in Y15_PRO_KEYS:
            if kd.key_id in self.keymap:
                self._select_key_id(kd.key_id)
                break

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill="both", expand=True)

        title = ttk.Label(main, text="Per-Key Keyboard Colors", font=("Sans", 14, "bold"))
        title.pack(pady=(0, 10))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content)
        left.pack(side="left", fill="both", expand=True)

        canvas_frame = ttk.Frame(left)
        canvas_frame.pack(fill="both", expand=True)

        # No scrollbars: draw keys to fit whatever canvas size is available.
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=self.bg_color,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        # Canvas-level click handler: reliable even when overlay rectangles have
        # no fill (Tk only reports clicks on outlines in that case).
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)

        # Deck image backdrop
        self._deck_img = None
        self._deck_img_tk = None
        self._deck_drawn_bbox = None  # (x0, y0, w, h) in canvas coords
        self._load_deck_image()

        # Keep the controls panel width stable so dynamic labels don’t resize the window.
        right = ttk.Frame(content, width=self._right_panel_width)
        right.pack(side="left", fill="y", padx=(16, 0))
        right.pack_propagate(False)

        self.status_label = ttk.Label(right, text="Click a key to start", font=("Sans", 9), width=32)
        self.status_label.pack(pady=(0, 8))

        initial = (
            tuple(self.config.color)
            if isinstance(self.config.color, (list, tuple)) and len(self.config.color) == 3
            else (255, 0, 0)
        )
        self.color_wheel = ColorWheel(
            right,
            size=self._wheel_size,
            initial_color=initial,
            callback=self._on_color_change,
            release_callback=self._on_color_release,
        )
        self.color_wheel.pack()

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=12)
        ttk.Button(btns, text="Fill All", command=self._fill_all).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Clear All", command=self._clear_all).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Run Keymap Calibrator", command=self._run_calibrator).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Reload Keymap", command=self._reload_keymap).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Profiles", command=self._toggle_profiles).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="Close", command=self.root.destroy).pack(fill="x")

        self._profiles_frame = ttk.LabelFrame(right, text="Profiles", padding=10)

        ttk.Label(self._profiles_frame, text="Profile").grid(row=0, column=0, sticky="w")
        self._profiles_combo = ttk.Combobox(
            self._profiles_frame,
            textvariable=self._profile_name_var,
            values=profiles.list_profiles(),
            width=22,
        )
        self._profiles_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._profiles_frame.columnconfigure(1, weight=1)

        pbtns = ttk.Frame(self._profiles_frame)
        pbtns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        pbtns.columnconfigure(0, weight=1)
        pbtns.columnconfigure(1, weight=1)
        pbtns.columnconfigure(2, weight=1)

        ttk.Button(pbtns, text="Activate", command=self._activate_profile).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(pbtns, text="Save", command=self._save_profile).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(pbtns, text="Delete", command=self._delete_profile).grid(row=0, column=2, sticky="ew")

        overlay = ttk.LabelFrame(right, text="Overlay alignment", padding=10)
        overlay.pack(fill="x", pady=(6, 0))

        scope_row = ttk.Frame(overlay)
        scope_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Radiobutton(scope_row, text="Global", variable=self._overlay_scope, value="global", command=self._sync_overlay_vars_from_scope).pack(side="left")
        ttk.Radiobutton(scope_row, text="Selected key", variable=self._overlay_scope, value="key", command=self._sync_overlay_vars_from_scope).pack(side="left", padx=(10, 0))

        # Tunable parameters are in BASE_IMAGE_SIZE pixel space.
        dx_var = tk.DoubleVar(value=float(self.layout_tweaks.get("dx", 0.0)))
        dy_var = tk.DoubleVar(value=float(self.layout_tweaks.get("dy", 0.0)))
        sx_var = tk.DoubleVar(value=float(self.layout_tweaks.get("sx", 1.0)))
        sy_var = tk.DoubleVar(value=float(self.layout_tweaks.get("sy", 1.0)))
        inset_var = tk.DoubleVar(value=float(self.layout_tweaks.get("inset", 0.06)))
        self._overlay_vars = (dx_var, dy_var, sx_var, sy_var, inset_var)

        def add_row(row: int, label: str, var: tk.DoubleVar):
            ttk.Label(overlay, text=label, width=6).grid(row=row, column=0, sticky="w")
            e = ttk.Entry(overlay, textvariable=var, width=10)
            e.grid(row=row, column=1, sticky="ew", padx=(6, 0))
            e.bind("<Return>", lambda _e: self._apply_overlay_from_vars())
            e.bind("<FocusOut>", lambda _e: self._apply_overlay_from_vars())

        overlay.columnconfigure(1, weight=1)
        add_row(1, "dx", dx_var)
        add_row(2, "dy", dy_var)
        add_row(3, "sx", sx_var)
        add_row(4, "sy", sy_var)
        add_row(5, "inset", inset_var)

        overlay_btns = ttk.Frame(overlay)
        overlay_btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        overlay_btns.columnconfigure(0, weight=1)
        overlay_btns.columnconfigure(1, weight=1)
        overlay_btns.columnconfigure(2, weight=1)

        ttk.Button(overlay_btns, text="Apply", command=self._apply_overlay_from_vars).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(overlay_btns, text="Save", command=self._save_layout_tweaks).grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(overlay_btns, text="Reset", command=self._reset_layout_tweaks).grid(row=0, column=2, sticky="ew")

        # Ensure entries reflect the current scope (global by default).
        self._sync_overlay_vars_from_scope()

    def _inset_pixels(self, w_px: float, h_px: float, inset_value: float) -> float:
        """Convert inset setting to canvas pixels.

        Backwards compatible behavior:
        - inset_value <= 0.5: treat as fraction of key size
        - inset_value > 0.5: treat as pixels
        """
        min_dim = max(1.0, min(w_px, h_px))
        if inset_value <= 0.5:
            inset = min_dim * max(0.0, inset_value)
        else:
            inset = max(0.0, inset_value)
        # Avoid insetting past the center.
        inset = min(inset, (min_dim / 2.0) - 1.0)
        return max(0.0, inset)

    def _apply_global_tweak(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        """Apply global dx/dy/sx/sy in base-image coordinates.

        Scale is anchored around the base-image center so changing sx/sy behaves
        like a zoom/resize rather than drifting the entire overlay.
        """
        iw, ih = BASE_IMAGE_SIZE
        px = iw / 2.0
        py = ih / 2.0

        g_dx = float(self.layout_tweaks.get("dx", 0.0))
        g_dy = float(self.layout_tweaks.get("dy", 0.0))
        g_sx = float(self.layout_tweaks.get("sx", 1.0))
        g_sy = float(self.layout_tweaks.get("sy", 1.0))

        x = (x - px) * g_sx + px + g_dx
        y = (y - py) * g_sy + py + g_dy
        w = w * g_sx
        h = h * g_sy
        return x, y, w, h

    def _apply_per_key_tweak(self, key_id: str, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float, float]:
        """Apply per-key dx/dy/sx/sy in base-image coordinates.

        Scale is anchored around the key's own center so sx/sy resize without
        shifting the key.
        Returns (x,y,w,h,inset_value).
        """
        g_inset = float(self.layout_tweaks.get("inset", 0.06))
        kt = self.per_key_layout_tweaks.get(key_id, {})
        k_dx = float(kt.get("dx", 0.0))
        k_dy = float(kt.get("dy", 0.0))
        k_sx = float(kt.get("sx", 1.0))
        k_sy = float(kt.get("sy", 1.0))
        k_inset = float(kt.get("inset", g_inset))

        cx = x + (w / 2.0)
        cy = y + (h / 2.0)
        w2 = w * k_sx
        h2 = h * k_sy
        x2 = cx - (w2 / 2.0) + k_dx
        y2 = cy - (h2 / 2.0) + k_dy
        return x2, y2, w2, h2, k_inset

    def _key_rect_canvas(self, key: KeyDef) -> tuple[float, float, float, float, float] | None:
        """Return (x1,y1,x2,y2,inset_value) in canvas coords for a key."""
        if self._deck_drawn_bbox is None:
            return None

        x0, y0, dw, dh = self._deck_drawn_bbox
        iw, ih = BASE_IMAGE_SIZE
        csx = dw / max(1, iw)
        csy = dh / max(1, ih)

        x, y, w, h = (float(v) for v in key.rect)
        x, y, w, h = self._apply_global_tweak(x, y, w, h)
        x, y, w, h, inset_value = self._apply_per_key_tweak(key.key_id, x, y, w, h)

        x1 = x0 + x * csx
        y1 = y0 + y * csy
        x2 = x0 + (x + w) * csx
        y2 = y0 + (y + h) * csy
        return x1, y1, x2, y2, inset_value

    def _on_canvas_press(self, event):
        # Enable drag-to-move for selected key when editing per-key overlay tweaks.
        if self._overlay_scope.get() != "key":
            self._drag_ctx = None
            return
        if not self.selected_key_id or self._deck_drawn_bbox is None:
            self._drag_ctx = None
            return

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid != self.selected_key_id:
            self._drag_ctx = None
            return

        kt = self.per_key_layout_tweaks.get(self.selected_key_id, {})
        self._drag_ctx = {
            "kid": self.selected_key_id,
            "x": float(event.x),
            "y": float(event.y),
            "dx": float(kt.get("dx", 0.0)),
            "dy": float(kt.get("dy", 0.0)),
        }

    def _on_canvas_drag(self, event):
        if not self._drag_ctx or self._deck_drawn_bbox is None:
            return
        kid = self._drag_ctx.get("kid")
        if not kid:
            return

        x0, y0, dw, dh = self._deck_drawn_bbox
        iw, ih = BASE_IMAGE_SIZE
        csx = dw / max(1, iw)
        csy = dh / max(1, ih)
        if csx <= 0 or csy <= 0:
            return

        dx_canvas = float(event.x) - float(self._drag_ctx["x"])
        dy_canvas = float(event.y) - float(self._drag_ctx["y"])

        dx_base = dx_canvas / csx
        dy_base = dy_canvas / csy

        new_dx = float(self._drag_ctx["dx"]) + dx_base
        new_dy = float(self._drag_ctx["dy"]) + dy_base

        kt = dict(self.per_key_layout_tweaks.get(kid, {}))
        kt["dx"] = new_dx
        kt["dy"] = new_dy
        self.per_key_layout_tweaks[kid] = kt

        # Keep the editor fields in sync while dragging.
        if self._overlay_vars and self.selected_key_id == kid:
            dx_var, dy_var, sx_var, sy_var, inset_var = self._overlay_vars
            dx_var.set(float(kt.get("dx", 0.0)))
            dy_var.set(float(kt.get("dy", 0.0)))
            sx_var.set(float(kt.get("sx", 1.0)))
            sy_var.set(float(kt.get("sy", 1.0)))
            inset_var.set(float(kt.get("inset", float(self.layout_tweaks.get("inset", 0.06)))))

        self._draw_keyboard()

    def _on_canvas_release(self, _event):
        self._drag_ctx = None

    def _draw_keyboard(self):
        self.canvas.delete("all")
        self._draw_deck_background()
        self.key_rects: dict[str, int] = {}
        self.key_texts: dict[str, int] = {}

        if self._deck_drawn_bbox is None:
            return

        for key in Y15_PRO_KEYS:
            rect = self._key_rect_canvas(key)
            if rect is None:
                return
            x1, y1, x2, y2, inset_value = rect

            inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
            x1 += inset
            y1 += inset
            x2 -= inset
            y2 -= inset

            mapped = self.keymap.get(key.key_id)
            color = self.colors.get(mapped) if mapped else None
            if color is None:
                # Keep the deck visible: use no fill for unmapped, light stipple for mapped-but-unset.
                fill = "" if mapped is None else "#000000"
                stipple = "" if mapped is None else "gray75"
                text_fill = "#cfcfcf" if mapped is None else "#e0e0e0"
            else:
                r, g, b = color
                fill = f"#{r:02x}{g:02x}{b:02x}"
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                text_fill = "#000000" if brightness > 128 else "#ffffff"
                stipple = "gray50"  # pseudo-transparency over the deck

            outline = "#00ffff" if self.selected_key_id == key.key_id else ("#777777" if mapped else "#8a8a8a")
            width = 3 if self.selected_key_id == key.key_id else 2
            dash = () if mapped else (3,)

            rect_id = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                fill=fill,
                stipple=stipple,
                outline=outline,
                width=width,
                dash=dash,
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_rects[key.key_id] = rect_id

            # Font size: scale with key size, clamp to avoid overlap.
            key_w = max(1, int(x2 - x1))
            key_h = max(1, int(y2 - y1))
            font_size = max(7, min(11, int(min(key_w, key_h) * 0.30)))
            text_id = self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=key.label,
                fill=text_fill,
                font=("TkDefaultFont", font_size),
                tags=(f"pkey_{key.key_id}", "pkey"),
            )
            self.key_texts[key.key_id] = text_id

            self.canvas.tag_bind(
                f"pkey_{key.key_id}",
                "<Button-1>",
                lambda _e, kid=key.key_id: self._select_key_id(kid),
            )

    def _key_bbox_canvas(self, key: KeyDef) -> tuple[float, float, float, float] | None:
        """Return the key's clickable bbox in canvas coords."""
        rect = self._key_rect_canvas(key)
        if rect is None:
            return None
        x1, y1, x2, y2, inset_value = rect
        inset = self._inset_pixels(x2 - x1, y2 - y1, inset_value)
        return (x1 + inset, y1 + inset, x2 - inset, y2 - inset)

    def _hit_test_key_id(self, cx: float, cy: float) -> str | None:
        for kd in Y15_PRO_KEYS:
            bbox = self._key_bbox_canvas(kd)
            if bbox is None:
                return None
            x1, y1, x2, y2 = bbox
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return kd.key_id
        return None

    def _on_canvas_click(self, event):
        # Fast-path: if Tk reported a current item with a pkey_* tag, use it.
        try:
            current = self.canvas.find_withtag("current")
            if current:
                tags = self.canvas.gettags(current[0])
                for t in tags:
                    if t.startswith("pkey_"):
                        self._select_key_id(t.removeprefix("pkey_"))
                        return
        except Exception:
            pass

        kid = self._hit_test_key_id(float(event.x), float(event.y))
        if kid is not None:
            self._select_key_id(kid)

    def _load_deck_image(self):
        try:
            repo_root = os.path.dirname(os.path.dirname(__file__))
            path = os.path.join(repo_root, 'assets', 'y15-pro-deck.png')
            self._deck_img = Image.open(path)
        except Exception:
            self._deck_img = None

    def _draw_deck_background(self):
        if self._deck_img is None:
            self._deck_drawn_bbox = None
            return

        cw = max(1, int(self.canvas.winfo_width()))
        ch = max(1, int(self.canvas.winfo_height()))

        iw, ih = self._deck_img.size
        scale = min(cw / iw, ch / ih)
        dw = max(1, int(iw * scale))
        dh = max(1, int(ih * scale))

        x0 = (cw - dw) // 2
        y0 = (ch - dh) // 2

        resized = self._deck_img.resize((dw, dh), Image.Resampling.LANCZOS)
        self._deck_img_tk = ImageTk.PhotoImage(resized)
        self.canvas.create_image(x0, y0, image=self._deck_img_tk, anchor='nw')
        self._deck_drawn_bbox = (x0, y0, dw, dh)

    def _on_canvas_resize(self, _event):
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.root.after(40, self._redraw_keyboard)

    def _redraw_keyboard(self):
        self._resize_job = None
        self._draw_keyboard()

    def _select_key_id(self, key_id: str):
        self.selected_key_id = key_id
        self.selected_cell = self.keymap.get(key_id)

        # If editing per-key overlay tweaks, reflect selected key in the editor.
        if self._overlay_scope.get() == "key":
            self._sync_overlay_vars_from_scope()

        if self.selected_cell is None:
            self.status_label.config(text=f"Selected {key_id} (unmapped) — run keymap calibrator")
            self._draw_keyboard()
            return

        row, col = self.selected_cell
        color = self.colors.get((row, col), (0, 0, 0))
        self.color_wheel.set_color(*color)
        self.status_label.config(text=f"Selected {key_id} -> {row},{col}")
        self._draw_keyboard()

    def _run_calibrator(self):
        """Launch the keymap calibrator as a separate process."""
        parent_path = os.path.dirname(os.path.dirname(__file__))
        try:
            subprocess.Popen([sys.executable, "-m", "src.gui_keymap_calibrator"], cwd=parent_path)
            self.status_label.config(text="Calibrator started — map keys then Save")
        except Exception:
            self.status_label.config(text="Failed to start calibrator")

    def _reload_keymap(self):
        """Reload key mapping from disk and redraw."""
        old = dict(self.keymap)
        self.keymap = self._load_keymap()
        if self.selected_key_id is not None:
            self.selected_cell = self.keymap.get(self.selected_key_id)
        if old != self.keymap:
            if self.keymap:
                self.status_label.config(text="Keymap reloaded")
            else:
                self.status_label.config(text="No keymap found — run keymap calibrator")
        self._draw_keyboard()

    def _update_key_visual_for_cell(self, cell: tuple[int, int], color: tuple[int, int, int]):
        # Update any physical keys mapped to this cell.
        target_key_ids = [k for k, rc in self.keymap.items() if rc == cell]
        if not target_key_ids:
            return

        r, g, b = color
        fill = f"#{r:02x}{g:02x}{b:02x}"
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_fill = "#000000" if brightness > 128 else "#ffffff"

        for key_id in target_key_ids:
            rect_id = self.key_rects.get(key_id)
            if rect_id is not None:
                self.canvas.itemconfig(rect_id, fill=fill)
            text_id = self.key_texts.get(key_id)
            if text_id is not None:
                self.canvas.itemconfig(text_id, fill=text_fill)

    def _commit(self, *, force: bool = False):
        now = time.monotonic()
        if not force and (now - self._last_commit_ts) < self._commit_interval:
            return
        self._last_commit_ts = now

        # Ensure we send a full map so only the edited key changes.
        self._ensure_full_map()

        # If brightness is 0, commits would be interpreted as "off" by the tray.
        # Default to something visible when the user is actively editing.
        if self.config.brightness == 0:
            self.config.brightness = 25

        self.config.effect = "perkey"
        self.config.per_key_colors = self.colors

        if self.kb is not None:
            try:
                self.kb.set_key_colors(
                    self.colors,
                    brightness=self.config.brightness,
                    enable_user_mode=True,
                )
            except OSError as e:
                if getattr(e, "errno", None) == 16:
                    self.kb = None
            except Exception:
                pass

    def _on_color_change(self, r: int, g: int, b: int):
        if self.selected_cell is None:
            return

        row, col = self.selected_cell
        color = (r, g, b)
        self.colors[(row, col)] = color
        self._update_key_visual_for_cell((row, col), color)
        self._commit(force=False)

    def _on_color_release(self, r: int, g: int, b: int):
        if self.selected_cell is None:
            return

        row, col = self.selected_cell
        color = (r, g, b)
        self.colors[(row, col)] = color
        self._update_key_visual_for_cell((row, col), color)
        self._commit(force=True)
        if self.selected_key_id is not None:
            self.status_label.config(text=f"Saved {self.selected_key_id} = RGB({r},{g},{b})")
        else:
            self.status_label.config(text=f"Saved key {row},{col} = RGB({r},{g},{b})")

    def _fill_all(self):
        r, g, b = self.color_wheel.get_color()
        color = (r, g, b)

        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.colors[(row, col)] = color

        # Redraw once (faster than updating every rect)
        self._draw_keyboard()

        self._commit(force=True)
        self.status_label.config(text=f"Filled all keys = RGB({r},{g},{b})")

    def _ensure_full_map(self):
        if len(self.colors) >= (NUM_ROWS * NUM_COLS):
            return

        base = tuple(self.config.color)
        for row in range(NUM_ROWS):
            for col in range(NUM_COLS):
                self.colors.setdefault((row, col), base)

    def _clear_all(self):
        # Explicitly set all keys to black/off.
        self.colors = {(row, col): (0, 0, 0) for row in range(NUM_ROWS) for col in range(NUM_COLS)}

        self._draw_keyboard()

        self.config.effect = "perkey"
        self.config.per_key_colors = self.colors

        if self.kb is not None:
            try:
                self.kb.set_key_colors(self.colors, brightness=self.config.brightness, enable_user_mode=True)
            except OSError as e:
                if getattr(e, "errno", None) == 16:
                    self.kb = None
            except Exception:
                pass

        self.status_label.config(text="Cleared all keys")

    def _keymap_file(self) -> Path:
        return profiles.paths_for(self.profile_name).keymap

    def _layout_tweaks_file(self) -> Path:
        return profiles.paths_for(self.profile_name).layout_global

    def _layout_tweaks_per_key_file(self) -> Path:
        return profiles.paths_for(self.profile_name).layout_per_key

    def _load_layout_tweaks(self) -> dict[str, float]:
        """Load optional layout tweaks.

                File: ~/.config/keyrgb/profiles/<profile>/layout_tweaks_y15_pro.json
        Keys:
          - dx, dy: translation in base-image px (1008×450 coords)
          - sx, sy: scale factors in base-image coords
                    - inset: fraction (<=0.5) or pixels (>0.5) for key inset
        """
        return profiles.load_layout_global(self.profile_name)

    def _load_per_key_layout_tweaks(self) -> dict[str, dict[str, float]]:
        return profiles.load_layout_per_key(self.profile_name)

    def _apply_overlay_from_vars(self):
        if not self._overlay_vars:
            return

        dx_var, dy_var, sx_var, sy_var, inset_var = self._overlay_vars

        def f(v: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, float(v)))

        payload = {
            "dx": float(dx_var.get()),
            "dy": float(dy_var.get()),
            # Allow a wider range for alignment fixes on different keyboard revisions.
            "sx": f(sx_var.get(), 0.3, 2.0),
            "sy": f(sy_var.get(), 0.3, 2.0),
            # Inset supports either a fraction (<= 0.5) or pixels (> 0.5).
            "inset": f(inset_var.get(), 0.0, 80.0),
        }

        if self._overlay_scope.get() == "key" and self.selected_key_id:
            self.per_key_layout_tweaks[self.selected_key_id] = payload
        else:
            self.layout_tweaks = payload
        self._draw_keyboard()

    def _save_layout_tweaks(self):
        self._apply_overlay_from_vars()

        if self._overlay_scope.get() == "key" and self.selected_key_id:
            profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
            self.status_label.config(text=f"Saved overlay tweaks for {self.selected_key_id}")
        else:
            profiles.save_layout_global(self.layout_tweaks, self.profile_name)
            self.status_label.config(text="Saved global overlay alignment tweaks")

    def _reset_layout_tweaks(self):
        if self._overlay_scope.get() == "key" and self.selected_key_id:
            self.per_key_layout_tweaks.pop(self.selected_key_id, None)
            self._sync_overlay_vars_from_scope()
            self._draw_keyboard()
            self.status_label.config(text=f"Reset overlay tweaks for {self.selected_key_id}")
            return

        self.layout_tweaks = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
        self._sync_overlay_vars_from_scope()
        self._draw_keyboard()
        self.status_label.config(text="Reset global overlay alignment tweaks")

    def _sync_overlay_vars_from_scope(self):
        if not self._overlay_vars:
            return
        dx_var, dy_var, sx_var, sy_var, inset_var = self._overlay_vars

        if self._overlay_scope.get() == "key" and self.selected_key_id:
            kt = self.per_key_layout_tweaks.get(self.selected_key_id, {})
            dx_var.set(float(kt.get("dx", 0.0)))
            dy_var.set(float(kt.get("dy", 0.0)))
            sx_var.set(float(kt.get("sx", 1.0)))
            sy_var.set(float(kt.get("sy", 1.0)))
            inset_var.set(float(kt.get("inset", float(self.layout_tweaks.get("inset", 0.06)))))
            return

        dx_var.set(float(self.layout_tweaks.get("dx", 0.0)))
        dy_var.set(float(self.layout_tweaks.get("dy", 0.0)))
        sx_var.set(float(self.layout_tweaks.get("sx", 1.0)))
        sy_var.set(float(self.layout_tweaks.get("sy", 1.0)))
        inset_var.set(float(self.layout_tweaks.get("inset", 0.06)))

    def _toggle_profiles(self):
        if self._profiles_visible:
            self._profiles_frame.pack_forget()
            self._profiles_visible = False
        else:
            self._profiles_combo.configure(values=profiles.list_profiles())
            self._profiles_frame.pack(fill="x", pady=(6, 0))
            self._profiles_visible = True

    def _activate_profile(self):
        name = profiles.set_active_profile(self._profile_name_var.get())
        self.profile_name = name
        self._profile_name_var.set(name)

        self.keymap = self._load_keymap()
        self.layout_tweaks = self._load_layout_tweaks()
        self.per_key_layout_tweaks = self._load_per_key_layout_tweaks()

        prof_colors = profiles.load_per_key_colors(self.profile_name)
        self.colors = dict(prof_colors)
        profiles.apply_profile_to_config(self.config, self.colors)

        self._sync_overlay_vars_from_scope()
        self._draw_keyboard()
        self.status_label.config(text=f"Active profile: {self.profile_name}")

    def _save_profile(self):
        name = profiles.set_active_profile(self._profile_name_var.get())
        self.profile_name = name
        self._profile_name_var.set(name)
        profiles.save_keymap(self.keymap, self.profile_name)
        profiles.save_layout_global(self.layout_tweaks, self.profile_name)
        profiles.save_layout_per_key(self.per_key_layout_tweaks, self.profile_name)
        profiles.save_per_key_colors(self.colors, self.profile_name)
        self.status_label.config(text=f"Saved profile: {self.profile_name}")

    def _delete_profile(self):
        name = self._profile_name_var.get().strip()
        if not name:
            return
        if not profiles.delete_profile(name):
            self.status_label.config(text="Cannot delete 'default'")
            return
        # If deleting current, fall back to default.
        if profiles.get_active_profile() == profiles._safe_name(name):
            profiles.set_active_profile("default")
            self.profile_name = "default"
            self._profile_name_var.set("default")
        self._profiles_combo.configure(values=profiles.list_profiles())
        self.status_label.config(text=f"Deleted profile: {profiles._safe_name(name)}")

    def _load_keymap(self) -> dict[str, tuple[int, int]]:
        path = self._keymap_file()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        out: dict[str, tuple[int, int]] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(k, str) and isinstance(v, str) and "," in v:
                    a, b = v.split(",", 1)
                    try:
                        out[k] = (int(a), int(b))
                    except ValueError:
                        continue
                elif isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 2:
                    try:
                        out[k] = (int(v[0]), int(v[1]))
                    except Exception:
                        continue
        return out

    def run(self):
        self.root.mainloop()


def main():
    PerKeyEditor().run()


if __name__ == "__main__":
    main()
