from __future__ import annotations

from pathlib import Path
from typing import Optional


_RECOVERABLE_READ_EXCEPTIONS = (OSError, UnicodeError)


def _profile_name(on_ac_power: Optional[bool]) -> str:
    if on_ac_power is False:
        return "Battery"
    return "AC"


def _parse_powerdevilrc_dim_timeout(text: str, *, on_ac_power: Optional[bool]) -> Optional[float]:
    """Parse DimDisplayIdleTimeoutSec from KDE powerdevilrc for the active profile.

    powerdevilrc uses nested groups written as ``[Profile][Subgroup]``,
    e.g. ``[AC][Display]``.  We look for ``DimDisplayIdleTimeoutSec`` in the
    matching ``[Profile][Display]`` section.  If the active profile does not
    define the key, we return ``None`` so the caller can fall back.
    """

    target_profile = _profile_name(on_ac_power)
    target_section = f"[{target_profile}][Display]"

    in_target_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            in_target_section = line == target_section
            continue
        if not in_target_section:
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != "DimDisplayIdleTimeoutSec":
            continue
        try:
            timeout_s = float(value.strip())
        except (TypeError, ValueError):
            return None
        if timeout_s < 0:
            return None
        return timeout_s

    return None


def read_kde_dim_timeout(
    on_ac_power: Optional[bool],
    *,
    config_home: Path | None = None,
) -> Optional[float]:
    """Best-effort KDE screen-dim timeout in seconds for the active power profile."""

    base = config_home or (Path.home() / ".config")
    path = base / "powerdevilrc"
    try:
        text = path.read_text(encoding="utf-8")
    except _RECOVERABLE_READ_EXCEPTIONS:
        return None
    return _parse_powerdevilrc_dim_timeout(text, on_ac_power=on_ac_power)
