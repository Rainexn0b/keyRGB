from __future__ import annotations

from pathlib import Path

import pytest

import src.core.power.system.modes as system_modes
from src.core.power.system import PowerMode, get_status, is_supported, set_mode


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
    from src.core.config import Config

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


def test_apply_mode_sysfs_uses_epp_preferences_for_amd_pstate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000, min_khz=600000)
    _add_epp_files(policy)

    monkeypatch.setattr(system_modes, "_set_boost_enabled", lambda enabled: None)

    system_modes._apply_mode_sysfs(
        PowerMode.EXTREME_SAVER,
        root=root,
        extreme_cap_khz=1_004_000,
    )

    assert (policy / "energy_performance_preference").read_text(encoding="utf-8").strip() == "power"
    assert (policy / "scaling_governor").read_text(encoding="utf-8").strip() == "powersave"
    assert int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip()) == 1_004_000
    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 1_004_000

    system_modes._apply_mode_sysfs(
        PowerMode.BALANCED,
        root=root,
        extreme_cap_khz=1_004_000,
    )

    assert (policy / "energy_performance_preference").read_text(encoding="utf-8").strip() == "balance_performance"
    assert (policy / "scaling_governor").read_text(encoding="utf-8").strip() == "powersave"
    assert int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip()) == 600_000
    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 3_000_000

    system_modes._apply_mode_sysfs(
        PowerMode.PERFORMANCE,
        root=root,
        extreme_cap_khz=1_004_000,
    )

    assert (policy / "energy_performance_preference").read_text(encoding="utf-8").strip() == "performance"
    assert (policy / "scaling_governor").read_text(encoding="utf-8").strip() == "performance"
    assert int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip()) == 600_000
    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 3_000_000


def test_apply_mode_sysfs_rereads_epp_after_governor_change(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000, min_khz=600000)
    _add_epp_files(policy, current_pref="performance", available_prefs="performance")
    (policy / "scaling_governor").write_text("performance\n", encoding="utf-8")

    def dynamic_epp_preferences(pol: Path) -> set[str]:
        governor = (pol / "scaling_governor").read_text(encoding="utf-8").strip()
        if governor == "performance":
            return {"performance"}
        return {"default", "performance", "balance_performance", "balance_power", "power"}

    monkeypatch.setattr(system_modes, "_available_epp_preferences", dynamic_epp_preferences)
    monkeypatch.setattr(system_modes, "_set_boost_enabled", lambda enabled: None)

    system_modes._apply_mode_sysfs(
        PowerMode.EXTREME_SAVER,
        root=root,
        extreme_cap_khz=1_004_000,
    )

    assert (policy / "scaling_governor").read_text(encoding="utf-8").strip() == "powersave"
    assert (policy / "energy_performance_preference").read_text(encoding="utf-8").strip() == "power"


def test_apply_mode_sysfs_enables_boost_before_restoring_performance_cap(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3000000, min_khz=600000)
    _add_epp_files(policy)
    (policy / "scaling_max_freq").write_text("1004000\n", encoding="utf-8")

    boost_enabled = False
    real_write_text = system_modes._write_text

    def fake_set_boost_enabled(enabled: bool) -> None:
        nonlocal boost_enabled
        boost_enabled = enabled

    def fake_write_text(path: Path, text: str) -> None:
        if path.name == "scaling_max_freq" and int(text.strip()) > 2_000_000 and not boost_enabled:
            real_write_text(path, "2000000\n")
            return
        real_write_text(path, text)

    monkeypatch.setattr(system_modes, "_set_boost_enabled", fake_set_boost_enabled)
    monkeypatch.setattr(system_modes, "_write_text", fake_write_text)

    system_modes._apply_mode_sysfs(
        PowerMode.PERFORMANCE,
        root=root,
        extreme_cap_khz=1_004_000,
    )

    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 3_000_000


def test_apply_mode_sysfs_reorders_min_max_writes_for_extreme_target_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "cpufreq"
    policy = _make_policy(root, "policy0", max_khz=3_000_000, min_khz=600_000)
    _add_epp_files(policy)

    real_write_text = system_modes._write_text

    def guarded_write_text(path: Path, text: str) -> None:
        if path.name == "scaling_min_freq":
            value = int(text.strip())
            current_max = int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip())
            assert value <= current_max
        if path.name == "scaling_max_freq":
            value = int(text.strip())
            current_min = int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip())
            assert value >= current_min
        real_write_text(path, text)

    monkeypatch.setattr(system_modes, "_set_boost_enabled", lambda enabled: None)
    monkeypatch.setattr(system_modes, "_write_text", guarded_write_text)

    system_modes._apply_mode_sysfs(
        PowerMode.EXTREME_SAVER,
        root=root,
        extreme_cap_khz=1_004_000,
    )
    assert int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip()) == 1_004_000
    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 1_004_000

    system_modes._apply_mode_sysfs(
        PowerMode.EXTREME_SAVER,
        root=root,
        extreme_cap_khz=1_709_000,
    )
    assert int((policy / "scaling_min_freq").read_text(encoding="utf-8").strip()) == 1_709_000
    assert int((policy / "scaling_max_freq").read_text(encoding="utf-8").strip()) == 1_709_000


