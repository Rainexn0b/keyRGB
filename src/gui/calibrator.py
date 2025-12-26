from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from src.legacy.config import Config
from src.core import profiles
from src.core.layout import BASE_IMAGE_SIZE, Y15_PRO_KEYS, KeyDef


MATRIX_ROWS = 6
MATRIX_COLS = 21


def _keymap_path() -> Path:
    # Store keymaps per active profile.
    return profiles.paths_for(profiles.get_active_profile()).keymap


def _layout_tweaks_path() -> Path:
    # Store overlay alignment tweaks per active profile.
    return profiles.paths_for(profiles.get_active_profile()).layout_global


def _load_layout_tweaks() -> Dict[str, float]:
    path = _layout_tweaks_path()
    if not path.exists():
        return {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}

    out = {"dx": 0.0, "dy": 0.0, "sx": 1.0, "sy": 1.0, "inset": 0.06}
    if isinstance(raw, dict):
        for k in list(out.keys()):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                out[k] = float(v)
    # Clamp inset to avoid weird rendering.
    out["inset"] = max(0.0, min(0.20, float(out.get("inset", 0.06))))
    return out


def _load_keymap() -> Dict[str, Tuple[int, int]]:
    path = _keymap_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    out: Dict[str, Tuple[int, int]] = {}
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


def _save_keymap(keymap: Dict[str, Tuple[int, int]]) -> None:
    path = _keymap_path()
    payload = {k: f"{rc[0]},{rc[1]}" for k, rc in sorted(keymap.items())}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _full_black_map() -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    return {(r, c): (0, 0, 0) for r in range(MATRIX_ROWS) for c in range(MATRIX_COLS)}


def _apply_probe_to_config(row: int, col: int) -> None:
    cfg = Config()
    colors = _full_black_map()
    colors[(row, col)] = (255, 255, 255)

    cfg.effect = "perkey"
    # Ensure visible even if user had brightness=0 (off)
    if getattr(cfg, "brightness", 0) <= 0:
        cfg.brightness = 50
    cfg.per_key_colors = colors


@dataclass
class _CanvasTransform:
    x0: float
    y0: float
    sx: float
    sy: float

    def to_canvas(self, rect: Tuple[int, int, int, int]) -> Tuple[float, float, float, float]:
        x, y, w, h = rect
        x1 = self.x0 + x * self.sx
        y1 = self.y0 + y * self.sy
        x2 = self.x0 + (x + w) * self.sx
        y2 = self.y0 + (y + h) * self.sy
        return x1, y1, x2, y2


