from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import src.core.power.system.modes as _modes

if TYPE_CHECKING:
    from src.core.power.system.modes import PowerMode


def _write_mode_epp_preferences(mode: PowerMode, *, policies: list[Path]) -> None:
    for pol in policies:
        epp_choice = _modes._pick_epp_value(mode, available=_modes._available_epp_preferences(pol))
        if epp_choice is None or not _modes._has_epp(pol):
            continue
        try:
            _modes._write_epp(pol, epp_choice)
        except OSError:
            pass


def _apply_mode_sysfs(mode: PowerMode, *, root: Path, extreme_cap_khz: int) -> None:
    policies = _modes._policy_dirs(root)
    if not policies:
        raise FileNotFoundError(f"No cpufreq policies under {root}")

    target_extreme_cap_khz = _modes.normalize_extreme_saver_cap_khz(extreme_cap_khz)

    if mode in (_modes.PowerMode.BALANCED, _modes.PowerMode.PERFORMANCE):
        try:
            _modes._set_boost_enabled(True)
        except OSError:
            pass

    for pol in policies:
        max_path = pol / "scaling_max_freq"
        if not max_path.exists():
            continue

        min_khz = _modes._read_int(pol / "cpuinfo_min_freq") or 0
        max_khz = _modes._read_int(pol / "cpuinfo_max_freq")
        available_governors = _modes._available_governors(pol)

        if mode == _modes.PowerMode.EXTREME_SAVER:
            target = target_extreme_cap_khz
            if min_khz:
                target = max(target, min_khz)
            if max_khz:
                target = min(target, max_khz)
            _modes._write_scaling_freq_range(pol, min_khz=int(target), max_khz=int(target))

            gov = pol / "scaling_governor"
            if gov.exists() and "powersave" in available_governors:
                # Best-effort; may not be supported.
                try:
                    _modes._write_text(gov, "powersave\n")
                except OSError:
                    pass

        elif mode in (_modes.PowerMode.BALANCED, _modes.PowerMode.PERFORMANCE):
            restore_min_khz = int(min_khz) if min_khz else None
            restore_max_khz = int(max_khz) if max_khz else None
            _modes._write_scaling_freq_range(pol, min_khz=restore_min_khz, max_khz=restore_max_khz)

            gov = pol / "scaling_governor"
            if gov.exists():
                try:
                    governor_value: str | None = None
                    if mode == _modes.PowerMode.PERFORMANCE:
                        if "performance" in available_governors:
                            governor_value = "performance\n"
                        elif "powersave" in available_governors:
                            governor_value = "powersave\n"
                    else:
                        if _modes._has_epp(pol) and "powersave" in available_governors:
                            governor_value = "powersave\n"
                        elif "schedutil" in available_governors:
                            governor_value = "schedutil\n"
                    if governor_value is not None:
                        _modes._write_text(gov, governor_value)
                except OSError:
                    pass

    # Boost handling is global-ish.
    if mode == _modes.PowerMode.EXTREME_SAVER:
        try:
            _modes._set_boost_enabled(False)
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
                _modes._POWER_HELPER_ACTION_ID,
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
        str(_modes.normalize_extreme_saver_cap_khz(extreme_cap_khz)),
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


def apply_mode(mode: PowerMode, *, root: Path, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
    """Apply a power mode via sysfs and/or privileged helper.

    Returns True if the writes completed (direct or via helper).
    Returns False if both direct writes and the helper failed.
    """
    # First try direct writes (works if user already has permissions).
    # We look up _apply_mode_sysfs on _modes so test monkeypatching of
    # the re-exported name continues to work.
    try:
        _modes._apply_mode_sysfs(mode, root=root, extreme_cap_khz=extreme_cap_khz)
        return True
    except PermissionError:
        pass
    except OSError:
        # If direct write fails for other reasons, still allow helper.
        pass

    return _modes._run_privileged_helper(
        mode,
        extreme_cap_khz=extreme_cap_khz,
        allow_interactive=allow_interactive,
    )
