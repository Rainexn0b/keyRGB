from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


_CPUFREQ_ROOT_DEFAULT = Path("/sys/devices/system/cpu/cpufreq")


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


def _cpufreq_root() -> Path:
    # Test hook: allow overriding the sysfs root.
    root = os.environ.get("KEYRGB_CPUFREQ_ROOT")
    return Path(root) if root else _CPUFREQ_ROOT_DEFAULT


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _read_int(path: Path) -> Optional[int]:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _policy_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    out: list[Path] = []
    try:
        for child in root.iterdir():
            if child.is_dir() and child.name.startswith("policy"):
                out.append(child)
    except Exception:
        return []
    return sorted(out, key=lambda p: p.name)


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


def is_supported() -> bool:
    root = _cpufreq_root()
    policies = _policy_dirs(root)
    if not policies:
        return False
    # Require at least one scaling_max_freq knob.
    return any((p / "scaling_max_freq").exists() for p in policies)


def _infer_mode(*, policies: list[Path]) -> PowerMode:
    # Infer from a couple of strong signals.
    max_freqs: list[int] = []
    max_possible: list[int] = []
    governors: list[str] = []

    for pol in policies:
        m = _read_int(pol / "scaling_max_freq")
        if m is not None:
            max_freqs.append(m)
        cm = _read_int(pol / "cpuinfo_max_freq")
        if cm is not None:
            max_possible.append(cm)
        g = _read_text(pol / "scaling_governor")
        if g:
            governors.append(g)

    boost = _read_boost_enabled()

    # If we can see an explicit performance governor, treat it as a hint.
    if governors and all(g == "performance" for g in governors) and boost is True:
        return PowerMode.PERFORMANCE

    # Extreme saver: capped hard and boost off.
    if max_freqs:
        cap = min(max_freqs)
        if cap <= 900_000 and (boost is False or boost is None):
            return PowerMode.EXTREME_SAVER

    # Balanced by default when supported.
    return PowerMode.BALANCED


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

    mode = _infer_mode(policies=policies)
    ids: dict[str, str] = {
        "cpufreq_root": str(root),
        "policies": str(len(policies)),
    }

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


def _apply_mode_sysfs(mode: PowerMode, *, root: Path) -> None:
    policies = _policy_dirs(root)
    if not policies:
        raise FileNotFoundError(f"No cpufreq policies under {root}")

    # Desired cap for extreme saver: 0.8 GHz (kHz units).
    extreme_cap_khz = 800_000

    for pol in policies:
        max_path = pol / "scaling_max_freq"
        if not max_path.exists():
            continue

        min_khz = _read_int(pol / "cpuinfo_min_freq") or 0
        max_khz = _read_int(pol / "cpuinfo_max_freq")

        if mode == PowerMode.EXTREME_SAVER:
            target = extreme_cap_khz
            if min_khz:
                target = max(target, min_khz)
            if max_khz:
                target = min(target, max_khz)
            _write_text(max_path, f"{int(target)}\n")

            gov = pol / "scaling_governor"
            if gov.exists():
                # Best-effort; may not be supported.
                try:
                    _write_text(gov, "powersave\n")
                except Exception:
                    pass

        elif mode in (PowerMode.BALANCED, PowerMode.PERFORMANCE):
            # Restore max to cpuinfo max.
            if max_khz:
                _write_text(max_path, f"{int(max_khz)}\n")

            gov = pol / "scaling_governor"
            if gov.exists():
                try:
                    _write_text(gov, "performance\n" if mode == PowerMode.PERFORMANCE else "schedutil\n")
                except Exception:
                    pass

    # Boost handling is global-ish.
    if mode == PowerMode.EXTREME_SAVER:
        try:
            _set_boost_enabled(False)
        except Exception:
            pass
    elif mode in (PowerMode.BALANCED, PowerMode.PERFORMANCE):
        try:
            _set_boost_enabled(True)
        except Exception:
            pass


def _run_privileged_helper(mode: PowerMode) -> bool:
    helper = os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")
    argv = [helper, "apply", str(mode.value)]

    if os.geteuid() == 0:
        cp = subprocess.run(argv, check=False, capture_output=True, text=True)
        return cp.returncode == 0

    pkexec = shutil.which("pkexec")
    if pkexec:
        cp = subprocess.run([pkexec, *argv], check=False, capture_output=True, text=True)
        return cp.returncode == 0

    sudo = shutil.which("sudo")
    if sudo:
        cp = subprocess.run([sudo, *argv], check=False)
        return cp.returncode == 0

    return False


def set_mode(mode: PowerMode) -> bool:
    if not isinstance(mode, PowerMode):
        try:
            mode = PowerMode(str(mode))
        except Exception:
            return False

    if mode == PowerMode.UNKNOWN:
        return False

    root = _cpufreq_root()

    # First try direct writes (works if user already has permissions).
    try:
        _apply_mode_sysfs(mode, root=root)
        return True
    except PermissionError:
        pass
    except Exception:
        # If direct write fails for other reasons, still allow helper.
        pass

    return _run_privileged_helper(mode)
