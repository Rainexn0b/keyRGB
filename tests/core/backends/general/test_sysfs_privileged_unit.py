from __future__ import annotations

import pytest

from tests._paths import ensure_repo_root_on_sys_path


ensure_repo_root_on_sys_path()

import src.core.backends.sysfs.privileged as sysfs_privileged


def test_helper_can_apply_led_matches_helper_contract() -> None:
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight") is True
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="multi_intensity") is True
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="color") is True
    assert sysfs_privileged.helper_can_apply_led("ite_8297:1") is False
    assert sysfs_privileged.helper_can_apply_led("rgb:kbd_backlight", color_kind="rgb") is False
    assert sysfs_privileged.helper_can_apply_led("system76::kbd_backlight", color_kind="file") is False


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
