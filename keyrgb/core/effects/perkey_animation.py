from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from typing import TypeVar, cast

from keyrgb.core.utils.logging_utils import log_throttled

logger = logging.getLogger(__name__)

RECOVERY_USER_MODE_SAVE_ENV = "KEYRGB_RECOVERY_USER_MODE_SAVE"

# Diagnostic override for the per-key mode policy. Each backend declares the
# policy its firmware needs (e.g. ITE8291R3 re-asserts user mode every frame,
# costing ~2-4ms of USB traffic per frame). This env var lets hardware testing
# A/B whether a specific device actually needs the reassert; the policy
# definition and normalization live in ``keyrgb.core.backends.policies``:
#   KEYRGB_PER_KEY_MODE_POLICY=init_once
# Failure mode when a device DOES need the reassert: the deck freezes, reverts
# to a hardware effect, or goes dark mid-animation. Unset = backend default.
_PERKEY_CONFIG_LOAD_ERRORS = (AttributeError, ImportError, LookupError, OSError, TypeError, ValueError)
_ENABLE_USER_MODE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_HIDDEN_PERKEY_RESTORE_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_T = TypeVar("_T")


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


def load_per_key_colors_from_config() -> dict[tuple[int, int], tuple[int, int, int]]:
    """Best-effort load of per-key colors from the legacy config."""

    def _load_colors() -> dict[tuple[int, int], tuple[int, int, int]]:
        from keyrgb.core.config import Config

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
    base_color: tuple[int, int, int],
    per_key_colors: Mapping[tuple[int, int], tuple[int, int, int]] | None,
    num_rows: int,
    num_cols: int,
) -> dict[tuple[int, int], tuple[int, int, int]]:
    """Fill the full matrix with base_color, then overlay per-key values."""

    base: tuple[int, int, int] = (
        int(base_color[0]),
        int(base_color[1]),
        int(base_color[2]),
    )
    rows = int(num_rows)
    cols = int(num_cols)
    full: dict[tuple[int, int], tuple[int, int, int]] = {(r, c): base for r in range(rows) for c in range(cols)}

    for (row, col), rgb in (per_key_colors or {}).items():
        try:
            row_i = int(row)
            col_i = int(col)
            if row_i < 0 or col_i < 0 or row_i >= rows or col_i >= cols:
                continue
            rr, gg, bb = rgb
            full[(row_i, col_i)] = (int(rr), int(gg), int(bb))
        except (TypeError, ValueError):
            continue

    return full


def scaled_color_map(
    full_colors: dict[tuple[int, int], tuple[int, int, int]],
    *,
    scale: float,
) -> dict[tuple[int, int], tuple[int, int, int]]:
    """Return a new color map with each channel scaled by `scale`."""

    s = float(scale)
    out: dict[tuple[int, int], tuple[int, int, int]] = {}
    for (row, col), (r, g, b) in full_colors.items():
        out[(row, col)] = (
            max(0, min(255, int(r * s))),
            max(0, min(255, int(g * s))),
            max(0, min(255, int(b * s))),
        )
    return out


def enable_user_mode_once(*, kb, kb_lock, brightness: int, save: bool = False) -> None:
    """Enable user mode once without saving, to avoid flicker."""

    fn = getattr(kb, "enable_user_mode", None)
    if not callable(fn):
        return

    _run_with_recoverable_logging(
        fn=lambda: _enable_user_mode_locked(kb_lock=kb_lock, fn=fn, brightness=brightness, save=save),
        recoverable_errors=_ENABLE_USER_MODE_RUNTIME_ERRORS,
        throttle_key="perkey_animation.enable_user_mode_once",
        msg="Failed to enable per-key user mode",
        fallback=None,
    )


def _enable_user_mode_locked(*, kb_lock, fn: Callable[..., object], brightness: int, save: bool) -> None:
    with kb_lock:
        fn(brightness=brightness, save=bool(save))


