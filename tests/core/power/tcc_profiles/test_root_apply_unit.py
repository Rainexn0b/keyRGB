from __future__ import annotations

import subprocess

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

from src.core.power.tcc_profiles.models import TccProfileWriteError
from src.core.power.tcc_profiles import root_apply


def _cp(argv: list[str], returncode: int, *, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)


def test_tccd_binary_prefers_env_override_and_has_default_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_TCCD_BIN", "/custom/tccd")
    assert root_apply._tccd_binary() == "/custom/tccd"

    monkeypatch.delenv("KEYRGB_TCCD_BIN", raising=False)
    assert root_apply._tccd_binary() == root_apply._DEFAULT_TCCD_BIN


def test_run_root_command_as_root_uses_direct_subprocess_run(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(argv: list[str], *, check: bool, capture_output: bool, text: bool):
        seen["argv"] = argv
        seen["check"] = check
        seen["capture_output"] = capture_output
        seen["text"] = text
        return _cp(argv, 0)

    monkeypatch.setattr(root_apply.os, "geteuid", lambda: 0)
    monkeypatch.setattr(root_apply.subprocess, "run", fake_run)

    result = root_apply._run_root_command(["/usr/bin/tccd", "--new_profiles", "/tmp/p.json"])

    assert result.returncode == 0
    assert seen["argv"] == ["/usr/bin/tccd", "--new_profiles", "/tmp/p.json"]
    assert seen["check"] is False
    assert seen["capture_output"] is True
    assert seen["text"] is True


def test_run_root_command_non_root_uses_pkexec_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(root_apply.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        root_apply.shutil,
        "which",
        lambda name: "/usr/bin/pkexec" if name == "pkexec" else None,
    )

    seen: dict[str, object] = {}

    def fake_run(argv: list[str], *, check: bool, capture_output: bool, text: bool):
        seen["argv"] = argv
        return _cp(argv, 0)

    monkeypatch.setattr(root_apply.subprocess, "run", fake_run)

    root_apply._run_root_command(["/usr/bin/tccd", "--new_profiles", "/tmp/p.json"])

    assert seen["argv"] == ["/usr/bin/pkexec", "/usr/bin/tccd", "--new_profiles", "/tmp/p.json"]


def test_run_root_command_non_root_uses_sudo_when_pkexec_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(root_apply.os, "geteuid", lambda: 1000)

    def fake_which(name: str):
        if name == "pkexec":
            return None
        if name == "sudo":
            return "/usr/bin/sudo"
        return None

    monkeypatch.setattr(root_apply.shutil, "which", fake_which)

    seen: dict[str, object] = {}

    def fake_run(argv: list[str], *, check: bool, capture_output: bool, text: bool):
        seen["argv"] = argv
        return _cp(argv, 0)

    monkeypatch.setattr(root_apply.subprocess, "run", fake_run)

    root_apply._run_root_command(["/usr/bin/tccd", "--new_settings", "/tmp/s.json"])

    assert seen["argv"] == ["/usr/bin/sudo", "/usr/bin/tccd", "--new_settings", "/tmp/s.json"]


def test_run_root_command_non_root_raises_when_no_escalation_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(root_apply.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(root_apply.shutil, "which", lambda name: None)

    with pytest.raises(TccProfileWriteError, match="Need root privileges"):
        root_apply._run_root_command(["/usr/bin/tccd", "--new_profiles", "/tmp/p.json"])


@pytest.mark.parametrize(
    "apply_fn_name, flag",
    [
        ("_apply_new_profiles_file", "--new_profiles"),
        ("_apply_new_settings_file", "--new_settings"),
    ],
)
def test_apply_new_file_raises_when_tccd_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
    apply_fn_name: str,
    flag: str,
) -> None:
    monkeypatch.setattr(root_apply, "_tccd_binary", lambda: "/missing/tccd")
    monkeypatch.setattr(root_apply.os.path, "exists", lambda path: False)

    def unexpected_run(argv: list[str]):
        raise AssertionError(f"should not run command when binary is missing: {argv}")

    monkeypatch.setattr(root_apply, "_run_root_command", unexpected_run)

    with pytest.raises(TccProfileWriteError, match="tccd binary not found"):
        getattr(root_apply, apply_fn_name)("/tmp/input.json")


@pytest.mark.parametrize(
    "apply_fn_name, flag",
    [
        ("_apply_new_profiles_file", "--new_profiles"),
        ("_apply_new_settings_file", "--new_settings"),
    ],
)
def test_apply_new_file_raises_with_stdout_fallback_text_when_command_fails(
    monkeypatch: pytest.MonkeyPatch,
    apply_fn_name: str,
    flag: str,
) -> None:
    monkeypatch.setattr(root_apply, "_tccd_binary", lambda: "/opt/tccd")
    monkeypatch.setattr(root_apply.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        root_apply,
        "_run_root_command",
        lambda argv: _cp(argv, 7, stdout="daemon said no", stderr=""),
    )

    with pytest.raises(TccProfileWriteError, match=f"tccd {flag} failed: daemon said no"):
        getattr(root_apply, apply_fn_name)("/tmp/input.json")


@pytest.mark.parametrize(
    "apply_fn_name",
    ["_apply_new_profiles_file", "_apply_new_settings_file"],
)
def test_apply_new_file_success_path_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    apply_fn_name: str,
) -> None:
    monkeypatch.setattr(root_apply, "_tccd_binary", lambda: "/opt/tccd")
    monkeypatch.setattr(root_apply.os.path, "exists", lambda path: True)
    monkeypatch.setattr(root_apply, "_run_root_command", lambda argv: _cp(argv, 0))

    getattr(root_apply, apply_fn_name)("/tmp/input.json")