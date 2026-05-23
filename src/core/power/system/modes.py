from __future__ import annotations

import os
import shutil
import subprocess
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


def _write_mode_epp_preferences(mode: PowerMode, *, policies: list[Path]) -> None:
    for pol in policies:
        epp_choice = _pick_epp_value(mode, available=_available_epp_preferences(pol))
        if epp_choice is None or not _has_epp(pol):
            continue
        try:
            _write_epp(pol, epp_choice)
        except OSError:
            pass


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


def _infer_mode(*, policies: list[Path], extreme_cap_khz: int) -> PowerMode:
    # Infer from a couple of strong signals.
    max_freqs: list[int] = []
    max_possible: list[int] = []
    governors: list[str] = []
    epp_values: list[str] = []

    for pol in policies:
        m = _read_int(pol / "scaling_max_freq")
        if m is not None:
            max_freqs.append(m)
        cm = _read_int(pol / "cpuinfo_max_freq")
        if cm is not None:
            max_possible.append(cm)
        g = _read_text(pol / "scaling_governor")
        if g:
            governors.append(g.strip().lower())
        epp = _read_epp(pol)
        if epp:
            epp_values.append(epp)

    boost = _read_boost_enabled()

    # If boost state is unavailable, explicit performance governor/EPP is still
    # the strongest signal. Only reject performance when boost is explicitly off.
    boost_allows_performance = boost is not False

    if governors and all(g == "performance" for g in governors) and boost_allows_performance:
        return PowerMode.PERFORMANCE

    # EPP-driven policies (for example amd-pstate-epp) often keep the governor
    # at powersave and express the effective mode via the EPP preference.
    if epp_values and all(value == "performance" for value in epp_values) and boost_allows_performance:
        return PowerMode.PERFORMANCE

    # Extreme saver: capped hard and boost off.
    if max_freqs:
        cap = min(max_freqs)
        threshold = int(extreme_cap_khz) + _EXTREME_SAVER_DETECTION_MARGIN_KHZ
        epp_extreme = not epp_values or all(value in {"power", "balance_power"} for value in epp_values)
        if cap <= threshold and (boost is False or boost is None) and epp_extreme:
            return PowerMode.EXTREME_SAVER

    # Balanced by default when supported.
    return PowerMode.BALANCED


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


def get_status() -> PowerModeStatus:
    root = _cpufreq_root()
    policies = _policy_dirs(root)
    if not policies:
        return PowerModeStatus(
            supported=False,
            mode=PowerMode.UNKNOWN,
            reason="cpufreq policies not found",
            identifiers={"cpufreq_root": str(root)},
        )

    if not any((p / "scaling_max_freq").exists() for p in policies):
        return PowerModeStatus(
            supported=False,
            mode=PowerMode.UNKNOWN,
            reason="cpufreq scaling_max_freq not available",
            identifiers={"cpufreq_root": str(root)},
        )

    extreme_cap_khz = configured_extreme_saver_cap_khz()
    mode = _infer_mode(policies=policies, extreme_cap_khz=extreme_cap_khz)
    ids: dict[str, str] = {
        "cpufreq_root": str(root),
        "policies": str(len(policies)),
        "configured_extreme_cap_khz": str(extreme_cap_khz),
    }
    driver_name = _driver_name(policies[0])
    if driver_name:
        ids["driver"] = driver_name
    epp = _read_epp(policies[0])
    if epp:
        ids["epp"] = epp

    # Can we likely apply changes without prompting every time?
    helper = os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")
    helper_present = Path(helper).exists()
    writable = any(os.access(p / "scaling_max_freq", os.W_OK) for p in policies)
    ids["helper_present"] = str(bool(helper_present)).lower()
    ids["sysfs_writable"] = str(bool(writable)).lower()
    ids["can_apply"] = str(bool(helper_present or writable)).lower()

    boost = _read_boost_enabled()
    if boost is not None:
        ids["boost_enabled"] = str(bool(boost)).lower()

    return PowerModeStatus(supported=True, mode=mode, reason="ok", identifiers=ids)


