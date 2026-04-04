from __future__ import annotations

from pathlib import Path

import pytest

from src.core.power.monitoring.power_supply_sysfs import (
    iter_ac_online_files,
    read_on_ac_power,
)


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


def test_iter_ac_online_files_ignores_unreadable_type_and_keeps_readable_mains(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write(tmp_path / "AC" / "type", "Mains\n")
    _write(tmp_path / "AC" / "online", "1\n")
    _write(tmp_path / "BAT0" / "type", "Battery\n")
    _write(tmp_path / "BAT0" / "online", "0\n")

    real_read_text = Path.read_text

    def fake_read_text(path: Path, *args, **kwargs):
        if path == tmp_path / "BAT0" / "type":
            raise PermissionError("denied")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert iter_ac_online_files(tmp_path) == [tmp_path / "AC" / "online"]


def test_iter_ac_online_files_falls_back_to_glob_when_directory_scan_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write(tmp_path / "AC0" / "online", "1\n")

    real_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == tmp_path:
            raise PermissionError("denied")
        return real_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    assert iter_ac_online_files(tmp_path) == [tmp_path / "AC0" / "online"]


def test_iter_ac_online_files_returns_empty_when_fallback_glob_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_iterdir = Path.iterdir
    real_glob = Path.glob

    def fake_iterdir(path: Path):
        if path == tmp_path:
            raise PermissionError("denied")
        return real_iterdir(path)

    def fake_glob(path: Path, pattern: str):
        if path == tmp_path and pattern == "AC*/online":
            raise PermissionError("denied")
        return real_glob(path, pattern)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    monkeypatch.setattr(Path, "glob", fake_glob)

    assert iter_ac_online_files(tmp_path) == []


def test_read_on_ac_power_returns_none_when_candidate_reads_fail_or_are_unparseable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write(tmp_path / "AC" / "type", "Mains\n")
    _write(tmp_path / "AC" / "online", "1\n")
    _write(tmp_path / "AC1" / "type", "Mains\n")
    _write(tmp_path / "AC1" / "online", "maybe\n")

    real_read_text = Path.read_text

    def fake_read_text(path: Path, *args, **kwargs):
        if path == tmp_path / "AC" / "online":
            raise PermissionError("denied")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert read_on_ac_power(power_supply_root=tmp_path) is None
