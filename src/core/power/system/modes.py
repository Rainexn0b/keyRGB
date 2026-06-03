from __future__ import annotations

import os
import shutil  # noqa: F401  — re-exported for test monkeypatching
import subprocess  # noqa: F401  — re-exported for test monkeypatching
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


_CPUFREQ_ROOT_DEFAULT = Path("/sys/devices/system/cpu/cpufreq")
DEFAULT_EXTREME_SAVER_CAP_KHZ = 800_000
MIN_EXTREME_SAVER_CAP_KHZ = 400_000
MAX_EXTREME_SAVER_CAP_KHZ = 5_000_000
_EXTREME_SAVER_DETECTION_MARGIN_KHZ = 100_000
_POWER_HELPER_ACTION_ID = "org.keyrgb.power-helper.apply"


class PowerMode(str, Enum):
    EXTREME_SAVER = "extreme-saver"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PowerModeStatus:
    supported: bool
    mode: PowerMode
    reason: str
    identifiers: dict[str, str]


def normalize_extreme_saver_cap_khz(value: object) -> int:
    try:
        if isinstance(value, (int, str, bytes, bytearray)):
            khz = int(value)
        else:
            khz = int(str(value))
    except (TypeError, ValueError, OverflowError):
        khz = DEFAULT_EXTREME_SAVER_CAP_KHZ
    return max(MIN_EXTREME_SAVER_CAP_KHZ, min(MAX_EXTREME_SAVER_CAP_KHZ, khz))


def configured_extreme_saver_cap_khz() -> int:
    try:
        from src.core.config import Config

        return normalize_extreme_saver_cap_khz(Config().system_power_extreme_cap_khz)
    except (AttributeError, ImportError, LookupError, OSError, RuntimeError, TypeError, ValueError):
        return DEFAULT_EXTREME_SAVER_CAP_KHZ


def _cpufreq_root() -> Path:
    # Test hook: allow overriding the sysfs root.
    root = os.environ.get("KEYRGB_CPUFREQ_ROOT")
    return Path(root) if root else _CPUFREQ_ROOT_DEFAULT


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None


def _read_int(path: Path) -> Optional[int]:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _normalized_lower_text(path: Path) -> str | None:
    value = _read_text(path)
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _policy_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    out: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and child.name.startswith("policy"):
                out.append(child)
    except OSError:
        return []
    return sorted(out, key=lambda p: p.name)


def _available_governors(policy: Path) -> set[str]:
    raw = _normalized_lower_text(policy / "scaling_available_governors")
    if not raw:
        return set()
    return {part for part in raw.split() if part}


def _driver_name(policy: Path) -> str | None:
    return _normalized_lower_text(policy / "scaling_driver")


def _epp_path(policy: Path) -> Path:
    return policy / "energy_performance_preference"


def _available_epp_preferences(policy: Path) -> set[str]:
    raw = _normalized_lower_text(policy / "energy_performance_available_preferences")
    if not raw:
        return set()
    return {part for part in raw.split() if part}


def _read_epp(policy: Path) -> str | None:
    return _normalized_lower_text(_epp_path(policy))


def _has_epp(policy: Path) -> bool:
    return _epp_path(policy).exists()


def _pick_epp_value(mode: PowerMode, *, available: set[str]) -> str | None:
    if not available:
        return None

    if mode == PowerMode.EXTREME_SAVER:
        for candidate in ("power", "balance_power", "default"):
            if candidate in available:
                return candidate
        return next(iter(sorted(available)))

    if mode == PowerMode.BALANCED:
        for candidate in ("balance_performance", "balance_power", "default", "power"):
            if candidate in available:
                return candidate
        return next(iter(sorted(available)))

    if mode == PowerMode.PERFORMANCE:
        for candidate in ("performance", "balance_performance", "default"):
            if candidate in available:
                return candidate
        return next(iter(sorted(available)))

    return None


def _write_epp(policy: Path, value: str) -> None:
    _write_text(_epp_path(policy), f"{value}\n")


def _boost_paths() -> list[Path]:
    # Different drivers expose boost/turbo differently.
    return [
        Path("/sys/devices/system/cpu/intel_pstate/no_turbo"),
        Path("/sys/devices/system/cpu/cpufreq/boost"),
    ]


def _read_boost_enabled() -> Optional[bool]:
    # intel_pstate/no_turbo: 1 => turbo disabled
    p = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if p.exists():
        v = _read_int(p)
        if v is None:
            return None
        return v == 0

    # cpufreq/boost: 1 => boost enabled
    p = Path("/sys/devices/system/cpu/cpufreq/boost")
    if p.exists():
        v = _read_int(p)
        if v is None:
            return None
        return v == 1

    return None


