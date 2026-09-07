from __future__ import annotations

from pathlib import Path

import pytest

import keyrgb.core.power.system._apply as system_apply
import keyrgb.core.power.system.modes as system_modes
from keyrgb.core.power.system import PowerMode


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
    monkeypatch.setattr(system_apply, "_privileged_bin", fake_which)
    monkeypatch.setattr(system_apply.subprocess, "run", fake_run)

    assert (
        system_apply._run_privileged_helper(
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
            "org.keyrgb.power-helper.apply",
            "--process",
            "12345",
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
    ]


def test_run_privileged_helper_skips_pkexec_when_noninteractive_keyrgb_action_rejects(
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
    monkeypatch.setattr(system_apply, "_privileged_bin", fake_which)
    monkeypatch.setattr(system_apply.subprocess, "run", fake_run)

    assert (
        system_apply._run_privileged_helper(
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
            "org.keyrgb.power-helper.apply",
            "--process",
            "12345",
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
    monkeypatch.setattr(system_apply, "_privileged_bin", fake_which)
    monkeypatch.setattr(system_apply.subprocess, "run", fake_run)

    assert (
        system_apply._run_privileged_helper(
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
            "org.keyrgb.power-helper.apply",
            "--process",
            "12345",
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
    monkeypatch.setattr(system_apply, "_privileged_bin", fake_which)
    monkeypatch.setattr(system_apply.subprocess, "run", fake_run)

    assert (
        system_apply._run_privileged_helper(
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


def test_privileged_bin_prefers_usr_bin_and_ignores_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    usr_bin = tmp_path / "usr" / "bin"
    alt_bin = tmp_path / "bin"
    evil_bin = tmp_path / "evil"
    usr_bin.mkdir(parents=True)
    alt_bin.mkdir()
    evil_bin.mkdir()
    pkexec = usr_bin / "pkexec"
    pkexec.write_text("#!/bin/sh\n", encoding="utf-8")
    pkexec.chmod(0o755)
    (evil_bin / "pkexec").write_text("#!/bin/sh\n", encoding="utf-8")
    (evil_bin / "pkexec").chmod(0o755)

    monkeypatch.setattr(system_apply, "_PRIVILEGED_BIN_DIRS", (usr_bin, alt_bin))
    monkeypatch.setenv("PATH", str(evil_bin))

    assert system_apply._privileged_bin("pkexec") == str(pkexec)
    assert system_apply._privileged_bin("sudo") is None
    assert system_apply._privileged_bin("bash") is None
