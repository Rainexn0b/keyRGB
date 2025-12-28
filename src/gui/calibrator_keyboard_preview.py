from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from src.legacy.config import Config


def _full_black_map(*, rows: int, cols: int) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    return {(r, c): (0, 0, 0) for r in range(rows) for c in range(cols)}


@dataclass
class KeyboardPreviewSession:
    """Manages temporary config changes while calibrating.

    The calibrator flashes a single matrix cell (white) using per-key mode.
    This session snapshots the original config values and restores them on exit.
    """

    cfg: Config
    rows: int
    cols: int

    def __post_init__(self) -> None:
        self._orig_effect = getattr(self.cfg, "effect", "rainbow")
        self._orig_speed = getattr(self.cfg, "speed", 5)
        self._orig_brightness = getattr(self.cfg, "brightness", 25)
        self._orig_color = tuple(getattr(self.cfg, "color", (255, 0, 0)) or (255, 0, 0))
        try:
            self._orig_per_key_colors = dict(getattr(self.cfg, "per_key_colors", {}) or {})
        except Exception:
            self._orig_per_key_colors = {}

    def apply_probe_cell(self, row: int, col: int) -> None:
        colors = _full_black_map(rows=self.rows, cols=self.cols)
        colors[(row, col)] = (255, 255, 255)

        self.cfg.effect = "perkey"
        if getattr(self.cfg, "brightness", 0) <= 0:
            self.cfg.brightness = 50
        self.cfg.per_key_colors = colors

    def restore(self) -> None:
        try:
            self.cfg.per_key_colors = self._orig_per_key_colors
            self.cfg.color = self._orig_color
            self.cfg.speed = int(self._orig_speed)
            self.cfg.brightness = int(self._orig_brightness)
            self.cfg.effect = str(self._orig_effect)
        except Exception:
            pass
