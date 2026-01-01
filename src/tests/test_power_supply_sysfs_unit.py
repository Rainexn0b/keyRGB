from __future__ import annotations

from pathlib import Path

from src.core.monitoring.power_supply_sysfs import iter_ac_online_files, read_on_ac_power


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_iter_ac_online_files_prefers_mains(tmp_path: Path) -> None:
    _write(tmp_path / "AC" / "type", "Mains\n")
    _write(tmp_path / "AC" / "online", "1\n")

    _write(tmp_path / "BAT0" / "type", "Battery\n")
    _write(tmp_path / "BAT0" / "online", "0\n")

    files = iter_ac_online_files(tmp_path)
    assert files == [tmp_path / "AC" / "online"]


def test_iter_ac_online_files_fallback_glob(tmp_path: Path) -> None:
    _write(tmp_path / "AC0" / "online", "1\n")

    files = iter_ac_online_files(tmp_path)
    assert files == [tmp_path / "AC0" / "online"]


def test_read_on_ac_power_returns_none_without_candidates(tmp_path: Path) -> None:
    assert read_on_ac_power(power_supply_root=tmp_path) is None


def test_read_on_ac_power_parses_online_values(tmp_path: Path) -> None:
    _write(tmp_path / "AC" / "type", "Mains\n")
    _write(tmp_path / "AC" / "online", "0\n")
    assert read_on_ac_power(power_supply_root=tmp_path) is False

    _write(tmp_path / "AC" / "online", "1\n")
    assert read_on_ac_power(power_supply_root=tmp_path) is True
