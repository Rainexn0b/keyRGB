from __future__ import annotations

from .modes import (
    DEFAULT_EXTREME_SAVER_CAP_KHZ,
    MAX_EXTREME_SAVER_CAP_KHZ,
    MIN_EXTREME_SAVER_CAP_KHZ,
    PowerMode,
    PowerModeStatus,
    configured_extreme_saver_cap_khz,
    get_current_freq_stats_khz,
    get_average_current_freq_khz,
    get_max_current_freq_khz,
    get_status,
    is_supported,
    normalize_extreme_saver_cap_khz,
    set_mode,
)

__all__ = [
    "DEFAULT_EXTREME_SAVER_CAP_KHZ",
    "MIN_EXTREME_SAVER_CAP_KHZ",
    "MAX_EXTREME_SAVER_CAP_KHZ",
    "PowerMode",
    "PowerModeStatus",
    "configured_extreme_saver_cap_khz",
    "get_current_freq_stats_khz",
    "get_average_current_freq_khz",
    "get_max_current_freq_khz",
    "get_status",
    "is_supported",
    "normalize_extreme_saver_cap_khz",
    "set_mode",
]
