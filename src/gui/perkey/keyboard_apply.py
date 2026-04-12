from __future__ import annotations

from typing import Any, Mapping, Tuple

from src.core.utils.exceptions import is_device_busy, is_device_disconnected


_RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_PERKEY_WRITE_RUNTIME_ERRORS = (AttributeError, LookupError, RuntimeError, TypeError, ValueError)


def push_per_key_colors(
    kb: Any,
    colors: Mapping[Tuple[int, int], Tuple[int, int, int]],
    *,
    brightness: int,
    enable_user_mode: bool = True,
) -> Any:
    """Best-effort push of per-key colors to the hardware.

    Returns the (possibly updated) kb handle. If the device is busy/unavailable,
    returns None so callers can stop attempting hardware writes.
    """

    if kb is None:
        return None

    try:
        if enable_user_mode and hasattr(kb, "enable_user_mode"):
            try:
                kb.enable_user_mode(brightness=brightness, save=True)
            except TypeError:
                # Some backends may expose enable_user_mode without a save kwarg.
                try:
                    kb.enable_user_mode(brightness=brightness)
                except _RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS:
                    pass
            except _RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS:
                pass

        kb.set_key_colors(
            colors,
            brightness=brightness,
            enable_user_mode=enable_user_mode,
        )
        return kb
    except OSError as exc:
        if is_device_busy(exc):
            return None
        if is_device_disconnected(exc):
            return None
        return kb
    except _PERKEY_WRITE_RUNTIME_ERRORS:
        return kb
