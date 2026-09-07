from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

import keyrgb.core.diagnostics.collectors as diagnostics_collectors
import keyrgb.core.diagnostics.io as diagnostics_io


def test_read_text_returns_none_on_decode_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "broken.txt"
    path.write_bytes(b"x")

    def bad_read_text(self: Path, *, encoding: str) -> str:
        assert self == path
        assert encoding == "utf-8"
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "boom")

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    assert diagnostics_io.read_text(path) is None


def test_run_command_returns_none_on_subprocess_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics_io.shutil, "which", lambda exe: f"/usr/bin/{exe}")

    def boom(*args: object, **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["echo", "hi"], timeout=1.5)

    monkeypatch.setattr(diagnostics_io.subprocess, "run", boom)

    assert diagnostics_io.run_command(["echo", "hi"]) is None


def test_read_kv_file_returns_empty_dict_on_read_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "os-release"
    path.write_text("ID=fedora\n", encoding="utf-8")

    def bad_read_text(self: Path, *, encoding: str, errors: str) -> str:
        assert self == path
        assert encoding == "utf-8"
        assert errors == "ignore"
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    assert diagnostics_io.read_kv_file(path) == {}


@pytest.mark.parametrize("value", [None, object(), "0xzz"])
def test_parse_hex_int_returns_none_for_invalid_values(value: object) -> None:
    assert diagnostics_io.parse_hex_int(value) is None


def test_config_snapshot_ignores_stat_metadata_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"effect": "wave", "brightness": 25}', encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_stat = Path.stat

    def bad_stat(self: Path, *args: object, **kwargs: object):
        if self == cfg_path:
            raise PermissionError("denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", bad_stat)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.mtime is None
    assert dict(snapshot.settings) == {"effect": "wave", "brightness": 25}
    assert snapshot.to_dict() == {"present": True, "settings": {"effect": "wave", "brightness": 25}}


def test_config_snapshot_reports_invalid_json_without_crashing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"effect": ', encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error is not None and snapshot.error.startswith("invalid JSON at line 1 column ")
    assert snapshot.error is not None and str(cfg_path) not in snapshot.error


def test_config_snapshot_sanitizes_unreadable_config_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "nested" / "config.json"
    cfg_path.parent.mkdir(parents=True)
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise PermissionError(13, "Permission denied", str(cfg_path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error == "Permission denied"
    assert snapshot.error is not None and str(cfg_path) not in snapshot.error


def test_config_snapshot_logs_unexpected_boundary_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise RuntimeError(f"unexpected failure while reading {cfg_path}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    with caplog.at_level(logging.DEBUG, logger=diagnostics_collectors.__name__):
        snapshot = diagnostics_collectors.config_snapshot()

    assert snapshot.present is True
    assert snapshot.error == "unexpected failure while reading config.json"
    records = [
        record
        for record in caplog.records
        if "Failed to collect config snapshot during diagnostics collection" in record.getMessage()
    ]
    assert records
    assert records[-1].exc_info is not None


def test_config_snapshot_propagates_unexpected_boundary_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(diagnostics_collectors, "config_file_path", lambda: cfg_path)

    original_read_text = Path.read_text

    def bad_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == cfg_path:
            raise AssertionError("unexpected config snapshot bug")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", bad_read_text)

    with pytest.raises(AssertionError, match="unexpected config snapshot bug"):
        diagnostics_collectors.config_snapshot()
