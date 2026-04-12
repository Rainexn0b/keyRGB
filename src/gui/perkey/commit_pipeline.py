from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Tuple

from src.core.utils.logging_utils import log_throttled
from src.core.utils.safe_attrs import safe_int_attr

from .ops.color_map_ops import ensure_full_map

logger = logging.getLogger(__name__)
_CONFIG_WRITE_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

Color = Tuple[int, int, int]
Cell = Tuple[int, int]
ColorMap = Mapping[Cell, Color]


def _safe_config_write(config: Any, name: str, value: Any) -> None:
    try:
        setattr(config, name, value)
    except _CONFIG_WRITE_ERRORS as exc:
        log_throttled(
            logger,
            f"perkey.commit_pipeline.config_write.{name}",
            interval_s=60,
            level=logging.DEBUG,
            msg=f"Failed to update per-key commit config field: {name}",
            exc=exc,
        )


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

        if safe_int_attr(config, "brightness", default=0) == 0:
            _safe_config_write(config, "brightness", 25)

        _safe_config_write(config, "effect", "perkey")
        _safe_config_write(config, "per_key_colors", full)

        brightness = safe_int_attr(config, "brightness", default=0)

        kb2 = push_fn(
            kb,
            full,
            brightness=brightness,
            enable_user_mode=True,
        )

        return kb2, full
