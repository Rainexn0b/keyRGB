from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests._paths import REPO_ROOT

_HELPER_PATH = Path(REPO_ROOT) / "system" / "bin" / "keyrgb-power-helper"


def _load_helper() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("keyrgb_power_helper", str(_HELPER_PATH))
    spec = importlib.util.spec_from_loader("keyrgb_power_helper", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_power_helper_ignores_sysfs_root_env_when_running_as_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 0)
    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(tmp_path / "cpufreq"))
    monkeypatch.setenv("KEYRGB_LEDS_ROOT", str(tmp_path / "leds"))

    assert helper._cpufreq_root() == helper.CPUFREQ_ROOT_DEFAULT
    assert helper._leds_root() == helper.LEDS_ROOT_DEFAULT


def test_power_helper_honors_sysfs_root_env_when_unprivileged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    cpufreq = tmp_path / "cpufreq"
    leds = tmp_path / "leds"
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1000)
    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(cpufreq))
    monkeypatch.setenv("KEYRGB_LEDS_ROOT", str(leds))

    assert helper._cpufreq_root() == cpufreq
    assert helper._leds_root() == leds


def test_power_helper_surfaces_nonfatal_epp_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    policy = tmp_path / "policy0"
    policy.mkdir()
    monkeypatch.setattr(helper, "_available_epp_preferences", lambda _policy: {"performance"})
    monkeypatch.setattr(helper, "_has_epp", lambda _policy: True)
    monkeypatch.setattr(
        helper,
        "_write",
        lambda _path, _text: (_ for _ in ()).throw(OSError("read-only EPP")),
    )

    assert helper._write_mode_epp_preferences("performance", policies=[policy]) is False
    assert "Non-fatal EPP write failed" in capsys.readouterr().err
