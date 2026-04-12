from __future__ import annotations

import logging

import pytest

from buildpython.utils.import_probe import ImportProbeResult

import buildpython.steps.step_import_scan as step_import_scan


def test_parse_imports_skips_unreadable_files(tmp_path) -> None:
    assert step_import_scan._parse_imports(tmp_path / "missing.py") == set()


def test_import_scan_runner_logs_import_failures_and_continues(monkeypatch, tmp_path, caplog) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import required_mod\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"required_mod", "gi", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_probe(name: str, *, cwd):
        assert cwd == tmp_path
        if name == "ok_mod":
            return ImportProbeResult(name, f"probe {name}", "", "", 0)
        if name == "gi":
            return ImportProbeResult(
                name,
                f"probe {name}",
                "",
                "Traceback (most recent call last):\nRuntimeError: optional boom\n",
                1,
            )
        return ImportProbeResult(
            name,
            f"probe {name}",
            "",
            "Traceback (most recent call last):\nImportError: required boom\n",
            1,
        )

    monkeypatch.setattr(step_import_scan, "probe_module_import", fake_probe)

    with caplog.at_level(logging.ERROR, logger=step_import_scan.__name__):
        result = step_import_scan.import_scan_runner()

    assert result.exit_code == 1
    assert "Modules seen: 3" in result.stdout
    assert "required_mod (ImportError: required boom)" in result.stdout
    assert "gi (RuntimeError: optional boom)" in result.stdout
    assert "  - ok_mod" in result.stdout

    records = [record for record in caplog.records if "Import scan failed for candidate module" in record.getMessage()]
    assert len(records) == 2
    assert any("gi" in record.getMessage() for record in records)
    assert any("required_mod" in record.getMessage() for record in records)
    assert all(record.exc_info is None for record in records)


def test_import_scan_runner_treats_gi_as_optional(monkeypatch, tmp_path, caplog) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import gi\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"gi", "ok_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())

    def fake_probe(name: str, *, cwd):
        assert cwd == tmp_path
        if name == "ok_mod":
            return ImportProbeResult(name, f"probe {name}", "", "", 0)
        return ImportProbeResult(
            name,
            f"probe {name}",
            "",
            "Traceback (most recent call last):\nModuleNotFoundError: No module named 'gi'\n",
            1,
        )

    monkeypatch.setattr(step_import_scan, "probe_module_import", fake_probe)

    with caplog.at_level(logging.ERROR, logger=step_import_scan.__name__):
        result = step_import_scan.import_scan_runner()

    assert result.exit_code == 0
    assert "Missing required imports:" not in result.stdout
    assert "Missing optional imports:" in result.stdout
    assert "gi (ModuleNotFoundError: No module named 'gi')" in result.stdout
    assert "  - ok_mod" in result.stdout

    records = [record for record in caplog.records if "Import scan failed for candidate module" in record.getMessage()]
    assert len(records) == 1
    assert "gi" in records[0].getMessage()
    assert records[0].exc_info is None


def test_import_scan_runner_propagates_unexpected_probe_failures(monkeypatch, tmp_path) -> None:
    scan_file = tmp_path / "scan.py"
    scan_file.write_text("import required_mod\n", encoding="utf-8")

    monkeypatch.setattr(step_import_scan, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(step_import_scan, "_iter_py_files", lambda: [scan_file])
    monkeypatch.setattr(step_import_scan, "_parse_imports", lambda _path: {"required_mod"})
    monkeypatch.setattr(step_import_scan, "_stdlib_modules", lambda: set())
    monkeypatch.setattr(
        step_import_scan,
        "probe_module_import",
        lambda _name, *, cwd: (_ for _ in ()).throw(AssertionError("unexpected probe bug")),
    )

    with pytest.raises(AssertionError, match="unexpected probe bug"):
        step_import_scan.import_scan_runner()
