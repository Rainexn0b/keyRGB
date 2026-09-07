from __future__ import annotations

from pathlib import Path

import pytest

import keyrgb.core.power.system.modes as system_modes
from keyrgb.core.power.system import PowerMode, get_status, is_supported, set_mode


def _make_policy(root: Path, name: str, *, max_khz: int = 2500000, min_khz: int = 400000) -> Path:
    pol = root / name
    pol.mkdir(parents=True)
    (pol / "scaling_min_freq").write_text(f"{min_khz}\n", encoding="utf-8")
    (pol / "scaling_max_freq").write_text(f"{max_khz}\n", encoding="utf-8")
    (pol / "cpuinfo_max_freq").write_text(f"{max_khz}\n", encoding="utf-8")
    (pol / "cpuinfo_min_freq").write_text(f"{min_khz}\n", encoding="utf-8")
    (pol / "scaling_governor").write_text("schedutil\n", encoding="utf-8")
    return pol


def _add_epp_files(
    policy: Path,
    *,
    driver: str = "amd-pstate-epp",
    current_pref: str = "balance_performance",
    available_prefs: str = "default performance balance_performance balance_power power",
    available_governors: str = "performance powersave",
) -> Path:
    (policy / "scaling_driver").write_text(f"{driver}\n", encoding="utf-8")
    (policy / "energy_performance_preference").write_text(f"{current_pref}\n", encoding="utf-8")
    (policy / "energy_performance_available_preferences").write_text(f"{available_prefs}\n", encoding="utf-8")
    (policy / "scaling_available_governors").write_text(f"{available_governors}\n", encoding="utf-8")
    return policy


def test_system_power_mode_supported_and_sets_extreme(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    _make_policy(root, "policy0")
    _make_policy(root, "policy1")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))

    assert is_supported() is True

    st0 = get_status()
    assert st0.supported is True

    assert set_mode(PowerMode.EXTREME_SAVER) is True

    pinned_min = int((root / "policy0" / "scaling_min_freq").read_text(encoding="utf-8").strip())
    pinned_max = int((root / "policy0" / "scaling_max_freq").read_text(encoding="utf-8").strip())
    assert pinned_min == system_modes.DEFAULT_EXTREME_SAVER_CAP_KHZ
    assert pinned_max == system_modes.DEFAULT_EXTREME_SAVER_CAP_KHZ

    st1 = get_status()
    assert st1.supported is True
    assert st1.mode in (PowerMode.EXTREME_SAVER, PowerMode.BALANCED)


def test_system_power_mode_balanced_restores_max(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    pol = _make_policy(root, "policy0", max_khz=3000000)

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))

    # First force a cap.
    (pol / "scaling_min_freq").write_text("800000\n", encoding="utf-8")
    (pol / "scaling_max_freq").write_text("800000\n", encoding="utf-8")

    assert set_mode(PowerMode.BALANCED) is True
    restored_min = int((pol / "scaling_min_freq").read_text(encoding="utf-8").strip())
    restored = int((pol / "scaling_max_freq").read_text(encoding="utf-8").strip())
    assert restored_min == 400000
    assert restored == 3000000


def test_system_power_mode_uses_configured_extreme_cap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from keyrgb.core.config import Config

    root = tmp_path / "cpufreq"
    _make_policy(root, "policy0", max_khz=3000000)

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setenv("KEYRGB_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setenv("KEYRGB_CONFIG_PATH", str(tmp_path / "cfg" / "config.json"))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: False)

    cfg = Config()
    cfg.system_power_extreme_cap_khz = 1_300_000

    assert set_mode(PowerMode.EXTREME_SAVER) is True

    pinned_min = int((root / "policy0" / "scaling_min_freq").read_text(encoding="utf-8").strip())
    capped = int((root / "policy0" / "scaling_max_freq").read_text(encoding="utf-8").strip())
    assert pinned_min == 1_300_000
    assert capped == 1_300_000
    assert get_status().mode == PowerMode.EXTREME_SAVER


def test_get_status_reports_performance_for_epp_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000)
    _add_epp_files(policy, current_pref="performance")
    (policy / "scaling_governor").write_text("powersave\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: True)

    assert get_status().mode == PowerMode.PERFORMANCE


def test_get_status_reports_performance_for_epp_policy_when_boost_state_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000)
    _add_epp_files(policy, current_pref="performance")
    (policy / "scaling_governor").write_text("powersave\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: None)

    assert get_status().mode == PowerMode.PERFORMANCE


def test_get_status_reports_performance_for_governor_when_boost_state_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000)
    (policy / "scaling_governor").write_text("performance\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: None)

    assert get_status().mode == PowerMode.PERFORMANCE


def test_get_status_reports_performance_for_balance_performance_epp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """EPP 'balance_performance' should be recognized as PERFORMANCE because
    _pick_epp_value legitimately falls back to it when 'performance' EPP is
    not available."""
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000)
    _add_epp_files(policy, current_pref="balance_performance")
    (policy / "scaling_governor").write_text("powersave\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: True)

    assert get_status().mode == PowerMode.PERFORMANCE


def test_get_status_reports_performance_for_mixed_epp_policies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """On heterogeneous CPUs different policies may have different EPP values
    after PERFORMANCE application (e.g. 'performance' on P-cores,
    'balance_performance' on E-cores)."""
    root = tmp_path / "cpufreq"
    policy0 = _make_policy(root, "policy0", max_khz=3000000)
    policy1 = _make_policy(root, "policy1", max_khz=3000000)
    _add_epp_files(policy0, current_pref="performance")
    _add_epp_files(policy1, current_pref="balance_performance")
    (policy0 / "scaling_governor").write_text("powersave\n", encoding="utf-8")
    (policy1 / "scaling_governor").write_text("powersave\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: True)

    assert get_status().mode == PowerMode.PERFORMANCE


def test_get_status_does_not_report_performance_when_boost_is_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000)
    _add_epp_files(policy, current_pref="performance")
    (policy / "scaling_governor").write_text("performance\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))
    monkeypatch.setattr(system_modes, "_read_boost_enabled", lambda: False)

    assert get_status().mode == PowerMode.BALANCED


def test_get_average_current_freq_khz_returns_policy_average(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    policy0 = _make_policy(root, "policy0", max_khz=3000000)
    policy1 = _make_policy(root, "policy1", max_khz=3000000)
    (policy0 / "scaling_cur_freq").write_text("600000\n", encoding="utf-8")
    (policy1 / "scaling_cur_freq").write_text("1400000\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))

    assert system_modes.get_average_current_freq_khz() == 1_000_000


def test_get_current_freq_stats_khz_returns_average_and_max(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    policy0 = _make_policy(root, "policy0", max_khz=3000000)
    policy1 = _make_policy(root, "policy1", max_khz=3000000)
    policy2 = _make_policy(root, "policy2", max_khz=3000000)
    (policy0 / "scaling_cur_freq").write_text("600000\n", encoding="utf-8")
    (policy1 / "scaling_cur_freq").write_text("1017000\n", encoding="utf-8")
    (policy2 / "scaling_cur_freq").write_text("620000\n", encoding="utf-8")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))

    assert system_modes.get_current_freq_stats_khz() == (745667, 1_017_000)
    assert system_modes.get_max_current_freq_khz() == 1_017_000
