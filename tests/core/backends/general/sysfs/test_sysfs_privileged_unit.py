from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import keyrgb.core.backends.sysfs.privileged as sysfs_privileged
from tests._paths import REPO_ROOT

_HELPER_PATH = Path(REPO_ROOT) / "system" / "bin" / "keyrgb-power-helper"


def _load_shipped_helper() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("keyrgb_power_helper_shipped", str(_HELPER_PATH))
    spec = importlib.util.spec_from_loader("keyrgb_power_helper_shipped", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_helper_can_apply_led_matches_helper_contract() -> None:
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight") is True
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="multi_intensity") is True
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="color") is True
    assert sysfs_privileged.helper_can_apply_led("ite_8297:1") is True
    assert sysfs_privileged.helper_can_apply_led("ite_8297:2") is True
    assert sysfs_privileged.helper_can_apply_led("ite_8297:3") is True
    assert sysfs_privileged.helper_can_apply_led("ite_8297:4") is False  # only channels 1-3
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="rgb") is False
    assert sysfs_privileged.helper_can_apply_led("system76::kbd_backlight", color_kind="file") is False


def test_caller_and_shipped_helper_agree_on_ite8297_allowlist() -> None:
    shipped = _load_shipped_helper()

    accepted = [
        "rgb:kbd_backlight",
        "ite_8297:1",
        "ite_8297:2",
        "ite_8297:3",
        "ITE_8297:1",
        "Ite_8297:3",
    ]
    for name in accepted:
        assert sysfs_privileged.helper_can_apply_led(name) is True, name
        assert shipped._validate_led_name(name) == name.strip(), name

    rejected = [
        "ite_8297:4",
        "ite_8297:0",
        "ite_8297:",
        "ite_8297:12",
        "ite_8297:1x",
        "ite_8298:1",
        "ite_8297-1",
        "ite_8297:1.",
        "../ite_8297:1",
        "ite_8297:1/../x",
        "..\\ite_8297:1",
        "ite_8297:1\\x",
        "platform::micmute",
        "input3::capslock",
        "random-led",
        "",
        "   ",
    ]
    for name in rejected:
        assert sysfs_privileged.helper_can_apply_led(name) is False, name
        with pytest.raises(SystemExit):
            shipped._validate_led_name(name)


def test_helper_supports_led_apply_returns_false_when_helper_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KEYRGB_POWER_HELPER", "/tmp/keyrgb-missing-helper")
    monkeypatch.setattr(
        sysfs_privileged.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run should not be called")),
    )

    assert sysfs_privileged.helper_supports_led_apply() is False


def test_helper_supports_led_apply_returns_false_when_helper_probe_raises_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    helper = tmp_path / "keyrgb-power-helper"
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("KEYRGB_POWER_HELPER", str(helper))

    def fake_run(*_args, **_kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(sysfs_privileged.subprocess, "run", fake_run)

    assert sysfs_privileged.helper_supports_led_apply() is False


def test_helper_supports_led_apply_propagates_unexpected_probe_bug(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    helper = tmp_path / "keyrgb-power-helper"
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("KEYRGB_POWER_HELPER", str(helper))

    def fake_run(*_args, **_kwargs):
        raise RuntimeError("probe bug")

    monkeypatch.setattr(sysfs_privileged.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="probe bug"):
        sysfs_privileged.helper_supports_led_apply()


def test_run_led_apply_ignores_recoverable_debug_logging_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG", "1")
    monkeypatch.setattr(sysfs_privileged.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        sysfs_privileged.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    monkeypatch.setattr(
        sysfs_privileged.logger,
        "info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    assert sysfs_privileged.run_led_apply(led="rgb:kbd_backlight", brightness=25, rgb=None) is True


def test_privileged_bin_prefers_usr_bin_and_ignores_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
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

    monkeypatch.setattr(sysfs_privileged, "_PRIVILEGED_BIN_DIRS", (usr_bin, alt_bin))
    monkeypatch.setenv("PATH", str(evil_bin))

    assert sysfs_privileged._privileged_bin("pkexec") == str(pkexec)
    assert sysfs_privileged._privileged_bin("sudo") is None
    assert sysfs_privileged._privileged_bin("bash") is None


def test_run_led_apply_uses_pinned_pkexec_when_unprivileged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_bin(name: str) -> str | None:
        return "/usr/bin/pkexec" if name == "pkexec" else None

    def fake_run(argv, **_kwargs):
        calls.append(list(argv))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sysfs_privileged.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(sysfs_privileged, "_privileged_bin", fake_bin)
    monkeypatch.setattr(sysfs_privileged.subprocess, "run", fake_run)

    assert sysfs_privileged.run_led_apply(led="rgb:kbd_backlight", brightness=25, rgb=None) is True
    assert calls == [
        ["/usr/bin/pkexec", sysfs_privileged._power_helper(), "led-apply", "rgb:kbd_backlight", "--brightness", "25"]
    ]


def test_run_led_apply_propagates_unexpected_debug_logging_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KEYRGB_DEBUG", "1")
    monkeypatch.setattr(sysfs_privileged.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        sysfs_privileged.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    monkeypatch.setattr(
        sysfs_privileged.logger,
        "info",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected logger bug")),
    )

    with pytest.raises(AssertionError, match="unexpected logger bug"):
        sysfs_privileged.run_led_apply(led="rgb:kbd_backlight", brightness=25, rgb=None)
