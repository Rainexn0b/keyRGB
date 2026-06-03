from __future__ import annotations

import os
from typing import TYPE_CHECKING

import src.core.power.system.modes as _modes

if TYPE_CHECKING:
    from pathlib import Path

    from src.core.power.system.modes import PowerMode, PowerModeStatus


def _infer_mode(*, policies: list[Path], extreme_cap_khz: int) -> PowerMode:
    # Infer from a couple of strong signals.
    max_freqs: list[int] = []
    max_possible: list[int] = []
    governors: list[str] = []
    epp_values: list[str] = []

    for pol in policies:
        m = _modes._read_int(pol / "scaling_max_freq")
        if m is not None:
            max_freqs.append(m)
        cm = _modes._read_int(pol / "cpuinfo_max_freq")
        if cm is not None:
            max_possible.append(cm)
        g = _modes._read_text(pol / "scaling_governor")
        if g:
            governors.append(g.strip().lower())
        epp = _modes._read_epp(pol)
        if epp:
            epp_values.append(epp)

    boost = _modes._read_boost_enabled()

    # If boost state is unavailable, explicit performance governor/EPP is still
    # the strongest signal. Only reject performance when boost is explicitly off.
    boost_allows_performance = boost is not False

    if governors and all(g == "performance" for g in governors) and boost_allows_performance:
        return _modes.PowerMode.PERFORMANCE

    # EPP-driven policies (for example amd-pstate-epp) often keep the governor
    # at powersave and express the effective mode via the EPP preference.
    # We accept "performance" or "balance_performance" because _pick_epp_value
    # legitimately falls back to "balance_performance" when "performance" is
    # not available on a given policy (common on heterogeneous CPUs).
    if (
        epp_values
        and all(value in {"performance", "balance_performance"} for value in epp_values)
        and boost_allows_performance
    ):
        return _modes.PowerMode.PERFORMANCE

    # Extreme saver: capped hard and boost off.
    if max_freqs:
        cap = min(max_freqs)
        threshold = int(extreme_cap_khz) + _modes._EXTREME_SAVER_DETECTION_MARGIN_KHZ
        epp_extreme = not epp_values or all(value in {"power", "balance_power"} for value in epp_values)
        if cap <= threshold and (boost is False or boost is None) and epp_extreme:
            return _modes.PowerMode.EXTREME_SAVER

    # Balanced by default when supported.
    return _modes.PowerMode.BALANCED


def get_status() -> PowerModeStatus:
    root = _modes._cpufreq_root()
    policies = _modes._policy_dirs(root)
    if not policies:
        return _modes.PowerModeStatus(
            supported=False,
            mode=_modes.PowerMode.UNKNOWN,
            reason="cpufreq policies not found",
            identifiers={"cpufreq_root": str(root)},
        )

    if not any((p / "scaling_max_freq").exists() for p in policies):
        return _modes.PowerModeStatus(
            supported=False,
            mode=_modes.PowerMode.UNKNOWN,
            reason="cpufreq scaling_max_freq not available",
            identifiers={"cpufreq_root": str(root)},
        )

    extreme_cap_khz = _modes.configured_extreme_saver_cap_khz()
    mode = _infer_mode(policies=policies, extreme_cap_khz=extreme_cap_khz)
    ids: dict[str, str] = {
        "cpufreq_root": str(root),
        "policies": str(len(policies)),
        "configured_extreme_cap_khz": str(extreme_cap_khz),
    }
    driver_name = _modes._driver_name(policies[0])
    if driver_name:
        ids["driver"] = driver_name
    epp = _modes._read_epp(policies[0])
    if epp:
        ids["epp"] = epp

    # Can we likely apply changes without prompting every time?
    from pathlib import Path as _Path

    helper = os.environ.get("KEYRGB_POWER_HELPER", "/usr/local/bin/keyrgb-power-helper")
    helper_present = _Path(helper).exists()
    writable = any(os.access(p / "scaling_max_freq", os.W_OK) for p in policies)
    ids["helper_present"] = str(bool(helper_present)).lower()
    ids["sysfs_writable"] = str(bool(writable)).lower()
    ids["can_apply"] = str(bool(helper_present or writable)).lower()

    boost = _modes._read_boost_enabled()
    if boost is not None:
        ids["boost_enabled"] = str(bool(boost)).lower()

    return _modes.PowerModeStatus(supported=True, mode=mode, reason="ok", identifiers=ids)
