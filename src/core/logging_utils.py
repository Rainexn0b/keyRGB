from __future__ import annotations

import threading
import time


_last_log_times: dict[str, float] = {}
_lock = threading.Lock()


def log_throttled(
    logger,
    key: str,
    *,
    interval_s: float,
    level: int,
    msg: str,
    exc: BaseException | None = None,
) -> bool:
    """Log at most once per *interval_s* for a given *key*.

    Returns True if the message was logged.
    """

    now = time.monotonic()
    with _lock:
        last = _last_log_times.get(key, 0.0)
        if (now - last) < interval_s:
            return False
        _last_log_times[key] = now

    if exc is not None:
        # Prefer proper exception logging when available.
        try:
            logger.log(level, msg, exc_info=exc)
        except TypeError:
            logger.log(level, msg, exc_info=True)
        return True

    logger.log(level, msg)
    return True
