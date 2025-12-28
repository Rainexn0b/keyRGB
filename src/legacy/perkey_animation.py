from __future__ import annotations

from typing import Dict, Tuple


def load_per_key_colors_from_config() -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Best-effort load of per-key colors from the legacy config."""

    try:
        from src.legacy.config import Config

        cfg = Config()
        return dict(getattr(cfg, "per_key_colors", {}) or {})
    except Exception:
        return {}


def build_full_color_grid(
    *,
    base_color: Tuple[int, int, int],
    per_key_colors: Dict[Tuple[int, int], Tuple[int, int, int]] | None,
    num_rows: int,
    num_cols: int,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Fill the full matrix with base_color, then overlay per-key values."""

    base: Tuple[int, int, int] = (int(base_color[0]), int(base_color[1]), int(base_color[2]))
    full: Dict[Tuple[int, int], Tuple[int, int, int]] = {
        (r, c): base for r in range(int(num_rows)) for c in range(int(num_cols))
    }

    for (row, col), rgb in (per_key_colors or {}).items():
        try:
            rr, gg, bb = rgb
            full[(int(row), int(col))] = (int(rr), int(gg), int(bb))
        except Exception:
            continue

    return full


def scaled_color_map(
    full_colors: Dict[Tuple[int, int], Tuple[int, int, int]],
    *,
    scale: float,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Return a new color map with each channel scaled by `scale`."""

    s = float(scale)
    out: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    for (row, col), (r, g, b) in full_colors.items():
        out[(row, col)] = (
            max(0, min(255, int(r * s))),
            max(0, min(255, int(g * s))),
            max(0, min(255, int(b * s))),
        )
    return out


def enable_user_mode_once(*, kb, kb_lock, brightness: int) -> None:
    """Enable user mode once without saving, to avoid flicker."""

    with kb_lock:
        kb.enable_user_mode(brightness=brightness, save=False)