def _recovery_user_mode_save_enabled() -> bool:
    # Hardware-validated on ite8291r3: after a hidden sleep recovery the
    # firmware's first-keypress wake ramp no longer drops the deck when the
    # restored scene was saved as its user mode.  Default on; set the env var
    # to "0" to opt out.
    return os.environ.get(RECOVERY_USER_MODE_SAVE_ENV) != "0"


def _save_restored_user_mode_best_effort(*, kb, brightness: int) -> None:
    """Save the just-restored scene as the controller's user mode.

    Enabled by default; opt out with ``KEYRGB_RECOVERY_USER_MODE_SAVE=0``.
    The ite8291r3 firmware runs its own brief brightness ramp toward its saved
    reference on the first physical keypress after a controller sleep, which
    shows up as a deck-wide dip/drop even though userspace never changed
    brightness.  Saving the restored scene makes that firmware reference match
    the deck so the wake ramp targets identical state and becomes invisible.
    """

    if not _recovery_user_mode_save_enabled():
        return
    fn = getattr(kb, "enable_user_mode", None)
    if not callable(fn):
        return

    def _save() -> None:
        fn(brightness=int(brightness), save=True)
        logger.info("recovery_user_mode_save: brightness=%d", int(brightness))

    _run_with_recoverable_logging(
        fn=_save,
        recoverable_errors=_ENABLE_USER_MODE_RUNTIME_ERRORS,
        throttle_key="perkey_animation.recovery_user_mode_save",
        msg="Failed to save restored per-key user mode",
        fallback=None,
    )


def restore_hidden_per_key_rows_once(
    *,
    kb,
    kb_lock,
    color_map,
    brightness: int,
    known_brightness: int | None = None,
    known_is_off: bool | None = None,
) -> bool:
    """Update per-key rows while brightness is already 0, then raise brightness.

    Some ITE backends keep user mode active during AC transition blanks: the
    device reports brightness 0 but does not report `is_off()`. In that window
    a full user-mode reassert can briefly flash the last programmed colors
    before the new row writes land. Prefer a hidden row rewrite first, then
    restore brightness.

    When the backend exposes ``enable_user_mode``, the restored scene is
    additionally saved as the controller's user mode (after rows and brightness
    land) so the firmware's first-keypress wake ramp targets the current scene.
    A save failure never changes the restore result.  Set
    ``KEYRGB_RECOVERY_USER_MODE_SAVE=0`` to disable the save.
    """

    def _restore_hidden_rows() -> bool:
        get_brightness = getattr(kb, "get_brightness", None)
        is_off = getattr(kb, "is_off", None)
        set_key_colors = getattr(kb, "set_key_colors", None)
        set_brightness = getattr(kb, "set_brightness", None)
        if known_brightness is None and not callable(get_brightness):
            return False
        if known_is_off is None and not callable(is_off):
            return False
        if not callable(set_key_colors) or not callable(set_brightness):
            return False

        current_brightness = (
            int(known_brightness) if known_brightness is not None else int(cast(Callable[[], int], get_brightness)())
        )
        current_is_off = bool(known_is_off) if known_is_off is not None else bool(cast(Callable[[], bool], is_off)())

        if current_brightness > 0:
            return False
        if current_is_off:
            return False

        with kb_lock:
            # Hidden blank path: rows land before brightness, user-mode command
            # deferred to the caller (blank recovery re-asserts; config-apply
            # reuse stays flash-free with enable_user_mode=False).
            set_key_colors(color_map, brightness=int(brightness), enable_user_mode=False)
            set_brightness(int(brightness))
            _save_restored_user_mode_best_effort(kb=kb, brightness=int(brightness))
        return True

    return _run_with_recoverable_logging(
        fn=_restore_hidden_rows,
        recoverable_errors=_HIDDEN_PERKEY_RESTORE_ERRORS,
        throttle_key="perkey_animation.restore_hidden_rows_once",
        msg="Failed to restore hidden per-key rows",
        fallback=False,
    )