class KeymapCalibrator(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeyRGB - Keymap Calibrator (Y15 Pro)")

        self.cfg = Config()
        self.keymap: Dict[str, Tuple[int, int]] = _load_keymap()
        self.layout_tweaks: Dict[str, float] = _load_layout_tweaks()

        self.current_cell: Tuple[int, int] = (0, 0)
        self.selected_key_id: Optional[str] = None

        self._deck_pil: Optional[Image.Image] = None
        self._deck_tk: Optional[ImageTk.PhotoImage] = None
        self._transform: Optional[_CanvasTransform] = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(root, background="#111111", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _e: self._redraw())
        self.canvas.bind("<Button-1>", self._on_click)

        side = ttk.Frame(root, padding=10)
        side.grid(row=0, column=1, sticky="ns")

        self.lbl_cell = ttk.Label(side, text="")
        self.lbl_cell.grid(row=0, column=0, sticky="w")

        self.lbl_status = ttk.Label(
            side,
            text=(
                "Step 1: look at the lit key on the keyboard\n"
                "Step 2: click that key on the image\n"
                "Step 3: click 'Assign selected key' (or press Enter)"
            ),
            justify="left",
        )
        self.lbl_status.grid(row=1, column=0, sticky="w", pady=(6, 12))

        btns = ttk.Frame(side)
        btns.grid(row=2, column=0, sticky="ew")
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Prev", command=self._prev).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Next", command=self._next).grid(row=0, column=1, sticky="ew")

        ttk.Button(side, text="Assign selected key", command=self._assign).grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(side, text="Skip (nothing lit)", command=self._skip).grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(side, text="Save", command=self._save).grid(row=5, column=0, sticky="ew", pady=(18, 0))
        ttk.Button(side, text="Save && Close", command=self._save_and_close).grid(row=6, column=0, sticky="ew", pady=(6, 0))

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

    def _load_deck_image(self) -> None:
        # Prefer workspace-relative asset; fall back to installed package layouts.
        candidates = [
            Path(__file__).resolve().parent.parent / "assets" / "y15-pro-deck.png",
            Path.cwd() / "assets" / "y15-pro-deck.png",
        ]
        for p in candidates:
            if p.exists():
                self._deck_pil = Image.open(p).convert("RGBA")
                return
        self._deck_pil = None

    def _apply_current_probe(self) -> None:
        r, c = self.current_cell
        self.lbl_cell.configure(text=f"Probing matrix cell: ({r}, {c})")
        _apply_probe_to_config(r, c)
        # Give the tray poller a moment to apply.
        self.after(50, lambda: None)

    def _prev(self) -> None:
        r, c = self.current_cell
        idx = r * MATRIX_COLS + c
        idx = (idx - 1) % (MATRIX_ROWS * MATRIX_COLS)
        self.current_cell = (idx // MATRIX_COLS, idx % MATRIX_COLS)
        self._apply_current_probe()

    def _next(self) -> None:
        r, c = self.current_cell
        idx = r * MATRIX_COLS + c
        idx = (idx + 1) % (MATRIX_ROWS * MATRIX_COLS)
        self.current_cell = (idx // MATRIX_COLS, idx % MATRIX_COLS)
        self._apply_current_probe()

    def _skip(self) -> None:
        # Explicitly record "no key" by just moving on.
        self.selected_key_id = None
        self.lbl_status.configure(text="Skipped. Move to next cell.")
        self._next()

    def _assign(self) -> None:
        if not self.selected_key_id:
            self.lbl_status.configure(text="Select a key on the image first")
            return
        self.keymap[self.selected_key_id] = self.current_cell
        self.lbl_status.configure(text=f"Assigned {self.selected_key_id} -> {self.current_cell}")
        self._redraw()
        self._next()

    def _save(self) -> None:
        _save_keymap(self.keymap)
        self.lbl_status.configure(text=f"Saved to {str(_keymap_path())}")

    def _save_and_close(self) -> None:
        self._save()
        self.destroy()

    def _calc_transform(self) -> _CanvasTransform:
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        iw, ih = BASE_IMAGE_SIZE

        s = min(cw / iw, ch / ih)
        draw_w = iw * s
        draw_h = ih * s
        x0 = (cw - draw_w) / 2
        y0 = (ch - draw_h) / 2
        return _CanvasTransform(x0=x0, y0=y0, sx=s, sy=s)

    def _redraw(self) -> None:
        self.canvas.delete("all")
        self._transform = self._calc_transform()

        if self._deck_pil is not None:
            # Resize deck image to current scale
            s = self._transform.sx
            iw, ih = BASE_IMAGE_SIZE
            resized = self._deck_pil.resize((int(iw * s), int(ih * s)), Image.Resampling.LANCZOS)
            self._deck_tk = ImageTk.PhotoImage(resized)
            self.canvas.create_image(self._transform.x0, self._transform.y0, anchor="nw", image=self._deck_tk)

        tweak_dx = float(self.layout_tweaks.get("dx", 0.0))
        tweak_dy = float(self.layout_tweaks.get("dy", 0.0))
        tweak_sx = float(self.layout_tweaks.get("sx", 1.0))
        tweak_sy = float(self.layout_tweaks.get("sy", 1.0))
        inset_frac = float(self.layout_tweaks.get("inset", 0.06))

        # Draw key rectangles
        for key in Y15_PRO_KEYS:
            x, y, w, h = key.rect
            x = x * tweak_sx + tweak_dx
            y = y * tweak_sy + tweak_dy
            w = w * tweak_sx
            h = h * tweak_sy
            x1, y1, x2, y2 = self._transform.to_canvas((int(x), int(y), int(w), int(h)))

            # Apply inset similar to the per-key editor.
            inset = max(1.0, min(x2 - x1, y2 - y1) * inset_frac)
            x1 += inset
            y1 += inset
            x2 -= inset
            y2 -= inset
            mapped = self.keymap.get(key.key_id)
            outline = "#00c853" if mapped else "#888888"
            width = 3 if (self.selected_key_id == key.key_id) else 1
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=outline, width=width, fill="")
            # Labels (small)
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=key.label, fill="#dddddd", font=("TkDefaultFont", 9))

    def _on_click(self, e: tk.Event) -> None:
        if self._transform is None:
            return
        x = e.x
        y = e.y
        hit = self._hit_test(x, y)
        if hit is None:
            self.selected_key_id = None
            self.lbl_status.configure(text="No key hit")
        else:
            self.selected_key_id = hit.key_id
            mapped = self.keymap.get(hit.key_id)
            self.lbl_status.configure(text=f"Selected {hit.label}" + (f" (mapped {mapped})" if mapped else " (unmapped)"))
        self._redraw()

    def _hit_test(self, x: int, y: int) -> Optional[KeyDef]:
        if self._transform is None:
            return None

        tweak_dx = float(self.layout_tweaks.get("dx", 0.0))
        tweak_dy = float(self.layout_tweaks.get("dy", 0.0))
        tweak_sx = float(self.layout_tweaks.get("sx", 1.0))
        tweak_sy = float(self.layout_tweaks.get("sy", 1.0))
        inset_frac = float(self.layout_tweaks.get("inset", 0.06))

        for key in Y15_PRO_KEYS:
            xk, yk, wk, hk = key.rect
            xk = xk * tweak_sx + tweak_dx
            yk = yk * tweak_sy + tweak_dy
            wk = wk * tweak_sx
            hk = hk * tweak_sy
            x1, y1, x2, y2 = self._transform.to_canvas((int(xk), int(yk), int(wk), int(hk)))

            inset = max(1.0, min(x2 - x1, y2 - y1) * inset_frac)
            x1 += inset
            y1 += inset
            x2 -= inset
            y2 -= inset
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key
        return None


def main() -> None:
    # Ensure config dir exists early (for saving)
    Config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeymapCalibrator()
    app.mainloop()


if __name__ == "__main__":
    main()
