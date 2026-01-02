from __future__ import annotations

from pathlib import Path

import pytest

from src.core.system_power import PowerMode, get_status, is_supported, set_mode


def _make_policy(root: Path, name: str, *, max_khz: int = 2500000, min_khz: int = 400000) -> Path:
    pol = root / name
    pol.mkdir(parents=True)
    (pol / "scaling_max_freq").write_text(f"{max_khz}\n", encoding="utf-8")
    (pol / "cpuinfo_max_freq").write_text(f"{max_khz}\n", encoding="utf-8")
    (pol / "cpuinfo_min_freq").write_text(f"{min_khz}\n", encoding="utf-8")
    (pol / "scaling_governor").write_text("schedutil\n", encoding="utf-8")
    return pol


def test_system_power_mode_supported_and_sets_extreme(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    _make_policy(root, "policy0")
    _make_policy(root, "policy1")

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))

    assert is_supported() is True

    st0 = get_status()
    assert st0.supported is True

    assert set_mode(PowerMode.EXTREME_SAVER) is True

    # After applying, we should see a capped max freq.
    capped = int((root / "policy0" / "scaling_max_freq").read_text(encoding="utf-8").strip())
    assert capped <= 900_000

    st1 = get_status()
    assert st1.supported is True
    assert st1.mode in (PowerMode.EXTREME_SAVER, PowerMode.BALANCED)


def test_system_power_mode_balanced_restores_max(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "cpufreq"
    pol = _make_policy(root, "policy0", max_khz=3000000)

    monkeypatch.setenv("KEYRGB_CPUFREQ_ROOT", str(root))

    # First force a cap.
    (pol / "scaling_max_freq").write_text("800000\n", encoding="utf-8")

    assert set_mode(PowerMode.BALANCED) is True
    restored = int((pol / "scaling_max_freq").read_text(encoding="utf-8").strip())
    assert restored == 3000000