def _apply_mode_sysfs(mode: PowerMode, *, root: Path, extreme_cap_khz: int) -> None:
    policies = _policy_dirs(root)
    if not policies:
        raise FileNotFoundError(f"No cpufreq policies under {root}")

    target_extreme_cap_khz = normalize_extreme_saver_cap_khz(extreme_cap_khz)

    if mode in (PowerMode.BALANCED, PowerMode.PERFORMANCE):
        try:
            _set_boost_enabled(True)
        except OSError:
            pass

    for pol in policies:
        max_path = pol / "scaling_max_freq"
        if not max_path.exists():
            continue

        min_khz = _read_int(pol / "cpuinfo_min_freq") or 0
        max_khz = _read_int(pol / "cpuinfo_max_freq")
        available_governors = _available_governors(pol)

        if mode == PowerMode.EXTREME_SAVER:
            target = target_extreme_cap_khz
            if min_khz:
                target = max(target, min_khz)
            if max_khz:
                target = min(target, max_khz)
            _write_scaling_freq_range(pol, min_khz=int(target), max_khz=int(target))

            gov = pol / "scaling_governor"
            if gov.exists() and "powersave" in available_governors:
                # Best-effort; may not be supported.
                try:
                    _write_text(gov, "powersave\n")
                except OSError:
                    pass

        elif mode in (PowerMode.BALANCED, PowerMode.PERFORMANCE):
            restore_min_khz = int(min_khz) if min_khz else None
            restore_max_khz = int(max_khz) if max_khz else None
            _write_scaling_freq_range(pol, min_khz=restore_min_khz, max_khz=restore_max_khz)

            gov = pol / "scaling_governor"
            if gov.exists():
                try:
                    governor_value: str | None = None
                    if mode == PowerMode.PERFORMANCE:
                        if "performance" in available_governors:
                            governor_value = "performance\n"
                        elif "powersave" in available_governors:
                            governor_value = "powersave\n"
                    else:
                        if _has_epp(pol) and "powersave" in available_governors:
                            governor_value = "powersave\n"
                        elif "schedutil" in available_governors:
                            governor_value = "schedutil\n"
                    if governor_value is not None:
                        _write_text(gov, governor_value)
                except OSError:
                    pass

    # Boost handling is global-ish.
    if mode == PowerMode.EXTREME_SAVER:
        try:
            _set_boost_enabled(False)
        except OSError:
            pass

    # Some drivers expose mode-dependent EPP choices. amd-pstate-epp, for
    # example, can show only "performance" while the governor is performance.
    # Re-read and write EPP after governor/boost changes settle.
    _write_mode_epp_preferences(mode, policies=policies)


def _pkexec_noninteractive_authorized(pkcheck: str) -> bool:
    try:
        cp = subprocess.run(
            [
                pkcheck,
                "--action-id",
                _POWER_HELPER_ACTION_ID,
                "--process",
                str(os.getpid()),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return cp.returncode == 0


def _run_privileged_helper(mode: PowerMode, *, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
    helper = os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")
    argv = [
        helper,
        "apply",
        str(mode.value),
        "--extreme-cap-khz",
        str(normalize_extreme_saver_cap_khz(extreme_cap_khz)),
    ]

    if os.geteuid() == 0:
        cp = subprocess.run(argv, check=False, capture_output=True, text=True)
        return cp.returncode == 0

    pkexec = shutil.which("pkexec")
    if pkexec:
        if allow_interactive:
            cp = subprocess.run([pkexec, *argv], check=False, capture_output=True, text=True)
            return cp.returncode == 0

        pkcheck = shutil.which("pkcheck")
        if pkcheck and _pkexec_noninteractive_authorized(pkcheck):
            cp = subprocess.run(
                [pkexec, "--disable-internal-agent", *argv],
                check=False,
                capture_output=True,
                text=True,
            )
            if cp.returncode == 0:
                return True

    sudo = shutil.which("sudo")
    if sudo:
        sudo_argv = [sudo, *argv] if allow_interactive else [sudo, "-n", *argv]
        cp = subprocess.run(sudo_argv, check=False, capture_output=True, text=True)
        return cp.returncode == 0

    return False


def _mode_is_active(mode: PowerMode) -> bool:
    status = get_status()
    return bool(status.supported and status.mode == mode)


def set_mode(mode: PowerMode, *, allow_interactive: bool = True) -> bool:
    if not isinstance(mode, PowerMode):
        try:
            mode = PowerMode(str(mode))
        except ValueError:
            return False

    if mode == PowerMode.UNKNOWN:
        return False

    root = _cpufreq_root()
    extreme_cap_khz = configured_extreme_saver_cap_khz()

    # First try direct writes (works if user already has permissions).
    try:
        _apply_mode_sysfs(mode, root=root, extreme_cap_khz=extreme_cap_khz)
        if _mode_is_active(mode):
            return True
    except PermissionError:
        pass
    except OSError:
        # If direct write fails for other reasons, still allow helper.
        pass

    helper_applied = _run_privileged_helper(
        mode,
        extreme_cap_khz=extreme_cap_khz,
        allow_interactive=allow_interactive,
    )
    if not helper_applied:
        return False
    return _mode_is_active(mode)