def _set_boost_enabled(enabled: bool) -> None:
    # Best-effort: write whichever knob exists.
    p = Path("/sys/devices/system/cpu/intel_pstate/no_turbo")
    if p.exists():
        _write_text(p, "0\n" if enabled else "1\n")
        return

    p = Path("/sys/devices/system/cpu/cpufreq/boost")
    if p.exists():
        _write_text(p, "1\n" if enabled else "0\n")
        return


def _write_scaling_freq_range(policy: Path, *, min_khz: int | None, max_khz: int | None) -> None:
    min_path = policy / "scaling_min_freq"
    max_path = policy / "scaling_max_freq"
    current_min = _read_int(min_path) if min_path.exists() else None
    current_max = _read_int(max_path) if max_path.exists() else None

    # Expand the current range first so the follow-up tightening writes do not
    # trip cpufreq validation when the requested target moves up or down.
    if min_khz is not None and min_path.exists() and current_min is not None and int(min_khz) < current_min:
        _write_text(min_path, f"{int(min_khz)}\n")
        current_min = int(min_khz)

    if max_khz is not None and max_path.exists() and current_max is not None and int(max_khz) > current_max:
        _write_text(max_path, f"{int(max_khz)}\n")
        current_max = int(max_khz)

    if max_khz is not None and max_path.exists() and current_max != int(max_khz):
        _write_text(max_path, f"{int(max_khz)}\n")
        current_max = int(max_khz)

    if min_khz is not None and min_path.exists() and current_min != int(min_khz):
        _write_text(min_path, f"{int(min_khz)}\n")


def is_supported() -> bool:
    root = _cpufreq_root()
    policies = _policy_dirs(root)
    if not policies:
        return False
    # Require at least one scaling_max_freq knob.
    return any((p / "scaling_max_freq").exists() for p in policies)


def get_current_freq_stats_khz() -> tuple[int | None, int | None]:
    root = _cpufreq_root()
    policies = _policy_dirs(root)
    if not policies:
        return (None, None)

    current_freqs: list[int] = []
    for pol in policies:
        current_khz = _read_int(pol / "scaling_cur_freq")
        if current_khz is not None:
            current_freqs.append(current_khz)

    if not current_freqs:
        return (None, None)
    average_khz = int(round(sum(current_freqs) / len(current_freqs)))
    max_khz = max(current_freqs)
    return (average_khz, max_khz)


def get_average_current_freq_khz() -> int | None:
    average_khz, _max_khz = get_current_freq_stats_khz()
    return average_khz


def get_max_current_freq_khz() -> int | None:
    _average_khz, max_khz = get_current_freq_stats_khz()
    return max_khz


# ---------------------------------------------------------------------------
# Observation layer (reads sysfs, best-effort mode inference)
# ---------------------------------------------------------------------------

from ._observe import get_status as _get_status_obs  # noqa: E402

# Re-export for the public facade and for test monkeypatching.
get_status = _get_status_obs


def _mode_is_active(mode: PowerMode) -> bool:
    """Best-effort check whether the requested mode appears to be active.

    This is intentionally heuristic: it reads sysfs and infers the current
    mode, which may disagree with the last-applied mode for legitimate
    driver-specific reasons. Callers should not treat a False result as a
    failure to apply."""
    status = get_status()
    return bool(status.supported and status.mode == mode)


# ---------------------------------------------------------------------------
# Apply layer (writes sysfs, invokes helper)
# ---------------------------------------------------------------------------

from ._apply import (  # noqa: E402
    _apply_mode_sysfs,  # noqa: F401  — re-exported for test monkeypatching
    _pkexec_noninteractive_authorized,  # noqa: F401  — re-exported for test monkeypatching
    _run_privileged_helper,  # noqa: F401  — re-exported for test monkeypatching
    apply_mode as _apply_mode_impl,
)


def set_mode(mode: PowerMode, *, allow_interactive: bool = True) -> bool:
    """Apply a power mode. Returns True if sysfs/helper writes succeeded.

    Success is based on whether the writes completed, not on a heuristic
    readback of the system state. The observation layer (get_status) may
    report a different mode for driver-specific reasons; that is expected
    and does not indicate an application failure."""
    if not isinstance(mode, PowerMode):
        try:
            mode = PowerMode(str(mode))
        except ValueError:
            return False

    if mode == PowerMode.UNKNOWN:
        return False

    root = _cpufreq_root()
    extreme_cap_khz = configured_extreme_saver_cap_khz()

    return _apply_mode_impl(
        mode,
        root=root,
        extreme_cap_khz=extreme_cap_khz,
        allow_interactive=allow_interactive,
    )
