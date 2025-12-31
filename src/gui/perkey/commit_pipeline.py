from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Tuple

from .ops.color_map_ops import ensure_full_map

Color = Tuple[int, int, int]
Cell = Tuple[int, int]
ColorMap = Mapping[Cell, Color]


@dataclass
class PerKeyCommitPipeline:
    """Stateful helper that throttles and commits per-key state.

    Keeps editor.py focused on UI concerns by centralizing:
    - commit throttling
    - ensuring a full per-key map
    - config updates
    - hardware push call
    """

    commit_interval_s: float = 0.06
    _last_commit_ts: float = 0.0
    _time_fn: Callable[[], float] = time.monotonic

    def commit(
        self,
        *,
        kb: Any,
        colors: dict[Cell, Color],
        config: Any,
        num_rows: int,
        num_cols: int,
        base_color: Color,
        fallback_color: Color,
        push_fn: Callable[..., Any],
        force: bool = False,
    ) -> tuple[Any, dict[Cell, Color]]:
        now = float(self._time_fn())
        if not force and (now - float(self._last_commit_ts)) < float(self.commit_interval_s):
            return kb, colors
        self._last_commit_ts = now

        full = ensure_full_map(
            colors=dict(colors),
            num_rows=int(num_rows),
            num_cols=int(num_cols),
            base_color=base_color,
            fallback_color=fallback_color,
        )

        try:
            if int(getattr(config, "brightness", 0) or 0) == 0:
                setattr(config, "brightness", 25)
        except Exception:
            pass

        try:
            setattr(config, "effect", "perkey")
            setattr(config, "per_key_colors", full)
        except Exception:
            pass

        try:
            brightness = int(getattr(config, "brightness", 0) or 0)
        except Exception:
            brightness = 0

        kb2 = push_fn(
            kb,
            full,
            brightness=brightness,
            enable_user_mode=True,
        )

        return kb2, full
