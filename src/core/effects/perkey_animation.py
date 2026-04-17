from __future__ import annotations

import logging
from collections.abc import Callable
from collections.abc import Mapping
from typing import Dict, Tuple, TypeVar

from src.core.utils.logging_utils import log_throttled


logger = logging.getLogger(__name__)

PER_KEY_MODE_POLICY_INIT_ONCE = "init_once"
PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME = "reassert_every_frame"
_PERKEY_CONFIG_LOAD_ERRORS = (AttributeError, ImportError, LookupError, OSError, TypeError, ValueError)
_ENABLE_USER_MODE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_T = TypeVar("_T")


def normalize_per_key_mode_policy(policy: object) -> str:
    value = str(policy or PER_KEY_MODE_POLICY_INIT_ONCE).strip().lower()
    if value == PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME:
        return PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME
    return PER_KEY_MODE_POLICY_INIT_ONCE


def per_key_mode_policy(kb: object) -> str:
    return normalize_per_key_mode_policy(getattr(kb, "keyrgb_per_key_mode_policy", None))


def per_key_mode_requires_frame_reassert(kb: object) -> bool:
    return per_key_mode_policy(kb) == PER_KEY_MODE_POLICY_REASSERT_EVERY_FRAME


def _run_with_recoverable_logging(
    *,
    fn: Callable[[], _T],
    recoverable_errors: tuple[type[BaseException], ...],
    throttle_key: str,
    msg: str,
    fallback: _T,
) -> _T:
    try:
        return fn()
    # @quality-exception exception-transparency: recoverable config/property access
    # and runtime hardware calls must keep logging and degrade behavior explicit.
    except recoverable_errors as exc:
        log_throttled(
            logger,
            throttle_key,
            interval_s=120,
            level=logging.DEBUG,
            msg=msg,
            exc=exc,
        )
        return fallback


def load_per_key_colors_from_config() -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Best-effort load of per-key colors from the legacy config."""

    def _load_colors() -> Dict[Tuple[int, int], Tuple[int, int, int]]:
        from src.core.config import Config

        cfg = Config()
        return dict(getattr(cfg, "per_key_colors", {}) or {})

    return _run_with_recoverable_logging(
        fn=_load_colors,
        recoverable_errors=_PERKEY_CONFIG_LOAD_ERRORS,
        throttle_key="legacy.perkey_animation.load_config",
        msg="Failed to load per-key colors from config",
        fallback={},
    )


def build_full_color_grid(
    *,
    base_color: Tuple[int, int, int],
    per_key_colors: Mapping[Tuple[int, int], Tuple[int, int, int]] | None,
    num_rows: int,
    num_cols: int,
) -> Dict[Tuple[int, int], Tuple[int, int, int]]:
    """Fill the full matrix with base_color, then overlay per-key values."""

    base: Tuple[int, int, int] = (
        int(base_color[0]),
        int(base_color[1]),
        int(base_color[2]),
    )
    full: Dict[Tuple[int, int], Tuple[int, int, int]] = {
        (r, c): base for r in range(int(num_rows)) for c in range(int(num_cols))
    }

    for (row, col), rgb in (per_key_colors or {}).items():
        try:
            rr, gg, bb = rgb
            full[(int(row), int(col))] = (int(rr), int(gg), int(bb))
        except (TypeError, ValueError):
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

    fn = getattr(kb, "enable_user_mode", None)
    if not callable(fn):
        return

    _run_with_recoverable_logging(
        fn=lambda: _enable_user_mode_locked(kb_lock=kb_lock, fn=fn, brightness=brightness),
        recoverable_errors=_ENABLE_USER_MODE_RUNTIME_ERRORS,
        throttle_key="perkey_animation.enable_user_mode_once",
        msg="Failed to enable per-key user mode",
        fallback=None,
    )


def _enable_user_mode_locked(*, kb_lock, fn: Callable[..., object], brightness: int) -> None:
    with kb_lock:
        fn(brightness=brightness, save=False)