def test_set_mode_falls_back_to_helper_on_sysfs_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    helper_calls: list[tuple[PowerMode, int, bool]] = []

    monkeypatch.setattr(system_modes, "configured_extreme_saver_cap_khz", lambda: 1_250_000)
    monkeypatch.setattr(
        system_modes,
        "get_status",
        lambda: system_modes.PowerModeStatus(
            supported=True,
            mode=PowerMode.BALANCED,
            reason="ok",
            identifiers={},
        ),
    )

    def raise_oserror(_mode: PowerMode, *, root: Path, extreme_cap_khz: int) -> None:
        assert extreme_cap_khz == 1_250_000
        raise OSError("sysfs write failed")

    def fake_helper(mode: PowerMode, *, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
        helper_calls.append((mode, extreme_cap_khz, allow_interactive))
        return True

    monkeypatch.setattr(system_modes, "_apply_mode_sysfs", raise_oserror)
    monkeypatch.setattr(system_modes, "_run_privileged_helper", fake_helper)

    assert set_mode(PowerMode.BALANCED) is True
    assert helper_calls == [(PowerMode.BALANCED, 1_250_000, True)]


def test_set_mode_falls_back_to_helper_when_direct_apply_does_not_change_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper_calls: list[tuple[PowerMode, int, bool]] = []
    observed_modes = [PowerMode.BALANCED, PowerMode.PERFORMANCE]

    monkeypatch.setattr(system_modes, "configured_extreme_saver_cap_khz", lambda: 1_250_000)
    monkeypatch.setattr(system_modes, "_apply_mode_sysfs", lambda *_args, **_kwargs: None)

    def fake_status() -> system_modes.PowerModeStatus:
        return system_modes.PowerModeStatus(
            supported=True,
            mode=observed_modes.pop(0),
            reason="ok",
            identifiers={},
        )

    def fake_helper(mode: PowerMode, *, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
        helper_calls.append((mode, extreme_cap_khz, allow_interactive))
        return True

    monkeypatch.setattr(system_modes, "get_status", fake_status)
    monkeypatch.setattr(system_modes, "_run_privileged_helper", fake_helper)

    assert set_mode(PowerMode.PERFORMANCE, allow_interactive=False) is True
    assert helper_calls == [(PowerMode.PERFORMANCE, 1_250_000, False)]


def test_set_mode_returns_false_when_helper_succeeds_but_mode_stays_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper_calls: list[tuple[PowerMode, int, bool]] = []

    monkeypatch.setattr(system_modes, "configured_extreme_saver_cap_khz", lambda: 1_250_000)
    monkeypatch.setattr(system_modes, "_apply_mode_sysfs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        system_modes,
        "get_status",
        lambda: system_modes.PowerModeStatus(
            supported=True,
            mode=PowerMode.BALANCED,
            reason="ok",
            identifiers={},
        ),
    )

    def fake_helper(mode: PowerMode, *, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
        helper_calls.append((mode, extreme_cap_khz, allow_interactive))
        return True

    monkeypatch.setattr(system_modes, "_run_privileged_helper", fake_helper)

    assert set_mode(PowerMode.PERFORMANCE, allow_interactive=False) is False
    assert helper_calls == [(PowerMode.PERFORMANCE, 1_250_000, False)]


def test_run_privileged_helper_uses_pkexec_disable_internal_agent_when_noninteractive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        run_calls.append(list(argv))
        return type("Completed", (), {"returncode": 0})()

    def fake_which(name: str) -> str | None:
        if name in {"pkcheck", "pkexec"}:
            return f"/usr/bin/{name}"
        return None

    monkeypatch.setattr(system_modes.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(system_modes.os, "getpid", lambda: 12345)
    monkeypatch.setattr(system_modes.shutil, "which", fake_which)
    monkeypatch.setattr(system_modes.subprocess, "run", fake_run)

    assert (
        system_modes._run_privileged_helper(
            PowerMode.EXTREME_SAVER,
            extreme_cap_khz=1_400_000,
            allow_interactive=False,
        )
        is True
    )
    assert run_calls == [
        [
            "/usr/bin/pkcheck",
            "--action-id",
            "org.freedesktop.policykit.exec",
            "--process",
            "12345",
            "--detail",
            "program",
            "/usr/local/bin/keyrgb-power-helper",
        ],
        [
            "/usr/bin/pkexec",
            "--disable-internal-agent",
            "/usr/local/bin/keyrgb-power-helper",
            "apply",
            "extreme-saver",
            "--extreme-cap-khz",
            "1400000",
        ]
    ]


def test_run_privileged_helper_skips_pkexec_when_noninteractive_pkcheck_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        run_calls.append(list(argv))
        return type("Completed", (), {"returncode": 0 if argv[0] == "/usr/bin/sudo" else 1})()

    def fake_which(name: str) -> str | None:
        if name in {"pkcheck", "pkexec", "sudo"}:
            return f"/usr/bin/{name}"
        return None

    monkeypatch.setattr(system_modes.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(system_modes.os, "getpid", lambda: 12345)
    monkeypatch.setattr(system_modes.shutil, "which", fake_which)
    monkeypatch.setattr(system_modes.subprocess, "run", fake_run)

    assert (
        system_modes._run_privileged_helper(
            PowerMode.EXTREME_SAVER,
            extreme_cap_khz=1_400_000,
            allow_interactive=False,
        )
        is True
    )
    assert run_calls == [
        [
            "/usr/bin/pkcheck",
            "--action-id",
            "org.freedesktop.policykit.exec",
            "--process",
            "12345",
            "--detail",
            "program",
            "/usr/local/bin/keyrgb-power-helper",
        ],
        [
            "/usr/bin/sudo",
            "-n",
            "/usr/local/bin/keyrgb-power-helper",
            "apply",
            "extreme-saver",
            "--extreme-cap-khz",
            "1400000",
        ],
    ]


def test_run_privileged_helper_falls_back_to_sudo_n_when_noninteractive_pkexec_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        run_calls.append(list(argv))
        if argv[0] == "/usr/bin/pkcheck":
            return type("Completed", (), {"returncode": 0})()
        return type("Completed", (), {"returncode": 0 if argv[0] == "/usr/bin/sudo" else 1})()

    def fake_which(name: str) -> str | None:
        if name in {"pkcheck", "pkexec", "sudo"}:
            return f"/usr/bin/{name}"
        return None

    monkeypatch.setattr(system_modes.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(system_modes.os, "getpid", lambda: 12345)
    monkeypatch.setattr(system_modes.shutil, "which", fake_which)
    monkeypatch.setattr(system_modes.subprocess, "run", fake_run)

    assert (
        system_modes._run_privileged_helper(
            PowerMode.EXTREME_SAVER,
            extreme_cap_khz=1_400_000,
            allow_interactive=False,
        )
        is True
    )
    assert run_calls == [
        [
            "/usr/bin/pkcheck",
            "--action-id",
            "org.freedesktop.policykit.exec",
            "--process",
            "12345",
            "--detail",
            "program",
            "/usr/local/bin/keyrgb-power-helper",
        ],
        [
            "/usr/bin/pkexec",
            "--disable-internal-agent",
            "/usr/local/bin/keyrgb-power-helper",
            "apply",
            "extreme-saver",
            "--extreme-cap-khz",
            "1400000",
        ],
        [
            "/usr/bin/sudo",
            "-n",
            "/usr/local/bin/keyrgb-power-helper",
            "apply",
            "extreme-saver",
            "--extreme-cap-khz",
            "1400000",
        ],
    ]


def test_run_privileged_helper_uses_sudo_noninteractive_flag_when_needed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls: list[list[str]] = []

    def fake_run(argv, **_kwargs):
        run_calls.append(list(argv))
        return type("Completed", (), {"returncode": 0})()

    def fake_which(name: str) -> str | None:
        if name == "sudo":
            return "/usr/bin/sudo"
        return None

    monkeypatch.setattr(system_modes.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(system_modes.shutil, "which", fake_which)
    monkeypatch.setattr(system_modes.subprocess, "run", fake_run)

    assert (
        system_modes._run_privileged_helper(
            PowerMode.BALANCED,
            extreme_cap_khz=1_400_000,
            allow_interactive=False,
        )
        is True
    )
    assert run_calls == [
        [
            "/usr/bin/sudo",
            "-n",
            "/usr/local/bin/keyrgb-power-helper",
            "apply",
            "balanced",
            "--extreme-cap-khz",
            "1400000",
        ]
    ]


def test_set_mode_propagates_unexpected_runtime_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    helper_calls: list[tuple[PowerMode, int, bool]] = []

    def raise_runtime_error(_mode: PowerMode, *, root: Path, extreme_cap_khz: int) -> None:
        assert extreme_cap_khz == 800_000
        raise RuntimeError("unexpected bug")

    def fake_helper(mode: PowerMode, *, extreme_cap_khz: int, allow_interactive: bool = True) -> bool:
        helper_calls.append((mode, extreme_cap_khz, allow_interactive))
        return True

    monkeypatch.setattr(system_modes, "_apply_mode_sysfs", raise_runtime_error)
    monkeypatch.setattr(system_modes, "_run_privileged_helper", fake_helper)

    with pytest.raises(RuntimeError, match="unexpected bug"):
        set_mode(PowerMode.BALANCED)

    assert helper_calls == []
