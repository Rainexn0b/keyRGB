from __future__ import annotations

from collections.abc import Callable


def read_logind_idle_seconds(
    *,
    session_id: str,
    run_fn: Callable[[list[str], float], str | None],
    monotonic_fn: Callable[[], float],
) -> float | None:
    """Read idle time via logind IdleHint, best-effort."""

    out = run_fn(
        [
            "loginctl",
            "show-session",
            session_id,
            "-p",
            "IdleHint",
            "-p",
            "IdleSinceHintMonotonic",
        ],
        1.0,
    )
    if out is None:
        return None

    idle_hint_s: str | None = None
    idle_since_us_s: str | None = None
    for raw_line in out.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "IdleHint":
            idle_hint_s = v
        elif k == "IdleSinceHintMonotonic":
            idle_since_us_s = v

    if idle_hint_s is None:
        return None

    s = idle_hint_s.strip().lower()
    if s in {"yes", "true", "1"}:
        is_idle = True
    elif s in {"no", "false", "0"}:
        is_idle = False
    else:
        return None

    if not is_idle:
        return 0.0

    try:
        idle_since_us = int((idle_since_us_s or "").strip())
        now_us = int(monotonic_fn() * 1_000_000)
        idle_us = max(0, now_us - idle_since_us)
        return idle_us / 1_000_000.0
    except (ValueError, OverflowError):
        return None
