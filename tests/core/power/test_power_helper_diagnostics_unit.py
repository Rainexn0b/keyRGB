from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from tests._paths import REPO_ROOT

_HELPER_PATH = Path(REPO_ROOT) / "system" / "bin" / "keyrgb-power-helper"


def _load_helper() -> ModuleType:
    loader = importlib.machinery.SourceFileLoader("keyrgb_power_helper_diagnostics", str(_HELPER_PATH))
    spec = importlib.util.spec_from_loader("keyrgb_power_helper_diagnostics", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_policy(root: Path, *, governors: str = "schedutil powersave") -> Path:
    policy = root / "policy0"
    policy.mkdir(parents=True, exist_ok=True)
    (policy / "cpuinfo_min_freq").write_text("400000\n", encoding="utf-8")
    (policy / "cpuinfo_max_freq").write_text("4000000\n", encoding="utf-8")
    (policy / "scaling_min_freq").write_text("400000\n", encoding="utf-8")
    (policy / "scaling_max_freq").write_text("4000000\n", encoding="utf-8")
    (policy / "scaling_available_governors").write_text(f"{governors}\n", encoding="utf-8")
    (policy / "scaling_governor").write_text("powersave\n", encoding="utf-8")
    return policy


def test_led_dir_fails_closed_when_resolve_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1000)
    monkeypatch.setenv("KEYRGB_LEDS_ROOT", str(tmp_path / "leds"))

    def _boom(self: Path, *args: object, **kwargs: object) -> Path:
        raise OSError("resolve unavailable")

    monkeypatch.setattr(helper.Path, "resolve", _boom)

    with pytest.raises(SystemExit):
        helper._led_dir("rgb:kbd_backlight")

    assert "Invalid LED path" in capsys.readouterr().err


def test_boost_enable_failure_is_diagnostic_not_silent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1000)
    cpufreq = tmp_path / "cpufreq"
    _make_policy(cpufreq)
    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(cpufreq))

    def _failing_boost(enabled: bool) -> None:
        raise OSError("read-only boost")

    monkeypatch.setattr(helper, "_set_boost", _failing_boost)

    helper.apply_mode("balanced")

    assert "Non-fatal boost enable failed" in capsys.readouterr().err


def test_governor_write_failure_is_diagnostic_not_silent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    helper = _load_helper()
    monkeypatch.setattr(helper.os, "geteuid", lambda: 1000)
    cpufreq = tmp_path / "cpufreq"
    policy = _make_policy(cpufreq)
    # A directory at the governor path makes the governor write fail while
    # the frequency-range writes still succeed.
    (policy / "scaling_governor").unlink()
    (policy / "scaling_governor").mkdir()
    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(cpufreq))
    monkeypatch.setattr(helper, "_set_boost", lambda enabled: None)

    helper.apply_mode("balanced")

    assert "Non-fatal governor write failed" in capsys.readouterr().err
